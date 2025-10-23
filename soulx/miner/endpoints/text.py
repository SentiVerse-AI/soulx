from functools import partial
from fastapi import Depends, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, Response
from fiber.encrypted.miner.security.encryption import decrypt_general_payload
import httpx
from soulx.core.models import payload_models
from fastapi.routing import APIRouter
from fiber.logging_utils import get_logger
from soulx.miner.logic.chat import chat_stream,completion_stream, chat_no_stream, completion_no_stream
from fiber.encrypted.miner.core.configuration import Config
from fiber.encrypted.miner.dependencies import blacklist_low_stake, get_config, verify_request
from soulx.miner.config import MultimodalConfig
from soulx.miner.dependencies import get_multimodal_config
from soulx.core.utils.generic_utils import async_chain

logger = get_logger(__name__)


async def chat_completions(
    decrypted_payload: payload_models.ChatPayload = Depends(partial(decrypt_general_payload, payload_models.ChatPayload)),
    config: Config = Depends(get_config),
    multimodal_config: MultimodalConfig = Depends(get_multimodal_config),
) -> Response:
    try:
        if decrypted_payload.stream:
            generator = chat_stream(config.httpx_client, decrypted_payload, multimodal_config)
            return StreamingResponse(generator, media_type="text/event-stream")
        else:
            try:
                text_response = await chat_no_stream(config.httpx_client, decrypted_payload, multimodal_config)

                return JSONResponse(content=text_response)
            except Exception as e:
                logger.error(f"Error in non-streaming text from the server: {e}")
                raise HTTPException(status_code=500, detail=str(e))
                
    except httpx.HTTPStatusError as e:
        logger.error(f"Error in streaming text from the server: {e}. ")
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def completions(
    decrypted_payload: payload_models.CompletionPayload = Depends(partial(decrypt_general_payload, payload_models.CompletionPayload)),
    config: Config = Depends(get_config),
    multimodal_config: MultimodalConfig = Depends(get_multimodal_config),
) -> Response:
    try:
        if decrypted_payload.stream:
            generator = completion_stream(config.httpx_client, decrypted_payload, multimodal_config)
            return StreamingResponse(generator, media_type="text/event-stream")
        else:
            try:
                text_response = await completion_no_stream(config.httpx_client, decrypted_payload, multimodal_config)
                response_data = {
                    "choices": [
                        {
                            "text": text_response,
                            "index": 0,
                            "finish_reason": "stop"
                        }
                    ],
                    "model": decrypted_payload.model,
                    "object": "text_completion",
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": len(text_response.split()) if text_response else 0,
                        "total_tokens": 0
                    }
                }
                return JSONResponse(content=response_data)
            except Exception as e:
                logger.error(f"Error in non-streaming text from the server: {e}")
                raise HTTPException(status_code=500, detail=str(e))
                
    except httpx.HTTPStatusError as e:
        logger.error(f"Error in streaming text from the server: {e}. ")
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        logger.error(f"Error in streaming text from the server: {e}. ")
        raise HTTPException(status_code=500, detail=f"Error in streaming text from the server: {e}")


def factory_router() -> APIRouter:
    router = APIRouter()
    router.add_api_route(
        "/chat/completions",
        chat_completions,
        tags=["Cognify Subnet"],
        methods=["POST"],
        dependencies=[Depends(blacklist_low_stake), Depends(verify_request)],
    )
    router.add_api_route(
        "/completions",
        completions,
        tags=["Cognify Subnet"],
        methods=["POST"],
        dependencies=[Depends(blacklist_low_stake), Depends(verify_request)],
    )
    return router 