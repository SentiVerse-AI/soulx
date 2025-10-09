from typing import Dict, List, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field
import constants as cst


class ModelEnum(str, Enum):
    DREAMSHAPER = "dreamshaper"
    PROTEUS = "proteus"
    PLAYGROUND = "playground"
    FLUX_SCHNELL = "flux"


class SamplerEnum(str, Enum):
    EULER = "euler"
    EULER_CFG_PP = "euler_cfg_pp"
    EULER_ANCESTRAL = "euler_ancestral"
    EULER_ANCESTRAL_CFG_PP = "euler_ancestral_cfg_pp"
    HEUN = "heun"
    HEUNPP2 = "heunp2"
    DPM_2 = "dpm_2"
    DPM_2_ANCESTRAL = "dpm_2_ancestral"
    LMS = "lms"
    DPM_FAST = "dpm_fast"
    DPM_ADAPTIVE = "dpm_adaptive"
    DPMPP_2S_ANCESTRAL = "dpmpp_2s_ancestral"
    DPMPP_SDE_GPU = "dpmpp_sde_gpu"
    DPMPP_2M_SDE_GPU = "dpmpp_2m_sde_gpu"
    DPMPP_3M_SDE_GPU = "dpmpp_3m_sde_gpu"
    DDPM = "ddpm"
    LCM = "lcm"
    IPNDM = "ipndm"
    PNDM = "pndm"
    UNI_PC = "uni_pc"
    UNI_PC_BH2 = "uni_pc_bh2"


class SchedulerEnum(str, Enum):
    NORMAL = "normal"
    KARRAS = "karras"
    EXPONENTIAL = "exponential"
    SGM_UNIFORM = "sgm_uniform"
    SIMPLE = "simple"
    DDIM_UNIFORM = "ddim_uniform"
    BETA = "beta"


class ModelStatus(str, Enum):
    ALREADY_EXISTS = "Model already exists"
    SUCCESS = "Model downloaded successfully"


class LoadModelRequest(BaseModel):
    model_repo: str = Field(..., example="Lykon/dreamshaper-xl-lightning")
    safetensors_filename: str = Field(..., example="DreamShaperXL_Lightning-SFW.safetensors")


class LoadModelResponse(BaseModel):
    status: ModelStatus

class TextGenerationBase(BaseModel):
    prompt: str = Field(..., description="The text prompt to generate from")
    model: str = Field(default=None, description="The model to use for text generation")
    max_tokens: int = Field(default=1000, description="Maximum number of tokens to generate", gt=0, le=4096)
    temperature: float = Field(default=0.7, description="Sampling temperature", ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, description="Top-p sampling parameter", ge=0.0, le=1.0)
    stop: List[str] = Field(default=None, description="Stop sequences")
    stream: bool = Field(default=False, description="Whether to stream the response")


class TextCompletionBase(BaseModel):
    prompt: str = Field(..., description="The text prompt to complete")
    model: str = Field(default=None, description="The model to use for text completion")
    max_tokens: int = Field(default=1000, description="Maximum number of tokens to generate", gt=0, le=4096)
    temperature: float = Field(default=0.7, description="Sampling temperature", ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, description="Top-p sampling parameter", ge=0.0, le=1.0)
    stop: List[str] = Field(default=None, description="Stop sequences")


class TextGenerationResponse(BaseModel):
    text: str = Field(..., description="Generated text")
    model: str = Field(..., description="Model used for generation")
    usage: Dict[str, Any] = Field(default_factory=dict, description="Token usage information")
    finish_reason: str = Field(..., description="Reason for finishing generation")


class TextCompletionResponse(BaseModel):
    text: str = Field(..., description="Completed text")
    model: str = Field(..., description="Model used for completion")
    usage: Dict[str, Any] = Field(default_factory=dict, description="Token usage information")
    finish_reason: str = Field(..., description="Reason for finishing completion")


class BatchTextGenerationBase(BaseModel):
    prompts: List[str] = Field(..., description="List of text prompts to generate from")
    model: str = Field(default=None, description="The model to use for text generation")
    max_tokens: int = Field(default=1000, description="Maximum number of tokens to generate", gt=0, le=4096)
    temperature: float = Field(default=0.7, description="Sampling temperature", ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, description="Top-p sampling parameter", ge=0.0, le=1.0)


class BatchTextGenerationResponse(BaseModel):
    results: List[TextGenerationResponse] = Field(..., description="List of generation results")


class ModelInfo(BaseModel):
    id: str = Field(..., description="Model ID")
    name: str = Field(..., description="Model name")
    type: str = Field(..., description="Model type")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Model parameters")


class ModelsResponse(BaseModel):
    models: List[ModelInfo] = Field(..., description="List of available models")
