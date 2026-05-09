"""Config flow for the Vialitoral integration.

Two-step setup:
  1. ``user``    — validates connectivity by fetching the camera list.
  2. ``cameras`` — lets the user pick which cameras to add to HA.

Only the selected camera IDs are persisted in entry.data; the full list is
always fetched live at runtime.
"""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)
from .api import Api
from . import CONF_CAMERAS, CONF_SCAN_INTERVAL

import logging

_LOGGER = logging.getLogger(__name__)


class VialitoralConfigFlow(config_entries.ConfigFlow, domain="vialitoral"):
    """Handle the Vialitoral config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self):
        """Initialise flow state."""
        self._available_cameras: list[dict] = []

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Validate connectivity and fetch the available camera list."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}

        api = Api()
        try:
            self._available_cameras = await api.get_cameras()
            _LOGGER.info("Found [%d] cameras", len(self._available_cameras))
        except Exception as e:
            _LOGGER.error("Cannot connect to Vialitoral API: %s", e)
            errors["base"] = "cannot_connect"
        finally:
            await api.close()

        if not errors:
            return await self.async_step_cameras()

        return self.async_show_form(step_id="user", errors=errors)

    async def async_step_cameras(self, user_input=None) -> FlowResult:
        """Let the user choose which cameras to add to Home Assistant."""
        if user_input is not None:
            return self.async_create_entry(
                title="Vialitoral CCTV",
                data={
                    CONF_CAMERAS: user_input[CONF_CAMERAS],
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                },
            )

        options = [
            {"value": str(cam["image"]), "label": cam["name"]}
            for cam in self._available_cameras
        ]
        # Pre-select all cameras so the user can deselect only the ones they
        # don't want, rather than having to pick every single one manually.
        all_ids = [str(cam["image"]) for cam in self._available_cameras]

        schema = vol.Schema(
            {
                vol.Required(CONF_CAMERAS, default=all_ids): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_SCAN_INTERVAL, default=5): NumberSelector(
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

        return self.async_show_form(
            step_id="cameras",
            data_schema=schema,
        )