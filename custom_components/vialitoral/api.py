"""HTTP client for the Vialitoral public API.

Provides async methods to fetch the camera list and retrieve individual
camera snapshots. A single aiohttp.ClientSession is reused across all
requests and must be closed via Api.close() when the integration unloads.
"""
import asyncio
import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=10)


class VialitoralApiError(Exception):
    """Raised when the Vialitoral API cannot be reached or returns an error."""


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

        Raises:
            VialitoralApiError: If the request fails or times out.
        """
        _LOGGER.debug('Fetching Vialitoral camera list')
        try:
            async with self._session.get(self.BASE_URL + self.CCTV_URL) as resp:
                resp.raise_for_status()
                return await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise VialitoralApiError(f"Error fetching camera list: {err}") from err

    async def get_camera_image(self, cam_id):
        """Fetch a JPEG snapshot for a single camera.

        Args:
            cam_id: Camera identifier (the API's image field) from the camera list.

        Returns:
            bytes: Raw JPEG image bytes.

        Raises:
            VialitoralApiError: If the request fails or times out.
        """
        _LOGGER.debug('Updating Vialitoral camera image %s', cam_id)
        try:
            async with self._session.get(self.BASE_URL + "/cctv.php?image=" + cam_id) as resp:
                resp.raise_for_status()
                return await resp.read()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise VialitoralApiError(f"Error fetching camera {cam_id}: {err}") from err
