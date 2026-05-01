"""Camera platform for the Vialitoral integration.

Exposes each Vialitoral highway CCTV as a HA Camera entity. Images are
fetched on a per-camera staggered schedule to avoid hitting the remote
server with a burst of simultaneous requests. Each camera waits a random
delay (0–30 s) before its first fetch, then refreshes every SCAN_INTERVAL.
"""
from homeassistant.components.camera import Camera
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval, async_call_later
from homeassistant.core import callback
from . import DOMAIN

import logging
import base64
import random
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)

# How often each camera refreshes after its initial staggered fetch.
SCAN_INTERVAL = timedelta(seconds=60)

# Maximum random delay (seconds) before a camera's first fetch.
# Spreads N cameras evenly across this window at startup.
_MAX_STAGGER_SECONDS = 30

# 1×1 transparent GIF used as a placeholder before the first successful fetch.
_BLANK_GIF = base64.b64decode(
    'R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw=='
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Vialitoral camera entities from a config entry."""
    api = hass.data[DOMAIN][config_entry.entry_id]

    cameras = [VialitoralCamera(cam, api) for cam in await api.get_cameras()]

    # update_before_add is intentionally False — each camera self-staggers
    # its first fetch via async_added_to_hass to avoid a request burst.
    async_add_entities(cameras, update_before_add=False)


class VialitoralCamera(Camera):
    """Representation of a single Vialitoral CCTV camera."""

    def __init__(self, data, api):
        """Initialise the camera entity from raw API data.

        Args:
            data: Camera dict from the Vialitoral API (name, image, latitude,
                  longitude, type).
            api:  Shared Api instance injected from hass.data.
        """
        super().__init__()

        self._distance = data['name'].split(' ')[1]
        self._name = " ".join(data['name'].split(' ')[2:])
        self._id = data['image']
        self._latitude = data['latitude']
        self._longitude = data['longitude']
        self._type = data['type']
        self._detection = 0

        self._api = api
        self._image = _BLANK_GIF
        self._unsub_interval = None

        # Each camera picks a unique random delay so fetches are spread out.
        self._stagger_delay = random.uniform(0, _MAX_STAGGER_SECONDS)

    async def async_added_to_hass(self):
        """Schedule the first fetch after a random stagger delay, then set up
        a fixed periodic interval for subsequent refreshes."""
        await super().async_added_to_hass()

        async def _initial_update(_now=None):
            await self._fetch_and_write()
            self._unsub_interval = async_track_time_interval(
                self.hass, self._handle_interval, SCAN_INTERVAL
            )

        async_call_later(self.hass, self._stagger_delay, _initial_update)
        _LOGGER.debug(
            "Camera %s will start fetching in %.1f s",
            self._name,
            self._stagger_delay,
        )

    async def async_will_remove_from_hass(self):
        """Cancel the periodic interval when the entity is removed."""
        if self._unsub_interval:
            self._unsub_interval()
            self._unsub_interval = None

    @callback
    def _handle_interval(self, now):
        """Fire-and-forget wrapper called by the time interval tracker."""
        self.hass.async_create_task(self._fetch_and_write())

    async def _fetch_and_write(self):
        """Fetch a new image and push the updated state to HA."""
        await self.async_update()
        self.async_write_ha_state()

    async def async_update(self):
        """Fetch a fresh snapshot from the Vialitoral API.

        On failure the previous image is retained and a warning is logged.
        """
        _LOGGER.info("Refreshing %s image", self._name)
        try:
            encoded = await self._api.get_camera_image(
                ("" if self._type == "vialitoral" else "_" + self._type),
                str(self._id),
            )
            self._image = base64.decodebytes(encoded)
        except Exception as e:
            _LOGGER.warning("Failed to update camera %s: %s", self._name, e, exc_info=True)

    async def async_camera_image(self, width=None, height=None):
        """Return the most recently fetched camera image bytes."""
        return self._image

    @property
    def should_poll(self):
        """Disable HA polling — this entity manages its own schedule."""
        return False

    @property
    def unique_id(self):
        """Return a unique ID for this camera entity."""
        return "vialitoral_" + str(self._id) + "_" + self._name

    @property
    def name(self):
        """Return the camera display name."""
        return self._name

    @property
    def icon(self):
        """Return the icon for this camera."""
        return "mdi:cctv"

    @property
    def device_info(self):
        """Group all cameras under a single 'Vialitoral CCTV' device."""
        return DeviceInfo(
            identifiers={(DOMAIN, "vialitoral_cctv")},
            name="Vialitoral CCTV",
            manufacturer=self._type,
            model="webcam",
        )

    @property
    def extra_state_attributes(self):
        """Return additional state attributes exposed to the HA frontend."""
        return {
            "latitude": self._latitude,
            "longitude": self._longitude,
            "type": self._type,
            "id": self._id,
            "distance": self._distance,
            "objects": self._detection,
        }
