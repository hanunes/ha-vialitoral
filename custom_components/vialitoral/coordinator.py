"""Data update coordinator for the Vialitoral integration.

A single coordinator fetches the camera list and refreshes the JPEG snapshot
for every selected camera once per ``scan_interval``. All camera entities read
their image from the coordinator, so there is exactly one shared polling loop
instead of a timer per entity.

The coordinator also runs "possible accident" detection: when a camera goes
offline Vialitoral serves a small placeholder JPEG. By tracking a rolling
median baseline of each camera's normal image size, a large drop below that
baseline (and below an absolute byte ceiling) is flagged as a possible
accident and surfaced through the camera entities' attributes.
"""
from __future__ import annotations

import logging
import os
import statistics
from collections import deque
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify

from .api import Api, VialitoralApiError
from .const import (
    ABSOLUTE_MAX_PLACEHOLDER_BYTES,
    BASELINE_HISTORY_SIZE,
    CONF_CAMERAS,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_ACCIDENT_CLEARED,
    EVENT_ACCIDENT_DETECTED,
    MIN_BASELINE_SAMPLES,
    SIZE_DROP_THRESHOLD,
    SNAPSHOT_DIR,
    STORAGE_KEY,
    STORAGE_VERSION,
    camera_label,
)

_LOGGER = logging.getLogger(__name__)


class VialitoralCoordinator(DataUpdateCoordinator[dict[str, bytes]]):
    """Coordinate a single shared refresh of all selected camera images."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: Api) -> None:
        """Initialise the coordinator from a config entry."""
        scan_minutes = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_minutes),
        )
        self.api = api
        self._entry = entry

        # Metadata (name, latitude, longitude, type, image id) for the cameras
        # that are currently selected. Populated on every refresh.
        self.cameras: list[dict] = []

        # Raw API id of the camera shown by camera.vialitoral_active. Driven by
        # the select entity; defaults to the first selected camera.
        self.selected_camera_id: str | None = None

        # --- Placeholder / "possible accident" detection state -------------
        # Persistent store for per-camera size baselines.
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

        # Recent normal (non-flagged) image sizes per camera id, used to
        # compute a spike-proof median baseline.
        self._size_history: dict[str, deque[int]] = {}

        # Median baseline size (bytes) per camera id, restored from disk.
        self.size_baseline: dict[str, float] = {}

        # Current cycle's image size (bytes) per camera id.
        self.image_sizes: dict[str, int] = {}

        # Most recent normal (non-flagged) image bytes per camera id, used to
        # attach the pre-accident frame to notifications when a placeholder is
        # detected. Not persisted across restarts.
        self._last_good_image: dict[str, bytes] = {}

        # Camera ids currently flagged as showing a placeholder.
        self.flagged: set[str] = set()

    async def async_init_store(self) -> None:
        """Load persisted size baselines from disk.

        Must be called before the first refresh so detection can flag a
        placeholder immediately after a restart without re-learning.
        """
        stored = await self._store.async_load()
        if not stored:
            return

        baselines = stored.get("baselines", {})
        histories = stored.get("histories", {})
        self.size_baseline = {str(k): float(v) for k, v in baselines.items()}
        self._size_history = {
            str(k): deque(v, maxlen=BASELINE_HISTORY_SIZE)
            for k, v in histories.items()
        }

    async def _async_save_store(self) -> None:
        """Persist the current size baselines and history to disk."""
        await self._store.async_save(
            {
                "baselines": self.size_baseline,
                "histories": {
                    cam_id: list(history)
                    for cam_id, history in self._size_history.items()
                },
            }
        )

    def is_placeholder(self, cam_id: str) -> bool:
        """Return True if the camera is currently showing a placeholder."""
        return cam_id in self.flagged

    def placeholder_stats(
        self, cam_id: str
    ) -> tuple[int | None, int | None, int | None]:
        """Return ``(current_size, baseline_size, drop_pct)`` for a camera.

        ``drop_pct`` is the percentage the current size has fallen below the
        baseline (0 when at or above baseline). Any component is ``None`` when
        the corresponding value is not yet known.
        """
        current = self.image_sizes.get(cam_id)
        baseline = self.size_baseline.get(cam_id)
        baseline_int = int(baseline) if baseline is not None else None

        drop_pct: int | None = None
        if current is not None and baseline:
            drop_pct = max(0, round((1 - current / baseline) * 100))

        return current, baseline_int, drop_pct

    async def _fire_accident_event(self, cam: dict, detected: bool) -> None:
        """Fire a bus event when a camera's placeholder flag changes state.

        Fires ``EVENT_ACCIDENT_DETECTED`` on a false→true transition and
        ``EVENT_ACCIDENT_CLEARED`` on true→false, with a payload describing the
        camera and its current size stats. On detection, the last known good
        frame is written to disk; its filesystem path is included as
        ``snapshot_path`` and its ready-to-use companion-app URL as
        ``snapshot_url`` so automations can attach the pre-accident image to a
        notification.
        """
        cam_id = str(cam["image"])
        current_size, baseline_size, drop_pct = self.placeholder_stats(cam_id)
        event = EVENT_ACCIDENT_DETECTED if detected else EVENT_ACCIDENT_CLEARED

        data: dict = {
            "camera_id": cam_id,
            "label": camera_label(cam),
            "latitude": cam.get("latitude"),
            "longitude": cam.get("longitude"),
            "current_size": current_size,
            "baseline_size": baseline_size,
            "drop_pct": drop_pct,
        }

        if detected:
            snapshot_path = await self._async_write_snapshot(cam_id)
            if snapshot_path is not None:
                data["snapshot_path"] = snapshot_path
                data["snapshot_url"] = f"/local/{SNAPSHOT_DIR}/{cam_id}.jpg"
        else:
            # On recovery the live feed is back online, so expose the camera
            # entity that proxies the current image. The detection snapshot is
            # no longer needed and is removed.
            data["entity_id"] = f"camera.{slugify(camera_label(cam))}"
            await self._async_delete_snapshot(cam_id)

        self.hass.bus.async_fire(event, data)

    async def _async_write_snapshot(self, cam_id: str) -> str | None:
        """Write the last good frame for a camera to the ``www`` folder.

        Returns the filesystem path of the written JPEG, or ``None`` when no
        good frame has been captured yet (e.g. the camera was already showing
        the placeholder when Home Assistant started).
        """
        image = self._last_good_image.get(cam_id)
        if image is None:
            return None

        directory = self.hass.config.path("www", SNAPSHOT_DIR)
        path = os.path.join(directory, f"{cam_id}.jpg")

        def _write() -> None:
            os.makedirs(directory, exist_ok=True)
            with open(path, "wb") as file:
                file.write(image)

        try:
            await self.hass.async_add_executor_job(_write)
        except OSError as err:
            _LOGGER.warning("Failed to write snapshot for camera %s: %s", cam_id, err)
            return None

        return path

    async def _async_delete_snapshot(self, cam_id: str) -> None:
        """Remove a camera's snapshot file once its feed returns to normal."""
        path = os.path.join(
            self.hass.config.path("www", SNAPSHOT_DIR), f"{cam_id}.jpg"
        )

        def _delete() -> None:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass

        try:
            await self.hass.async_add_executor_job(_delete)
        except OSError as err:
            _LOGGER.warning(
                "Failed to delete snapshot for camera %s: %s", cam_id, err
            )

    def _evaluate_camera(self, cam_id: str, size: int) -> bool:
        """Update baseline for a camera and return whether it is flagged.

        A camera is flagged when its current image is both far below its own
        median baseline and below an absolute byte ceiling. Only non-flagged
        sizes feed the baseline, so placeholder frames never poison it.
        """
        baseline = self.size_baseline.get(cam_id)
        history = self._size_history.get(cam_id)

        flagged = (
            baseline is not None
            and history is not None
            and len(history) >= MIN_BASELINE_SAMPLES
            and size < baseline * (1 - SIZE_DROP_THRESHOLD)
            and size < ABSOLUTE_MAX_PLACEHOLDER_BYTES
        )

        if not flagged:
            if history is None:
                history = deque(maxlen=BASELINE_HISTORY_SIZE)
                self._size_history[cam_id] = history
            history.append(size)
            self.size_baseline[cam_id] = statistics.median(history)

        return flagged

    async def _async_update_data(self) -> dict[str, bytes]:
        """Fetch the camera list and a fresh snapshot for each selected camera."""
        selected_ids = set(self._entry.data.get(CONF_CAMERAS, []))

        try:
            all_cameras = await self.api.get_cameras()
        except VialitoralApiError as err:
            raise UpdateFailed(f"Error fetching camera list: {err}") from err

        self.cameras = [
            cam for cam in all_cameras if str(cam["image"]) in selected_ids
        ] if selected_ids else all_cameras

        valid_ids = {str(cam["image"]) for cam in self.cameras}
        if self.selected_camera_id not in valid_ids:
            self.selected_camera_id = (
                str(self.cameras[0]["image"]) if self.cameras else None
            )

        previous = self.data or {}
        previous_flagged = self.flagged
        images: dict[str, bytes] = {}
        self.image_sizes = {}
        self.flagged = set()
        baseline_changed = False

        for cam in self.cameras:
            cam_id = str(cam["image"])
            try:
                image = await self.api.get_camera_image(cam_id)
            except VialitoralApiError as err:
                _LOGGER.warning("Failed to update camera %s: %s", cam_id, err)
                # Keep the previous image so the entity does not go blank.
                if cam_id in previous:
                    images[cam_id] = previous[cam_id]
                continue

            if not image:
                # An empty response is a transient fetch glitch, not a
                # placeholder. Keep the previous image and skip evaluation so
                # it never flags a possible accident.
                _LOGGER.debug("Camera %s returned an empty image; skipping", cam_id)
                if cam_id in previous:
                    images[cam_id] = previous[cam_id]
                continue

            images[cam_id] = image
            size = len(image)
            self.image_sizes[cam_id] = size

            previous_baseline = self.size_baseline.get(cam_id)
            was_flagged = cam_id in previous_flagged
            flagged = self._evaluate_camera(cam_id, size)
            if flagged:
                self.flagged.add(cam_id)
            else:
                # Retain the last good frame so it can be attached to a
                # notification if a placeholder is detected next.
                self._last_good_image[cam_id] = image

            if flagged != was_flagged:
                _LOGGER.debug(
                    "Camera %s possible_accident %s (size=%s, baseline=%s)",
                    cam_id,
                    "detected" if flagged else "cleared",
                    size,
                    self.size_baseline.get(cam_id),
                )
                await self._fire_accident_event(cam, flagged)
            else:
                _LOGGER.debug(
                    "Camera %s size=%s baseline=%s flagged=%s",
                    cam_id,
                    size,
                    self.size_baseline.get(cam_id),
                    flagged,
                )

            if self.size_baseline.get(cam_id) != previous_baseline:
                baseline_changed = True

        if baseline_changed:
            await self._async_save_store()

        return images
