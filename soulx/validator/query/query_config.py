# -*- coding: utf-8 -*-

from dataclasses import dataclass
from fiber import Keypair
import httpx
from fiber.logging_utils import get_logger
from redis.asyncio import Redis
from typing import Optional, Dict, Any, List
import asyncio
import os

from soulx.validator.node_client import NodeClient
from soulx.validator.contender_client import ContenderClient
from soulx.validator.reward_client import RewardClient

logger = get_logger(__name__)

def create_fiber_compatible_config(
    redis_db: Redis,
    netuid: int,
    httpx_client: httpx.AsyncClient = None,
    replace_with_localhost: bool = False,
    replace_with_docker_localhost: bool = True,
    prod: bool = True
) -> 'Config':

    wallet_seed = os.getenv("WALLET_SECRET_SEED")
    if not wallet_seed:
        logger.error("WALLET_SECRET_SEED environment variable not set")
        raise ValueError("WALLET_SECRET_SEED environment variable is required")
    
    try:
        from substrateinterface import Keypair
        keypair = Keypair.create_from_seed(wallet_seed)
        ss58_address = keypair.ss58_address
        logger.info(f"Created fiber-compatible keypair with ss58_address: {ss58_address}")
    except Exception as e:
        logger.error(f"Failed to create keypair from seed: {e}")
        raise
    
    if httpx_client is None:
        httpx_client = httpx.AsyncClient(timeout=5)
    
    return Config(
        keypair=keypair,
        redis_db=redis_db,
        ss58_address=ss58_address,
        netuid=netuid,
        httpx_client=httpx_client,
        replace_with_localhost=replace_with_localhost,
        replace_with_docker_localhost=replace_with_docker_localhost,
        prod=prod
    )

@dataclass
class Config:
    keypair: Keypair
    redis_db: Redis
    ss58_address: str
    netuid: int
    httpx_client: httpx.AsyncClient = httpx.AsyncClient(timeout=5)
    replace_with_localhost: bool = False
    replace_with_docker_localhost: bool = True
    prod: bool = True
    
    node_client: Optional[NodeClient] = None
    contender_client: Optional[ContenderClient] = None
    reward_client: Optional[RewardClient] = None
    
    def __post_init__(self):

        import os
        central_server_url = os.getenv('CONFIG_SERVER_URL', 'http://config.asiatensor.xyz')
        central_server_token = os.getenv('VALIDATOR_TOKEN')
        
        if not hasattr(self.keypair, 'sign'):
            try:
                from substrateinterface import Keypair
                wallet_seed = os.getenv("WALLET_SECRET_SEED")
                if wallet_seed:
                    self.keypair = Keypair.create_from_seed(wallet_seed)
                    self.ss58_address = self.keypair.ss58_address
                    logger.info(f"Updated keypair from seed with ss58_address: {self.ss58_address}")
                else:
                    logger.warning("WALLET_SECRET_SEED not set, using provided keypair")
            except Exception as e:
                logger.error(f"Failed to create keypair from seed: {e}")
        
        if self.node_client is None:
            self.node_client = NodeClient(central_server_url, central_server_token)
        
        if self.contender_client is None:
            self.contender_client = ContenderClient(central_server_url, "validator_hotkey", central_server_token)
        
        if self.reward_client is None:
            self.reward_client = RewardClient(central_server_url, self.ss58_address, central_server_token)
    
    async def get_nodes(self) -> Dict[str, Any]:
        if self.node_client is None:
            logger.error("Node client not initialized")
            return {}
        
        return await self.node_client.get_nodes()
    
    async def get_contenders(self) -> Dict[str, Any]:
        if self.contender_client is None:
            logger.error("Contender client not initialized")
            return {}
        
        return await self.contender_client.get_contenders()
    
    async def get_node_by_hotkey(self, hotkey: str) -> Optional[Dict[str, Any]]:
        if self.node_client is None:
            logger.error("Node client not initialized")
            return None
        
        return await self.node_client.get_node_by_hotkey(hotkey)
    
    async def get_contender_by_id(self, contender_id: str) -> Optional[Dict[str, Any]]:
        if self.contender_client is None:
            logger.error("Contender client not initialized")
            return None
        
        return await self.contender_client.get_contender_by_id(contender_id)
    
    async def insert_reward_data(self, reward_data: Dict[str, Any]) -> bool:
        if self.reward_client is None:
            logger.error("Reward client not initialized")
            return False
        
        return await self.reward_client.insert_reward_data(reward_data)
    
    async def get_reward_data_by_validator(
        self,
        validator_hotkey: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        if self.reward_client is None:
            logger.error("Reward client not initialized")
            return []
        
        return await self.reward_client.get_reward_data_by_validator(validator_hotkey, limit, offset)
    
    async def get_reward_statistics(
        self,
        validator_hotkey: Optional[str] = None,
        node_hotkey: Optional[str] = None,
        task: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        if self.reward_client is None:
            logger.error("Reward client not initialized")
            return {}
        
        return await self.reward_client.get_reward_statistics(validator_hotkey, node_hotkey, task, days)
    
    def clear_cache(self):
        if self.node_client:
            self.node_client.clear_cache()
        if self.contender_client:
            self.contender_client.clear_cache()
        if self.reward_client:
            self.reward_client.clear_cache()
        logger.info("All caches cleared")