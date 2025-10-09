import contextlib
import json
import logging
import time
from typing import AsyncGenerator
import random
import copy

from fiber.logging_utils import get_logger

logger = get_logger(__name__)


@contextlib.contextmanager
def log_time(description: str, logger: logging.Logger):
    start_time = time.time()
    try:
        yield
    finally:
        end_time = time.time()
        elapsed_time = end_time - start_time
        logger.debug(f"{description} took {elapsed_time:.4f} seconds")


async def async_chain(first_chunk: str, async_gen: AsyncGenerator[str, str]) -> AsyncGenerator[str, str]:

    yield first_chunk
    async for item in async_gen:
        yield item


def get_error_event(job_id: str, error_message: str | None, status_code: int) -> str:
    return json.dumps({"job_id": job_id, "error_message": error_message, "status_code": status_code})


def get_success_event(content: str, job_id: str, status_code: int) -> str:
    return json.dumps({"job_id": job_id, "status_code": status_code, "content": content})


def tweaks_in_payload(payload: dict) -> dict:

    modified_payload = copy.deepcopy(payload)
    
    is_chat = 'messages' in modified_payload
    
    if 'temperature' in modified_payload:
        current_temp = modified_payload['temperature']
        delta = random.uniform(-0.01, 0.01)
        new_temp = max(0.01, min(0.99, current_temp + delta))
        modified_payload['temperature'] = round(new_temp, 4)
    
    if is_chat:
        for i, message in enumerate(modified_payload['messages']):
            if 'content' in message and isinstance(message['content'], str):
                modified_payload['messages'][i]['content'] = _tweak_text(message['content'])
    else:
        if 'prompt' in modified_payload and isinstance(modified_payload['prompt'], str):
            modified_payload['prompt'] = _tweak_text(modified_payload['prompt'])    
    
    return modified_payload


def _tweak_text(text: str) -> str:

    if not text:
        return text
    
    original_text = text
    modified = False
    
    chars = list(text)
    if len(chars) > 1:
        pos = random.randint(0, len(chars) - 1)
        if chars[pos] == ' ':
            chars.pop(pos)
            modified = True
        elif pos > 0 and pos < len(chars) - 1:
            chars.insert(pos, ' ')
            modified = True
        text = ''.join(chars)
    
    punctuation_swaps = {
        '.': ',',
        ',': '.',
        '!': '?',
        '?': '!',
        ';': ':',
        ':': ';',
        '-': '–', 
        '–': '-',
    }
    
    if not modified:
        for old_punct, new_punct in punctuation_swaps.items():
            if old_punct in text:
                positions = [i for i, char in enumerate(text) if char == old_punct]
                if positions:
                    pos = random.choice(positions)
                    text = text[:pos] + new_punct + text[pos+1:]
                    modified = True
                    break
    
    if not modified:
        zero_width_space = '\u200B'
        pos = random.randint(0, len(text))
        text = text[:pos] + zero_width_space + text[pos:]
        modified = True
    
    if text == original_text and ' ' in text:
        positions = [i for i, char in enumerate(text) if char == ' ']
        if positions:
            pos = random.choice(positions)
            text = text[:pos] + ' ' + text[pos:]
    
    if text == original_text:
        text = text + '\u200B'
    
    return text 