from homeassistant.components.camera import Camera
from custom_components.vialitoral.api import Api

import logging, time, base64

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    api = Api()
    
    cameras = [ VialitoralCamera(cam, api) for cam in await api.get_cameras() ]

    async_add_entities(cameras)

class VialitoralCamera(Camera):

    def __init__(self, data, api):
        super().__init__()

        self._distance = data['name'].split(' ')[1]
        self._name = " ".join(data['name'].split(' ')[2:])
        self._id = data['image']
        self._latitude = data['latitude']
        self._longitude = data['longitude']
        self._type = data['type']
        self._detection = 0

        self._api = api

        self._last_update = time.time() - 600

    async def async_camera_image(self, width=None, height=None):
        if time.time() - self._last_update > 60:
            _LOGGER.info("Timer expired, refreshing %s image" % (self._name))
            
            try:
                self._image = await self._api.get_camera_image(("" if self._type == "vialitoral" else "_"+ self._type), str(self._id))
                #self._detection = await self._api.get_camera_objects(("" if self._type == "vialitoral" else "_"+ self._type), str(self._id))
            except:
                self._image = 'data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw=='
                
            self._last_update = time.time()

        return base64.decodebytes(self._image)
        
    @property
    def unique_id(self):
        return "vialitoral_"+ str(self._id) +"_"+ self._name

    @property
    def name(self):
        return self._name

    @property
    def should_poll(self):
        return False

    @property
    def brand(self):
        return self._type

    @property
    def model(self):
        return "webcam"

    @property
    def icon(self):
        return "mdi:cctv"

    @property
    def state_attributes(self):
        attrs = {"latitude": self._latitude}
        attrs["access_token"] = self.access_tokens[-1]
        attrs["longitude"] = self._longitude
        attrs["type"] = self._type
        attrs["id"] = self._id
        attrs["distance"] = self._distance
        attrs["friendly_name"] = self._name
        attrs["last_update"] = self._last_update
        attrs["objects"] = self._detection
        #attrs["objects"] = self._detection.objects
        #attrs["time"] = self._detection.time

        return attrs
