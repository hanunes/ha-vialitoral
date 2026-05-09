"""Vialitoral custom component for Home Assistant.

This integration exposes CCTV cameras from the Vialitoral highway network
as HA camera entities and provides a select entity to choose the active
camera from the frontend.

Platforms: camera, select
"""
import logging
from .api import Api

DOMAIN = 'vialitoral'
CONF_CAMERAS = "cameras"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry):
    """Set up Vialitoral from a config entry.

    Creates a shared Api instance, stores it in hass.data so both the camera
    and select platforms can reuse it, then forwards setup to each platform.
    """
    api = Api()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = api

    await hass.config_entries.async_forward_entry_setups(entry, ["camera", "select"])

    return True


async def async_unload_entry(hass, entry):
    """Unload a Vialitoral config entry.

    Unloads all platforms, closes the shared aiohttp session, and removes
    the Api instance from hass.data.
    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["camera", "select"])

    if unload_ok:
        api = hass.data[DOMAIN].pop(entry.entry_id)
        await api.close()

    return unload_ok