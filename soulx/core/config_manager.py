import json
import time
import requests
from urllib.parse import urlparse
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass
import os
from pathlib import Path

from bittensor import logging
from soulx.core.path_utils import PathUtils
from soulx.core.config_client import ConfigClientSync

from soulx.core.constants import DEFAULT_PENALTY_COEFFICIENT, OWNER_DEFAULT_SCORE


@dataclass
class ValidatorListConfig:
    whitelist: List[str]
    blacklist: List[str]
    penalty_coefficient: float
    owner_default_score: float
    last_updated: int
    cache_duration: int = 300


class ConfigManager:

    def __init__(self, config_url: Optional[str] = None, validator_token: Optional[str] = None,
                 cache_file: Optional[str] = None, hotkey: Optional[str] = None):

        self.api_version = os.getenv("VALIDATOR_API_VERSION", "v1.0.1")
        base_url = os.getenv("CONFIG_SERVER_URL", "http://config.asiatensor.xyz")
        validator_hotkey = os.getenv("VALIDATOR_HOTKEY", "")
        token = os.getenv("VALIDATOR_TOKEN", "")
        self.client = ConfigClientSync(
            base_url=base_url,
            validator_hotkey=validator_hotkey,
            token=token)

        if cache_file:
            self.cache_file = Path(cache_file)
        else:
            project_root = PathUtils.get_project_root()
            self.cache_file = project_root / "data" / "validator_config.json"

        self.cache_file.parent.mkdir(parents=True, exist_ok=True)

        self.default_config = ValidatorListConfig(
            whitelist=[],
            blacklist=[],
            penalty_coefficient=DEFAULT_PENALTY_COEFFICIENT,
            owner_default_score=OWNER_DEFAULT_SCORE,
            last_updated=0,
            cache_duration=1200
        )

        self._cached_config: Optional[ValidatorListConfig] = None

    def _load_from_cache(self) -> Optional[ValidatorListConfig]:
        try:
            if not self.cache_file.exists():
                return None

            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            return ValidatorListConfig(
                whitelist=data.get('whitelist', []),
                blacklist=data.get('blacklist', []),
                penalty_coefficient=data.get('penalty_coefficient', 0.1),
                owner_default_score=data.get('owner_default_score', OWNER_DEFAULT_SCORE),
                last_updated=data.get('last_updated', 0),
                cache_duration=data.get('cache_duration', 300)
            )
        except Exception as e:
            logging.error(f"Failed to load validator config from cache: {e}")
            return None

    def _save_to_cache(self, config: ValidatorListConfig) -> None:
        try:
            data = {
                'whitelist': config.whitelist,
                'blacklist': config.blacklist,
                'penalty_coefficient': config.penalty_coefficient,
                'owner_default_score': config.owner_default_score,
                'last_updated': config.last_updated,
                'cache_duration': config.cache_duration
            }

            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logging.error(f"Failed to save validator config to cache: {e}")

    def _fetch_from_server(self) -> Optional[ValidatorListConfig]:
        if not self.client:
            logging.debug("No validator config URL provided")
            return None

        try:


            data = self.client.get_all_configs()

            config = ValidatorListConfig(
                whitelist=data.get('whitelist', []),
                blacklist=data.get('blacklist', []),
                penalty_coefficient=data.get('penalty_coefficient', DEFAULT_PENALTY_COEFFICIENT),
                owner_default_score=data.get('owner_default_score', OWNER_DEFAULT_SCORE),
                last_updated=int(time.time()),
                cache_duration=data.get('cache_duration', 1200)
            )

            self._save_to_cache(config)

            logging.info(f"Successfully fetched validator config from server: "
                         f"{len(config.whitelist)} whitelist, "
                         f"{len(config.blacklist)} blacklist, "
                         f"penalty coefficient: {config.penalty_coefficient}")

            return config

        except Exception as e:
            return None


    def get_config(self, force_refresh: bool = False) -> ValidatorListConfig:

        current_time = int(time.time())

        if (not force_refresh and
                self._cached_config and
                current_time - self._cached_config.last_updated < self._cached_config.cache_duration):
            return self._cached_config


        config = self._fetch_from_server()

        if not config:
            config = self._load_from_cache()

        if not config:
            logging.warning("Using default validator config")
            config = self.default_config

        self._cached_config = config
        return config

    def is_validator_whitelisted(self, validator_hotkey: str) -> bool:
        config = self.get_validator_init_config().get("validator_config")
        return validator_hotkey in config.get("whitelist")

    def is_validator_blacklisted(self, validator_hotkey: str) -> bool:
        config = self.get_validator_init_config().get("validator_config")
        return validator_hotkey in config.get("blacklist")



    def get_penalty_coefficient(self) -> float:
        config = self.get_validator_init_config().get("validator_config")
        return config.get("penalty_coefficient")

    def get_filtered_validators(self, all_validators: List[str]) -> List[str]:

        config = self.get_validator_init_config().get("validator_config")
        blacklist_set = set(config.get("blacklist"))

        filtered = [v for v in all_validators if v not in blacklist_set]

        if len(filtered) != len(all_validators):
            logging.info(f"Filtered out {len(all_validators) - len(filtered)} blacklisted validators")

        return filtered

    def apply_whitelist_penalty(self, validator_hotkey: str, original_score: float) -> float:

        config = self.get_validator_init_config().get("validator_config")

        if validator_hotkey in config.get("blacklist"):
            return 0.0

        if validator_hotkey in config.get("whitelist"):
            return original_score

        penalized_score = original_score * config.get("penalty_coefficient")

        return penalized_score

    def refresh_config(self) -> bool:
        try:
            self.get_config(force_refresh=True)
            return True
        except Exception as e:
            logging.error(f"Failed to refresh validator config: {e}")
            return False

    def get_stats(self) -> Dict:
        config = self.get_config()
        return {
            "whitelist_count": len(config.whitelist),
            "blacklist_count": len(config.blacklist),
            "penalty_coefficient": config.penalty_coefficient,
            "owner_default_score": config.owner_default_score,
            "last_updated": config.last_updated,
            "cache_duration": config.cache_duration,
            "config_url": self.config_url,
            "use_client": True
        }


    def get_system_config(self, config_key: str) -> Any:

        try:
            config_value = self.client.get_config_value(config_key)
            return config_value
        except Exception as e:
            logging.error(f"Error getting system config from client for {config_key}: {e}")
            return None

    def get_miners_config(self)-> List[str]:
        try:
            miners_config = self.client.get_miners_config()
            return miners_config
        except Exception as e:
            logging.error(f"Error get_miners_config from client : {e}")
            return None

    def get_validator_init_config(self) -> Optional[Dict[str, Any]]:

        try:
            validator_config = self.client.get_validator_init_config()
            
            if validator_config and validator_config.get('success'):
                return validator_config
            else:
                logging.warning("Failed to get validator init config from server")
                return None
                
        except Exception as e:
            logging.error(f"Error getting validator init config: {e}")
            return None

    def get_validators_config(self) -> List[str]:

        try:
            validators_config = self.client.get_validators_config()
            return validators_config or []
        except Exception as e:
            logging.error(f"Error getting validators config: {e}")
            return []