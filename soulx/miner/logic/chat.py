import json
import asyncio
from typing import AsyncGenerator, Optional
import httpx
from soulx.core.models import payload_models
from soulx.miner.config import MultimodalConfig
from fiber.logging_utils import get_logger

logger = get_logger(__name__)


async def chat_stream(
    httpx_client: httpx.AsyncClient,
    payload: payload_models.ChatPayload,
    multimodal_config: MultimodalConfig,
) -> AsyncGenerator[Optional[str], None]:

    try:
        url = f"http://{multimodal_config.server_host}:{multimodal_config.server_port}/chat/completions"
        
        headers = {
            "Content-Type": "application/json",
        }
        if multimodal_config.api_key:
            headers["Authorization"] = f"Bearer {multimodal_config.api_key}"
        
        request_body = {
            "model": payload.model,
            "messages": payload.messages,
            "stream": payload.stream,
            "temperature": payload.temperature,
            "max_tokens": payload.max_tokens,
        }
        
        async with httpx_client.stream(
            "POST",
            url,
            headers=headers,
            json=request_body,
            timeout=multimodal_config.request_timeout,
        ) as response:
            response.raise_for_status()
            
            async for line in response.aiter_lines():
                if line.strip():

                    if "data: " in line:
                        parts = line.split("data: ")
                        for part in parts:
                            if part.strip():
                                yield f"data: {part.strip()}\n"
                    else:
                        yield line
                        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error in chat stream: {e}")
        yield None
    except Exception as e:
        logger.error(f"Unexpected error in chat stream: {e}")
        yield None


async def completion_stream(
    httpx_client: httpx.AsyncClient,
    payload: payload_models.CompletionPayload,
    multimodal_config: MultimodalConfig,
) -> AsyncGenerator[Optional[str], None]:

    try:
        url = f"http://{multimodal_config.server_host}:{multimodal_config.server_port}/v1/completions"
        
        headers = {
            "Content-Type": "application/json",
        }
        if multimodal_config.api_key:
            headers["Authorization"] = f"Bearer {multimodal_config.api_key}"
        
        request_body = {
            "model": payload.model,
            "prompt": payload.prompt,
            "stream": payload.stream,
            "temperature": payload.temperature,
            "max_tokens": payload.max_tokens,
        }
        
        async with httpx_client.stream(
            "POST",
            url,
            headers=headers,
            json=request_body,
            timeout=multimodal_config.request_timeout,
        ) as response:
            response.raise_for_status()
            
            async for line in response.aiter_lines():
                if line.strip():

                    if "data: " in line:
                        parts = line.split("data: ")
                        for part in parts:
                            if part.strip():
                                yield f"data: {part.strip()}\n"
                    else:
                        yield line
                        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error in completion stream: {e}")
        yield None
    except Exception as e:
        logger.error(f"Unexpected error in completion stream: {e}")
        yield None 


async def chat_no_stream(
    httpx_client: httpx.AsyncClient,
    payload: payload_models.ChatPayload,
    multimodal_config: MultimodalConfig,
) -> str:

    try:
        url = f"http://{multimodal_config.server_host}:{multimodal_config.server_port}/chat/completions"
        
        headers = {
            "Content-Type": "application/json",
        }
        if multimodal_config.api_key:
            headers["Authorization"] = f"Bearer {multimodal_config.api_key}"
        
        request_body = {
            "model": payload.model,
            "messages": payload.messages,
            "stream": False,
            "temperature": payload.temperature,
            "max_tokens": payload.max_tokens,
        }
        
        response = await httpx_client.post(
            url,
            headers=headers,
            json=request_body,
            timeout=multimodal_config.request_timeout,
        )
        response.raise_for_status()
        
        data = response.json()
        return  data

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error in chat text: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in chat text: {e}")
        raise 


async def completion_no_stream(
    httpx_client: httpx.AsyncClient,
    payload: payload_models.CompletionPayload,
    multimodal_config: MultimodalConfig,
) -> str:

    try:
        url = f"http://{multimodal_config.server_host}:{multimodal_config.server_port}/completions"
        
        headers = {
            "Content-Type": "application/json",
        }
        if multimodal_config.api_key:
            headers["Authorization"] = f"Bearer {multimodal_config.api_key}"
        
        request_body = {
            "model": payload.model,
            "prompt": payload.prompt,
            "stream": False,
            "temperature": payload.temperature,
            "max_tokens": payload.max_tokens,
        }
        
        response = await httpx_client.post(
            url,
            headers=headers,
            json=request_body,
            timeout=multimodal_config.request_timeout,
        )
        response.raise_for_status()
        
        data = response.json()
        if "choices" in data and len(data["choices"]) > 0:
            choice = data["choices"][0]
            if "text" in choice:
                return choice["text"]
            else:
                raise ValueError("Invalid response format: missing text")
        else:
            raise ValueError("Invalid response format: missing choices")
            
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error in completion text: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in completion text: {e}")
        raise 