from typing import List
import base_model
import utils.api_gate as api_gate
from utils import base64_utils
from payload import PayloadModifier
from clip_embeddings.clip_manager import ClipEmbeddingsProcessor
import torch
from utils import misc
import clip
from loguru import logger


payload_modifier = PayloadModifier()
clip_emb_processor = ClipEmbeddingsProcessor()


async def generate_text(
    infer_props: base_model.TextGenerationBase,
) -> base_model.TextGenerationResponse:
    from text_processor import get_text_processor
    
    text_processor = await get_text_processor()
    result = await text_processor.generate_text(
        prompt=infer_props.prompt,
        model=infer_props.model,
        max_tokens=infer_props.max_tokens,
        temperature=infer_props.temperature,
        top_p=infer_props.top_p,
        stop=infer_props.stop,
        stream=infer_props.stream
    )
    
    if result["success"]:
        return base_model.TextGenerationResponse(
            text=result["text"],
            model=result["model"],
            usage=result["usage"],
            finish_reason=result["finish_reason"]
        )
    else:
        raise Exception(f"Text generation failed: {result['error']}")


async def complete_text(
    infer_props: base_model.TextCompletionBase,
) -> base_model.TextCompletionResponse:
    from text_processor import get_text_processor
    
    text_processor = await get_text_processor()
    result = await text_processor.generate_text_completion(
        prompt=infer_props.prompt,
        model=infer_props.model,
        max_tokens=infer_props.max_tokens,
        temperature=infer_props.temperature,
        top_p=infer_props.top_p,
        stop=infer_props.stop
    )
    
    if result["success"]:
        return base_model.TextCompletionResponse(
            text=result["text"],
            model=result["model"],
            usage=result["usage"],
            finish_reason=result["finish_reason"]
        )
    else:
        raise Exception(f"Text completion failed: {result['error']}")


async def batch_generate_text(
    infer_props: base_model.BatchTextGenerationBase,
) -> base_model.BatchTextGenerationResponse:
    from text_processor import get_text_processor
    
    text_processor = await get_text_processor()
    results = await text_processor.batch_generate_text(
        prompts=infer_props.prompts,
        model=infer_props.model,
        max_tokens=infer_props.max_tokens,
        temperature=infer_props.temperature,
        top_p=infer_props.top_p
    )
    
    response_results = []
    for result in results:
        if result["success"]:
            response_results.append(base_model.TextGenerationResponse(
                text=result["text"],
                model=result["model"],
                usage=result["usage"],
                finish_reason=result["finish_reason"]
            ))
        else:
            raise Exception(f"Batch text generation failed: {result['error']}")
    
    return base_model.BatchTextGenerationResponse(results=response_results)


async def get_available_models() -> base_model.ModelsResponse:
    from text_processor import get_text_processor
    
    text_processor = await get_text_processor()
    models = await text_processor.get_available_models()
    
    model_infos = []
    for model_id in models:
        model_infos.append(base_model.ModelInfo(
            id=model_id,
            name=model_id,
            type="text-generation",
            parameters={}
        ))
    
    return base_model.ModelsResponse(models=model_infos)
