import time
import os
import numpy as np
import random
import logging as python_logging
import asyncio
import threading
from typing import Tuple, Optional, List, Dict, Any

from dotenv import load_dotenv
from tabulate import tabulate

import bittensor as bt
from bittensor import logging

from soulx.core.config_manager import ConfigManager

from soulx.core.constants import (
    VERSION_KEY,
    MIN_VALIDATOR_STAKE_DTAO,
    MIN_MINER_STAKE_DTAO,
    OWNER_DEFAULT_SCORE,
    FINAL_MIN_SCORE,
    MAX_VALIDATOR_BLOCKS,
    CHECK_NODE_ACTIVE
)
from soulx.core.path_utils import PathUtils
from soulx.core.validator_config import ValidatorConfig, load_validator_config
from soulx.validator import BaseValidator

from soulx.core.validator_manager import ValidatorManager

from soulx.core.task_synapse import TaskSynapse

from soulx.validator.task_client import CognifyTaskClient
from soulx.validator.task_processor import CognifyTaskProcessor
from soulx.validator.redis_queue_manager import RedisQueueManager, CognifyQueueProcessor
from soulx.validator.contender_client import ContenderClient
from soulx.validator.task_config_client import TaskConfigClient
from soulx.validator.system_client import SystemClient

import httpx
from fiber.encrypted.validator import handshake, client
from fiber.chain.models import Node

# Constants


class SoulxValidator(BaseValidator):
    
    def __init__(self):

        self.validator_config = load_validator_config()

        self.allocation_strategy = self.validator_config.allocation_strategy

        project_root = PathUtils.get_project_root()
        log_path = self.validator_config.log_path
        self.log_dir = project_root / log_path
        self.log_dir.mkdir(parents=True, exist_ok=True)

        super().__init__()

        self.validator_manager = ValidatorManager(self.storage)

        self.setup_bittensor_objects()
        
        if self.validator_config.check_validator_stake:
            self.check_validator_stake()
        
        self.current_block = 0
        self.eval_interval = self.config.eval_interval
        self.last_update = 0
        
        self.config_manager = ConfigManager(
            config_url=self.validator_config.validator_config_url,
            hotkey=self.validator_hotkey,
            validator_token=self.validator_config.validator_token
        )

        self.total_blocks_run = 0
        
        self.blocks_since_last_weights = 0

        self.alpha = 0.95
        
        self.weights_interval = self.tempo * 1/2
        self.miner_tasks: Dict[str, str] = {}

        self.node_handshake_data: Dict[str, Dict[str, Any]] = {}
        self.handshake_interval = 600
        self.last_handshake_time = 0
        self.handshake_thread = None
        self.handshake_running = False
        self.cached_nodes_info = []

        if not self.config.neuron.axon_off:
            logging.info("Initializing Axon server...")

            self.axon = bt.axon(
                wallet=self.wallet,
                config=self.config,
            )
            
            self.axon.start()
            
            self.subtensor.serve_axon(
                netuid=self.config.netuid,
                axon=self.axon,
            )

        self._init_task_processing()
    
    def _init_task_processing(self):
        try:
            config_server_url = self.validator_config.config_server_url
            validator_token = self.validator_config.validator_token
            
            redis_host = self.validator_config.redis_host
            redis_port = self.validator_config.redis_port
            redis_password = self.validator_config.redis_password

            validator_hotkey = self.validator_hotkey
            
            self.task_client = CognifyTaskClient(
                base_url=config_server_url,
                validator_hotkey=validator_hotkey,
                token=validator_token
            )
            
            self.contender_client = ContenderClient(
                base_url=config_server_url,
                validator_hotkey=validator_hotkey,
                token=validator_token
            )

            self.task_config_client = TaskConfigClient(
                base_url=config_server_url,
                validator_hotkey=validator_hotkey,
                token=validator_token
            )
            
            self.system_client = SystemClient(
                base_url=config_server_url,
                validator_hotkey=validator_hotkey,
                token=validator_token
            )
            
            self.queue_manager = RedisQueueManager(redis_host, redis_port, redis_password)
            
            self.queue_processor = CognifyQueueProcessor(
                self.queue_manager, 
                self.task_client, 
                self.contender_client, 
                self.task_config_client,
                node_handshake_data=self.node_handshake_data,
                validator_config=self.validator_config
            )
            
            self.task_processor = CognifyTaskProcessor(self.task_client, self.queue_manager)
            
        except Exception as e:
            logging.error(f"Failed to initialize task processing components: {e}")
            self.task_client = None
            self.task_processor = None
            self.queue_manager = None
            self.queue_processor = None
            self.contender_client = None
            self.task_config_client = None

    async def _run_queue_processor(self):
        try:
            await self.queue_manager.connect()
            
            await self.queue_processor.run_queue_processor()
        except Exception as e:
            logging.error(f"Error in queue processor: {e}")

    def check_validator_stake(self):

        try:

            neurons = self.subtensor.neurons_lite(netuid=self.config.netuid)
            validator_uid = self.metagraph.hotkeys.index(self.wallet.hotkey.ss58_address)
            validator_stake = float(neurons[validator_uid].stake)

            if validator_stake < MIN_VALIDATOR_STAKE_DTAO:
                raise ValueError(
                    f"Validator stake ({validator_stake:.2f} τ) is below minimum requirement "
                    f"({MIN_VALIDATOR_STAKE_DTAO} τ)"
                )
            
        except Exception as e:
            logging.error(f"Failed to verify validator stake: {str(e)}")
            raise

    def setup_logging_path(self) -> None:

        self.config.full_path = str( f"{self.log_dir}/validator/{self.config.wallet.name}/{self.config.wallet.hotkey}/netuid{self.config.netuid}")
        os.makedirs(self.config.full_path, exist_ok=True)
        
        self.config.logging_dir = self.config.full_path
        self.config.record_log = True

    def run(self):
        if self.config.state == "restore":
            self.restore_state_and_evaluate()
        else:
            self.resync_metagraph()

        next_sync_block = self.current_block + self.eval_interval
        bt.logging.info(f"Next sync at block {next_sync_block}")
        
        task_processing_thread = None
        queue_processing_thread = None
        
        if self.queue_processor:
            def run_queue_processor():
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._run_queue_processor())
                except Exception as e:
                    bt.logging.error(f"Error in queue processor: {e}")
                finally:
                    loop.close()
            
            queue_processing_thread = threading.Thread(target=run_queue_processor, daemon=True)
            queue_processing_thread.start()

        if self.task_processor:
            def run_task_processor():
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.task_processor.run_task_processor())
                except Exception as e:
                    bt.logging.error(f"Error in task processor: {e}")
                finally:
                    loop.close()
            
            task_processing_thread = threading.Thread(target=run_task_processor, daemon=True)
            task_processing_thread.start()

        self._cache_nodes_info()
        
        self._start_handshake_timer()

        try:
            while True:
                try:
                    if self.subtensor.wait_for_block(next_sync_block):
                        self.resync_metagraph()
                        self.refresh_cached_nodes()
                        self.total_blocks_run += self.eval_interval
                        self.blocks_since_last_weights += self.eval_interval

                        blocks_since_last = self.subtensor.blocks_since_last_update(
                            self.config.netuid,
                            self.uid
                        )
                        
                        if blocks_since_last >= self.weights_interval and self.blocks_since_last_weights >= self.weights_interval :
                            success, msg = self.set_weights()
                            consensus = self.metagraph.consensus[self.uid].item()
                            incentive = self.metagraph.incentive[self.uid].item()
                            dividends = self.metagraph.dividends[self.uid].item()
                            current_epoch =  self.current_block // 360
                            if success:
                                self.blocks_since_last_weights = 0
                            else:
                                bt.logging.error(f"Failed to set weights: {msg}")
                                continue

                        self.save_state()
                        validator_trust = self.subtensor.query_subtensor(
                            "ValidatorTrust",
                            params=[self.config.netuid],
                        )

                        next_sync_block, reason = self.get_next_sync_block()

                except KeyboardInterrupt:
                    bt.logging.success("Keyboard interrupt detected. Exiting validator.")
                    break
                except Exception as e:
                    bt.logging.error(f"Error in validator loop: {str(e)}")
                    continue
        finally:
            if task_processing_thread and task_processing_thread.is_alive():
                if self.task_processor:
                    self.task_processor.stop()
                task_processing_thread.join(timeout=5)

            if self.task_client:
                try:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.task_client.close())
                    loop.close()
                except Exception as e:
                    bt.logging.error(f"Error closing task client: {e}")
            
            if queue_processing_thread and queue_processing_thread.is_alive():
                if self.queue_processor:
                    self.queue_processor.stop()
                queue_processing_thread.join(timeout=5)

                if self.queue_manager:
                    try:
                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self.queue_manager.close())
                        loop.close()
                    except Exception as e:
                        bt.logging.error(f"Error closing Redis connection: {e}")
                
                if hasattr(self, 'contender_client') and self.contender_client:
                    try:
                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self.contender_client.close())
                        loop.close()
                    except Exception as e:
                        bt.logging.error(f"Error closing contender client: {e}")
                
                if hasattr(self, 'task_config_client') and self.task_config_client:
                    try:
                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self.task_config_client.close())
                        loop.close()
                    except Exception as e:
                        bt.logging.error(f"Error closing task config client: {e}")
            
            if hasattr(self, 'axon'):
                self.axon.stop()

            if self.handshake_running:
                self.handshake_running = False
                if self.handshake_thread and self.handshake_thread.is_alive():
                    self.handshake_thread.join(timeout=5)

    def _convert_ip_to_stringip(self, ip_val):
        try:
            if ip_val is None:
                return '0.0.0.0'
            
            if ip_val == '0.0.0.0':
                return '0.0.0.0'
            
            if isinstance(ip_val, str):
                parts = ip_val.split('.')
                if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
                    return ip_val

            ip_int = int(ip_val)

            if ip_int == 0:
                return '0.0.0.0'

            import socket
            import struct
            ip_str = socket.inet_ntoa(struct.pack("!I", ip_int))

            return ip_str
        except Exception as e:
            bt.logging.warning(f"Failed to convert IP {ip_val}: {e}")
            return '0.0.0.0'

    async def _try_handshake(self, async_client: httpx.AsyncClient, server_address: str, keypair, hotkey):
        return await handshake.perform_handshake(
            async_client, server_address, keypair, hotkey
        )

    async def _handshake_node(self, node_info: Dict[str, Any]) -> Dict[str, Any]:
        try:
            hotkey = node_info['hotkey']
            ip = node_info['ip']
            port = node_info['port']
            uid = node_info['uid']
            
            if ip == '0.0.0.0':
                return node_info

            address_ip = ip
            if self.validator_config.replace_with_localhost:
                address_ip = '0.0.0.1'
            try:
                replace_with_docker_localhost = getattr(self.validator_config, 'replace_with_docker_localhost', False)
                replace_with_localhost = getattr(self.validator_config, 'replace_with_localhost', False)
            except AttributeError:
                replace_with_docker_localhost = False
                replace_with_localhost = False

            node = Node
            node.ip = address_ip
            node.port = port
            node.protocol=  'http'
            server_address = client.construct_server_address(
                node=node,
                replace_with_docker_localhost=replace_with_docker_localhost,
                replace_with_localhost=replace_with_localhost,
            )
            
            async with httpx.AsyncClient(timeout=10.0) as async_client:
                try:

                    try:
                        keypair = getattr(self.validator_config, 'keypair', self.wallet.hotkey)
                    except AttributeError:
                        keypair = self.wallet.hotkey
                    
                    symmetric_key, symmetric_key_uid = await self._try_handshake(
                        async_client, server_address, keypair, hotkey
                    )
                    
                    node_info['symmetric_key'] = symmetric_key.decode() if isinstance(symmetric_key, bytes) else str(symmetric_key)
                    node_info['symmetric_key_uid'] = symmetric_key_uid
                    node_info['handshake_success'] = True
                    node_info['last_handshake_time'] = time.time()
                    
                except Exception as e:
                    node_info['handshake_success'] = False
                    node_info['handshake_error'] = str(e)
                    
            return node_info
            
        except Exception as e:
            bt.logging.error(f"Error in _handshake_node for {node_info.get('hotkey', 'unknown')}: {e}")
            node_info['handshake_success'] = False
            node_info['handshake_error'] = str(e)
            return node_info

    async def _perform_handshakes(self):

        try:
            bt.logging.info("Starting batch handshake process...")

            if not hasattr(self, 'subtensor') or not hasattr(self, 'metagraph'):
                bt.logging.error("Missing required attributes: subtensor or metagraph")
                return

            try:
                neurons = self.subtensor.neurons_lite(netuid=self.config.netuid)
            except Exception as e:
                bt.logging.error(f"Failed to get neurons from subtensor: {e}")
                return
            
            nodes_to_handshake = []
            
            for idx, hotkey in enumerate(self.metagraph.hotkeys):
                try:
                    if idx >= len(neurons):
                        bt.logging.info(f"Index {idx} out of range for neurons list")
                        continue
                        
                    neuron = neurons[idx]
                    ip = neuron.axon_info.ip
                    port = neuron.axon_info.port
                    if ip == '0.0.0.0':
                        continue

                    node_info = {
                        'uid': idx,
                        'hotkey': hotkey,
                        'ip': self._convert_ip_to_stringip(ip),
                        'port': port,
                        'symmetric_key': None,
                        'symmetric_key_uid': None,
                        'handshake_success': False,
                        'last_handshake_time': 0
                    }
                    
                    nodes_to_handshake.append(node_info)
                    
                except Exception as e:
                    bt.logging.warning(f"Error getting node info for {hotkey}: {e}")
                    continue
            
            if not nodes_to_handshake:
                return

            semaphore = asyncio.Semaphore(10)
            
            async def limited_handshake(node_info):
                try:
                    async with semaphore:
                        result = await self._handshake_node(node_info)
                        return result
                except Exception as e:
                    bt.logging.error(f"Error in limited_handshake for {node_info['hotkey']}: {e}")
                    return {'handshake_success': False, 'handshake_error': str(e), **node_info}

            limited_tasks = []
            for node_info in nodes_to_handshake:
                limited_tasks.append(limited_handshake(node_info))
            
            try:
                results = await asyncio.gather(*limited_tasks, return_exceptions=True)
            except Exception as e:
                bt.logging.error(f"Error in asyncio.gather: {e}")
                import traceback
                bt.logging.error(f"Traceback: {traceback.format_exc()}")
                return
            
            successful_handshakes = 0
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    bt.logging.error(f"Handshake task failed for node {nodes_to_handshake[i]['hotkey']}: {result}")
                    continue
                
                if result.get('handshake_success', False):
                    successful_handshakes += 1
                    self.node_handshake_data[result['hotkey']] = result
            
            self.last_handshake_time = time.time()
            
            self.update_queue_processor_handshake_data()
            
        except Exception as e:
            bt.logging.error(f"Error in _perform_handshakes: {e}")
            import traceback
            bt.logging.error(f"Traceback: {traceback.format_exc()}")

    async def _perform_handshakes_with_nodes(self, nodes_to_handshake):

        try:

            if not nodes_to_handshake:
                return
            
            semaphore = asyncio.Semaphore(10)
            
            async def limited_handshake(node_info):
                try:
                    async with semaphore:
                        result = await self._handshake_node(node_info)
                        return result
                except Exception as e:
                    bt.logging.error(f"Error in limited_handshake for {node_info['hotkey']}: {e}")
                    return {'handshake_success': False, 'handshake_error': str(e), **node_info}
            
            limited_tasks = []
            for node_info in nodes_to_handshake:
                limited_tasks.append(limited_handshake(node_info))
            
            try:
                results = await asyncio.gather(*limited_tasks, return_exceptions=True)
            except Exception as e:
                bt.logging.error(f"Error in asyncio.gather: {e}")
                import traceback
                bt.logging.error(f"Traceback: {traceback.format_exc()}")
                return
            
            successful_handshakes = 0
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    continue
                
                if result.get('handshake_success', False):
                    successful_handshakes += 1
                    self.node_handshake_data[result['hotkey']] = result
            
            self.last_handshake_time = time.time()
            
            self.update_queue_processor_handshake_data()
            
        except Exception as e:
            bt.logging.error(f"Error in _perform_handshakes_with_nodes: {e}")
            import traceback
            bt.logging.error(f"Traceback: {traceback.format_exc()}")

    def _cache_nodes_info(self):
        try:

            if not hasattr(self, 'subtensor') or not hasattr(self, 'metagraph'):
                bt.logging.error("Missing required attributes: subtensor or metagraph")
                return
            
            try:
                neurons = self.subtensor.neurons_lite(netuid=self.config.netuid)
            except Exception as e:
                bt.logging.error(f"Failed to get neurons from subtensor: {e}")
                return
            
            nodes_to_handshake = []
            
            for idx, hotkey in enumerate(self.metagraph.hotkeys):
                try:
                    if idx >= len(neurons):
                        bt.logging.warning(f"Index {idx} out of range for neurons list")
                        continue
                        
                    neuron = neurons[idx]
                    ip = neuron.axon_info.ip
                    port = neuron.axon_info.port
                    if ip == '0.0.0.0':
                        continue
                    
                    node_info = {
                        'uid': idx,
                        'hotkey': hotkey,
                        'ip': ip,
                        'port': port,
                        'symmetric_key': None,
                        'symmetric_key_uid': None,
                        'handshake_success': False,
                        'last_handshake_time': 0
                    }
                    
                    nodes_to_handshake.append(node_info)
                    
                except Exception as e:
                    bt.logging.warning(f"Error getting node info for {hotkey}: {e}")
                    continue
            
            self.cached_nodes_info = nodes_to_handshake
            
        except Exception as e:
            bt.logging.error(f"Error in _cache_nodes_info: {e}")
            import traceback
            bt.logging.error(f"Traceback: {traceback.format_exc()}")

    def _start_handshake_timer(self):
        def handshake_timer():
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._perform_handshakes_with_nodes(self.cached_nodes_info))
                except Exception as e:
                    bt.logging.error(f"Error in initial handshake: {e}")
                finally:
                    loop.close()
            except Exception as e:
                bt.logging.error(f"Failed to start initial handshake: {e}")

            while self.handshake_running:
                try:
                    time.sleep(self.handshake_interval)
                    
                    if self.handshake_running:

                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(self._perform_handshakes_with_nodes(self.cached_nodes_info))
                        except Exception as e:
                            bt.logging.error(f"Error in scheduled handshake: {e}")
                        finally:
                            loop.close()
                    
                except Exception as e:
                    bt.logging.error(f"Error in handshake timer: {e}")
                    time.sleep(60)
        
        self.handshake_running = True
        self.handshake_thread = threading.Thread(target=handshake_timer, daemon=True)
        self.handshake_thread.start()

    def get_node_handshake_data(self, hotkey: str = None) -> Dict[str, Any]:
        if hotkey is None:
            return self.node_handshake_data
        return self.node_handshake_data.get(hotkey, {})

    def get_handshake_stats(self) -> Dict[str, Any]:
        total_nodes = len(self.node_handshake_data)
        successful_handshakes = sum(1 for data in self.node_handshake_data.values() 
                                  if data.get('handshake_success', False))
        
        return {
            'total_nodes': total_nodes,
            'successful_handshakes': successful_handshakes,
            'success_rate': successful_handshakes / total_nodes if total_nodes > 0 else 0.0,
            'last_handshake_time': self.last_handshake_time,
            'next_handshake_time': self.last_handshake_time + self.handshake_interval,
            'cached_nodes_count': len(self.cached_nodes_info)
        }

    def update_queue_processor_handshake_data(self):
        try:
            if hasattr(self, 'queue_processor') and self.queue_processor:
                if hasattr(self.queue_processor, 'contender_allocator'):
                    self.queue_processor.contender_allocator.node_handshake_data = self.node_handshake_data
        except Exception as e:
            bt.logging.error(f"Error updating handshake data in queue processor: {e}")

    def refresh_cached_nodes(self):
        try:
            self._cache_nodes_info()
        except Exception as e:
            bt.logging.error(f"Error refreshing cached nodes: {e}")

    def switch_allocation_strategy(self, strategy: str):
        if strategy not in ["stake", "equal"]:
            raise ValueError(f"Unknown allocation strategy: {strategy}")
        self.allocation_strategy = strategy

    def save_state(self):

        scores = [float(score) for score in self.scores]
        moving_avg_scores = [float(score) for score in self.moving_avg_scores]
        hotkeys = [str(key) for key in self.hotkeys]
        block_at_registration = [int(block) for block in self.block_at_registration]
        
        state = {
            "current_block": int(self.current_block),
            "total_blocks_run": int(self.total_blocks_run),
            "scores": scores,
            "moving_avg_scores": moving_avg_scores,
            "hotkeys": hotkeys,
            "block_at_registration": block_at_registration
        }
        self.storage.save_state(state)

    def restore_state_and_evaluate(self) -> None:
        state = self.storage.load_latest_state()
        if not state or "current_block" not in state:
            return

        self.total_blocks_run = state.get("total_blocks_run", 0)
        
        blocks_down = self.current_block - state["current_block"]
        if blocks_down >= (self.tempo * 1.5):
            logging.warning(
                f"Validator was down for {blocks_down} blocks (> {self.tempo * 1.5}). Starting fresh."
            )
            return

        total_hotkeys = len(state.get("hotkeys", []))
        self.scores = state.get("scores", [0.0] * total_hotkeys)
        self.moving_avg_scores = state.get("moving_avg_scores", [0.0] * total_hotkeys)
        self.hotkeys = state.get("hotkeys", [])
        self.block_at_registration = state.get("block_at_registration", [])

        self.resync_metagraph()

        if blocks_down > 230:  # 1 hour
            logging.warning(
                f"Validator was down for {blocks_down} blocks (> 230). Will fetch last hour's scores."
            )

    def set_weights(self) -> Tuple[bool, str]:

        try:

            miner_indices = []
            weights = []
            total_stake = 0.0
            
            neurons = self.subtensor.neurons_lite(netuid=self.config.netuid)
            
            validator_trust = self.subtensor.query_subtensor(
                "ValidatorTrust",
                params=[self.config.netuid],
            )

            total_stake = sum(float(neurons[idx].stake) for idx in range(len(self.metagraph.hotkeys))
                            if not validator_trust[idx] > 0)  # 排除验证者
            
            # 遍历所有矿工
            for idx, hotkey in enumerate(self.metagraph.hotkeys):
                is_validator = False
                try:
                    neuron = neurons[idx]
                    ip = neuron.axon_info.ip
                    if ip == '0.0.0.0':
                        continue

                    is_validator = self.metagraph.validator_permit[idx]
                    is_active = bool(neuron.active)
                    stake = float(neuron.stake)

                    if CHECK_NODE_ACTIVE and not is_active:
                        logging.debug(f"Skipping inactive node: {hotkey}")
                        continue
                        
                except Exception as e:
                    bt.logging.warning(f"Error checking node status for {hotkey}: {e}")
                    continue

                from soulx.validator.scoring_results_manager import scoring_results_manager
                
                historical_score = scoring_results_manager.get_historical_score(hotkey)
                current_quality_score = scoring_results_manager.get_current_cycle_score(hotkey)

                if historical_score == 0.0:
                    historical_score = self.alpha
                
                stake_weight = (stake / total_stake) * 0.2 if total_stake > 0 else 0
                
                final_score = (
                    stake_weight +
                    current_quality_score * 0.7 +
                    historical_score * 0.1
                )

                if final_score < FINAL_MIN_SCORE or final_score> 1.0 :
                    final_score = round(random.uniform(0.8, 1.0), 2)

                if current_quality_score > 0 :
                    miner_indices.append(idx)
                    weights.append(final_score)

            is_blacklisted = self.config_manager.is_validator_blacklisted(self.validator_hotkey)

            if is_blacklisted :
                return False, f"{self.validator_hotkey} "

            if not weights or all(w == 0 for w in weights):
                owner_uid = self.get_subnet_owner_uid()
                if owner_uid is None:
                    return False, "No subnet owner found"
                    
                weights = [0.0] * len(self.metagraph.hotkeys)

                miner_indices = list(range(len(self.metagraph.hotkeys)))
            else:
                total_weight = sum(weights)
                if total_weight > 0:

                    MIN_WEIGHT_THRESHOLD = 0.001  # 0.1%

                    weights = [w if w >= MIN_WEIGHT_THRESHOLD else 0.0 for w in weights]
                    
                    total_weight = sum(weights)
                    if total_weight > 0:
                            weights = [ w / total_weight for w in weights]
                    else:
                        owner_uid = self.get_subnet_owner_uid()
                        if owner_uid is not None:
                            weights = [0.0] * len(self.metagraph.hotkeys)

                            weights[owner_uid] =  self.config_manager.get_config().owner_default_score

                            logging.info(f"All weights below threshold, setting all weight to subnet owner (uid: {owner_uid})")
                            

            success = self.subtensor.set_weights(
                netuid=self.config.netuid,
                wallet=self.wallet,
                uids=miner_indices,
                weights=weights,
                wait_for_inclusion=True,
                version_key=VERSION_KEY
            )

            if success:
                self.last_update = self.current_block
                from soulx.validator.scoring_results_manager import scoring_results_manager
                scoring_results_manager.clear_current_cycle_scores()
            else:
                logging.error("Failed to set weights")
                
            return success, ""
            
        except Exception as e:
            error_msg = f"Error setting weights: {str(e)}"
            logging.error(error_msg)
            return False, error_msg
            
    def _log_weights(self, indices: List[int], weights: List[float]) -> None:
        rows = []
        headers = ["UID", "Hotkey", "Weight", "Normalized (%)"]
        
        # 按权重排序
        sorted_pairs = sorted(zip(indices, weights), key=lambda x: x[1], reverse=True)
        
        for idx, weight in sorted_pairs:
            if weight > 0:
                hotkey = self.metagraph.hotkeys[idx]

                rows.append([
                    idx,
                    f"{hotkey[:10]}...{hotkey[-6:]}",
                    f"{weight:.10f}",
                    f"{weight * 100:.10f}%"
                ])
                
        if not rows:
            return
            
        table = tabulate(
            rows,
            headers=headers,
            tablefmt="grid",
            numalign="right",
            stralign="left"
        )
        logging.info(f"Weight distribution at block {self.current_block}:\n{table}")
        
    def get_subnet_owner_uid(self) -> Optional[int]:
        try:
            owner_coldkey = self.subtensor.query_subtensor(
                "SubnetOwner",
                params=[self.config.netuid]
            )
            return self.metagraph.coldkeys.index(owner_coldkey)
        except Exception as e:
            logging.error(f"Error getting subnet owner: {str(e)}")
            return None

    def serve_axon(self):

        try:

            logging.info(f"Initializing Axon with IP: {self.config.axon.ip}, Port: {self.config.axon.port}")

            self.axon = bt.axon(wallet=self.wallet, config=self.config)

            self.axon.attach(
                forward_fn=self.forward
            )

            self.axon.start()

            try:
                self.subtensor.serve_axon(
                    netuid=self.config.netuid,
                    axon=self.axon,
                )
            except Exception as e:
                logging.error(f"Failed to serve Axon with exception: {e}")
                raise e

        except Exception as e:
            logging.error(
                f"Failed to create Axon initialize with exception: {e}"
            )
            raise e

    def setup_logging(self) -> None:

        logging(config=self.config, logging_dir=self.config.full_path)

        root_logger = python_logging.getLogger()
        root_logger.handlers = []
        null_handler = python_logging.NullHandler()
        root_logger.addHandler(null_handler)
        
        bt_logger = python_logging.getLogger("bittensor")
        bt_logger.propagate = False
        
        log_level = self.validator_config.bt_logging_info
        if log_level == "TRACE":
            logging.set_trace(True)
        else:
            logging.set_trace(False)
            logging.setLevel(log_level)

        if not self.validator_config.check_max_blocks:
            logging.info(
                f"Running validator for subnet: {self.config.netuid} on network: {self.config.subtensor.network} with config:\n{self.config}"
            )
            
        if hasattr(self, 'validator_config'):
            from soulx.core.validator_config import print_config_summary
            print_config_summary(self.validator_config)

# Run the validator.
if __name__ == "__main__":
    validator_env = PathUtils.get_project_root() / ".env.validator"
    default_env = PathUtils.get_env_file_path()
    
    if validator_env.exists():
        load_dotenv(validator_env)
    else:
        load_dotenv(default_env)
    validator = SoulxValidator()
    validator.run()
