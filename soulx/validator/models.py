# -*- coding: utf-8 -*-

from dataclasses import dataclass
from typing import Optional


@dataclass
class Contender:
    contender_id: str
    node_hotkey: str
    validator_hotkey: str
    task: str
    node_id: int
    netuid: int
    capacity: float
    raw_capacity: float
    capacity_to_score: float
    total_requests_made: int
    requests_429: int
    requests_500: int
    period_score: float 