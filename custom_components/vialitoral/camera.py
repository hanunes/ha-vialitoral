"""Camera platform for the Vialitoral integration.

Exposes each selected Vialitoral highway CCTV as a HA Camera entity. Images
are refreshed by the shared VialitoralCoordinator; entities simply read the
latest bytes from ``coordinator.data``.

Also provides a VialitoralActiveCamera entity (camera.vialitoral_active) that
always serves the image of whichever camera is currently selected in the
select entity, with no additional API calls.
"""
from __future__ import annotations

import base64
import logging

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, camera_label
from .coordinator import VialitoralCoordinator

_LOGGER = logging.getLogger(__name__)

# 1×1 transparent GIF used as a placeholder before the first successful fetch.
_BLANK_GIF = base64.b64decode(
    'R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw=='
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vialitoral camera entities from a config entry."""
    coordinator: VialitoralCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[Camera] = [
        VialitoralCamera(coordinator, cam) for cam in coordinator.cameras
    ]
    entities.append(VialitoralActiveCamera(coordinator))

    async_add_entities(entities)


class VialitoralCamera(CoordinatorEntity[VialitoralCoordinator], Camera):
    """Representation of a single Vialitoral CCTV camera."""

    _attr_has_entity_name = False
    _attr_icon = "mdi:cctv"

    def __init__(self, coordinator: VialitoralCoordinator, data: dict):
        """Initialise the camera entity from raw API data.

        Args:
            coordinator: Shared coordinator holding the latest images.
            data: Camera dict from the Vialitoral API (name, image, latitude,
                  longitude, type).
        """
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)

        self._distance = data['name'].split(' ')[1]
        self._name = camera_label(data)
        self._id = str(data['image'])
        self._latitude = data['latitude']
        self._longitude = data['longitude']
        self._type = data['type']

        self._attr_unique_id = f"vialitoral_{self._type}_{self._id}"

    async def async_camera_image(self, width=None, height=None):
        """Return the most recently fetched camera image bytes."""
        return self.coordinator.data.get(self._id, _BLANK_GIF)

    @property
    def name(self):
        """Return the camera display name."""
        return self._name

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
        current_size, baseline_size, drop_pct = self.coordinator.placeholder_stats(
            self._id
        )
        return {
            "latitude": self._latitude,
            "longitude": self._longitude,
            "type": self._type,
            "id": self._id,
            "distance": self._distance,
            "possible_accident": self.coordinator.is_placeholder(self._id),
            "current_size": current_size,
            "baseline_size": baseline_size,
            "drop_pct": drop_pct,
        }


class VialitoralActiveCamera(CoordinatorEntity[VialitoralCoordinator], Camera):
    """Proxy camera that always shows the currently selected camera.

    Serves the cached image of whichever camera id is stored in
    ``coordinator.selected_camera_id`` (driven by the select entity). No
    additional API calls are made. Use 'camera.vialitoral_active' in Lovelace
    cards for dynamic selection:

        type: picture-entity
        entity: camera.vialitoral_active
    """

    # Prevent HA from prefixing the entity_id with the device name.
    _attr_has_entity_name = False
    _attr_icon = "mdi:cctv"
    _attr_name = "Vialitoral Active"
    _attr_unique_id = "vialitoral_active_camera"

    def __init__(self, coordinator: VialitoralCoordinator):
        """Initialise the active camera proxy."""
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)

    async def async_camera_image(self, width=None, height=None):
        """Return the image of the currently selected camera."""
        cam_id = self.coordinator.selected_camera_id
        if cam_id is None:
            return _BLANK_GIF
        return self.coordinator.data.get(cam_id, _BLANK_GIF)

    @property
    def extra_state_attributes(self):
        """Expose the selected camera id and its placeholder detection stats."""
        cam_id = self.coordinator.selected_camera_id
        current_size, baseline_size, drop_pct = self.coordinator.placeholder_stats(
            cam_id
        )
        return {
            "active_camera": cam_id,
            "possible_accident": (
                self.coordinator.is_placeholder(cam_id)
                if cam_id is not None
                else False
            ),
            "current_size": current_size,
            "baseline_size": baseline_size,
            "drop_pct": drop_pct,
        }

    @property
    def device_info(self):
        """Group the active camera under the same Vialitoral CCTV device."""
        return DeviceInfo(
            identifiers={(DOMAIN, "vialitoral_cctv")},
            name="Vialitoral CCTV",
            model="webcam",
        )
