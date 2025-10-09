import json

from soulx.core.constants import CHARACTER_TO_TOKEN_CONVERSION, INP_TO_OUTP_TXT_WORK_RATIO, IMG_WORK_WINDOW
from soulx.core.models import config_models as cmodels
from fiber.logging_utils import get_logger

logger = get_logger(__name__)


def _calculate_work_image(steps: int, img_resolution: tuple[int, int]) -> float:

    img_resolution_work_factor = img_resolution[0]/IMG_WORK_WINDOW[0] * img_resolution[1]/IMG_WORK_WINDOW[1] #img_resolution expected to be > 128x128 always
    work = steps * img_resolution_work_factor
    return work


def _calculate_work_text(inp_character_count: int, out_character_count: int) -> float:

    work = out_character_count / CHARACTER_TO_TOKEN_CONVERSION + (inp_character_count / CHARACTER_TO_TOKEN_CONVERSION) * INP_TO_OUTP_TXT_WORK_RATIO
    logger.info(f"Work for text: {work}; Input chars: {inp_character_count}; Output chars: {out_character_count}")
    return work


def calculate_work(
    task_config: dict,
    result: dict,
    inp_character_count: int,
    steps: int | None = None,
    img_resolution: tuple[int | None, int | None] = (None, None),
) -> tuple[float, float]:
    config = task_config

    raw_formatted_response = result.get("formatted_response", {})
    if not raw_formatted_response:
        return 0, 0
    task_type = config.get("task_type")
    task = task_config.get("task")

    if task_type == cmodels.TaskType.IMAGE.value:
        assert steps is not None and img_resolution != (None, None)
        out = _calculate_work_image(steps, img_resolution)
        return out, out
    elif task_type == cmodels.TaskType.TEXT.value:

        formatted_response = (
            json.loads(raw_formatted_response) if isinstance(raw_formatted_response, str) else raw_formatted_response
        )
        character_count = 0
        for text_json in formatted_response:
            try:
                if '-comp' in task:
                    character_count += len(text_json["choices"][0]["text"])
                else:
                    if isinstance(formatted_response, dict) and  text_json =='choices' :
                        if formatted_response["choices"]:
                            choice = formatted_response["choices"][0]
                            if "message" in choice:
                                character_count += len(choice["message"]["content"])
                            elif "delta" in choice:
                                if "content" in choice["delta"]:
                                    character_count += len(choice["delta"]["content"])
                            else:
                                logger.warning(f"Unknown choice format: {choice}")

            except KeyError as e:
                logger.error(f"KeyError in text_json: {e}, text_json: {text_json}")  

        if character_count == 0:
            return 1, 1

        return _calculate_work_text(inp_character_count, character_count), len(formatted_response)
    else:
        raise ValueError(f"Task {task} not found for work bonus calculation")