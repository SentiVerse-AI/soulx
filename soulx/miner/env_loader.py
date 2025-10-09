#!/usr/bin/env python3

import os
import sys
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from fiber.logging_utils import get_logger

logger = get_logger(__name__)


def find_env_file(env_filename: str, search_paths: Optional[list] = None) -> Optional[Path]:

    if search_paths is None:
        current_dir = Path.cwd()
        project_root = Path(__file__).parent.parent.parent
        search_paths = [
            current_dir,
            project_root,
            project_root.parent,
            Path.home(),
        ]
    
    for search_path in search_paths:
        env_file = search_path / env_filename
        if env_file.exists():
            logger.info(f"Found environment file: {env_file}")
            return env_file
    
    logger.warning(f"Environment file '{env_filename}' not found in search paths: {search_paths}")
    return None


def load_miner_environment() -> bool:

    env_filename = ".miner.env"
    
    env_file = find_env_file(env_filename)
    
    if env_file:
        load_dotenv(env_file, override=True)
        logger.info(f"Loaded environment from: {env_file}")
        
        print_environment_info()
        return True
    else:
        logger.warning(f"No {env_filename} file found, using system environment variables")
        return False


def print_environment_info():

    logger.info("=== Miner Environment Configuration ===")

    host = os.getenv("MINER_HOST", "127.0.0.1")
    port = os.getenv("MINER_PORT", "8091")
    reload = os.getenv("MINER_RELOAD", "true")
    
    logger.info(f"Server Configuration:")
    logger.info(f"  MINER_HOST: {host}")
    logger.info(f"  MINER_PORT: {port}")
    logger.info(f"  MINER_RELOAD: {reload}")
    
    multimodal_host = os.getenv("MULTIMODAL_SERVER_HOST", "127.0.0.1")
    multimodal_port = os.getenv("MULTIMODAL_SERVER_PORT", "6919")
    multimodal_model = os.getenv("MULTIMODAL_MODEL_NAME", "Not set")
    multimodal_gpu = os.getenv("MULTIMODAL_GPU_ID", "Not set")
    
    logger.info(f"Multimodal Configuration:")
    logger.info(f"  MULTIMODAL_SERVER_HOST: {multimodal_host}")
    logger.info(f"  MULTIMODAL_SERVER_PORT: {multimodal_port}")
    logger.info(f"  MULTIMODAL_MODEL_NAME: {multimodal_model}")
    logger.info(f"  MULTIMODAL_GPU_ID: {multimodal_gpu}")
    
    max_batch = os.getenv("MULTIMODAL_MAX_BATCH_SIZE", "1")
    max_concurrent = os.getenv("MULTIMODAL_MAX_CONCURRENT_REQUESTS", "10")
    timeout = os.getenv("MULTIMODAL_REQUEST_TIMEOUT", "30.0")
    
    logger.info(f"Performance Configuration:")
    logger.info(f"  MULTIMODAL_MAX_BATCH_SIZE: {max_batch}")
    logger.info(f"  MULTIMODAL_MAX_CONCURRENT_REQUESTS: {max_concurrent}")
    logger.info(f"  MULTIMODAL_REQUEST_TIMEOUT: {timeout}")
    
    logger.info("=============================================")


def validate_miner_environment() -> bool:

    required_vars = [
        "MINER_HOST",
        "MINER_PORT",
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        return False
    
    try:
        port = int(os.getenv("MINER_PORT", "8091"))
        if port < 1 or port > 65535:
            logger.error(f"Invalid MINER_PORT: {port}. Must be between 1 and 65535")
            return False
    except ValueError:
        logger.error("MINER_PORT must be a valid integer")
        return False
    
    logger.info("Environment validation passed")
    return True


if __name__ == "__main__":
    load_miner_environment()
    validate_miner_environment() 