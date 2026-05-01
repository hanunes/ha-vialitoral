"""Camera platform for the Vialitoral integration.

Exposes each Vialitoral highway CCTV as a HA Camera entity. Images are
fetched on HA's standard polling interval via async_update() and cached
locally so async_camera_image() can return synchronously.
"""
from homeassistant.components.camera import Camera
from homeassistant.helpers.device_registry import DeviceInfo
from .api import Api
from . import DOMAIN

import logging
import base64

_LOGGER = logging.getLogger(__name__)

# 1×1 transparent GIF used as a placeholder before the first successful fetch.
_BLANK_GIF = base64.b64decode(
    'R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw=='
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Vialitoral camera entities from a config entry."""
    api = hass.data[DOMAIN][config_entry.entry_id]

    cameras = [VialitoralCamera(cam, api) for cam in await api.get_cameras()]

    async_add_entities(cameras, update_before_add=True)


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

    async def async_update(self):
        """Fetch a fresh snapshot from the Vialitoral API.

        Called by HA on each polling cycle. On failure the previous image is
        retained and a warning is logged.
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
        """Return True so HA calls async_update() on its scan interval."""
        return True

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
