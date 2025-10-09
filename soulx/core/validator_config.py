#!/usr/bin/env python3

import os
from dataclasses import dataclass
from redis.asyncio import Redis, ConnectionPool
from redis.retry import Retry
from redis.backoff import ExponentialBackoff
from typing import Optional
from soulx.core.constants import TESTNET_NETUID

from fiber.logging_utils import get_logger
from fiber.chain import interface
from fiber.chain import chain_utils
import httpx
from substrateinterface import SubstrateInterface, Keypair

logger = get_logger(__name__)


@dataclass
class ValidatorConfig:
    substrate: Optional[SubstrateInterface]
    keypair: Keypair
    subtensor_network: str
    subtensor_address: Optional[str]
    
    netuid: int
    replace_with_localhost: bool
    replace_with_docker_localhost: bool
    
    refresh_nodes: bool
    capacity_to_score_multiplier: float
    scoring_period_time_multiplier: float
    set_metagraph_weights_with_high_updated_to_not_dereg: bool
    
    httpx_client: httpx.AsyncClient
    
    gpu_server_address: Optional[str]
    
    redis_host: str
    redis_port: int
    redis_db: int
    redis_password: Optional[str] = None
    redis_db_instance: Optional[Redis] = None
    
    testnet: bool = False
    debug: bool = False
    
    allocation_strategy: str = "stake"
    log_path: str = "logs"
    check_validator_stake: bool = False
    use_database: bool = False
    validator_token: str = ""
    validator_config_url: str = "http://config.asiatensor.xyz/api/validator/config?ver=1.0.1"
    config_server_url: str = "http://config.asiatensor.xyz"
    public_key_path: str = "keys/cognify_pub.pem"
    check_max_blocks: bool = False
    bt_logging_info: str = "INFO"


def load_hotkey_keypair_from_seed(secret_seed: str) -> Keypair:
    try:
        keypair = Keypair.create_from_seed(secret_seed)
        logger.info("Loaded keypair from seed directly!")
        return keypair
    except Exception as e:
        raise ValueError(f"Failed to load keypair: {str(e)}")


def load_validator_config() -> ValidatorConfig:
    subtensor_network = os.getenv("SUBTENSOR_NETWORK")
    if not subtensor_network:
        raise ValueError("SUBTENSOR_NETWORK must be set")
    
    subtensor_address = os.getenv("SUBTENSOR_ADDRESS") or None
    gpu_server_address = os.getenv("GPU_SERVER_ADDRESS", None)
    dev_env = os.getenv("ENV", "prod").lower() != "prod"
    
    wallet_name = os.getenv("BT_WALLET_NAME", "default")
    hotkey_name = os.getenv("BT_WALLET_HOTKEY", "default")
    
    netuid = os.getenv("NETUID")
    if netuid is None:
        raise ValueError("NETUID must be set")
    else:
        netuid = int(netuid)
    
    localhost = bool(os.getenv("LOCALHOST", "false").lower() == "true")
    if localhost:
        redis_host = "localhost"
        mysql_host = "localhost"
    else:
        redis_host = os.getenv("REDIS_HOST", "redis")
        mysql_host = os.getenv("MYSQL_HOST", "mysql")
    
    replace_with_docker_localhost = bool(os.getenv("REPLACE_WITH_DOCKER_LOCALHOST", "false").lower() == "true")
    
    refresh_nodes: bool = os.getenv("REFRESH_NODES", "true").lower() == "true"
    if refresh_nodes:
        substrate = interface.get_substrate(subtensor_network=subtensor_network, subtensor_address=subtensor_address)
    else:
        substrate = None
    
    try:
        keypair = chain_utils.load_hotkey_keypair(wallet_name=wallet_name, hotkey_name=hotkey_name)
    except (ValueError, FileNotFoundError) as e:
        logger.info("Attempting to use WALLET_SECRET_SEED environment variable")
        secret_seed = os.getenv("WALLET_SECRET_SEED", None)
        if secret_seed:
            try:
                keypair = load_hotkey_keypair_from_seed(secret_seed)
            except Exception as e:
                logger.error(f"Failed to load keypair from seed: {str(e)}")
                raise ValueError(f"Invalid secret seed provided: {str(e)}")
        else:
            logger.error("WALLET_SECRET_SEED environment variable not set")
            raise ValueError(f"Could not load wallet from path and WALLET_SECRET_SEED env var is not set. Original error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error loading hotkey from wallet: {str(e)}")
        raise
    
    default_capacity_to_score_multiplier = 0.1 if subtensor_network == "test" else 1.0
    capacity_to_score_multiplier = float(os.getenv("CAPACITY_TO_SCORE_MULTIPLIER", default_capacity_to_score_multiplier))
    logger.info(f"Capacity to score multiplier: {capacity_to_score_multiplier}")
    
    httpx_limits = httpx.Limits(max_connections=500, max_keepalive_connections=100)
    httpx_client = httpx.AsyncClient(limits=httpx_limits)
    
    scoring_period_time_multiplier = float(os.getenv("SCORING_PERIOD_TIME_MULTIPLIER", 1.0))
    
    set_metagraph_weights_with_high_updated_to_not_dereg = bool(
        os.getenv("SET_METAGRAPH_WEIGHTS_WITH_HIGH_UPDATED_TO_NOT_DEREG", "false").lower() == "true"
    )
    
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    redis_db = int(os.getenv("REDIS_DB", "0"))
    redis_password = os.getenv("REDIS_PASSWORD", None)
    
    allocation_strategy = os.getenv("ALLOCATION_STRATEGY", "stake")
    log_path = os.getenv("LOG_PATH", "logs")
    check_validator_stake = bool(os.getenv("CHECK_VALIDATOR_STAKE", "false").lower() == "true")
    use_database = bool(os.getenv("USE_DATABASE", "false").lower() == "true")
    validator_token = os.getenv("VALIDATOR_TOKEN", "")
    validator_config_url = os.getenv("VALIDATOR_CONFIG_URL", "http://config.asiatensor.xyz/api/validator/config?ver=1.0.1")
    config_server_url = os.getenv("CONFIG_SERVER_URL", "http://config.asiatensor.xyz")
    public_key_path = os.getenv("PUBLIC_KEY_PATH", "keys/cognify_pub.pem")
    check_max_blocks = bool(os.getenv("CHECK_MAX_BLOCKS", "false").lower() == "true")
    bt_logging_info = os.getenv("BT_LOGGING_INFO", "INFO")
    
    if "://" in redis_host:
        pool = ConnectionPool.from_url(
            redis_host,
            max_connections=10,
            socket_keepalive=True,
            health_check_interval=30,
            retry=Retry(ExponentialBackoff(), 3)
        )
        redis_db_instance = Redis(connection_pool=pool)
    else:
        pool = ConnectionPool(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            db=redis_db,
            max_connections=10,
            socket_keepalive=True,
            health_check_interval=30,
            retry=Retry(ExponentialBackoff(), 3)
        )
        redis_db_instance = Redis(connection_pool=pool)
    
    return ValidatorConfig(
        substrate=substrate,
        keypair=keypair,
        subtensor_network=subtensor_network,
        subtensor_address=subtensor_address,
        netuid=netuid,
        replace_with_docker_localhost=replace_with_docker_localhost,
        replace_with_localhost=localhost,
        refresh_nodes=refresh_nodes,
        capacity_to_score_multiplier=capacity_to_score_multiplier,
        httpx_client=httpx_client,
        gpu_server_address=gpu_server_address,
        debug=dev_env,
        scoring_period_time_multiplier=scoring_period_time_multiplier,
        set_metagraph_weights_with_high_updated_to_not_dereg=set_metagraph_weights_with_high_updated_to_not_dereg,
        redis_host=redis_host,
        redis_port=redis_port,
        redis_db=redis_db,
        redis_password=redis_password,
        redis_db_instance=redis_db_instance,
        testnet=subtensor_network.lower() == "test",
        allocation_strategy=allocation_strategy,
        log_path=log_path,
        check_validator_stake=check_validator_stake,
        use_database=use_database,
        validator_token=validator_token,
        validator_config_url=validator_config_url,
        config_server_url=config_server_url,
        public_key_path=public_key_path,
        check_max_blocks=check_max_blocks,
        bt_logging_info=bt_logging_info
    )


def create_test_config() -> ValidatorConfig:

    keypair = Keypair.create_from_uri("//Alice")
    
    httpx_client = httpx.AsyncClient(limits=httpx.Limits(max_connections=10, max_keepalive_connections=5))
    
    return ValidatorConfig(
        substrate=None,
        keypair=keypair,
        subtensor_network="test",
        subtensor_address=None,
        netuid=TESTNET_NETUID,
        replace_with_localhost=True,
        replace_with_docker_localhost=False,
        refresh_nodes=False,
        capacity_to_score_multiplier=0.1,
        scoring_period_time_multiplier=1.0,
        set_metagraph_weights_with_high_updated_to_not_dereg=False,
        httpx_client=httpx_client,
        gpu_server_address=None,
        debug=True,
        redis_host="localhost",
        redis_port=6379,
        redis_db=1,
        redis_password=None,
        testnet=True,
        allocation_strategy="stake",
        log_path="logs",
        check_validator_stake=False,
        use_database=False,
        validator_token="test_token",
        validator_config_url="http://config.asiatensor.xyz/api/validator/config?ver=1.0.1",
        config_server_url="http://config.asiatensor.xyz",
        public_key_path="keys/cognify_pub.pem",
        check_max_blocks=False,
        bt_logging_info="INFO"
    )


def validate_config(config: ValidatorConfig) -> bool:
    try:
        if not config.subtensor_network:
            logger.error("SUBTENSOR_NETWORK is required")
            return False
        
        if not config.keypair:
            logger.error("Keypair is required")
            return False
        
        if config.netuid <= 0:
            logger.error("NETUID must be positive")
            return False
        
        if config.capacity_to_score_multiplier <= 0:
            logger.error("CAPACITY_TO_SCORE_MULTIPLIER must be positive")
            return False
        
        if config.scoring_period_time_multiplier <= 0:
            logger.error("SCORING_PERIOD_TIME_MULTIPLIER must be positive")
            return False
        
        if not config.mysql_config.host:
            logger.error("MySQL host is required")
            return False
        
        if not config.mysql_config.database:
            logger.error("MySQL database is required")
            return False
        
        if not config.redis_host:
            logger.error("Redis host is required")
            return False
        
        logger.info("Configuration validation passed")
        return True
        
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        return False


def print_config_summary(config: ValidatorConfig):
    logger.info(f"Subtensor Network: {config.subtensor_network}")
    logger.info(f"NetUID: {config.netuid}")
    logger.info(f"Validator Hotkey: {config.keypair.ss58_address}")
    logger.info(f"Refresh Nodes: {config.refresh_nodes}")
    logger.info(f"Capacity to Score Multiplier: {config.capacity_to_score_multiplier}")
    logger.info(f"Scoring Period Time Multiplier: {config.scoring_period_time_multiplier}")
    logger.info(f"Redis Host: {config.redis_host}:{config.redis_port}")
    logger.info(f"Debug Mode: {config.debug}")
    logger.info(f"Testnet: {config.testnet}")
    logger.info(f"Allocation Strategy: {config.allocation_strategy}")
    logger.info(f"Log Path: {config.log_path}")
    logger.info(f"Check Validator Stake: {config.check_validator_stake}")
    logger.info(f"Use Database: {config.use_database}")
    logger.info(f"Validator Token: {'***' if config.validator_token else 'None'}")
    logger.info(f"Validator Config URL: {config.validator_config_url}")
    logger.info(f"Config Server URL: {config.config_server_url}")
    logger.info(f"Public Key Path: {config.public_key_path}")
    logger.info(f"Check Max Blocks: {config.check_max_blocks}")
    logger.info(f"BT Logging Info: {config.bt_logging_info}")
    logger.info("=============================================") 