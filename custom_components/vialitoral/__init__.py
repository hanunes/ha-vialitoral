"""Vialitoral custom component for Home Assistant.

This integration exposes CCTV cameras from the Vialitoral highway network
as HA camera entities and provides a select entity to choose the active
camera from the frontend.

Platforms: camera, select
"""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import Api
from .const import DOMAIN
from .coordinator import VialitoralCoordinator

PLATFORMS = [Platform.CAMERA, Platform.SELECT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Vialitoral from a config entry.

    Creates a shared Api instance and a single DataUpdateCoordinator, performs
    the first refresh, stores the coordinator in hass.data, then forwards setup
    to each platform.
    """
    api = Api()
    coordinator = VialitoralCoordinator(hass, entry, api)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await api.close()
        raise

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Vialitoral config entry.

    Unloads all platforms, closes the shared aiohttp session, and removes
    the coordinator from hass.data.
    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.api.close()

    return unload_ok