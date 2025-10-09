# -*- coding: utf-8 -*-

import aiohttp
import asyncio
from typing import Dict, Any, Optional
from fiber.logging_utils import get_logger

logger = get_logger(__name__)

class NodeClient:

    def __init__(self, central_server_url: str, central_server_token: Optional[str] = None):
        self.central_server_url = central_server_url
        self.central_server_token = central_server_token
        self._nodes_cache: Optional[Dict[str, Any]] = None
        self._last_cache_update: float = 0
        self._cache_ttl: float = 60
    
    async def get_nodes(self) -> Dict[str, Any]:
        try:
            if (self._nodes_cache is not None and
                asyncio.get_event_loop().time() - self._last_cache_update < self._cache_ttl):
                return self._nodes_cache
            
            headers = {}
            if self.central_server_token:
                headers['Authorization'] = f'Bearer {self.central_server_token}'
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.central_server_url}/nodes",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        nodes = data['nodes']
                        self._nodes_cache = nodes
                        self._last_cache_update = asyncio.get_event_loop().time()
                        return nodes
                    else:
                        return {}
                        
        except Exception as e:
            logger.error(f"Error fetching nodes from central server: {e}")
            return {}
    
    async def get_node_by_hotkey(self, hotkey: str) -> Optional[Dict[str, Any]]:
        nodes = await self.get_nodes()
        return nodes.get(hotkey)
    
    def clear_cache(self):
        self._nodes_cache = None
        self._last_cache_update = 0
        logger.info("Node cache cleared") 