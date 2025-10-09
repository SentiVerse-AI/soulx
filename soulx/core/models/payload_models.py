# -*- coding: utf-8 -*-

from typing import Any, Optional, List, Union
from typing_extensions import Literal, Required, TypedDict
from pydantic import BaseModel, Field
from soulx.core.models import utility_models

ContentArrayOfContentPart = List[Any]

class ChatCompletionContentPartTextParam(TypedDict, total=False):
    text: Required[str]
    type: Required[Literal["text"]]

class ChatCompletionSystemMessageParam(TypedDict, total=False):
    content: Required[Union[str, List[ChatCompletionContentPartTextParam]]]
    role: Required[Literal["system"]]
    name: str

class ImageURL(TypedDict, total=False):
    url: str
    detail: Literal["auto", "low", "high"]

class ChatCompletionContentPartImageParam(TypedDict, total=False):
    image_url: Required[ImageURL]
    type: Required[Literal["image_url"]]

ChatCompletionContentPartParam = Union[
    ChatCompletionContentPartTextParam,
    ChatCompletionContentPartImageParam
]

class ChatCompletionUserMessageParam(TypedDict, total=False):
    content: Required[Union[str, List[ChatCompletionContentPartParam]]]
    role: Required[Literal["user"]]
    name: str

class ChatCompletionAssistantMessageParam(TypedDict, total=False):
    role: Required[Literal["assistant"]]
    content: Union[str, List[ContentArrayOfContentPart], None]
    name: str

ChatCompletionMessageParam = Union[
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
    ChatCompletionAssistantMessageParam
]

class ChatPayload(BaseModel):
    messages: List[ChatCompletionMessageParam]
    model: str = Field(..., examples=["unsloth/Llama-3.2-3B-Instruct"], title="Model")
    logprobs: Optional[bool] = True
    max_tokens: Optional[int] = Field(default=None)
    seed: Optional[int] = Field(None)
    stream: Optional[bool] = True
    temperature: Optional[float] = None
    top_p: float = 1.0
    top_k: int = 5

    class Config:
        use_enum_values = True

class CompletionPayload(BaseModel):
    prompt: str = Field(...)
    temperature: Optional[float] = None
    seed: Optional[int] = Field(None)
    model: str = Field(default=..., examples=["chat-llama-3-2-3b"], title="Model")
    stream: Optional[bool] = True
    logprobs: Optional[bool] = True
    top_p: float = 1.0
    top_k: int = 5
    max_tokens: int = Field(500, title="Max Tokens", description="Max tokens for text generation.")

    class Config:
        use_enum_values = True

class ImageResponse(BaseModel):
    image_b64: str | None
    is_nsfw: bool | None
    clip_embeddings: list[float] | None
    image_hashes: utility_models.ImageHashes | None

class ChatCompletionChoice(BaseModel):
    index: int
    message: dict
    finish_reason: str

class ChatCompletionUsage(BaseModel):
    prompt_tokens: int
    total_tokens: int
    completion_tokens: int
    prompt_tokens_details: dict | None = None

class TextResponse(BaseModel):
    id: str | None = None
    object: str = "chat.completion"
    created: int | None = None
    model: str | None = None
    choices: list[ChatCompletionChoice] | None = None
    usage: ChatCompletionUsage | None = None

class TextToImagePayload(BaseModel):
    prompt: str = Field(...)
    negative_prompt: str = Field("", title="Negative Prompt", description="Negative Prompt for text generation.")
    seed: int = Field(0, title="Seed", description="Seed for text generation.")
    steps: int = Field(10, title="Steps", description="Steps for text generation.")
    cfg_scale: float = Field(3.0, title="CFG Scale", description="CFG Scale for text generation.")
    width: int = Field(1024, title="Width", description="Width for text generation.")
    height: int = Field(1024, title="Height", description="Height for text generation.")
    model: str = Field(default="proteus-text-to-image", title="Model")

class ImageToImagePayload(BaseModel):
    prompt: str = Field(...)
    negative_prompt: str = Field("", title="Negative Prompt", description="Negative Prompt for text generation.")
    seed: int = Field(0, title="Seed", description="Seed for text generation.")
    steps: int = Field(10, title="Steps", description="Steps for text generation.")
    cfg_scale: float = Field(3.0, title="CFG Scale", description="CFG Scale for text generation.")
    width: int = Field(1024, title="Width", description="Width for text generation.")
    height: int = Field(1024, title="Height", description="Height for text generation.")
    image_strength: float = Field(0.5, title="Image Strength", description="Image Strength for text generation.")
    model: str = Field(default="proteus-text-to-image", title="Model")
    init_image: str = Field(...)

class AvatarPayload(BaseModel):
    prompt: str = Field(...)
    negative_prompt: str | None = Field(None, title="Negative Prompt", description="Negative Prompt for text generation.")
    seed: int = Field(0, title="Seed", description="Seed for text generation.")
    steps: int = Field(10, title="Steps", description="Steps for text generation.")
    width: int = Field(1024, title="Width", description="Width for text generation.")
    height: int = Field(1024, title="Height", description="Height for text generation.")
    ipadapter_strength: float = Field(0.5, title="Image Adapter Strength", description="Image Adapter Strength for text generation.")
    control_strength: float = Field(0.5, title="Control Strength", description="Control Strength for text generation.")
    init_image: str = Field(..., title="Init Image")
    model: str = Field(default="avatar", title="Model")

class CapacityPayload(BaseModel):
    task_configs: List[dict[str, Any]]