# -*- coding: utf-8 -*-

import asyncio
import json
from bittensor import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

import requests

class SystemClient:

    def __init__(self, base_url: str, validator_hotkey: str, token: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.validator_hotkey = validator_hotkey
        self.token = token
        self.session = requests.Session()
        self._setup_session()
    
    def _setup_session(self):

        self.session.headers.update({
            'Content-Type': 'application/json',
            'Hotkey': self.validator_hotkey
        })
        
        if self.token:
            self.session.headers.update({
                'Authorization': f'Bearer {self.token}'
            })
        
        self.session.timeout = 30
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def ensure_session(self):
        pass
    
    async def close(self):
        pass
    
    def _get_headers(self) -> Dict[str, str]:
        headers = {
            'Content-Type': 'application/json',
            'Hotkey': self.validator_hotkey
        }
        
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        
        return headers
    
    async def get_validators_config(self) -> List[str]:
        try:
            url = f"{self.base_url}/system/config/validators"
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            if data.get('success'):
                return data.get('validators', [])
            else:
                return []
                    
        except requests.exceptions.RequestException as e:
            return []
        except Exception as e:
            return []
    
    async def get_system_config(self, config_key: str) -> Optional[Dict[str, Any]]:
        try:
            url = f"{self.base_url}/system/config/{config_key}"
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return data
                    
        except requests.exceptions.RequestException as e:
            return None
        except Exception as e:
            return None
    
    async def is_validator_hotkey(self, hotkey: str) -> bool:
        try:
            validators = await self.get_validators_config()
            return hotkey in validators
        except Exception as e:
            logging.error(f"Error checking if hotkey is validator: {e}")
            return False
    

    async def refresh_configs(self) -> bool:
        try:
            validators = await self.get_validators_config()
            logging.info(f"Refreshed configs: {len(validators)} validators")
            return True
        except Exception as e:
            logging.error(f"Error refreshing configs: {e}")
            return False
    
    async def validate_configs(self) -> Dict[str, bool]:
        try:
            results = {}
            
            validators = await self.get_validators_config()
            results['validators_valid'] = len(validators) > 0 and all(len(hotkey) > 0 for hotkey in validators)
            
            all_hotkeys =  validators
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

async def create_system_client(base_url: str, validator_hotkey: str, token: Optional[str] = None) -> SystemClient:
    return SystemClient(base_url, validator_hotkey, token)
