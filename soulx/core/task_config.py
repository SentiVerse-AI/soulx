# -*- coding: utf-8 -*-

from typing import Optional, Dict, Any
from fiber.logging_utils import get_logger
import os

logger = get_logger(__name__)

# 任务类型常量
CHAT_LLAMA_3_2_3B = "chat-llama-3-2-3b"
CHAT_QWEN3_DEEPSEEK_R1_8B = "chat-deepseek-r1-0528-qwen3-8b"
CHAT_QWEN_QWQ_32B = "chat-qwen-qwq-32b"
CHAT_MISTRAL_NEMO_12B = "chat-mistral-nemo-12b"
CHAT_MISTRAL_NEMO_12B_COMP = "chat-mistral-nemo-12b-comp"
CHAT_LLAMA_3_2_3B_COMP = "chat-llama-3-2-3b-comp"
CHAT_QWEN3_DEEPSEEK_R1_8B_COMP = "chat-deepseek-r1-0528-qwen3-8b-comp"
CHAT_QWEN_QWQ_32B_COMP = "chat-qwen-qwq-32b-comp"
CHAT_INTERNVL3_14B = "chat-internvl3-14b"

PROTEUS_TEXT_TO_IMAGE = "proteus-text-to-image"
PROTEUS_IMAGE_TO_IMAGE = "proteus-image-to-image"
FLUX_SCHNELL_TEXT_TO_IMAGE = "flux-schnell-text-to-image"
FLUX_SCHNELL_IMAGE_TO_IMAGE = "flux-schnell-image-to-image"
AVATAR = "avatar"
DREAMSHAPER_TEXT_TO_IMAGE = "dreamshaper-text-to-image"
DREAMSHAPER_IMAGE_TO_IMAGE = "dreamshaper-image-to-image"

_task_configs_cache: Optional[Dict[str, Any]] = None
_last_cache_update: float = 0
_cache_ttl: float = 300

def _get_task_config_client():
    try:
        from soulx.validator.task_config_client import TaskConfigClient
        central_server_url = os.getenv('CONFIG_SERVER_URL', 'http://config.asiatensor.xyz')
        central_server_token = os.getenv('VALIDATOR_TOKEN')
        validator_hotkey = os.getenv('VALIDATOR_HOTKEY', 'test_validator')
        return TaskConfigClient(central_server_url, validator_hotkey, central_server_token)
    except ImportError:
        logger.error("TaskConfigClient not available")
        return None

def get_enabled_task_config(task: str) -> Optional[Dict[str, Any]]:
    try:
        all_configs = get_task_configs()
        if not all_configs:
            logger.warning(f"No task configs available, using fallback for task: {task}")
            return _get_fallback_config(task)
        
        task_config = all_configs.get(task)
        if task_config and task_config.get('enabled', False):
            logger.debug(f"Found enabled task config for {task}")
            return task_config
        else:
            logger.warning(f"Task {task} not found or not enabled")
            return None
            
    except Exception as e:
        logger.error(f"Error getting task config for {task}: {e}")
        return _get_fallback_config(task)

def get_task_configs() -> Dict[str, Dict[str, Any]]:
    global _task_configs_cache, _last_cache_update
    
    import time
    current_time = time.time()
    
    if (_task_configs_cache is not None and
        current_time - _last_cache_update < _cache_ttl):
        logger.debug("Using cached task configs")
        return _task_configs_cache
    
    try:
        client = _get_task_config_client()
        if client is None:
            logger.error("TaskConfigClient not available, using fallback configs")
            return _get_fallback_configs()
        
        configs = _get_task_configs_sync(client)
        if configs:
            _task_configs_cache = configs
            _last_cache_update = current_time
            logger.info(f"Successfully loaded {len(configs)} task configs from central server")
            return configs
        else:
            logger.warning("No task configs received from central server, using fallback")
            return _get_fallback_configs()
            
    except Exception as e:
        logger.error(f"Error loading task configs from central server: {e}")
        return _get_fallback_configs()

def _get_task_configs_sync(client) -> Dict[str, Dict[str, Any]]:
    try:
        import requests
        
        url = f"{client.base_url}/task_configs"
        headers = client.headers
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                return data.get('task_configs', {})
            else:
                logger.error(f"Failed to get task configs: {data.get('error')}")
                return {}
        else:
            logger.error(f"HTTP {response.status_code}: Failed to get task configs")
            return {}
            
    except Exception as e:
        logger.error(f"Error getting task configs synchronously: {e}")
        return {}

def get_public_task_configs() -> list[dict]:
    configs = get_task_configs()
    return [
        {
            "task": task,
            "display_name": config.get("display_name", task),
            "task_type": config.get("task_type", "text"),
            "max_capacity": config.get("max_capacity", 1000),
            "endpoint": config.get("endpoint", "/chat/completions"),
            "is_reasoning": config.get("is_reasoning", False),
            "is_stream": config.get("is_stream", True),
            "weight": config.get("weight", 0.1),
            "timeout": config.get("timeout", 30),
            "enabled": config.get("enabled", True)
        }
        for task, config in configs.items()
        if config and config.get("enabled", False)
    ]

def clear_cache():
    global _task_configs_cache, _last_cache_update
    _task_configs_cache = None
    _last_cache_update = 0
    logger.info("Task config cache cleared")

def _get_fallback_config(task: str) -> Optional[Dict[str, Any]]:
    fallback_configs = _get_fallback_configs()
    return fallback_configs.get(task)

def _get_fallback_configs() -> Dict[str, Dict[str, Any]]:
    return {
        CHAT_LLAMA_3_2_3B: {
            "task": CHAT_LLAMA_3_2_3B,
            "display_name": "Llama 3.2 3B",
            "task_type": "text",
            "max_capacity": 6000,
            "endpoint": "/chat/completions",
            "is_reasoning": False,
            "is_stream": True,
            "weight": 0.04,
            "timeout": 2,
            "enabled": True,
            "volume_to_requests_conversion": 250
        },
        CHAT_LLAMA_3_2_3B_COMP: {
            "task": CHAT_LLAMA_3_2_3B_COMP,
            "display_name": "Llama 3.2 3B Completions",
            "task_type": "text",
            "max_capacity": 6000,
            "endpoint": "/completions",
            "is_reasoning": False,
            "is_stream": True,
            "weight": 0.04,
            "timeout": 2,
            "enabled": True,
            "volume_to_requests_conversion": 250
        },
        PROTEUS_TEXT_TO_IMAGE: {
            "task": PROTEUS_TEXT_TO_IMAGE,
            "display_name": "Proteus Text to Image",
            "task_type": "image",
            "max_capacity": 1000,
            "endpoint": "/text-to-image",
            "is_reasoning": False,
            "is_stream": False,
            "weight": 0.1,
            "timeout": 30,
            "enabled": True,
            "volume_to_requests_conversion": 100
        },
        PROTEUS_IMAGE_TO_IMAGE: {
            "task": PROTEUS_IMAGE_TO_IMAGE,
            "display_name": "Proteus Image to Image",
            "task_type": "image",
            "max_capacity": 1000,
            "endpoint": "/image-to-image",
            "is_reasoning": False,
            "is_stream": False,
            "weight": 0.1,
            "timeout": 30,
            "enabled": True,
            "volume_to_requests_conversion": 100
        },
        AVATAR: {
            "task": AVATAR,
            "display_name": "Avatar",
            "task_type": "image",
            "max_capacity": 500,
            "endpoint": "/avatar",
            "is_reasoning": False,
            "is_stream": False,
            "weight": 0.05,
            "timeout": 60,
            "enabled": True,
            "volume_to_requests_conversion": 50
        }
    } 