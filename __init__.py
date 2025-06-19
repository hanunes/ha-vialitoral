"""vialitoral integration."""
import logging

DOMAIN = 'vialitoral'

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry):
    hass.async_create_task(hass.config_entries.async_forward_entry_setups(entry, ["camera", "select"]))
    
    return True