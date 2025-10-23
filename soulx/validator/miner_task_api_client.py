# -*- coding: utf-8 -*-
import logging
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger("soulx.validator.miner_task_api")

class MinerTaskApiClient:

    def __init__(self, api_server_url: str, timeout: int = 30):

        self.api_server_url = api_server_url.rstrip('/')
        self.timeout = timeout
        self.base_url = f"{self.api_server_url}/miner-tasks"
        
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
        )
        
    async def set_miner_task(self, miner_hotkey: str, task_id: str,
                           validator_hotkey: str, task_type: str = None) -> bool:

        try:
            url = f"{self.base_url}/set"
            payload = {
                "miner_hotkey": miner_hotkey,
                "task_id": task_id,
                "validator_hotkey": validator_hotkey,
                "task_type": task_type
            }
            
            response = await self.http_client.post(url, json=payload)
            response.raise_for_status()
            
            result = response.json()
            success = result.get("success", False)
            
            if success:
                logger.info(f"Successfully set miner task via API: {miner_hotkey} -> {task_id}")
            else:
                logger.warning(f"Failed to set miner task via API: {miner_hotkey}")
            
            return success
            
        except httpx.HTTPStatusError as e:
            return False
        except Exception as e:
            return False

    async def check_miner_has_task(self, miner_hotkey: str) -> bool:

        try:
            url = f"{self.base_url}/check/{miner_hotkey}"
            
            response = await self.http_client.get(url)
            response.raise_for_status()
            
            result = response.json()
            has_task = result.get("has_task", False)
            
            return has_task
            
        except httpx.HTTPStatusError as e:
            return False
        except Exception as e:
            return False

    async def get_miner_task(self, miner_hotkey: str) -> Optional[Dict[str, Any]]:

        try:
            url = f"{self.base_url}/get/{miner_hotkey}"
            
            response = await self.http_client.get(url)
            response.raise_for_status()
            
            result = response.json()
            success = result.get("success", False)
            
            if success:
                task_data = result.get("task_data")
                return task_data
            else:
                return None
                
        except httpx.HTTPStatusError as e:
            return None
        except Exception as e:
            return None

    async def remove_miner_task(self, miner_hotkey: str) -> bool:

        try:
            url = f"{self.base_url}/remove/{miner_hotkey}"
            
            response = await self.http_client.delete(url)
            response.raise_for_status()
            
            result = response.json()
            success = result.get("success", False)
            
            if success:
                logger.info(f"Successfully removed miner task via API: {miner_hotkey}")
            else:
                logger.warning(f"Failed to remove miner task via API: {miner_hotkey}")
            
            return success
            
        except httpx.HTTPStatusError as e:
            return False
        except Exception as e:
            return False

    async def get_all_active_miners(self) -> List[Dict[str, Any]]:

        try:
            url = f"{self.base_url}/active"
            
            response = await self.http_client.get(url)
            response.raise_for_status()
            
            result = response.json()
            success = result.get("success", False)
            
            if success:
                active_miners = result.get("active_miners", [])
                return active_miners
            else:
                return []
                
        except httpx.HTTPStatusError as e:
            return []
        except Exception as e:
            return []

    async def get_miner_task_stats(self) -> Dict[str, Any]:

        try:
            url = f"{self.base_url}/stats"
            
            response = await self.http_client.get(url)
            response.raise_for_status()
            
            result = response.json()
            return result
            
        except httpx.HTTPStatusError as e:
            return {}
        except Exception as e:
            return {}

    async def health_check(self) -> Dict[str, Any]:

        try:
            url = f"{self.base_url}/health"
            
            response = await self.http_client.get(url)
            response.raise_for_status()
            
            result = response.json()
            return result
            
        except httpx.HTTPStatusError as e:
            return {"success": False, "error": f"HTTP {e.response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def close(self):
        try:
            await self.http_client.aclose()
        except Exception as e:
            logger.error(f"Error closing MinerTaskApiClient: {e}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


_miner_task_api_client_instance = None

async def get_miner_task_api_client() -> MinerTaskApiClient:
    global _miner_task_api_client_instance
    
    if _miner_task_api_client_instance is None:
        import os
        config_server_url = os.getenv("CONFIG_SERVER_URL", "http://config.asiatensor.xyz")
        timeout = int(os.getenv("MINER_TASK_API_TIMEOUT", "30"))
        
        _miner_task_api_client_instance = MinerTaskApiClient(
            api_server_url=config_server_url,
            timeout=timeout
        )
    
    return _miner_task_api_client_instance
