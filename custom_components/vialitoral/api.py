"""HTTP client for the Vialitoral public API.

Provides async methods to fetch the camera list and retrieve individual
camera snapshots. A single aiohttp.ClientSession is reused across all
requests and must be closed via Api.close() when the integration unloads.
"""
import aiohttp
import logging
import base64

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=10)


class Api:
    """Wrapper around the Vialitoral HTTP API."""

    def __init__(self):
        """Initialise the API client with a shared aiohttp session."""
        self.BASE_URL = 'https://www.vialitoral.com'
        self.CCTV_URL = '/assets/json/cctvs.json'
        self.HEADERS = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'referer': 'https://www.vialitoral.com/map',
        }
        self._session = aiohttp.ClientSession(headers=self.HEADERS, timeout=_TIMEOUT)

    async def close(self):
        """Close the underlying aiohttp session. Call this on integration unload."""
        await self._session.close()

    async def get_cameras(self):
        """Fetch the full list of cameras from the Vialitoral API.

        Returns:
            list[dict]: Each item contains at minimum 'name', 'image',
            'latitude', 'longitude', and 'type' keys.
        """
        _LOGGER.info('Fetching Vialitoral camera list')
        async with self._session.get(self.BASE_URL + self.CCTV_URL) as resp:
            _LOGGER.info('Finished fetching Vialitoral camera list')
            return await resp.json()

    async def get_camera_image(self, cam_type, cam_id):
        """Fetch a JPEG snapshot for a single camera.

        Args:
            cam_type: Camera type suffix used to build the request path.
            cam_id: Numeric camera identifier from the camera list.

        Returns:
            bytes: Base64-encoded image bytes.
        """
        _LOGGER.info('Updating Vialitoral camera image %s %s', cam_type, cam_id)
        async with self._session.get(self.BASE_URL + "/cctv.php?image=" + cam_id) as resp:
            data = await resp.read()
            _LOGGER.info('Updated Vialitoral camera %s %s', cam_type, cam_id)
            return base64.b64encode(data)
