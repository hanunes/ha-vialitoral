"""Config flow for the Vialitoral integration.

Handles the one-time setup triggered when a user adds the integration from
the HA UI. No user input is required — the integration auto-discovers all
cameras from the Vialitoral API at setup time.
"""
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from .api import Api

import logging

_LOGGER = logging.getLogger(__name__)


class VialitoralConfigFlow(config_entries.ConfigFlow, domain="vialitoral"):
    """Handle the Vialitoral config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(self, info) -> FlowResult:
        """Handle the initial step triggered from the UI.

        Validates connectivity by fetching the camera list, then creates the
        config entry. The camera list itself is not persisted — it is always
        fetched live at runtime.
        """
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}

        if info is not None:
            api = Api()
            try:
                cameras = await api.get_cameras()
                _LOGGER.info("Found [%d] cameras", len(cameras))
            except Exception as e:
                _LOGGER.error("Cannot connect to Vialitoral API: %s", e)
                errors["base"] = "cannot_connect"
            finally:
                await api.close()

            if not errors:
                return self.async_create_entry(title="Vialitoral CCTV", data={})

        return self.async_show_form(step_id="user", errors=errors)