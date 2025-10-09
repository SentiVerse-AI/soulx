from enum import Enum
import time
from pydantic import BaseModel, Field, ConfigDict
from substrateinterface import Keypair
from substrateinterface import SubstrateInterface
import httpx
from dataclasses import dataclass


class TaskType(Enum):
    IMAGE = "IMAGE"
    TEXT = "TEXT"


class ServerType(Enum):
    LLM = "llm_server"
    IMAGE = "image_server"


class Endpoints(Enum):
    text_to_image = "/text-to-image"
    image_to_image = "/image-to-image"
    avatar = "/avatar"
    upscale = "/upscale"
    clip_embeddings = "/clip-embeddings"
    chat_completions = "/chat/completions"
    completions = "/completions"


class TaskScoringConfig(BaseModel):
    task: str
    mean: float
    variance: float
    overhead: float
    task_type: TaskType


class OrchestratorServerConfig(BaseModel):
    server_needed: ServerType = Field(examples=[ServerType.LLM, ServerType.IMAGE])
    load_model_config: dict | None = Field(examples=[None])
    checking_function: str = Field(examples=["check_text_result", "check_image_result"])
    task: str = Field(examples=["chat_llama_3_2_3b"])
    endpoint: str = Field(examples=["/generate_text"])

    model_config = ConfigDict(use_enum_values=True)


class SyntheticGenerationConfig(BaseModel):
    func: str
    kwargs: dict


class FullTaskConfig(BaseModel):
    task: str
    task_type: TaskType
    max_capacity: float
    orchestrator_server_config: OrchestratorServerConfig
    synthetic_generation_config: SyntheticGenerationConfig
    endpoint: str  # endpoint for the miner server
    volume_to_requests_conversion: float
    is_stream: bool
    weight: float
    timeout: float
    enabled: bool = True
    task_model_info: dict | None = None
    architecture: dict = {}
    pricing: dict | None = None
    display_name: str | None = None
    description: str | None = None
    created: int = Field(default_factory=lambda: int(time.time()))
    is_reasoning: bool | None = None
    type: str | None = None

    model_config = ConfigDict(protected_namespaces=())

    def get_public_config(self) -> dict | None:
        if not self.enabled:
            return None
        if self.task_model_info is not None:
            model_config = self.task_model_info
        else:
            assert self.orchestrator_server_config.load_model_config, "Model info is None but load_model_config is not set"
            model_config = self.orchestrator_server_config.load_model_config
        if "gpu_memory_utilization" in model_config:
            del model_config["gpu_memory_utilization"]
        return {
            "task": self.task,
            "task_type": self.task_type.value,
            "max_capacity": self.max_capacity,
            "model_config": model_config,
            "endpoint": self.endpoint,
            "weight": self.weight,
            "timeout": self.timeout,
            "display_name": self.display_name if self.display_name else self.task.strip("chat-"),
            "enabled": self.enabled,
            "is_reasoning": self.is_reasoning
        }


@dataclass
class AuditConfig:
    substrate: SubstrateInterface
    keypair: Keypair | None
    netuid: int
    httpx_client: httpx.AsyncClient 