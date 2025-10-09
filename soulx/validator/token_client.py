# -*- coding: utf-8 -*-

import asyncio
import json
import time
from typing import Dict, List, Optional, Any
import httpx
from dataclasses import dataclass

from bittensor import logging


@dataclass
class TokenInfo:
    token: str
    validator_hotkey: str
    created_at: str
    last_used_at: Optional[str]
    description: Optional[str]
    is_active: bool


class TokenClient:

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
    
    async def create_token(self, validator_hotkey: str, description: str = "") -> Optional[str]:
        try:
            url = f"{self.base_url}/api/validator/tokens?ver={self.api_version}"
            
            payload = {
                "validator_hotkey": validator_hotkey,
                "description": description
            }
            
            response = await self.client.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            token = data.get('token')
            
            if token:
                logging.info(f"Successfully created token for validator {validator_hotkey}")
                return token
            else:
                logging.error(f"Failed to create token for validator {validator_hotkey}")
                return None
                
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error creating token: {e.response.status_code}")
            return None
        except Exception as e:
            logging.error(f"Error creating token: {e}")
            return None
    
    async def validate_token(self, token: str) -> Optional[Dict]:
        try:
            url = f"{self.base_url}/api/validator/tokens/validate?ver={self.api_version}"
            
            payload = {
                "token": token
            }
            
            response = await self.client.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            if data.get('valid', False):
                return {
                    'validator_hotkey': data.get('validator_hotkey'),
                    'created_at': data.get('created_at'),
                    'last_used_at': data.get('last_used_at'),
                    'description': data.get('description')
                }
            else:
                return None
                
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error validating token: {e.response.status_code}")
            return None
        except Exception as e:
            logging.error(f"Error validating token: {e}")
            return None
    
    async def revoke_token(self, token: str = None, validator_hotkey: str = None) -> bool:
        try:
            url = f"{self.base_url}/api/validator/tokens/revoke?ver={self.api_version}"
            
            payload = {}
            if token:
                payload['token'] = token
            if validator_hotkey:
                payload['validator_hotkey'] = validator_hotkey
            
            response = await self.client.delete(url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            logging.info(f"Successfully revoked token")
            return True
            
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error revoking token: {e.response.status_code}")
            return False
        except Exception as e:
            logging.error(f"Error revoking token: {e}")
            return False
    
    async def list_tokens(self, validator_hotkey: str = None, active_only: bool = True) -> List[TokenInfo]:
        try:
            url = f"{self.base_url}/api/validator/tokens?ver={self.api_version}"
            
            params = {}
            if validator_hotkey:
                params['validator_hotkey'] = validator_hotkey
            if active_only:
                params['active_only'] = 'true'
            
            response = await self.client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            tokens = []
            
            for item in data.get('tokens', []):
                tokens.append(TokenInfo(
                    token=item.get('token'),
                    validator_hotkey=item.get('validator_hotkey'),
                    created_at=item.get('created_at'),
                    last_used_at=item.get('last_used_at'),
                    description=item.get('description'),
                    is_active=item.get('is_active', True)
                ))
            
            logging.info(f"Successfully fetched {len(tokens)} tokens")
            return tokens
            
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error listing tokens: {e.response.status_code}")
            return []
        except Exception as e:
            logging.error(f"Error listing tokens: {e}")
            return []
    
    async def get_token_stats(self) -> Dict:
        try:
            url = f"{self.base_url}/api/validator/tokens/stats?ver={self.api_version}"
            response = await self.client.get(url, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            return data
            
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error getting token stats: {e.response.status_code}")
            return {}
        except Exception as e:
            logging.error(f"Error getting token stats: {e}")
            return {}

class TokenClientSync:

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
    
    def validate_token(self, token: str) -> Optional[Dict]:
        try:
            import requests
            
            url = f"{self.base_url}/api/validator/tokens/validate?ver={self.api_version}"
            
            payload = {
                "token": token
            }
            
            response = requests.post(url, headers=self.headers, json=payload, timeout=20, verify=False)
            response.raise_for_status()
            
            data = response.json()
            if data.get('valid', False):
                return {
                    'validator_hotkey': data.get('validator_hotkey'),
                    'created_at': data.get('created_at'),
                    'last_used_at': data.get('last_used_at'),
                    'description': data.get('description')
                }
            else:
                return None
                
        except Exception as e:
            logging.error(f"Error validating token: {e}")
            return None
    
    
    def list_tokens(self, validator_hotkey: str = None, active_only: bool = True) -> List[TokenInfo]:
        try:
            import requests
            
            url = f"{self.base_url}/api/validator/tokens?ver={self.api_version}"
            
            params = {}
            if validator_hotkey:
                params['validator_hotkey'] = validator_hotkey
            if active_only:
                params['active_only'] = 'true'
            
            response = requests.get(url, headers=self.headers, params=params, timeout=20, verify=False)
            response.raise_for_status()
            
            data = response.json()
            tokens = []
            
            for item in data.get('tokens', []):
                tokens.append(TokenInfo(
                    token=item.get('token'),
                    validator_hotkey=item.get('validator_hotkey'),
                    created_at=item.get('created_at'),
                    last_used_at=item.get('last_used_at'),
                    description=item.get('description'),
                    is_active=item.get('is_active', True)
                ))
            
            logging.info(f"Successfully fetched {len(tokens)} tokens")
            return tokens
            
        except Exception as e:
            logging.error(f"Error listing tokens: {e}")
            return []
    
    def get_token_stats(self) -> Dict:
        try:
            import requests
            
            url = f"{self.base_url}/api/validator/tokens/stats?ver={self.api_version}"
            response = requests.get(url, headers=self.headers, timeout=20, verify=False)
            response.raise_for_status()
            
            data = response.json()
            return data
            
        except Exception as e:
            logging.error(f"Error getting token stats: {e}")
            return {} 