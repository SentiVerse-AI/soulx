from fastapi import FastAPI, HTTPException
import base_model
import inference
import traceback
from typing import Callable
from functools import wraps
from model_manager import model_manager
from starlette.responses import PlainTextResponse
from loguru import logger
import base64
import io
from PIL import Image
import asyncio
import threading
import time
import json
import os
from dotenv import load_dotenv
from utils import safety_checker as sc

safety_checker = sc.Safety_Checker()

from service_manager import create_service_manager, ServiceManager

load_dotenv('.env.multimodal_server')

service_manager: ServiceManager = None
service_thread: threading.Thread = None


def start_backend_services():

    global service_manager, service_thread
    
    def run_services():
        global service_manager
        try:
            config = {
                'work_dir': os.getenv('WORK_DIR', './workspace'),
                'vllm': {
                    'host': os.getenv('VLLM_HOST', '127.0.0.1'),
                    'port': int(os.getenv('VLLM_PORT', '8198')),
                    'model': os.getenv('VLLM_MODEL', 'Qwen/Qwen3-32B'),
                    'max-num-batched-tokens': int(os.getenv('VLLM_MAX_NUM_BATCHED_TOKENS', '2048')),
                    'max-num-seqs': int(os.getenv('VLLM_MAX_NUM_SEQS', '16')),
                    'max_model_len': int(os.getenv('VLLM_MAX_MODEL_LEN', '4096'))
                }
            }
            
            service_manager = create_service_manager(config)

            if service_manager.start_services():
                logger.info("Backend services started successfully")

                while service_manager.running:
                    time.sleep(1)

                    if not service_manager.check_service_health():
                        logger.error("Service health check failed")
                        break
            else:
                logger.error("Failed to start backend services")
                
        except Exception as e:
            logger.error(f"Service thread error: {e}")

    service_thread = threading.Thread(target=run_services, daemon=True)
    service_thread.start()

    time.sleep(10)


def stop_backend_services():
    global service_manager
    if service_manager:
        service_manager.stop_all_services()

app = FastAPI(title="Multimodal Server", version="1.0.0")


def handle_request_errors(func: Callable):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            tb_str = traceback.format_exc()
            logger.error(f"Error in {func.__name__}: {str(e)}\n{tb_str}")
            if 'no face detected' in str(e).lower():
                raise HTTPException(status_code=400, detail={"error": str(e), "traceback": tb_str})
            else:    
                raise HTTPException(status_code=500, detail={"error": str(e), "traceback": tb_str})
    return wrapper


@app.get("/")
async def home():
    return PlainTextResponse("Image!")


@app.post("/load_model")
@handle_request_errors
async def load_model(request_data: base_model.LoadModelRequest) -> base_model.LoadModelResponse:
    return await model_manager.download_model(request_data)

@app.post("/upscale")
@handle_request_errors
async def upscale(request_data: base_model.UpscaleBase) -> base_model.ImageResponseBody:
    return await inference.upscale_infer(request_data)

@app.post("/clip-embeddings")
@handle_request_errors
async def clip_embeddings(
    request_data: base_model.ClipEmbeddingsBase,
) -> base_model.ClipEmbeddingsResponse:
    embeddings = await inference.get_clip_embeddings(request_data)
    return base_model.ClipEmbeddingsResponse(clip_embeddings=embeddings)

@app.post("/text-generation")
@handle_request_errors
async def text_generation(
    request_data: base_model.TextGenerationBase,
) -> base_model.TextGenerationResponse:
    return await inference.generate_text(request_data)


@app.post("/text-completion")
@handle_request_errors
async def text_completion(
    request_data: base_model.TextCompletionBase,
) -> base_model.TextCompletionResponse:
    return await inference.complete_text(request_data)


@app.post("/batch-text-generation")
@handle_request_errors
async def batch_text_generation(
    request_data: base_model.BatchTextGenerationBase,
) -> base_model.BatchTextGenerationResponse:
    return await inference.batch_generate_text(request_data)


@app.get("/models")
@handle_request_errors
async def get_models() -> base_model.ModelsResponse:
    return await inference.get_available_models()

@app.get("/service-status")
async def get_service_status():

    global service_manager
    if service_manager:
        return service_manager.get_service_status()
    else:
        return {"running": False, "services": {}}

@app.post("/chat/completions")
@handle_request_errors
async def chat_completions_proxy(request_data: dict):

    try:
        from text_processor import get_text_processor
        
        text_processor = await get_text_processor()
        
        is_stream = request_data.get("stream", True)

        vllm_payload = {
            "model": request_data.get("model", "Qwen/Qwen3-32B"),
            "messages": request_data.get("messages", []),
            "stream": is_stream,
            "temperature": request_data.get("temperature", 0.7),
            "max_tokens": request_data.get("max_tokens", 1000),
            "top_p": request_data.get("top_p", 0.9),
            "top_k": request_data.get("top_k", 5)
        }
        
        if is_stream:
            async def generate_stream():
                try:
                    async for chunk in text_processor.generate_text_stream(
                        prompt=vllm_payload["messages"][-1]["content"] if vllm_payload["messages"] else "",
                        model=vllm_payload["model"],
                        max_tokens=vllm_payload["max_tokens"],
                        temperature=vllm_payload["temperature"],
                        top_p=vllm_payload["top_p"]
                    ):
                        yield chunk
                except Exception as e:
                    logger.error(f"Stream generation error: {e}")
                    yield f"Error: {str(e)}"
            
            from fastapi.responses import StreamingResponse
            return StreamingResponse(
                generate_stream(), 
                media_type="text/event-stream"
            )
        else:
            result = await text_processor.generate_text(
                prompt=vllm_payload["messages"][-1]["content"] if vllm_payload["messages"] else "",
                model=vllm_payload["model"],
                max_tokens=vllm_payload["max_tokens"],
                temperature=vllm_payload["temperature"],
                top_p=vllm_payload["top_p"],
                stream=False
            )
            
            if result["success"]:

                response = {
                    "id": "chatcmpl-" + str(int(time.time())),
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": result["model"],
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": result["text"]
                            },
                            "finish_reason": result["finish_reason"]
                        }
                    ],
                    "usage": result["usage"]
                }
                return response
            else:
                raise HTTPException(status_code=500, detail=f"Text generation failed: {result['error']}")
            
    except Exception as e:
        logger.error(f"Chat completions proxy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/completions")
@handle_request_errors
async def completions_proxy(request_data: dict):
    try:
        from text_processor import get_text_processor
        
        text_processor = await get_text_processor()
        
        is_stream = request_data.get("stream", True)
        
        vllm_payload = {
            "model": request_data.get("model", "Qwen/Qwen3-32B"),
            "prompt": request_data.get("prompt", ""),
            "stream": is_stream,
            "temperature": request_data.get("temperature", 0.7),
            "max_tokens": request_data.get("max_tokens", 1000),
            "top_p": request_data.get("top_p", 0.9),
            "top_k": request_data.get("top_k", 5)
        }
        
        if is_stream:
            async def generate_stream():
                try:
                    async for chunk in text_processor.generate_text_completion_stream(
                        prompt=vllm_payload["prompt"],
                        model=vllm_payload["model"],
                        max_tokens=vllm_payload["max_tokens"],
                        temperature=vllm_payload["temperature"],
                        top_p=vllm_payload["top_p"]
                    ):
                        yield chunk
                        await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Stream completion error: {e}")
                    yield f"Error: {str(e)}"
            
            from fastapi.responses import StreamingResponse
            return StreamingResponse(
                generate_stream(), 
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "Transfer-Encoding": "chunked"
                }
            )
        else:
            result = await text_processor.generate_text_completion(
                prompt=vllm_payload["prompt"],
                model=vllm_payload["model"],
                max_tokens=vllm_payload["max_tokens"],
                temperature=vllm_payload["temperature"],
                top_p=vllm_payload["top_p"]
            )
            
            if result["success"]:
                response = {
                    "id": "cmpl-" + str(int(time.time())),
                    "object": "text_completion",
                    "created": int(time.time()),
                    "model": result["model"],
                    "choices": [
                        {
                            "index": 0,
                            "text": result["text"],
                            "finish_reason": result["finish_reason"]
                        }
                    ],
                    "usage": result["usage"]
                }
                return response
            else:
                raise HTTPException(status_code=500, detail=f"Text completion failed: {result['error']}")
            
    except Exception as e:
        logger.error(f"Completions proxy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/completions/stream")
@handle_request_errors
async def chat_completions_stream_proxy(request_data: dict):
    try:
        from text_processor import get_text_processor
        
        text_processor = await get_text_processor()
        
        vllm_payload = {
            "model": request_data.get("model", "Qwen/Qwen3-32B"),
            "messages": request_data.get("messages", []),
            "stream": True,
            "temperature": request_data.get("temperature", 0.7),
            "max_tokens": request_data.get("max_tokens", 1000),
            "top_p": request_data.get("top_p", 0.9),
            "top_k": request_data.get("top_k", 5)
        }
        
        async def generate_stream():
            try:
                async for chunk in text_processor.generate_text_stream(
                    prompt=vllm_payload["messages"][-1]["content"] if vllm_payload["messages"] else "",
                    model=vllm_payload["model"],
                    max_tokens=vllm_payload["max_tokens"],
                    temperature=vllm_payload["temperature"],
                    top_p=vllm_payload["top_p"]
                ):
                    yield f"data: {json.dumps({'choices': [{'delta': {'content': chunk}}]})}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"Stream generation error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            generate_stream(), 
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Transfer-Encoding": "chunked"
            }
        )
            
    except Exception as e:
        logger.error(f"Chat completions stream proxy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/completions/stream")
@handle_request_errors
async def completions_stream_proxy(request_data: dict):
    try:
        from text_processor import get_text_processor
        
        text_processor = await get_text_processor()
        
        vllm_payload = {
            "model": request_data.get("model", "Qwen/Qwen3-32B"),
            "prompt": request_data.get("prompt", ""),
            "stream": True,
            "temperature": request_data.get("temperature", 0.7),
            "max_tokens": request_data.get("max_tokens", 1000),
            "top_p": request_data.get("top_p", 0.9),
            "top_k": request_data.get("top_k", 5)
        }
        
        async def generate_stream():
            try:
                async for chunk in text_processor.generate_text_completion_stream(
                    prompt=vllm_payload["prompt"],
                    model=vllm_payload["model"],
                    max_tokens=vllm_payload["max_tokens"],
                    temperature=vllm_payload["temperature"],
                    top_p=vllm_payload["top_p"]
                ):
                    yield f"data: {json.dumps({'choices': [{'text': chunk}]})}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"Stream completion error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            generate_stream(), 
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Transfer-Encoding": "chunked"
            }
        )
            
    except Exception as e:
        logger.error(f"Completions stream proxy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    import os
    import argparse
    import signal
    import sys

    parser = argparse.ArgumentParser(description='Multimodal Server')
    parser.add_argument('--host', default='0.0.0.0', help='Server host')
    parser.add_argument('--port', type=int, default=6919, help='Server port')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--start-services', action='store_true', help='Start backend services (vLLM)')
    
    args = parser.parse_args()

    if "CUBLAS_WORKSPACE_CONFIG" not in os.environ:
        os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"

    import torch

    torch.use_deterministic_algorithms(False)

    def signal_handler(signum, frame):
        stop_backend_services()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    start_services = args.start_services or os.getenv('START_BACKEND_SERVICES', 'true').lower() == 'true'
    
    if start_services:
        logger.info("Starting backend services...")
        start_backend_services()
        
        logger.info("Waiting for services to be ready...")
        import time
        
        logger.info("Waiting for vLLM service...")
        vllm_ready = False
        vllm_host = os.getenv('VLLM_HOST', '127.0.0.1')
        vllm_port = os.getenv('VLLM_PORT', '8000')
        for i in range(30):
            try:
                import requests
                response = requests.get(f"http://{vllm_host}:{vllm_port}/v1/models", timeout=5)
                if response.status_code == 200:
                    logger.info("vLLM service is ready!")
                    vllm_ready = True
                    break
            except:
                pass
            time.sleep(2)
            if i % 5 == 0:
                logger.info(f"Still waiting for vLLM service... ({i*2}s)")
        
        if not vllm_ready:
            logger.warning("vLLM service may not be ready, but continuing...")
        
    else:
        logger.info("Skipping backend services startup")

    try:
        uvicorn.run(app, host=args.host, port=args.port)
    finally:
        stop_backend_services()
