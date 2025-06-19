from homeassistant import config_entries

from custom_components.vialitoral.api import Api

import voluptuous as vol, logging

_LOGGER = logging.getLogger(__name__)

class VialitoralConfigFlow(config_entries.ConfigFlow, domain="vialitoral"):
    
    async def async_step_user(self, info):
        api = Api()
        
        cameras = await api.get_cameras()
        
        _LOGGER.info("Found [%d] cameras" % (len(cameras)))
        
        return self.async_create_entry(title="Vialitoral CCTV", data={ "cameras": cameras })