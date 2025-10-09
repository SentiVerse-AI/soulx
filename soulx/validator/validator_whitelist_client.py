# -*- coding: utf-8 -*-

import asyncio
import json
import time
from typing import Dict, List, Optional, Any
import httpx
from dataclasses import dataclass

from bittensor import logging

@dataclass
class ValidatorListConfig:
    whitelist: List[str]
    blacklist: List[str]
    penalty_coefficient: float
    owner_default_score: float
    last_updated: int
    cache_duration: int = 300


class ValidatorWhitelistClient:

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
    
    async def get_whitelist(self) -> List[str]:
        try:
            url = f"{self.base_url}/api/validator/whitelist?ver={self.api_version}"
            response = await self.client.get(url, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            whitelist = data.get('whitelist', [])
            
            return whitelist
            
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error fetching whitelist: {e.response.status_code}")
            return []
        except Exception as e:
            logging.error(f"Error fetching whitelist: {e}")
            return []
    
    async def get_blacklist(self) -> List[str]:
        try:
            url = f"{self.base_url}/api/validator/blacklist?ver={self.api_version}"
            response = await self.client.get(url, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            blacklist = data.get('blacklist', [])
            
            return blacklist
            
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error fetching blacklist: {e.response.status_code}")
            return []
        except Exception as e:
            logging.error(f"Error fetching blacklist: {e}")
            return []
    
    async def get_config(self) -> ValidatorListConfig:
        try:
            url = f"{self.base_url}/api/validator/config?ver={self.api_version}"
            response = await self.client.get(url, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            
            config = ValidatorListConfig(
                whitelist=data.get('whitelist', []),
                blacklist=data.get('blacklist', []),
                penalty_coefficient=data.get('penalty_coefficient', 0.1),
                owner_default_score=data.get('owner_default_score', 1.0),
                last_updated=int(time.time()),
                cache_duration=data.get('cache_duration', 300)
            )
            
            logging.info(f"Successfully fetched validator config: "
                        f"{len(config.whitelist)} whitelist, "
                        f"{len(config.blacklist)} blacklist")
            return config
            
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error fetching validator config: {e.response.status_code}")
            return self._get_default_config()
        except Exception as e:
            logging.error(f"Error fetching validator config: {e}")
            return self._get_default_config()
    
    async def get_system_config(self, config_key: str) -> Any:
        try:
            url = f"{self.base_url}/api/validator/system_config/{config_key}?ver={self.api_version}"
            response = await self.client.get(url, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            if not data:
                return None
            
            config_value = data.get('config_value')
            data_type = data.get('data_type', 'string')
            
            if data_type == 'string':
                return str(config_value)
            elif data_type == 'number':
                try:
                    return float(config_value)
                except ValueError:
                    return int(config_value)
            elif data_type == 'boolean':
                return config_value.lower() in ('true', '1', 'yes', 'on')
            elif data_type == 'json':
                return json.loads(config_value) if isinstance(config_value, str) else config_value
            else:
                logging.warning(f"Unknown data type '{data_type}' for config key '{config_key}'")
                return config_value
                
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error fetching system config {config_key}: {e.response.status_code}")
            return None
        except Exception as e:
            logging.error(f"Error fetching system config {config_key}: {e}")
            return None
    
    async def is_validator_whitelisted(self, validator_hotkey: str) -> bool:
        try:
            whitelist = await self.get_whitelist()
            return validator_hotkey in whitelist
        except Exception as e:
            logging.error(f"Error checking whitelist status for {validator_hotkey}: {e}")
            return False
    
    async def is_validator_blacklisted(self, validator_hotkey: str) -> bool:
        try:
            blacklist = await self.get_blacklist()
            return validator_hotkey in blacklist
        except Exception as e:
            logging.error(f"Error checking blacklist status for {validator_hotkey}: {e}")
            return False
    
    def _get_default_config(self) -> ValidatorListConfig:
        from soulx.core.constants import DEFAULT_PENALTY_COEFFICIENT, OWNER_DEFAULT_SCORE
        
        return ValidatorListConfig(
            whitelist=[],
            blacklist=[],
            penalty_coefficient=DEFAULT_PENALTY_COEFFICIENT,
            owner_default_score=OWNER_DEFAULT_SCORE,
            last_updated=int(time.time()),
            cache_duration=300
        )

class ValidatorWhitelistClientSync:

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
    
    def get_whitelist(self) -> List[str]:
        try:
            import requests
            
            url = f"{self.base_url}/api/validator/whitelist?ver={self.api_version}"
            response = requests.get(url, headers=self.headers, timeout=20, verify=False)
            response.raise_for_status()
            
            data = response.json()
            whitelist = data.get('whitelist', [])
            
            logging.info(f"Successfully fetched whitelist: {len(whitelist)} validators")
            return whitelist
            
        except Exception as e:
            logging.error(f"Error fetching whitelist: {e}")
            return []
    
    def get_blacklist(self) -> List[str]:
        try:
            import requests
            
            url = f"{self.base_url}/api/validator/blacklist?ver={self.api_version}"
            response = requests.get(url, headers=self.headers, timeout=20, verify=False)
            response.raise_for_status()
            
            data = response.json()
            blacklist = data.get('blacklist', [])
            
            logging.info(f"Successfully fetched blacklist: {len(blacklist)} validators")
            return blacklist
            
        except Exception as e:
            logging.error(f"Error fetching blacklist: {e}")
            return []
    
    def get_config(self) -> ValidatorListConfig:
        try:
            import requests
            
            url = f"{self.base_url}/api/validator/config?ver={self.api_version}"
            response = requests.get(url, headers=self.headers, timeout=20, verify=False)
            response.raise_for_status()
            
            data = response.json()
            
            config = ValidatorListConfig(
                whitelist=data.get('whitelist', []),
                blacklist=data.get('blacklist', []),
                penalty_coefficient=data.get('penalty_coefficient', 0.1),
                owner_default_score=data.get('owner_default_score', 1.0),
                last_updated=int(time.time()),
                cache_duration=data.get('cache_duration', 300)
            )
            
            logging.info(f"Successfully fetched validator config: "
                        f"{len(config.whitelist)} whitelist, "
                        f"{len(config.blacklist)} blacklist")
            return config
            
        except Exception as e:
            logging.error(f"Error fetching validator config: {e}")
            return self._get_default_config()
    
    def get_system_config(self, config_key: str) -> Any:
        try:
            import requests
            
            url = f"{self.base_url}/api/validator/system_config/{config_key}?ver={self.api_version}"
            response = requests.get(url, headers=self.headers, timeout=20, verify=False)
            response.raise_for_status()
            
            data = response.json()
            if not data:
                return None
            
            config_value = data.get('config_value')
            data_type = data.get('data_type', 'string')
            
            if data_type == 'string':
                return str(config_value)
            elif data_type == 'number':
                try:
                    return float(config_value)
                except ValueError:
                    return int(config_value)
            elif data_type == 'boolean':
                return config_value.lower() in ('true', '1', 'yes', 'on')
            elif data_type == 'json':
                return json.loads(config_value) if isinstance(config_value, str) else config_value
            else:
                logging.warning(f"Unknown data type '{data_type}' for config key '{config_key}'")
                return config_value
                
        except Exception as e:
            logging.error(f"Error fetching system config {config_key}: {e}")
            return None
    
    def is_validator_whitelisted(self, validator_hotkey: str) -> bool:
        try:
            whitelist = self.get_whitelist()
            return validator_hotkey in whitelist
        except Exception as e:
            logging.error(f"Error checking whitelist status for {validator_hotkey}: {e}")
            return False
    
    def is_validator_blacklisted(self, validator_hotkey: str) -> bool:
        try:
            blacklist = self.get_blacklist()
            return validator_hotkey in blacklist
        except Exception as e:
            logging.error(f"Error checking blacklist status for {validator_hotkey}: {e}")
            return False
    
    def _get_default_config(self) -> ValidatorListConfig:
        from soulx.core.constants import DEFAULT_PENALTY_COEFFICIENT, OWNER_DEFAULT_SCORE
        
        return ValidatorListConfig(
            whitelist=[],
            blacklist=[],
            penalty_coefficient=DEFAULT_PENALTY_COEFFICIENT,
            owner_default_score=OWNER_DEFAULT_SCORE,
            last_updated=int(time.time()),
            cache_duration=300
        ) 