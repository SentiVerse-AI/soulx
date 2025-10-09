#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from soulx.validator.scoring_system import scoring_system

logger = logging.getLogger(__name__)

@dataclass
class ScoringResult:
    hotkey: str
    node_id: int
    task: str
    quality_score: float
    timestamp: datetime
    synthetic_query: bool
    response_time: float
    success: bool
    status_code: int


class ScoringResultsManager:

    def __init__(self):
        self.scoring_results: Dict[str, List[ScoringResult]] = {}  # hotkey -> [ScoringResult]
        self.historical_scores: Dict[str, float] = {}  # hotkey -> historical_score
    
    def add_scoring_result(self, result: ScoringResult):
        if result.hotkey not in self.scoring_results:
            self.scoring_results[result.hotkey] = []
        
        self.scoring_results[result.hotkey].append(result)

    def get_current_cycle_score(self, hotkey: str) -> float:
        if hotkey not in self.scoring_results:
            return 0.0
        
        results = self.scoring_results[hotkey]
        if not results:
            return 0.0
        
        avg_score = sum(r.quality_score for r in results) / len(results)

        return avg_score
    

    
    def get_historical_score(self, hotkey: str) -> float:
        return self.historical_scores.get(hotkey, 0.0)
    
    def _start_new_cycle(self):

        for hotkey in self.scoring_results.keys():
            results = self.scoring_results[hotkey]
            if results:
                current_score = sum(r.quality_score for r in results) / len(results)
                
                historical_score = self.historical_scores.get(hotkey, 0.0)
                if historical_score == 0.0:
                    self.historical_scores[hotkey] = current_score
                else:
                    alpha = 0.3
                    self.historical_scores[hotkey] = alpha * current_score + (1 - alpha) * historical_score
        
        cutoff_time = datetime.now() - timedelta(hours=24)
        for hotkey in list(self.scoring_results.keys()):
            self.scoring_results[hotkey] = [
                r for r in self.scoring_results[hotkey] 
                if r.timestamp >= cutoff_time
            ]
        
    def clear_current_cycle_scores(self):
        self.scoring_results.clear()
        self.historical_scores.clear()

    def get_all_scoring_results(self, hotkey: str) -> List[ScoringResult]:
        return self.scoring_results.get(hotkey, [])
    
    def get_current_cycle_results(self, hotkey: str) -> List[ScoringResult]:
        if hotkey not in self.scoring_results:
            return []
        
        return self.scoring_results[hotkey]
    
    def get_all_current_scores(self) -> Dict[str, float]:
        scores = {}
        for hotkey in self.scoring_results.keys():
            scores[hotkey] = self.get_current_cycle_score(hotkey)
        return scores
    
    def get_all_historical_scores(self) -> Dict[str, float]:
        return self.historical_scores.copy()
    
    def get_node_stats(self, hotkey: str) -> Dict[str, any]:
        results = self.scoring_results.get(hotkey, [])
        if not results:
            return {
                'total_tasks': 0,
                'successful_tasks': 0,
                'avg_quality_score': 0.0,
                'avg_response_time': 0.0,
                'current_cycle_score': 0.0,
                'historical_score': 0.0
            }
        
        successful_results = [r for r in results if r.success]
        
        return {
            'total_tasks': len(results),
            'successful_tasks': len(successful_results),
            'avg_quality_score': sum(r.quality_score for r in results) / len(results),
            'avg_response_time': sum(r.response_time for r in results) / len(results),
            'current_cycle_score': self.get_current_cycle_score(hotkey),
            'historical_score': self.get_historical_score(hotkey)
        }

scoring_results_manager = ScoringResultsManager()