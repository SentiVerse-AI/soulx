#!/usr/bin/env python3
"""
 Miner Server Startup Script
"""

import os
import sys
from pathlib import Path
from bittensor import logging
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def load_environment():
    from soulx.core.path_utils import PathUtils
    
    logging.info("Loading Cognify Miner environment configuration...")
    miner_env = PathUtils.get_env_file_path("miner")
    logging.info( f"miner_env path is : {miner_env}")
    if miner_env.exists():
        load_dotenv(miner_env)
        logging.info(f"Loaded environment from: {miner_env}")
    else:
        default_env = project_root / ".env"
        if default_env.exists():
            load_dotenv(default_env)
            logging.info(f"Loaded environment from: {default_env}")
        else:
            logging.warning("No .env file found")

load_environment()

from soulx.miner.server import app
from soulx.miner.env_loader import load_miner_environment, validate_miner_environment
import uvicorn
from fiber.logging_utils import get_logger

def main():
    host = os.getenv("MINER_HOST", "127.0.0.1")
    port = int(os.getenv("MINER_PORT", "8091"))
    reload = os.getenv("MINER_RELOAD", "true").lower() == "true"
    
    logging.info(f"Starting Cognify Miner Server on {host}:{port}")
    logging.info(f"Reload mode: {reload}")
    
    uvicorn.run(
        "soulx.miner.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


if __name__ == "__main__":
    main() 