"""Config flow for the Vialitoral integration.

Handles the one-time setup triggered when a user adds the integration from
the HA UI. No user input is required — the integration auto-discovers all
cameras from the Vialitoral API at setup time.
"""
from homeassistant import config_entries
from .api import Api

import logging

_LOGGER = logging.getLogger(__name__)


class VialitoralConfigFlow(config_entries.ConfigFlow, domain="vialitoral"):
    """Handle the Vialitoral config flow."""

    VERSION = 1

    async def async_step_user(self, info):
        """Handle the initial step triggered from the UI.

        Validates connectivity by fetching the camera list, then creates the
        config entry. The camera list itself is not persisted — it is always
        fetched live at runtime.
        """
        api = Api()

        try:
            cameras = await api.get_cameras()
            _LOGGER.info("Found [%d] cameras", len(cameras))
        finally:
            await api.close()

        return self.async_create_entry(title="Vialitoral CCTV", data={})