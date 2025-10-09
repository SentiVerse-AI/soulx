# -*- coding: utf-8 -*-

import aiohttp
import time
from bittensor import logging
from typing import Dict, Any, Optional

class TaskConfigClient:

    def __init__(self, base_url: str, validator_hotkey: str, token: str):
        self.base_url = base_url.rstrip('/')
        self.validator_hotkey = validator_hotkey
        self.token = token
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        self._task_configs_cache = {}
        self._cache_timestamp = 0
        self._cache_duration = 300
    
    async def get_all_task_configs(self) -> Dict[str, Any]:
        try:
            url = f"{self.base_url}/task_configs"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('success'):
                            self._task_configs_cache = data.get('task_configs', {})
                            self._cache_timestamp = time.time()
                            return self._task_configs_cache
                        else:
                            logging.error(f"Failed to get task configs: {data.get('error')}")
                            return {}
                    else:
                        logging.error(f"HTTP {response.status}: Failed to get task configs")
                        return {}
                        
        except Exception as e:
            logging.error(f"Error getting task configs: {e}")
            return {}
    
    async def get_task_config(self, task_type: str) -> Optional[Dict[str, Any]]:
        try:
            current_time = time.time()
            if (current_time - self._cache_timestamp) < self._cache_duration and self._task_configs_cache:
                if task_type in self._task_configs_cache:
                    return self._task_configs_cache[task_type]
            
            all_configs = await self.get_all_task_configs()
            return all_configs.get(task_type)
            
        except Exception as e:
            logging.error(f"Error getting task config for {task_type}: {e}")
            return None
    
    def _convert_db_config_to_api_format(self, db_config: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'is_stream': db_config.get('is_stream', False),
            'endpoint': db_config.get('endpoint', '/chat/completions'),
            'timeout': db_config.get('timeout', 30),
            'response_model': db_config.get('task_type', 'text'),
            'description': db_config.get('description') or db_config.get('display_name') or db_config.get('task', ''),
            'task_type': db_config.get('task_type', 'text'),
            'max_capacity': db_config.get('max_capacity', 1.0),
            'weight': db_config.get('weight', 1.0),
            'enabled': db_config.get('enabled', True),
            'display_name': db_config.get('display_name'),
            'is_reasoning': db_config.get('is_reasoning', False)
        }
    
    async def get_task_configs_with_cache(self) -> Dict[str, Any]:
        current_time = time.time()
        
        if (current_time - self._cache_timestamp) < self._cache_duration and self._task_configs_cache:
            return self._task_configs_cache
        
        return await self.get_all_task_configs()
    
    def clear_cache(self):
        self._task_configs_cache = {}
        self._cache_timestamp = 0
    
    async def test_connection(self) -> bool:
        try:
            url = f"{self.base_url}/task_configs"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, timeout=10) as response:
                    return response.status == 200
                    
        except Exception as e:
            logging.error(f"Error testing connection: {e}")
            return False
