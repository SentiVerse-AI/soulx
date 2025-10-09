import json
import base64
from typing import Optional, Dict, Any
import httpx
from pydantic import BaseModel
from soulx.miner.config import MultimodalConfig
from fiber.logging_utils import get_logger

logger = get_logger(__name__)


async def get_image_from_server(
    httpx_client: httpx.AsyncClient,
    body: BaseModel,
    post_endpoint: str,
    multimodal_config: MultimodalConfig,
    timeout: float = 60.0,
) -> Optional[Dict[str, Any]]:

    try:
        url = f"http://{multimodal_config.server_host}:{multimodal_config.server_port}/{post_endpoint}"
        
        headers = {
            "Content-Type": "application/json",
        }
        if multimodal_config.api_key:
            headers["Authorization"] = f"Bearer {multimodal_config.api_key}"
        
        request_body = body.model_dump()
        
        logger.info(f"Sending image request to multimodal server: {url}")

        response = await httpx_client.post(
            url,
            headers=headers,
            json=request_body,
            timeout=timeout,
        )
        response.raise_for_status()
        
        response_data = response.json()
        # logger.debug(f"Image response: {response_data}")
        
        if "image_b64" in response_data:
            try:
                base64.b64decode(response_data["image_b64"])
            except Exception as e:
                logger.error(f"Invalid base64 image data: {e}")
                return None
                
        return response_data
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error in image generation: {e}")
        if hasattr(e, "response"):
            logger.error(f"Response content: {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in image generation: {e}")
        return None


async def text_to_image(
    httpx_client: httpx.AsyncClient,
    prompt: str,
    model: str,
    multimodal_config: MultimodalConfig,
    **kwargs
) -> Optional[Dict[str, Any]]:

    from soulx.core.models.payload_models import TextToImagePayload
    
    payload = TextToImagePayload(
        prompt=prompt,
        model=model,
        **kwargs
    )
    
    return await get_image_from_server(
        httpx_client=httpx_client,
        body=payload,
        post_endpoint="text-to-image",
        multimodal_config=multimodal_config,
    )


async def image_to_image(
    httpx_client: httpx.AsyncClient,
    prompt: str,
    image_b64: str,
    model: str,
    multimodal_config: MultimodalConfig,
    **kwargs
) -> Optional[Dict[str, Any]]:

    from soulx.core.models.payload_models import ImageToImagePayload
    
    payload = ImageToImagePayload(
        prompt=prompt,
        image_b64=image_b64,
        model=model,
        **kwargs
    )
    
    return await get_image_from_server(
        httpx_client=httpx_client,
        body=payload,
        post_endpoint="image-to-image",
        multimodal_config=multimodal_config,
    )


async def avatar_generation(
    httpx_client: httpx.AsyncClient,
    prompt: str,
    model: str,
    multimodal_config: MultimodalConfig,
    **kwargs
) -> Optional[Dict[str, Any]]:

    from soulx.core.models.payload_models import AvatarPayload
    
    payload = AvatarPayload(
        prompt=prompt,
        model=model,
        **kwargs
    )
    
    return await get_image_from_server(
        httpx_client=httpx_client,
        body=payload,
        post_endpoint="avatar",
        multimodal_config=multimodal_config,
    ) 