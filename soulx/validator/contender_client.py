# -*- coding: utf-8 -*-

import asyncio
import json
import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

import aiohttp

logger = logging.getLogger(__name__)


class ContenderClient:

    def __init__(self, base_url: str, validator_hotkey: str, token: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.validator_hotkey = validator_hotkey
        self.token = token
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def ensure_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
    
    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None
    
    def _get_headers(self) -> Dict[str, str]:
        headers = {
            'Content-Type': 'application/json',
            'Hotkey': self.validator_hotkey
        }
        
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        
        return headers
    
    async def get_contenders_for_task(self, task: str, top_x: int = 5) -> List[Dict[str, Any]]:
        try:
            await self.ensure_session()
            
            url = f"{self.base_url}/contenders/task/{task}"
            params = {
                'top_x': top_x,
                'validator_hotkey': self.validator_hotkey
            }
            
            async with self.session.get(url, params=params, headers=self._get_headers()) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('success'):
                        return data.get('contenders', [])
                    else:
                        logger.error(f"Failed to get contenders: {data.get('error')}")
                        return []
                else:
                    logger.error(f"HTTP {response.status}: {await response.text()}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error getting contenders for task {task}: {e}")
            return []
    
    async def get_contenders_by_node(self, node_hotkey: str) -> List[Dict[str, Any]]:
        try:
            await self.ensure_session()
            
            url = f"{self.base_url}/contenders/node/{node_hotkey}"
            params = {
                'validator_hotkey': self.validator_hotkey
            }
            
            async with self.session.get(url, params=params, headers=self._get_headers()) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('success'):
                        return data.get('contenders', [])
                    else:
                        logger.error(f"Failed to get contenders: {data.get('error')}")
                        return []
                else:
                    logger.error(f"HTTP {response.status}: {await response.text()}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error getting contenders for node {node_hotkey}: {e}")
            return []
    
    async def get_all_contenders(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        try:
            await self.ensure_session()
            
            url = f"{self.base_url}/contenders"
            params = {
                'limit': limit,
                'offset': offset,
                'validator_hotkey': self.validator_hotkey
            }
            
            async with self.session.get(url, params=params, headers=self._get_headers()) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('success'):
                        return data.get('contenders', [])
                    else:
                        return []
                else:
                    return []
                    
        except Exception as e:
            logger.error(f"Error getting all contenders: {e}")
            return []
    
    async def update_contender_stats(self, contender_id: str, stats: Dict[str, Any]) -> bool:
        try:
            await self.ensure_session()
            
            url = f"{self.base_url}/contenders/{contender_id}/stats"
            data = {
                'stats': stats,
                'validator_hotkey': self.validator_hotkey
            }
            
            async with self.session.put(url, json=data, headers=self._get_headers()) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get('success', False)
                else:
                    return False
                    
        except Exception as e:
            logger.error(f"Error updating contender stats: {e}")
            return False
    
    async def update_contender_capacity(self, contender_id: str, capacity_data: Dict[str, Any]) -> bool:
        try:
            await self.ensure_session()
            
            url = f"{self.base_url}/contenders/{contender_id}/capacity"
            data = {
                'capacity_consumed': capacity_data.get('capacity_consumed', 0),
                'validator_hotkey': self.validator_hotkey
            }
            
            async with self.session.put(url, json=data, headers=self._get_headers()) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get('success', False)
                else:
                    return False
                    
        except Exception as e:
            logger.error(f"Error updating contender capacity: {e}")
            return False
    
    async def update_contender_error_count(self, contender_id: str, error_data: Dict[str, Any]) -> bool:
        try:
            await self.ensure_session()
            
            url = f"{self.base_url}/contenders/{contender_id}/error_count"
            data = {
                'error_type': error_data.get('error_type', '500'),
                'validator_hotkey': self.validator_hotkey
            }
            
            async with self.session.put(url, json=data, headers=self._get_headers()) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get('success', False)
                else:
                    logger.error(f"HTTP {response.status}: {await response.text()}")
                    return False
                    
        except Exception as e:
            return False
    
    async def store_task_result(self, task_result_data: Dict[str, Any]) -> bool:
        try:
            await self.ensure_session()
            
            url = f"{self.base_url}/task_results"
            data = {
                'task_result': task_result_data,
                'validator_hotkey': self.validator_hotkey
            }
            
            async with self.session.post(url, json=data, headers=self._get_headers()) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get('success', False)
                else:
                    return False
                    
        except Exception as e:
            logger.error(f"Error storing task result: {e}")
            return False