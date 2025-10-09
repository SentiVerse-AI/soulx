# -*- coding: utf-8 -*-

import asyncio
import json
import time
from typing import Dict, List, Optional, Any
import httpx
from dataclasses import dataclass

from bittensor import logging


@dataclass
class ConfigValue:
    config_key: str
    config_value: Any
    data_type: str
    description: Optional[str] = None
    updated_at: Optional[str] = None


class ConfigClient:

    def __init__(self, base_url: str, validator_hotkey: str, token: str = ""):

        self.base_url = base_url.rstrip('/')
        self.validator_hotkey = validator_hotkey
        self.token = token
        self.api_version = "v1.0.1"
        
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
        
        self.headers = {
            "Content-Type": "application/json"
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"
        if self.validator_hotkey:
            self.headers["Hotkey"] = self.validator_hotkey
    
    async def close(self):
        await self.client.aclose()
    
    async def get_config(self, config_key: str) -> Optional[ConfigValue]:
        try:
            url = f"{self.base_url}/system/config/{config_key}?ver={self.api_version}"
            response = await self.client.get(url, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            if not data:
                return None
            
            return ConfigValue(
                config_key=data.get('config_key'),
                config_value=data.get('config_value'),
                data_type=data.get('data_type', 'string'),
                description=data.get('description'),
                updated_at=data.get('updated_at')
            )
            
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error fetching config {config_key}: {e.response.status_code}")
            return None
        except Exception as e:
            logging.error(f"Error fetching config {config_key}: {e}")
            return None
    
    async def get_config_value(self, config_key: str, default_value: Any = None) -> Any:
        try:
            config = await self.get_config(config_key)
            if config is None:
                return default_value
            
            if config.data_type == 'number':
                try:
                    return float(config.config_value) if '.' in str(config.config_value) else int(config.config_value)
                except ValueError:
                    return default_value
            elif config.data_type == 'boolean':
                return str(config.config_value).lower() in ('true', '1', 'yes', 'on')
            elif config.data_type == 'json':
                try:
                    return json.loads(config.config_value) if isinstance(config.config_value, str) else config.config_value
                except json.JSONDecodeError:
                    return default_value
            else:
                return config.config_value
                
        except Exception as e:
            logging.error(f"Error getting config value for {config_key}: {e}")
            return default_value
    

    async def get_all_configs(self) -> List[ConfigValue]:
        try:
            url = f"{self.base_url}/system/configs?ver={self.api_version}"
            response = await self.client.get(url, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            configs = []
            
            for item in data.get('configs', []):
                configs.append(ConfigValue(
                    config_key=item.get('config_key'),
                    config_value=item.get('config_value'),
                    data_type=item.get('data_type', 'string'),
                    description=item.get('description'),
                    updated_at=item.get('updated_at')
                ))
            
            logging.info(f"Successfully fetched {len(configs)} configs")
            return configs
            
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error fetching all configs: {e.response.status_code}")
            return []
        except Exception as e:
            logging.error(f"Error fetching all configs: {e}")
            return []
    
    async def get_miners_config(self) -> List[str]:
        try:
            url = f"{self.base_url}/system/config/miners"
            response = await self.client.get(url, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            if data.get('success'):
                return data.get('miners', [])
            else:
                logging.error(f"Failed to get miners config: {data.get('error', 'Unknown error')}")
                return []
                    
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error getting miners config: {e.response.status_code}")
            return []
        except Exception as e:
            logging.error(f"Error getting miners config: {e}")
            return []
    
    async def get_validators_config(self) -> List[str]:
        try:
            url = f"{self.base_url}/system/config/validators"
            response = await self.client.get(url, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            if data.get('success'):
                return data.get('validators', [])
            else:
                logging.error(f"Failed to get validators config: {data.get('error', 'Unknown error')}")
                return []
                    
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error getting validators config: {e.response.status_code}")
            return []
        except Exception as e:
            logging.error(f"Error getting validators config: {e}")
            return []

    async def get_validator_init_config(self) -> Optional[Dict[str, Any]]:
        try:
            url = f"{self.base_url}/system/config/validatorinit"
            response = await self.client.get(url, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            if data.get('success'):
                logging.info(f"Successfully fetched validator init config: "
                           f"{data.get('count', {}).get('whitelist', 0)} whitelist, "
                           f"{data.get('count', {}).get('blacklist', 0)} blacklist")
                return data
            else:
                logging.error(f"Failed to get validator init config: {data.get('error', 'Unknown error')}")
                return None
                    
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error getting validator init config: {e.response.status_code}")
            return None
        except Exception as e:
            logging.error(f"Error getting validator init config: {e}")
            return None
    
    async def is_miner_hotkey(self, hotkey: str) -> bool:
        try:
            miners = await self.get_miners_config()
            return hotkey in miners
        except Exception as e:
            logging.error(f"Error checking if hotkey is miner: {e}")
            return False
    
    async def is_validator_hotkey(self, hotkey: str) -> bool:
        try:
            validators = await self.get_validators_config()
            return hotkey in validators
        except Exception as e:
            logging.error(f"Error checking if hotkey is validator: {e}")
            return False
    
    async def get_config_summary(self) -> Dict[str, Any]:
        try:
            miners = await self.get_miners_config()
            validators = await self.get_validators_config()
            
            return {
                'miners_count': len(miners),
                'validators_count': len(validators),
                'miners': miners[:5],
                'validators': validators[:5],
                'timestamp': time.time()
            }
        except Exception as e:
            logging.error(f"Error getting config summary: {e}")
            return {
                'miners_count': 0,
                'validators_count': 0,
                'miners': [],
                'validators': [],
                'timestamp': time.time(),
                'error': str(e)
            }
    
    async def refresh_configs(self) -> bool:
        try:
            miners = await self.get_miners_config()
            validators = await self.get_validators_config()
            
            logging.info(f"Refreshed configs: {len(miners)} miners, {len(validators)} validators")
            return True
        except Exception as e:
            logging.error(f"Error refreshing configs: {e}")
            return False
    
    async def validate_configs(self) -> Dict[str, bool]:
        try:
            results = {}
            
            miners = await self.get_miners_config()
            results['miners_valid'] = len(miners) > 0 and all(len(hotkey) > 0 for hotkey in miners)
            
            validators = await self.get_validators_config()
            results['validators_valid'] = len(validators) > 0 and all(len(hotkey) > 0 for hotkey in validators)
            
            all_hotkeys = miners + validators
            results['no_duplicates'] = len(all_hotkeys) == len(set(all_hotkeys))
            
            results['overall_valid'] = all(results.values())
            
            return results
        except Exception as e:
            logging.error(f"Error validating configs: {e}")
            return {
                'miners_valid': False,
                'validators_valid': False,
                'no_duplicates': False,
                'overall_valid': False,
                'error': str(e)
            }
    
class ConfigClientSync:

    def __init__(self, base_url: str, validator_hotkey: str, token: str = ""):

        self.base_url = base_url.rstrip('/')
        self.validator_hotkey = validator_hotkey
        self.token = token
        self.api_version = "v1.0.1"
        
        self.headers = {
            "Content-Type": "application/json"
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"
        if self.validator_hotkey:
            self.headers["Hotkey"] = self.validator_hotkey
    
    def get_config(self, config_key: str) -> Optional[ConfigValue]:
        try:
            import requests
            
            url = f"{self.base_url}/system/config/{config_key}?ver={self.api_version}"
            response = requests.get(url, headers=self.headers, timeout=20, verify=False)
            response.raise_for_status()
            
            data = response.json()
            if not data:
                return None
            
            return ConfigValue(
                config_key=data.get('config_key'),
                config_value=data.get('config_value'),
                data_type=data.get('data_type', 'string'),
                description=data.get('description'),
                updated_at=data.get('updated_at')
            )
            
        except Exception as e:
            logging.error(f"Error fetching config {config_key}: {e}")
            return None
    
    def get_config_value(self, config_key: str, default_value: Any = None) -> Any:
        try:
            config = self.get_config(config_key)
            if config is None:
                return default_value
            
            if config.data_type == 'number':
                try:
                    return float(config.config_value) if '.' in str(config.config_value) else int(config.config_value)
                except ValueError:
                    return default_value
            elif config.data_type == 'boolean':
                return str(config.config_value).lower() in ('true', '1', 'yes', 'on')
            elif config.data_type == 'json':
                try:
                    return json.loads(config.config_value) if isinstance(config.config_value, str) else config.config_value
                except json.JSONDecodeError:
                    return default_value
            else:
                return config.config_value
                
        except Exception as e:
            logging.error(f"Error getting config value for {config_key}: {e}")
            return default_value
    
    def get_miners_config(self) -> List[str]:
        try:
            import requests
            
            url = f"{self.base_url}/system/miners/config"
            response = requests.get(url, headers=self.headers, timeout=20, verify=False)
            response.raise_for_status()
            
            data = response.json()
            if data.get('success'):
                return data.get('miners', [])
            else:
                logging.error(f"Failed to get miners config: {data.get('error', 'Unknown error')}")
                return []
                    
        except Exception as e:
            logging.error(f"Error getting miners config: {e}")
            return []
    
    def get_validators_config(self) -> List[str]:
        try:
            import requests
            
            url = f"{self.base_url}/system/validators/config"
            response = requests.get(url, headers=self.headers, timeout=20, verify=False)
            response.raise_for_status()
            
            data = response.json()
            if data.get('success'):
                return data.get('validators', [])
            else:
                logging.error(f"Failed to get validators config: {data.get('error', 'Unknown error')}")
                return []
                    
        except Exception as e:
            logging.error(f"Error getting validators config: {e}")
            return []

    def get_validator_init_config(self) -> Optional[Dict[str, Any]]:
        try:
            import requests
            
            url = f"{self.base_url}/system/validatorinit/config"
            response = requests.get(url, headers=self.headers, timeout=20, verify=False)
            response.raise_for_status()
            
            data = response.json()
            if data.get('success'):
                logging.info(f"Successfully fetched validator init config: ")
                return data
            else:
                logging.error(f"Failed to get validator init config: {data.get('error', 'Unknown error')}")
                return None
                    
        except Exception as e:
            logging.error(f"Error getting validator init config: {e}")
            return None
    
    def is_miner_hotkey(self, hotkey: str) -> bool:
        try:
            miners = self.get_miners_config()
            return hotkey in miners
        except Exception as e:
            logging.error(f"Error checking if hotkey is miner: {e}")
            return False
    
    def is_validator_hotkey(self, hotkey: str) -> bool:
        try:
            validators = self.get_validators_config()
            return hotkey in validators
        except Exception as e:
            logging.error(f"Error checking if hotkey is validator: {e}")
            return False
    
    def get_config_summary(self) -> Dict[str, Any]:
        try:
            miners = self.get_miners_config()
            validators = self.get_validators_config()
            
            return {
                'miners_count': len(miners),
                'validators_count': len(validators),
                'miners': miners[:5],
                'validators': validators[:5],
                'timestamp': time.time()
            }
        except Exception as e:
            logging.error(f"Error getting config summary: {e}")
            return {
                'miners_count': 0,
                'validators_count': 0,
                'miners': [],
                'validators': [],
                'timestamp': time.time(),
                'error': str(e)
            }
    

    def get_all_configs(self) -> List[ConfigValue]:
        try:
            import requests
            
            url = f"{self.base_url}/system/configs?ver={self.api_version}"
            response = requests.get(url, headers=self.headers, timeout=20, verify=False)
            response.raise_for_status()
            
            data = response.json()
            configs = []
            
            for item in data.get('configs', []):
                configs.append(ConfigValue(
                    config_key=item.get('config_key'),
                    config_value=item.get('config_value'),
                    data_type=item.get('data_type', 'string'),
                    description=item.get('description'),
                    updated_at=item.get('updated_at')
                ))
            
            logging.info(f"Successfully fetched {len(configs)} configs")
            return configs
            
        except Exception as e:
            logging.error(f"Error fetching all configs: {e}")
            return []

def get_config_value(config_key: str, default_value: Any = None) -> Any:
    logging.warning(f"get_config_value called for {config_key}, returning default value. Please use ConfigClient instead.")
    return default_value