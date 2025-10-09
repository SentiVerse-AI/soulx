#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import importlib
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from soulx.core.models import utility_models
from soulx.core import task_config
from soulx.core import work_and_speed_functions

logger = logging.getLogger(__name__)

class LocalScoringSystem:

    def __init__(self):
        self.scoring_functions = {}
        self._load_scoring_functions()
    
    def _load_scoring_functions(self):
        pass
    
    async def score_result(
        self,
        result: utility_models.QueryResult,
        payload: Dict[str, Any],
        task_config: Any,
        node_id: int
    ) -> float:

        try:

            if task_config is None:
                logger.error(f"Task {result.task} is not enabled")
                return 0.0
            
            inp_character_count = self._calculate_input_character_count(payload)
            
            volume, num_tokens = work_and_speed_functions.calculate_work(
                task_config=task_config,
                result=result.model_dump(),
                inp_character_count=inp_character_count,
                steps=payload.get("steps"),
                img_resolution=(payload.get("width"), payload.get("height"))
            )
            
            metric = volume / result.response_time if result.response_time else 0
            stream_metric = num_tokens / result.stream_time if result.stream_time else 0
            
            base_score = await self._calculate_base_score(
                result, payload, task_config, metric, stream_metric
            )
            
            quality_score = self._apply_quality_adjustments(base_score, result, metric, stream_metric)
            
            quality_score = max(0.0, min(1.0, quality_score))
            
            return quality_score
            
        except Exception as e:
            logger.error(f"Error scoring result for node {node_id}: {e}")
            return 0.0
    
    def _calculate_input_character_count(self, payload: Dict[str, Any]) -> int:
        if payload.get("prompt"):
            return len(payload["prompt"])
        
        if payload.get("messages"):
            total_chars = 0
            for message in payload["messages"]:
                content = message.get("content", "")
                if isinstance(content, str):
                    total_chars += len(content)
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            total_chars += len(item.get("text", ""))
            return total_chars
        
        return 0
    
    async def _calculate_base_score(
        self,
        result: utility_models.QueryResult,
        payload: Dict[str, Any],
        task_config: Any,
        metric: float,
        stream_metric: float
    ) -> float:

        if not result.success or result.status_code != 200:
            return 0.0
        
        if result.response_time and result.response_time > 30:
            return 0.1
        
        base_score = 0.5
        
        if result.task.startswith("chat-"):
            base_score = await self._score_chat_task(result, payload, metric, stream_metric)
        elif result.task.startswith("text-to-image"):
            base_score = await self._score_image_task(result, payload, metric)
        elif result.task.startswith("image-to-image"):
            base_score = await self._score_image_task(result, payload, metric)
        elif result.task.startswith("avatar"):
            base_score = await self._score_avatar_task(result, payload, metric)
        else:
            base_score = await self._score_generic_task(result, payload, metric, stream_metric)
        
        return base_score
    
    async def _score_chat_task(
        self,
        result: utility_models.QueryResult,
        payload: Dict[str, Any],
        metric: float,
        stream_metric: float
    ) -> float:
        score = 0.5
        
        if result.formatted_response:
            content = ""

            first_block = None
            try:
                if isinstance(result.formatted_response, list):
                    first_block = result.formatted_response[0] if result.formatted_response else None
                elif isinstance(result.formatted_response, dict):
                    first_block = result.formatted_response
                else:
                    logger.warning(f"Unsupported formatted_response type: {type(result.formatted_response)}")
            except Exception as e:
                logger.warning(f"Failed to parse formatted_response head: {e}")

            if first_block is not None:
                choices = None
                if isinstance(first_block, dict):
                    choices = first_block.get("choices")
                else:
                    choices = getattr(first_block, "choices", None)

                choice = None
                if isinstance(choices, list) and choices:
                    choice = choices[0]
                elif isinstance(choices, dict):
                    choice = choices
                else:
                    logger.warning(f"Invalid choices in formatted_response: {choices}")

                if choice is not None:
                    if isinstance(choice, dict):
                        if "message" in choice and isinstance(choice["message"], dict):
                            content = choice["message"].get("content", "") or ""
                        elif "delta" in choice and isinstance(choice["delta"], dict):
                            content = choice["delta"].get("content", "") or ""
                    else:
                        if hasattr(choice, "message") and getattr(choice, "message"):
                            try:
                                content = (choice.message.get("content", "")  # type: ignore[attr-defined]
                                           if isinstance(choice.message, dict) else
                                           getattr(choice.message, "content", ""))
                            except Exception:
                                content = getattr(choice.message, "content", "")
                        elif hasattr(choice, "delta") and getattr(choice, "delta"):
                            try:
                                content = (choice.delta.get("content", "")  # type: ignore[attr-defined]
                                           if isinstance(choice.delta, dict) else
                                           getattr(choice.delta, "content", ""))
                            except Exception:
                                content = getattr(choice.delta, "content", "")

            if isinstance(content, str) and content:
                response_length = len(content)
                if response_length > 10:
                    score += 0.2

                lowered = content.lower()
                if any(keyword in lowered for keyword in ["hello", "hi"]):
                    score += 0.1
        
        if metric > 0:
            if metric > 100:
                score += 0.2
            elif metric > 50:
                score += 0.1
        
        if stream_metric > 0:
            if stream_metric > 50:
                score += 0.1
        
        return min(1.0, score)
    
    async def _score_image_task(
        self,
        result: utility_models.QueryResult,
        payload: Dict[str, Any],
        metric: float
    ) -> float:
        score = 0.5
        
        if result.response_time and result.response_time < 10:
            score += 0.2
        elif result.response_time and result.response_time < 20:
            score += 0.1
        
        if metric > 0:
            if metric > 50:
                score += 0.2
            elif metric > 20:
                score += 0.1
        
        return min(1.0, score)
    
    async def _score_avatar_task(
        self,
        result: utility_models.QueryResult,
        payload: Dict[str, Any],
        metric: float
    ) -> float:
        score = 0.5
        
        if result.response_time and result.response_time < 30:
            score += 0.2
        elif result.response_time and result.response_time < 60:
            score += 0.1
        
        if metric > 0:
            if metric > 30:
                score += 0.2
            elif metric > 10:
                score += 0.1
        
        return min(1.0, score)
    
    async def _score_generic_task(
        self,
        result: utility_models.QueryResult,
        payload: Dict[str, Any],
        metric: float,
        stream_metric: float
    ) -> float:
        score = 0.5
        
        if result.response_time and result.response_time < 15:
            score += 0.2
        elif result.response_time and result.response_time < 30:
            score += 0.1
        
        if metric > 0:
            if metric > 100:
                score += 0.2
            elif metric > 50:
                score += 0.1
        
        return min(1.0, score)
    
    def _apply_quality_adjustments(
        self,
        base_score: float,
        result: utility_models.QueryResult,
        metric: float,
        stream_metric: float
    ) -> float:

        adjusted_score = base_score
        
        if result.status_code == 200:
            adjusted_score *= 1.0
        elif result.status_code == 400:
            adjusted_score *= 0.3
        elif result.status_code == 429:
            adjusted_score *= 0.2
        elif result.status_code == 500:
            adjusted_score *= 0.1
        else:
            adjusted_score *= 0.5
        
        if metric > 0:
            performance_factor = min(metric / 100, 1.0)
            adjusted_score *= (0.8 + 0.2 * performance_factor)
        
        if stream_metric > 0:
            stream_factor = min(stream_metric / 50, 1.0)
            adjusted_score *= (0.9 + 0.1 * stream_factor)
        
        return adjusted_score
    
    async def score_multiple_results(
        self,
        results: Dict[str, utility_models.QueryResult],
        payload: Dict[str, Any],
        task_config: Any
    ) -> Dict[int, float]:

        node_scores = {}
        
        for node_id, result in results.items():
            score = await self.score_result(result, payload, task_config, node_id)
            node_scores[node_id] = score
        
        return node_scores

scoring_system = LocalScoringSystem() 