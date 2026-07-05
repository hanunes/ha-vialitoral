"""Config flow for the Vialitoral integration.

Two-step setup:
  1. ``user``    — validates connectivity by fetching the camera list.
  2. ``cameras`` — lets the user pick which cameras to add to HA.

Reconfigure (three-dot menu on the integration card):
  - Re-fetches the live camera list and shows the same picker pre-filled
    with the current saved selection, so cameras can be added/removed
    without removing and re-adding the integration.

Only the selected camera IDs and scan interval are persisted in entry.data.
"""
import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .api import Api, VialitoralApiError
from .const import CONF_CAMERAS, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, MAP_URL

_LOGGER = logging.getLogger(__name__)


class VialitoralConfigFlow(config_entries.ConfigFlow, domain="vialitoral"):
    """Handle the Vialitoral config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self):
        """Initialise flow state."""
        self._available_cameras: list[dict] = []

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Validate connectivity and fetch the available camera list."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}

        api = Api()
        try:
            self._available_cameras = await api.get_cameras()
            _LOGGER.debug("Found [%d] cameras", len(self._available_cameras))
        except VialitoralApiError as err:
            _LOGGER.error("Cannot connect to Vialitoral API: %s", err)
            errors["base"] = "cannot_connect"
        finally:
            await api.close()

        if not errors:
            return await self.async_step_cameras()

        return self.async_show_form(step_id="user", errors=errors)

    def _build_cameras_schema(
        self, current_cameras: list[str] | None = None, current_interval: int = 5
    ) -> vol.Schema:
        """Build the camera-selection schema, pre-filled with current values."""
        options = [
            {"value": str(cam["image"]), "label": cam["name"]}
            for cam in self._available_cameras
        ]
        default_ids = current_cameras if current_cameras is not None else [
            str(cam["image"]) for cam in self._available_cameras
        ]
        return vol.Schema(
            {
                vol.Required(CONF_CAMERAS, default=default_ids): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_SCAN_INTERVAL, default=current_interval): NumberSelector(
                    NumberSelectorConfig(
                        min=2,
                        max=10,
                        step=1,
                        unit_of_measurement="min",
                        mode=NumberSelectorMode.SLIDER,
                    )
                ),
            }
        )

    async def async_step_cameras(self, user_input=None) -> ConfigFlowResult:
        """Let the user choose which cameras to add to Home Assistant."""
        if user_input is not None:
            return self.async_create_entry(
                title="Vialitoral CCTV",
                data={
                    CONF_CAMERAS: user_input[CONF_CAMERAS],
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                },
            )

        return self.async_show_form(
            step_id="cameras",
            data_schema=self._build_cameras_schema(),
            description_placeholders={"map_url": MAP_URL},
        )

    async def async_step_reconfigure(self, user_input=None) -> ConfigFlowResult:
        """Handle reconfiguration from the integration's three-dot menu.

        Re-fetches the live camera list, pre-fills the form with the current
        saved selection, and reloads the integration on save.
        """
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_update_reload_and_abort(
                entry,
                data_updates={
                    CONF_CAMERAS: user_input[CONF_CAMERAS],
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                },
            )

        api = Api()
        try:
            self._available_cameras = await api.get_cameras()
        except VialitoralApiError as err:
            _LOGGER.error("Cannot connect to Vialitoral API: %s", err)
            errors["base"] = "cannot_connect"
        finally:
            await api.close()

        if errors:
            return self.async_show_form(
                step_id="reconfigure",
                errors=errors,
                description_placeholders={"map_url": MAP_URL},
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._build_cameras_schema(
                current_cameras=entry.data.get(CONF_CAMERAS),
                current_interval=entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ),
            description_placeholders={"map_url": MAP_URL},
        )