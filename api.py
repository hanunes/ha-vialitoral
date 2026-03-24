import aiohttp, logging, base64

_LOGGER = logging.getLogger(__name__)

class Api:

        def __init__(self):
            self.BASE_URL = 'http://www.vialitoral.com'
            self.CCTV_URL = '/assets/json/cctvs.json'
            
            self.HEADERS = { 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.128 Safari/537.36', 'referer': 'https://www.vialitoral.com/map' }
            self.HEADERS_CONTENT_TYPE = { 'content-type': 'application/json' }

        async def get_cameras(self):
            _LOGGER.info('Fetching Vialitoral camera list')
            
            async with aiohttp.ClientSession(headers=self.HEADERS) as session:
                async with session.get(self.BASE_URL + self.CCTV_URL) as resp:
                    _LOGGER.info('Finished fetching Vialitoral camera list')
                    
                    return await resp.json()

        async def get_camera_image(self, type, id):
            _LOGGER.info('Updating Vialitoral camera image %s %s' % (type, id))
            
            async with aiohttp.ClientSession(headers=self.HEADERS) as session:
                async with session.get(self.BASE_URL +"/cctv.php?image="+ id) as resp:
                    data = await resp.read()
                    
                    _LOGGER.info('Updated Vialitoral camera %s %s' % (type, id))
                    
                    return base64.b64encode(data)
                    
        async def get_camera_objects(self, type, id):
            _LOGGER.info('Updating Vialitoral object count for camera %s %s' % (type, id))
            
            async with aiohttp.ClientSession(headers=self.HEADERS_CONTENT_TYPE) as session:
                async with session.post("https://windmill.proxy.myhouselab.xyz/api/r/yolo/detect_from_url", json={"image_url": f"{self.BASE_URL}/imagens/{id}/snap_c1.jpg"}) as resp:
                    data = await resp.json()
                    
                    _LOGGER.info('Updated Vialitoral object count for camera %s %s' % (type, id, data.time))
                    
                    return int(data["count"])
