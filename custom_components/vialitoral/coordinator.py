"""Data update coordinator for the Vialitoral integration.

A single coordinator fetches the camera list and refreshes the JPEG snapshot
for every selected camera once per ``scan_interval``. All camera entities read
their image from the coordinator, so there is exactly one shared polling loop
instead of a timer per entity.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import Api, VialitoralApiError
from .const import CONF_CAMERAS, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

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
        images: dict[str, bytes] = {}
        for cam in self.cameras:
            cam_id = str(cam["image"])
            try:
                images[cam_id] = await self.api.get_camera_image(cam_id)
            except VialitoralApiError as err:
                _LOGGER.warning("Failed to update camera %s: %s", cam_id, err)
                # Keep the previous image so the entity does not go blank.
                if cam_id in previous:
                    images[cam_id] = previous[cam_id]

        return images
