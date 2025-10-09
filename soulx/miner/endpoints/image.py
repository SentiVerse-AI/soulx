from functools import partial
from fastapi import Depends, HTTPException
from fiber.encrypted.miner.security.encryption import decrypt_general_payload
from pydantic import BaseModel
from soulx.core.models import payload_models
from fastapi.routing import APIRouter
from soulx.miner import constants as mcst
from soulx.miner import task_config as tcfg
from soulx.miner.config import MultimodalConfig
from soulx.miner.dependencies import get_multimodal_config
from soulx.miner.logic.image import get_image_from_server
from fiber.encrypted.miner.core.configuration import Config
from fiber.encrypted.miner.dependencies import blacklist_low_stake, get_config as get_fiber_config, verify_request
from fiber.logging_utils import get_logger

logger = get_logger(__name__)


async def _process_image_request(
    decrypted_payload: BaseModel,
    fiber_config: Config,
    post_endpoint: str,
    multimodal_config: MultimodalConfig,
) -> payload_models.ImageResponse:

    assert hasattr(decrypted_payload, "model"), "The image request payload must have a 'model' attribute"


    image_response = await get_image_from_server(
        httpx_client=fiber_config.httpx_client,
        body=decrypted_payload,
        post_endpoint=post_endpoint,
        multimodal_config=multimodal_config,
        timeout=180,
    )
    if image_response is None or (image_response.get("image_b64") is None and image_response.get("is_nsfw") is None):
        # logger.debug(f"Image response: {image_response}")
        raise HTTPException(status_code=500, detail="Image generation failed")
    return payload_models.ImageResponse(**image_response)


async def text_to_image(
    decrypted_payload: payload_models.TextToImagePayload = Depends(
        partial(decrypt_general_payload, payload_models.TextToImagePayload)
    ),
    fiber_config: Config = Depends(get_fiber_config),
    multimodal_config: MultimodalConfig = Depends(get_multimodal_config),
) -> payload_models.ImageResponse:
    return await _process_image_request(decrypted_payload, fiber_config, mcst.TEXT_TO_IMAGE_SERVER_ENDPOINT, multimodal_config)


async def image_to_image(
    decrypted_payload: payload_models.ImageToImagePayload = Depends(
        partial(decrypt_general_payload, payload_models.ImageToImagePayload)
    ),
    fiber_config: Config = Depends(get_fiber_config),
    multimodal_config: MultimodalConfig = Depends(get_multimodal_config),
) -> payload_models.ImageResponse:
    return await _process_image_request(decrypted_payload, fiber_config, mcst.IMAGE_TO_IMAGE_SERVER_ENDPOINT, multimodal_config)

def factory_router() -> APIRouter:
    router = APIRouter()
    router.add_api_route(
        "/text-to-image",
        text_to_image,
        tags=["Cognify Subnet"],
        methods=["POST"],
        dependencies=[Depends(blacklist_low_stake), Depends(verify_request)],
    )
    router.add_api_route(
        "/image-to-image",
        image_to_image,
        tags=["Cognify Subnet"],
        methods=["POST"],
        dependencies=[Depends(blacklist_low_stake), Depends(verify_request)],
    )
    return router