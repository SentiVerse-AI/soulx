# -*- coding: utf-8 -*-

import asyncio
import json
import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
import aiohttp

logger = logging.getLogger(__name__)

class RewardClient:

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
    
    async def insert_reward_data(self, reward_data: Dict[str, Any]) -> bool:
        try:
            await self.ensure_session()
            
            url = f"{self.base_url}/reward_data"
            
            payload = {
                'id': reward_data.get('id'),
                'task': reward_data.get('task'),
                'node_id': reward_data.get('node_id'),
                'quality_score': reward_data.get('quality_score'),
                'validator_hotkey': reward_data.get('validator_hotkey'),
                'node_hotkey': reward_data.get('node_hotkey'),
                'synthetic_query': reward_data.get('synthetic_query', False),
                'metric': reward_data.get('metric'),
                'response_time': reward_data.get('response_time'),
                'volume': reward_data.get('volume'),
                'stream_metric': reward_data.get('stream_metric'),
                'created_at': reward_data.get('created_at')
            }
            
            wrapped_payload = {'reward_data': payload}
            
            async with self.session.post(url, json=wrapped_payload, headers=self._get_headers()) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get('success'):
                        logger.info(f"Successfully inserted reward data {reward_data.get('id')}")
                        return True
                    else:
                        logger.error(f"Failed to insert reward data: {result.get('error')}")
                        return False
                else:
                    logger.error(f"HTTP {response.status}: {await response.text()}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error inserting reward data: {e}")
            return False
    
    async def get_reward_data_by_validator(
        self,
        validator_hotkey: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        try:
            await self.ensure_session()
            
            url = f"{self.base_url}/reward_data/validator/{validator_hotkey}"
            params = {
                'limit': limit,
                'offset': offset
            }
            
            async with self.session.get(url, params=params, headers=self._get_headers()) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('success'):
                        return data.get('reward_data', [])
                    else:
                        logger.error(f"Failed to get reward data: {data.get('error')}")
                        return []
                else:
                    logger.error(f"HTTP {response.status}: {await response.text()}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error getting reward data for validator {validator_hotkey}: {e}")
            return []
    
    async def get_reward_statistics(
        self,
        validator_hotkey: Optional[str] = None,
        node_hotkey: Optional[str] = None,
        task: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        try:
            await self.ensure_session()
            
            url = f"{self.base_url}/reward_data/statistics"
            params = {'days': days}
            
            if validator_hotkey:
                params['validator_hotkey'] = validator_hotkey
            if node_hotkey:
                params['node_hotkey'] = node_hotkey
            if task:
                params['task'] = task
            
            async with self.session.get(url, params=params, headers=self._get_headers()) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('success'):
                        return data.get('statistics', {})
                    else:
                        logger.error(f"Failed to get reward statistics: {data.get('error')}")
                        return {}
                else:
                    logger.error(f"HTTP {response.status}: {await response.text()}")
                    return {}
                    
        except Exception as e:
            logger.error(f"Error getting reward statistics: {e}")
            return {}
    
    def clear_cache(self):
        logger.debug("Reward client cache cleared")
