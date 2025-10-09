import json
import time
import traceback
from typing import AsyncGenerator, Any
from fiber.encrypted.validator import client
from fiber.encrypted.networking.models import NodeWithFernet as Node
from fiber.logging_utils import get_logger

import httpx
from opentelemetry import metrics

from soulx.core.constants import CHARACTER_TO_TOKEN_CONVERSION
from soulx.core.models import utility_models
from soulx.validator.query.query_config import Config
from soulx.validator.common import utils
from soulx.validator.models import Contender
from soulx.core import task_config as tcfg
from soulx.core.utils import generic_constants as gcst, generic_utils
from soulx.core.utils import redis_constants as rcst
from soulx.core.utils.query_utils import load_sse_jsons


logger = get_logger(__name__)

GAUGE_ORGANIC_TOKENS_PER_SEC = metrics.get_meter(__name__).create_gauge(
    "validator.synthetic_node.query.streaming.organic.tokens_per_sec",
    description="Average tokens per second metric for LLM streaming for any organic query"
)
GAUGE_ORGANIC_TOKENS = metrics.get_meter(__name__).create_gauge(
    "validator.synthetic_node.query.streaming.organic.tokens",
    description="Total tokens for LLM streaming for an organic LLM query"
)
GAUGE_SYNTHETIC_INPUT_TOKENS = metrics.get_meter(__name__).create_gauge(
    "validator.synthetic_node.query.streaming.synthetic.input_tokens",
    description="Total input tokens for a synthetic LLM query"
)
GAUGE_SYNTHETIC_TOKENS_PER_SEC = metrics.get_meter(__name__).create_gauge(
    "validator.synthetic_node.query.streaming.synthetic.tokens_per_sec",
    description="Average tokens per second metric for LLM streaming for any synthetic query"
)
GAUGE_SYNTHETIC_TOKENS = metrics.get_meter(__name__).create_gauge(
    "validator.synthetic_node.query.streaming.synthetic.tokens",
    description="Total tokens for LLM streaming for a synthetic LLM query"
)

def _get_formatted_payload(content: str, first_message: bool, add_finish_reason: bool = False, task: str = "") -> dict:
    if 'comp' in task:
        choices_payload: dict[str, str | dict[str, str]] = {"text": content}
        choices_payload["finish_reason"] = "stop"
    else:
        delta_payload = {"content": content}
        if first_message:
            delta_payload["role"] = "assistant"
        choices_payload: dict[str, str | dict[str, str]] = {"delta": delta_payload}
        if add_finish_reason:
            choices_payload["finish_reason"] = "stop"
    payload = {
        "choices": [choices_payload],
    }
    return payload


async def _handle_event(
    config: Config,
    content: str | None,
    synthetic_query: bool,
    job_id: str,
    status_code: int,
    error_message: str | None = None,
) -> None:
    if synthetic_query:
        return
    if content is not None:
        if isinstance(content, dict):
            content = json.dumps(content)
        await config.redis_db.publish(
            f"{rcst.JOB_RESULTS}:{job_id}",
            generic_utils.get_success_event(content=content, job_id=job_id, status_code=status_code),
        )
    else:
        await config.redis_db.publish(
            f"{rcst.JOB_RESULTS}:{job_id}",
            generic_utils.get_error_event(job_id=job_id, error_message=error_message, status_code=status_code),
        )


async def async_chain(first_chunk, async_gen):
    yield first_chunk  # manually yield the first chunk
    async for item in async_gen:
        yield item  # then yield from the original generator


def construct_500_query_result(node: Node, task: str) -> utility_models.QueryResult:
    query_result = utility_models.QueryResult(
        node_id=node.node_id,
        task=task,
        success=False,
        node_hotkey=node.hotkey,
        formatted_response=None,
        status_code=500,
        response_time=None,
        stream_time=None,
    )
    return query_result


def construct_400_query_result(node: Node, task: str) -> utility_models.QueryResult:
    query_result = utility_models.QueryResult(
        node_id=node.node_id,
        task=task,
        success=False,
        node_hotkey=node.hotkey,
        formatted_response=None,
        status_code=400,
        response_time=None,
        stream_time=None,
    )
    return query_result


async def consume_generator(
    config: Config,
    generator: AsyncGenerator,
    job_id: str,
    synthetic_query: bool,
    contender: Contender,
    node: Node,
    payload: dict,
    start_time: float,
    sus_task: bool = False,
    speed_data: dict = None, # type: ignore
    task_config: dict = None
) -> bool:
    assert job_id
    task = contender.task
    query_result = None
    tokens = 0

    text_jsons, status_code, first_message = [], 200, True  # TODO: remove unused variable

    stream_time_init = None
    try:
        out_tokens_counter = 0

        if payload.get('prompt') is not None:
            num_input_tokens = int(len(payload['prompt']) // CHARACTER_TO_TOKEN_CONVERSION)
        elif payload.get('messages') is not None:
            num_input_tokens = int(sum(len(message['content']) for message in payload['messages']) // CHARACTER_TO_TOKEN_CONVERSION)
        else:
            logger.error(f"Can't count input tokens in payload for task: {task}; payload: {payload}")
            num_input_tokens = 0
        
        async for text in generator:
            if isinstance(text, bytes):
                text = text.decode()

            if isinstance(text, str):
                try:
                    loaded_jsons = load_sse_jsons(text)
                    if isinstance(loaded_jsons, dict):
                        status_code = loaded_jsons.get(gcst.STATUS_CODE)  # noqa
                        break

                except (IndexError, json.JSONDecodeError) as e:
                    logger.warning(f"Error {e} when trying to load text: {text}")
                    break

                for text_json in loaded_jsons:
                    if not isinstance(text_json, dict):
                        logger.debug(f"Invalid text_json because its not a dict?: {text_json}")
                        first_message = True
                        break

                    try:
                        if "comp" in task:
                            _ = text_json["choices"][0]["text"]
                        else:
                            _ = text_json["choices"][0]["delta"]["content"]
                    except KeyError:
                        logger.debug(f"Invalid text_json because there's not delta content: {text_json}")
                        first_message = True
                        break
                    
                    out_tokens_counter += 1
                    text_json["usage"] = {
                        "prompt_tokens": num_input_tokens,
                        "completion_tokens": out_tokens_counter,
                        "total_tokens": num_input_tokens + out_tokens_counter,
                    }

                    text_jsons.append(text_json)
                    dumped_payload = json.dumps(text_json)
                    first_message = False

                    if synthetic_query:
                        await _handle_event(
                            config, dumped_payload, synthetic_query, job_id, status_code=status_code
                        )
                    else:
                        await _handle_event(
                            config, dumped_payload, synthetic_query, job_id, status_code=status_code
                        )

                    if stream_time_init is None:
                        stream_time_init = time.time()

                    if "finish_reason" in text_json["choices"][0]:
                        break

        response_time = time.time() - start_time
        if stream_time_init is not None:
            stream_time = time.time() - stream_time_init
        else:
            stream_time = response_time

        query_result = utility_models.QueryResult(
            formatted_response=text_jsons if len(text_jsons) > 0 else None,
            node_id=node.node_id,
            response_time=response_time,
            stream_time=stream_time,
            task=task,
            success=not first_message,
            node_hotkey=node.hotkey,
            status_code=200,
        )
        success = not first_message
        if success:
            if synthetic_query:
                GAUGE_SYNTHETIC_INPUT_TOKENS.set(num_input_tokens, {"task": task})
                GAUGE_SYNTHETIC_TOKENS.set(tokens, {"task": task})
                GAUGE_SYNTHETIC_TOKENS_PER_SEC.set(tokens / response_time, {"task": task})
            else:
                GAUGE_ORGANIC_TOKENS.set(tokens, {"task": task})
                GAUGE_ORGANIC_TOKENS_PER_SEC.set(tokens / response_time, {"task": task})
    except Exception as e:
        query_result = construct_500_query_result(node, task)
        success = False
    finally:
        if query_result is not None:
            await utils.adjust_contender_from_result(config, query_result, contender, synthetic_query, 
                                                     payload=payload, sus_task=sus_task, speed_data=speed_data, task_config=task_config)
            await config.redis_db.expire(rcst.QUERY_RESULTS_KEY + ":" + job_id, 10)

    return success


def convert_payload_to_serializable(payload):
    if isinstance(payload, dict):
        result = {}
        for key, value in payload.items():
            result[key] = convert_payload_to_serializable(value)
        return result
    elif isinstance(payload, list):
        return [convert_payload_to_serializable(item) for item in payload]
    elif hasattr(payload, '__iter__') and not isinstance(payload, (str, bytes, bytearray)):
        if hasattr(payload, '__class__') and payload.__class__.__name__ == 'SerializationIterator':
            try:
                content_items = []
                for item in payload:
                    if isinstance(item, dict) and 'text' in item:
                        content_items.append({'type': 'text', 'text': item['text']})
                    elif isinstance(item, dict):
                        content_items.append(convert_payload_to_serializable(item))
                    else:
                        content_items.append({'type': 'text', 'text': str(item)})
                return content_items
            except Exception as e:
                return []
        try:
            return [convert_payload_to_serializable(item) for item in payload]
        except:
            return []
    elif hasattr(payload, '__dict__'):
        try:
            return convert_payload_to_serializable(payload.__dict__)
        except:
            return {}
    else:
        return payload
    

async def query_node_stream(config: Config, contender: Contender, node: Any, payload: dict, task_config: dict = None):

    if config.replace_with_localhost:
        node.ip = "0.0.0.1"

    address = client.construct_server_address(
        node,
        replace_with_docker_localhost=config.replace_with_docker_localhost,
        replace_with_localhost=config.replace_with_localhost,
    )
    
    if task_config is None:
            return

    assert node.fernet is not None
    assert node.symmetric_key_uuid is not None

    serializable_payload = convert_payload_to_serializable(payload)

    validator_keypair = config.keypair
    validator_ss58_address = config.ss58_address
    
    if not hasattr(validator_keypair, 'sign'):
        logger.error("Keypair is not compatible with fiber. Please use create_fiber_compatible_config() to create Config object.")
        return

    return client.make_streamed_post(
        httpx_client=config.httpx_client,
        server_address=address,
        keypair=validator_keypair,
        validator_ss58_address=validator_ss58_address,
        miner_ss58_address=node.hotkey,
        fernet=node.fernet,
        symmetric_key_uuid=node.symmetric_key_uuid,
        payload=serializable_payload,
        endpoint=task_config.get('endpoint', '/chat/completions'),
        timeout=task_config.get('timeout', 30),
    ) 