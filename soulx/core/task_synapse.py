# MIT License
import typing
import bittensor as bt
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class NPCResponse:
    dialogue_response: str
    metrics: Dict[str, float]
    memory_references: Optional[List[str]] = None
    emotions: Optional[List[str]] = None
    actions: Optional[List[str]] = None

class TaskSynapse(bt.Synapse):

    task_id: typing.Optional[str] = None
    task_text: typing.Optional[str] = None
    task_metadata: typing.Optional[dict] = None
    blocks_allocated: typing.Optional[int] = None
    signature: typing.Optional[str] = None
    

    scene_description: typing.Optional[str] = None
    npc_profile: typing.Optional[dict] = None
    player_goal: typing.Optional[dict] = None
    dialogue_history: typing.Optional[List[Dict[str, str]]] = None
    

    response: typing.Optional[dict] = None
    npc_response: typing.Optional[NPCResponse] = None
    response_time: typing.Optional[float] = None
    success: typing.Optional[bool] = None
    error_message: typing.Optional[str] = None
    

    miner_hotkey: typing.Optional[str] = None
    validator_hotkey: typing.Optional[str] = None
    timestamp: typing.Optional[int] = None
    

    miner_uid: typing.Optional[str] = None
    miner_history: typing.Optional[dict] = None
    total_tasks_completed: typing.Optional[int] = None
    recent_failures: typing.Optional[int] = None
    current_task: typing.Optional[dict] = None
    
    def deserialize(self) -> dict:
        base_data = {
            'task_id': self.task_id,
            'task_text': self.task_text,
            'task_metadata': self.task_metadata,
            'blocks_allocated': self.blocks_allocated,
            
            'response': self.response,
            'response_time': self.response_time,
            'success': self.success,
            'error_message': self.error_message,
            
            'signature': self.signature,
            'miner_hotkey': self.miner_hotkey,
            'validator_hotkey': self.validator_hotkey,
            'timestamp': self.timestamp,
            
            'miner_uid': self.miner_uid,
            'miner_history': self.miner_history,
            'total_tasks_completed': self.total_tasks_completed,
            'recent_failures': self.recent_failures,
            'current_task': self.current_task,
        }
        

        if self.scene_description:
            base_data.update({
                'scene_description': self.scene_description,
                'npc_profile': self.npc_profile,
                'player_goal': self.player_goal,
                'dialogue_history': self.dialogue_history,
                'npc_response': self.npc_response.__dict__ if self.npc_response else None
            })
            
        return base_data 