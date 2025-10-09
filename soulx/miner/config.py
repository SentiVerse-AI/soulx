import os
from pydantic import BaseModel, ConfigDict
from typing import Optional


class MultimodalConfig(BaseModel):

    server_host: str = os.getenv("MULTIMODAL_SERVER_HOST", "127.0.0.1")
    server_port: int = int(os.getenv("MULTIMODAL_SERVER_PORT", "6919"))
    
    multimodal_model_name: Optional[str] = os.getenv("MULTIMODAL_MODEL_NAME")
    multimodal_model_path: Optional[str] = os.getenv("MULTIMODAL_MODEL_PATH")
    
    gpu_id: Optional[int] = None
    if os.getenv("MULTIMODAL_GPU_ID"):
        gpu_id = int(os.getenv("MULTIMODAL_GPU_ID"))
    
    max_batch_size: int = int(os.getenv("MULTIMODAL_MAX_BATCH_SIZE", "1"))
    max_concurrent_requests: int = int(os.getenv("MULTIMODAL_MAX_CONCURRENT_REQUESTS", "10"))
    
    request_timeout: float = float(os.getenv("MULTIMODAL_REQUEST_TIMEOUT", "60.0"))
    
    log_level: str = os.getenv("MULTIMODAL_LOG_LEVEL", "INFO")
    
    api_key: Optional[str] = os.getenv("MULTIMODAL_API_KEY")
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        protected_namespaces=()
    )


def get_multimodal_config() -> MultimodalConfig:
    return MultimodalConfig()