# -*- coding: utf-8 -*-

from datetime import datetime
import enum
from typing import Optional, Any

from pydantic import BaseModel
from pydantic.fields import Field

class RewardData(BaseModel):
    id: str
    task: str
    node_id: int
    quality_score: float
    validator_hotkey: str
    node_hotkey: str
    synthetic_query: bool
    metric: float | None = None
    stream_metric: float | None = None
    response_time: float | None = None
    volume: float | None = None
    created_at: datetime = Field(default_factory=datetime.now)

    def dict(self):  # type: ignore
        return {
            "id": self.id,
            "task": self.task,
            "node_id": self.node_id,
            "quality_score": self.quality_score,
            "validator_hotkey": self.validator_hotkey,
            "node_hotkey": self.node_hotkey,
            "synthetic_query": self.synthetic_query,
            "metric": self.metric,
            "stream_metric": self.stream_metric,
            "response_time": self.response_time,
            "volume": self.volume,
            "created_at": self.created_at.isoformat(),  # Convert datetime to ISO string
        }


class QueryResult(BaseModel):
    formatted_response: Any
    node_id: Optional[int]
    node_hotkey: Optional[str]
    response_time: Optional[float]
    stream_time: Optional[float]
    task: str
    status_code: Optional[int]
    success: bool
    created_at: datetime = Field(default_factory=datetime.now)


class ImageHashes(BaseModel):
    average_hash: str = ""
    perceptual_hash: str = ""
    difference_hash: str = ""
    color_hash: str = "" 