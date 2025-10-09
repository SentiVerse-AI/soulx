# -*- coding: utf-8 -*-

import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from fiber.logging_utils import get_logger

from soulx.validator.query.query_config import Config
from soulx.validator.models import Contender
from soulx.core.models import utility_models
from soulx.core.models import config_models as cmodels
import uuid
from soulx.core.models.utility_models import RewardData
from soulx.core import work_and_speed_functions
from soulx.validator.scoring_system import scoring_system
from soulx.validator.scoring_results_manager import scoring_results_manager, ScoringResult

logger = get_logger(__name__)

async def adjust_contender_from_result(
    config: Config,
    query_result: utility_models.QueryResult,
    contender: Any,
    synthetic_query: bool,
    payload: dict,
    sus_task: bool = False,
    speed_data: dict = None, # type: ignore
    is_text_task: bool = True,
    task_config: dict = None
) -> Tuple[utility_models.QueryResult, Optional[float]]:

    output_cache = None
    quality_score = None
    
    if task_config is None:
            logger.error(f"Task {query_result.task} is not enabled")
            return query_result, None

    inp_character_count = len(payload.get("prompt")) if payload.get("prompt") else sum(
        len(m['content']) if isinstance(m['content'], str)
        else sum(len(b.get('text', '')) for b in m['content'] if b.get('type') == 'text')
        for m in payload['messages']
    ) if payload.get('messages') else 0

    if sus_task:
        try:
            capacity_consumed, num_tokens = work_and_speed_functions.calculate_work(
                task_config=task_config,
                result=query_result.model_dump(),
                inp_character_count=inp_character_count,
                steps=payload.get("steps"),
                img_resolution=(payload.get("width"), payload.get("height"))
            )
            metric = capacity_consumed / query_result.response_time if query_result.response_time else 0
            stream_metric = num_tokens / query_result.stream_time if query_result.stream_time else 0

            claimed_metric = speed_data['metric'] if speed_data else None
            claimed_stream_metric = speed_data['stream_metric'] if speed_data else None

            metric_diff_percent = abs(metric - claimed_metric) / claimed_metric * 100 if claimed_metric else None
            stream_metric_diff_percent = abs(stream_metric - claimed_stream_metric) / claimed_stream_metric * 100 if claimed_stream_metric else None
            logger.info(f"Sus task comparison for node {getattr(contender, 'node_hotkey', None)}, task {getattr(contender, 'task', None)}:")
            logger.info(f"  Claimed metric: {claimed_metric}, Actual metric: {metric}, Diff: {metric_diff_percent:.2f}%")
            logger.info(f"  Claimed stream metric: {claimed_stream_metric}, Actual: {stream_metric}, Diff: {stream_metric_diff_percent:.2f}%")

            metric_threshold = 50.0
            stream_metric_threshold = 50.0
            is_metric_suspicious = metric_diff_percent and metric_diff_percent > metric_threshold
            is_stream_metric_suspicious = stream_metric_diff_percent and stream_metric_diff_percent > stream_metric_threshold
            if is_metric_suspicious:
                quality_score = -10.0
                
                reward_data = RewardData(
                    id=uuid.uuid4().hex,
                    task=getattr(contender, 'task', None),
                    node_id=int(getattr(contender, 'node_id', 0)),
                    quality_score=quality_score,
                    validator_hotkey=getattr(config.keypair, 'ss58_address', None),
                    node_hotkey=getattr(contender, 'node_hotkey', None),
                    synthetic_query=synthetic_query,
                    response_time=999,
                    volume=capacity_consumed,
                    metric=metric,
                    stream_metric=stream_metric,
                    created_at=query_result.created_at,
                )
                if hasattr(config, 'reward_client') and config.reward_client:
                    reward_data_dict = {
                        'id': reward_data.id,
                        'task': reward_data.task,
                        'node_id': reward_data.node_id,
                        'quality_score': reward_data.quality_score,
                        'validator_hotkey': reward_data.validator_hotkey,
                        'node_hotkey': reward_data.node_hotkey,
                        'synthetic_query': reward_data.synthetic_query,
                        'response_time': reward_data.response_time,
                        'volume': reward_data.volume,
                        'metric': reward_data.metric,
                        'stream_metric': reward_data.stream_metric,
                        'created_at': reward_data.created_at.isoformat() if reward_data.created_at else None
                    }
                    await config.reward_client.insert_reward_data(reward_data_dict)
                else:
                    logger.warning("No reward_client available to insert reward data.")
        except Exception as e:
            logger.error(f"Couldn't process sus task {getattr(contender, 'task', None)} for node id {getattr(contender, 'node_id', None)}: {e}")

    if query_result.status_code == 200 and query_result.success:
        task_type = task_config.get("task_type")

        if task_type == cmodels.TaskType.IMAGE.value:

            capacity_consumed, _ = work_and_speed_functions.calculate_work(
                task_config=task_config,
                result=query_result.model_dump(),
                inp_character_count=inp_character_count,
                steps=payload.get("steps"),
                img_resolution=(payload.get("width"), payload.get("height"))
            )
        else:
            capacity_consumed, _ = work_and_speed_functions.calculate_work(
                task_config=task_config,
                result=query_result.model_dump(),
                inp_character_count=inp_character_count,
                steps=payload.get("steps")
            )
        
        node_id = int(getattr(contender, 'nodeid', 0))
        quality_score = await scoring_system.score_result(
            result=query_result,
            payload=payload,
            task_config=task_config,
            node_id=node_id
        )
        
        scoring_result = ScoringResult(
            hotkey=getattr(contender, 'node_hotkey', ''),
            node_id=node_id,
            task=query_result.task,
            quality_score=quality_score,
            timestamp=datetime.now(),
            synthetic_query=synthetic_query,
            response_time=query_result.response_time or 0.0,
            success=query_result.success,
            status_code=query_result.status_code
        )
        scoring_results_manager.add_scoring_result(scoring_result)
        
        if hasattr(config, 'reward_client') and config.reward_client:
            reward_data = RewardData(
                id=uuid.uuid4().hex,
                task=query_result.task,
                node_id=node_id,
                quality_score=quality_score,
                validator_hotkey=getattr(config.keypair, 'ss58_address', None),
                node_hotkey=getattr(contender, 'node_hotkey', None),
                synthetic_query=synthetic_query,
                response_time=query_result.response_time,
                volume=capacity_consumed,
                metric=capacity_consumed / query_result.response_time if query_result.response_time else 0,
                stream_metric=0,
                created_at=query_result.created_at,
            )
            
            reward_data_dict = {
                'id': reward_data.id,
                'task': reward_data.task,
                'node_id': reward_data.node_id,
                'quality_score': reward_data.quality_score,
                'validator_hotkey': reward_data.validator_hotkey,
                'node_hotkey': reward_data.node_hotkey,
                'synthetic_query': reward_data.synthetic_query,
                'response_time': reward_data.response_time,
                'volume': reward_data.volume,
                'metric': reward_data.metric,
                'stream_metric': reward_data.stream_metric,
                'created_at': reward_data.created_at.isoformat() if reward_data.created_at else None
            }
            await config.reward_client.insert_reward_data(reward_data_dict)
        else:
            logger.warning("No reward_client available to insert reward data.")
            
    elif query_result.status_code == 400:
        logger.debug(f"400 error; Node {getattr(contender, 'node_id', None)} - Task {query_result.task}.")
        quality_score = 0.0
        
    elif query_result.status_code == 429:
        logger.debug(f" 429 error; Adjusting node {getattr(contender, 'node_id', None)} for task {query_result.task}.")
        quality_score = 0.0
        
    else:
        logger.debug(f"500 error; Adjusting node {getattr(contender, 'node_id', None)} for task {query_result.task}.")
        quality_score = 0.0
            
    return query_result, quality_score 