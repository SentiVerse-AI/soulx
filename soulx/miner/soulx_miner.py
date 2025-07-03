import time
import os
import random
from typing import Optional, Dict, Any, Tuple, List
from dotenv import load_dotenv

import bittensor as bt
from bittensor import logging

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from soulx.miner import BaseMiner
from soulx.core.allocation import AllocationManager, TaskAllocation
from soulx.core.constants import DEFAULT_ALLOCATION_STRATEGY, DEFAULT_MODEL_NAME, BLOCK_TIME, DEFAULT_LOG_PATH, BAD_COLDKEYS, U16_MAX, MIN_VALIDATOR_STAKE_DTAO
from soulx.core.path_utils import PathUtils
from soulx.core.validator_manager import ValidatorManager
from soulx.core.task_type import TaskType
from soulx.core.task_synapse import TaskSynapse
from soulx.core.hardware_check import HardwareChecker
from soulx.core.validator_whitelist import ValidatorWhitelistManager

class SoulxAIMiner(BaseMiner):

    def __init__(self):
        project_root = PathUtils.get_project_root()
        log_path = os.getenv("LOG_PATH", DEFAULT_LOG_PATH)
        self.log_dir = project_root / log_path
        self.log_dir.mkdir(parents=True, exist_ok=True)

        super().__init__()

        self.check_requirements()

        self.model_name = os.getenv("MODEL_NAME", DEFAULT_MODEL_NAME)
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model.to(self.device)
        
        self.allocation_manager = AllocationManager(self.config)
        
        self.validator_manager = ValidatorManager(self.storage)
        
        self.current_allocation: Optional[TaskAllocation] = None
        self.allocation_strategy = os.getenv("ALLOCATION_STRATEGY", DEFAULT_ALLOCATION_STRATEGY)
        
        self.current_task: Optional[Dict[str, Any]] = None
        
        self.performance_metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "average_response_time": 0.0,
            "total_blocks_completed": 0,
            "current_blocks_allocated": 0
        }

        self.whitelist_manager = ValidatorWhitelistManager(hotkey=self.miner_hotkey, use_database= False)
        

    def check_requirements(self):

        hardware_passed, hardware_results = HardwareChecker.check_hardware()
        
        model_name = os.getenv("MODEL_NAME", "SentiVerse-AI/SoulX")
        model_passed, model_info = HardwareChecker.check_model_availability(model_name)

        if not hardware_passed:
            raise RuntimeError("Hardware requirements not met. Please check the logs for details.")
            
        if not model_passed:
            raise RuntimeError(f"Model {model_name} is not installed. Please install it first.")
            
    def setup_logging_path(self) -> None:
        self.config.full_path = str( f"{self.log_dir}/miner/{self.config.wallet.name}/{self.config.wallet.hotkey}/netuid{self.config.netuid}")
        os.makedirs(self.config.full_path, exist_ok=True)

        self.config.logging.logging_dir = self.config.full_path
        self.config.record_log = True

    async def forward(self, dendrite, validator_hotkey: str) -> float:
        start_time = time.time()
        
        try:
            validator_uid = self.metagraph.hotkeys.index(validator_hotkey)
            if validator_uid is None:
                return 0.0
                
            axon_info = self.metagraph.axons[validator_uid]
            if not axon_info:
                return 0.0

            if isinstance(axon_info, dict):
                if not axon_info.get('ip') or not axon_info.get('port'):
                    return 0.0
                    
                validator_axon = bt.axon(
                    wallet=self.wallet,
                    ip="0.0.0.0",
                    port=8091
                )
            else:
                validator_axon = axon_info
                
            if not self.current_task:
                try:
                    synapse = TaskSynapse()
                    
                    synapse.miner_hotkey = self.wallet.hotkey.ss58_address
                    synapse.validator_hotkey = validator_hotkey
                    synapse.timestamp = int(time.time())
                    synapse.miner_uid = str(self.uid)

                    miner_history = self.storage.get(f"miner_history_{self.uid}", {})
                    synapse.miner_history = miner_history
                    synapse.total_tasks_completed = self.performance_metrics["successful_requests"]
                    synapse.recent_failures = miner_history.get("recent_failures", 0)
                    synapse.current_task = self.current_task


                    response = await self._dendrite.forward(
                        validator_axon,
                        synapse,
                        deserialize=True,
                        timeout=10.0
                    )

                    if not response or not response.get("success",False) or not hasattr(synapse, 'task_id'):
                        return 0.0

                    synapse.task_id = response.get("task_id")
                    synapse.task_text = response.get("task_text")
                    synapse.task_metadata = response.get("task_metadata")
                    synapse.blocks_allocated = response.get("blocks_allocated")
                    self.current_task = {
                        'task_id': synapse.task_id,
                        'text': synapse.task_text,
                        'metadata': synapse.task_metadata,
                        'blocks_allocated': synapse.blocks_allocated
                    }
                    
                    task_result = self._process_task(self.current_task)
                    
                    synapse.response = task_result
                    response_time = time.time() - start_time
                    synapse.response_time = response_time
                    
                    success = task_result is not None and "error" not in task_result
                    self.update_performance_metrics(success, response_time)
                    
                    miner_history = self.storage.get(f"miner_history_{self.uid}", {})
                    if success:
                        miner_history["current_task"] = None
                    else:
                        miner_history["current_task"] = self.current_task
                    self.storage.set(f"miner_history_{self.uid}", miner_history)
                    
                    synapse.miner_history = miner_history
                    synapse.total_tasks_completed = self.performance_metrics["successful_requests"]
                    synapse.recent_failures = miner_history.get("recent_failures", 0)
                    synapse.current_task = None if success else self.current_task
                    
                    response = await self._dendrite.forward(
                        validator_axon,
                        synapse,
                        deserialize=True,
                        timeout=10.0
                    )

                    if success:
                        self.current_task = None
                    
                    return 1.0 if response.get("response") is not None else 0.0
                    
                except Exception as e:
                    self.update_performance_metrics(False, time.time() - start_time)
                    return 0.0
                
        except Exception as e:
            self.update_performance_metrics(False, time.time() - start_time)
            return 0.0
            
    def _process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        try:
            task_category = task['metadata'].get('category', '')
            task_type = TaskType(task_category) if task_category else TaskType.TEXT_CLASSIFICATION
            
            if task_type in [TaskType.SENTIMENT_ANALYSIS, TaskType.EMOTION_ANALYSIS, TaskType.NPC_DIALOGUE]:
                return self._process_text_sentiment(task)
            elif task_type == TaskType.SCENE_UNDERSTANDING:
                return self._process_scene_understanding(task)
            elif task_type == TaskType.OBJECT_DETECTION:
                return self._process_object_detection(task)
            else:
                return self._process_text_classification(task)
                
        except Exception as e:
            return {"error": str(e)}

    def _process_npc_dialogue(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """处理NPC对话任务"""
        try:
            # 获取任务上下文
            scene_description = task['metadata'].get('scene_description', '')
            npc_profile = task['metadata'].get('npc_profile', {})
            player_goal = task['metadata'].get('player_goal', {})
            dialogue_history = task['metadata'].get('dialogue_history', [])
            
            # 使用模型生成NPC回应
            context = f"""
            场景: {scene_description}
            NPC角色: {npc_profile.get('name', '')}
            种族: {npc_profile.get('race', '')}
            年龄: {npc_profile.get('age', '')}
            性格特征: {', '.join(npc_profile.get('character_traits', []))}
            对话风格: {', '.join(npc_profile.get('dialogue_style', []))}
            描述: {npc_profile.get('description', '')}
            """
            
            # 构建对话历史
            dialogue_context = "\n".join([
                f"{turn['turn']}: {turn['dialogue']}"
                for turn in dialogue_history
            ])
            
            inputs = self.tokenizer(
                context + "\n对话历史:\n" + dialogue_context,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True
            ).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                # 这里需要根据实际模型输出进行处理
                response_text = "这是一个测试回应"  # 实际应该用模型生成的回应
                
            # 评估指标
            consistency = self._evaluate_consistency(response_text, npc_profile)
            memory = self._evaluate_memory(response_text, dialogue_history)
            creativity = self._evaluate_creativity(response_text)
            goal_driven = self._evaluate_goal_driven(response_text, player_goal)
            
            return {
                "dialogue_response": response_text,
                "metrics": {
                    "consistency": consistency,
                    "memory": memory,
                    "creativity": creativity,
                    "goal_driven": goal_driven
                },
                "memory_references": self._extract_memory_references(response_text, dialogue_history),
                "emotions": self._extract_emotions(response_text),
                "actions": self._extract_actions(response_text)
            }
            
        except Exception as e:
            return {"error": str(e)}
            
    def _evaluate_consistency(self, response: str, npc_profile: Dict) -> float:
        """评估回应与NPC角色设定的一致性"""
        try:
            # 这里应该实现具体的一致性评估逻辑
            # 例如检查是否符合性格特征、对话风格等
            return 0.85  # 示例分数
        except:
            return 0.5
            
    def _evaluate_memory(self, response: str, dialogue_history: List) -> float:
        """评估回应对之前对话的引用程度"""
        try:
            # 实现记忆评估逻辑
            # 检查是否引用了之前的对话内容
            return 0.8  # 示例分数
        except:
            return 0.5
            
    def _evaluate_creativity(self, response: str) -> float:
        """评估回应的创造性和自然度"""
        try:
            # 实现创造性评估逻辑
            # 检查是否有独特的表达方式
            return 0.9  # 示例分数
        except:
            return 0.5
            
    def _evaluate_goal_driven(self, response: str, player_goal: Dict) -> float:
        """评估回应是否推动任务目标"""
        try:
            # 实现目标导向评估逻辑
            # 检查是否帮助玩家达成目标
            return 0.85  # 示例分数
        except:
            return 0.5
            
    def _extract_memory_references(self, response: str, dialogue_history: List) -> List[str]:
        """提取回应中对之前对话的引用"""
        try:
            # 实现记忆引用提取逻辑
            return ["之前提到的信息"]  # 示例引用
        except:
            return []
            
    def _extract_emotions(self, response: str) -> List[str]:
        """提取回应中的情感状态"""
        try:
            # 实现情感提取逻辑
            return ["好奇", "谨慎"]  # 示例情感
        except:
            return []
            
    def _extract_actions(self, response: str) -> List[str]:
        """提取回应中的动作描述"""
        try:
            # 实现动作提取逻辑
            return ["摸了摸下巴", "环顾四周"]  # 示例动作
        except:
            return []
            
    def _process_text_sentiment(self, task: Dict[str, Any]) -> Dict[str, Any]:
        try:
            inputs = self.tokenizer(
                task['text'],
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True
            ).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
                sentiment_score = probabilities[0][1].item()
                
            return {
                "sentiment_score": sentiment_score,
                "description": "Positive" if sentiment_score > 0.5 else "Negative",
                "confidence": sentiment_score if sentiment_score > 0.5 else 1 - sentiment_score
            }
            
        except Exception as e:
            return {"error": str(e)}
            
    def _process_scene_understanding(self, task: Dict[str, Any]) -> Dict[str, Any]:
        try:
            inputs = self.tokenizer(
                task['text'],
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True
            ).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
                
            return {
                "description": task['text'],
                "confidence": probabilities.max().item()
            }
            
        except Exception as e:
            return {"error": str(e)}
            
    def _process_object_detection(self, task: Dict[str, Any]) -> Dict[str, Any]:
        try:

            return {
                "objects": ["placeholder_object"],
                "confidence": 0.8
            }
            
        except Exception as e:
            return {"error": str(e)}
            
    def _process_text_classification(self, task: Dict[str, Any]) -> Dict[str, Any]:
        try:
            inputs = self.tokenizer(
                task['text'],
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True
            ).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
                predicted_class = torch.argmax(probabilities).item()
                confidence = probabilities[0][predicted_class].item()
                
            return {
                "class_id": predicted_class,
                "confidence": confidence,
                "description": f"Class {predicted_class}"
            }
            
        except Exception as e:
            return {"error": str(e)}
            
    def update_performance_metrics(self, success: bool, response_time: float):
        self.performance_metrics["total_requests"] += 1
        if success:
            self.performance_metrics["successful_requests"] += 1
            
        n = self.performance_metrics["total_requests"]
        old_avg = self.performance_metrics["average_response_time"]
        self.performance_metrics["average_response_time"] = (old_avg * (n-1) + response_time) / n
        
    def get_performance_stats(self) -> Dict:
        if self.performance_metrics["total_requests"] == 0:
            return {
                "success_rate": 0.0,
                "average_response_time": 0.0,
                "total_blocks_completed": self.performance_metrics["total_blocks_completed"],
                "current_blocks_allocated": self.performance_metrics["current_blocks_allocated"]
            }
            
        return {
            "success_rate": self.performance_metrics["successful_requests"] / self.performance_metrics["total_requests"],
            "average_response_time": self.performance_metrics["average_response_time"],
            "total_blocks_completed": self.performance_metrics["total_blocks_completed"],
            "current_blocks_allocated": self.performance_metrics["current_blocks_allocated"]
        }
        
    def switch_allocation_strategy(self, strategy: str):
        if strategy not in ["stake", "equal"]:
            raise ValueError(f"Unknown allocation strategy: {strategy}")
        self.allocation_strategy = strategy
        self.current_allocation = None

    def get_next_sync_block(self) -> tuple[int, str]:

        if not self.current_task:
            blocks_per_sync = 0.2 * 60 // BLOCK_TIME
            next_sync = self.current_block + (
                blocks_per_sync - (self.current_block % blocks_per_sync)
            )
            sync_reason = "No schedule"
            return next_sync, sync_reason

        next_sync = self.current_block + (
                self.blocks_per_sync - (self.current_block % self.blocks_per_sync)
        )
        sync_reason = "Regular interval"
        blocks_until_epoch = self.blocks_until_next_epoch()
        if blocks_until_epoch > 0 and blocks_until_epoch <  self.blocks_per_sync:
            next_sync = self.current_block + blocks_until_epoch
            sync_reason = "Epoch boundary"

        if self.current_task and self.current_task.get('blocks_allocated'):
            blocks_remaining = self.current_task['blocks_allocated']
            task_end_block = self.current_block + blocks_remaining
            if task_end_block < next_sync:
                next_sync = task_end_block
                sync_reason = "Task completion"

        return next_sync, sync_reason

    async def run(self):

        next_sync_block, sync_reason = self.get_next_sync_block()
        while True:
            try:
                if self.subtensor.wait_for_block(next_sync_block):
                    next_sync_block, sync_reason = self.get_next_sync_block()
                    
                    validator_hotkey = self.get_priority_validator()
                    if validator_hotkey is None:
                        continue
                        
                    response = await self.forward(self._dendrite, validator_hotkey)
                    
                    if response > 0:
                        self.performance_metrics["total_blocks_completed"] += 1
                        
                    if self.current_block % 100 == 0:
                        stats = self.get_performance_stats()

                        
            except KeyboardInterrupt:
                logging.success("Keyboard interrupt detected. Exiting miner.")
                break
            except Exception as e:
                logging.error(f"Error in miner loop: {str(e)}")
                continue
                
    def get_priority_validator(self) -> Optional[Tuple[int, str]]:

        try:
            validator_trust = self.subtensor.query_subtensor(
                "ValidatorTrust",
                params=[self.config.netuid],
            )

            neurons = self.subtensor.neurons_lite(netuid=self.config.netuid)
            
            validators = []
            for idx, trust in enumerate(validator_trust):
                if trust <= 0:
                    continue
                    
                try:
                    neuron = neurons[idx]
                    stake = float(neuron.stake)

                    check_validator_stake = os.getenv("CHECK_VALIDATOR_STAKE", "true").lower() == "true"
                    if check_validator_stake and stake < MIN_VALIDATOR_STAKE_DTAO:
                        continue

                    if self.metagraph.axons[idx].ip in self.config.blacklist:
                        continue

                    if self.metagraph.coldkeys[idx] in BAD_COLDKEYS:
                        continue
                        
                    if not bool(neuron.active):
                        continue

                    validator_hotkey = self.metagraph.hotkeys[idx]
                    if self.whitelist_manager.is_validator_blacklisted(validator_hotkey):
                        continue

                    normalized_trust = trust / U16_MAX
                    validators.append((idx, normalized_trust, stake))
                    
                except Exception as e:
                    continue
                    
            if not validators:
                return None

            validators.sort(key=lambda x: (x[1], x[2]), reverse=True)

            chosen_validator = random.choice(validators)
            validator_uid = chosen_validator[0]
            validator_hotkey = self.metagraph.hotkeys[validator_uid]
            
            return validator_hotkey
            
        except Exception as e:
            return None

    def get_validator_stats(self, validator_hotkey: str) -> Optional[Dict]:
        return self.validator_manager.get_validator_info(validator_hotkey)
        
    def emergency_unlock_validator(self):
        self.validator_manager.emergency_unlock()


if __name__ == "__main__":
    import asyncio
    import argparse

    miner_env = PathUtils.get_env_file_path("miner")
    default_env = PathUtils.get_env_file_path()
    
    if miner_env.exists():
        load_dotenv(miner_env)
    else:
        load_dotenv(default_env)
        
    miner = SoulxAIMiner()
    asyncio.run(miner.run())