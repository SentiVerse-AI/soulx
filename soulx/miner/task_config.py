from functools import lru_cache
from typing import Optional
from soulx.core.models import config_models as cmodels
from soulx.miner import constants as cst
from fiber.logging_utils import get_logger
from soulx.validator.task_config_client import TaskConfigClient

logger = get_logger(__name__)

TASK_CONFIGS = {
    "chat-llama-3-2-3b": {
        "task": "chat-llama-3-2-3b",
        "task_type": "text",
        "max_capacity": 6000,
        "model_config": {
            "model": "unsloth/Llama-3.2-3B-Instruct",
            "half_precision": True,
            "tokenizer": "tau-vision/llama-tokenizer-fix",
            "max_model_len": 20000,
            "gpu_memory_utilization": 0.5,
            "eos_token_id": 128009
        },
        "endpoint": "/chat/completions",
        "weight": 0.04,
        "enabled": True
    },
    "chat-deepseek-r1-0528-qwen3-8b": {
        "task": "chat-deepseek-r1-0528-qwen3-8b",
        "task_type": "text",
        "max_capacity": 6000,
        "model_config": {
            "model": "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B",
            "half_precision": True,
            "tokenizer": "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B",
            "max_model_len": 32000,
            "tensor_parallel_size": 1,
            "gpu_memory_utilization": 0.57,
            "eos_token_id": 151645
        },
        "endpoint": "/chat/completions",
        "weight": 0.105,
        "enabled": True
    },
    "proteus-text-to-image": {
        "task": "proteus-text-to-image",
        "task_type": "image",
        "max_capacity": 80,
        "model_config": {},
        "endpoint": "/text-to-image",
        "weight": 0.06,
        "enabled": True
    },
    "proteus-image-to-image": {
        "task": "proteus-image-to-image",
        "task_type": "image",
        "max_capacity": 80,
        "model_config": {},
        "endpoint": "/image-to-image",
        "weight": 0.03,
        "enabled": True
    },
    "avatar": {
        "task": "avatar",
        "task_type": "image",
        "max_capacity": 80,
        "model_config": {},
        "endpoint": "/avatar",
        "weight": 0.06,
        "enabled": True
    }
}


@lru_cache(maxsize=1)
def get_task_configs() -> dict:
    return TASK_CONFIGS


def get_enabled_task_config(task: str) -> Optional[dict]:
    task_configs = get_task_configs()
    config = task_configs.get(task)
    if config is None or not config.get("enabled", False):
        return None
    return config


def get_public_task_configs() -> list[dict]:
    task_configs = get_task_configs()
    return [config for config in task_configs.values() if config.get("enabled", False)] 