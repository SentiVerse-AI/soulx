import secrets
import string
import hashlib
import time
import os
from typing import Optional, Dict, List
from datetime import datetime, timedelta

from bittensor import logging
from soulx.validator.token_client import TokenClientSync

from dotenv import load_dotenv
from soulx.core.path_utils import PathUtils


class TokenManager:

    def __init__(self):
        base_url = os.getenv("CONFIG_SERVER_URL", "http://config.asiatensor.xyz")
        validator_hotkey = os.getenv("VALIDATOR_HOTKEY", "")
        token = os.getenv("VALIDATOR_TOKEN", "")
        
        self.token_client = TokenClientSync(
            base_url=base_url,
            validator_hotkey=validator_hotkey,
            token=token
        )
        
        logging.info(f"Token manager initialized with config server: {base_url}")
        
    def generate_token(self, length: int = 64) -> str:

        alphabet = string.ascii_letters + string.digits
        token = ''.join(secrets.choice(alphabet) for _ in range(length))
        return token
        
    def hash_token(self, token: str) -> str:

        return hashlib.sha256(token.encode()).hexdigest()
        
    def create_token(self, validator_hotkey: str, description: str = "", created_by: str = "system") -> Optional[str]:

        try:
            token = self.token_client.create_token(validator_hotkey, description)
            
            if token:
                logging.info(f"Created new token for validator {validator_hotkey}")
                return token
            else:
                logging.error(f"Failed to create token for validator {validator_hotkey}")
                return None
                
        except Exception as e:
            logging.error(f"Error creating token for validator {validator_hotkey}: {e}")
            return None
            
    def validate_token(self, token: str) -> Optional[Dict]:

        try:
            result = self.token_client.validate_token(token)
            
            if result:
                logging.info(f"Token validated successfully for validator {result.get('validator_hotkey')}")
                return result
            else:
                logging.warning(f"Token validation failed")
                return None
                
        except Exception as e:
            logging.error(f"Error validating token: {e}")
            return None
            
    def _update_last_used(self, token: str):
        logging.warning("_update_last_used is deprecated. Token usage is tracked by the central server.")
            
    def revoke_token(self, token: str = None, validator_hotkey: str = None) -> bool:

        try:
            success = self.token_client.revoke_token(token, validator_hotkey)
            
            if success:
                target = token or f"validator {validator_hotkey}"
                logging.info(f"Revoked token(s) for {target}")
                return True
            else:
                logging.warning(f"No active tokens found to revoke")
                return False
                
        except Exception as e:
            logging.error(f"Error revoking token: {e}")
            return False
            
    def list_tokens(self, validator_hotkey: str = None, active_only: bool = True) -> List[Dict]:

        try:
            token_infos = self.token_client.list_tokens(validator_hotkey, active_only)
            
            tokens = []
            for token_info in token_infos:
                masked_token = f"{token_info.token[:8]}...{token_info.token[-8:]}" if len(token_info.token) > 16 else token_info.token
                
                tokens.append({
                    'validator_hotkey': token_info.validator_hotkey,
                    'token': masked_token,
                    'full_token': token_info.token,
                    'created_at': token_info.created_at,
                    'last_used_at': token_info.last_used_at,
                    'description': token_info.description,
                    'is_active': token_info.is_active
                })
                
            return tokens
            
        except Exception as e:
            logging.error(f"Error listing tokens: {e}")
            return []
            
    def get_validator_by_token(self, token: str) -> Optional[str]:

        validator_info = self.validate_token(token)
        return validator_info['validator_hotkey'] if validator_info else None
        
    def cleanup_expired_tokens(self) -> int:

        logging.warning("cleanup_expired_tokens is deprecated. Token cleanup is managed by the central server.")
        return 0
            
    def get_token_stats(self) -> Dict:

        try:
            stats = self.token_client.get_token_stats()
            return stats
            
        except Exception as e:
            logging.error(f"Error getting token stats: {e}")
            return {}
            
    def regenerate_token(self, validator_hotkey: str, description: str = "") -> Optional[str]:

        try:
            self.revoke_token(validator_hotkey=validator_hotkey)
            
            new_token = self.create_token(validator_hotkey, description)
            
            if new_token:
                logging.info(f"Regenerated token for validator {validator_hotkey}")
                
            return new_token
            
        except Exception as e:
            logging.error(f"Error regenerating token for validator {validator_hotkey}: {e}")
            return None