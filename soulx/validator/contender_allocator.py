# -*- coding: utf-8 -*-
import asyncio
from bittensor import logging
import time
import os
import httpx
from fiber.chain import chain_utils
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
from datetime import datetime
from substrateinterface import  Keypair
import json

from soulx.core.path_utils import PathUtils
import base64

from soulx.validator.contender_client import ContenderClient
from soulx.validator.task_config_client import TaskConfigClient
from soulx.validator.miner_task_api_client import MinerTaskApiClient

class ContenderAllocator:

    def __init__(self, contender_client: ContenderClient, task_config_client: TaskConfigClient, 
                 redis_host: str = "localhost", redis_port: int = 6379, redis_password: str = None,
                 node_handshake_data: Dict[str, Dict[str, Any]] = None):
        self.contender_client = contender_client
        self.task_config_client = task_config_client
        self.api_server_url = os.getenv("CONFIG_SERVER_URL", "http://config.asiatensor.xyz")
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_password = redis_password
        self.node_handshake_data = node_handshake_data or {}
        self.contenders = []
        self.miner_tasks = {}
        self.task_history = {}
        self.validator_ss58_address = contender_client.validator_hotkey
        self.miner_task_api_client = None
        self.redis_client = None
        self.miner_task_expire_time = 1800

    async def _get_miner_task_api_client(self):
        if self.miner_task_api_client is None:
            try:
                self.miner_task_api_client = MinerTaskApiClient(
                    api_server_url=self.api_server_url,
                    timeout=30
                )
                health_result = await self.miner_task_api_client.health_check()
                if health_result.get("success", False):
                    logging.info("Miner task API client initialized successfully")
                else:
                    logging.warning(f"Miner task API client health check failed: {health_result}")
            except Exception as e:
                logging.error(f"Failed to initialize miner task API client: {e}")
                self.miner_task_api_client = None
        return self.miner_task_api_client

    async def _get_redis_client(self):
        if self.redis_client is None:
            try:
                from redis.asyncio import Redis
                self.redis_client = Redis(
                    host=self.redis_host,
                    port=self.redis_port,
                    password=self.redis_password,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                await self.redis_client.ping()
                logging.info("Redis client initialized successfully as fallback")
            except Exception as e:
                logging.error(f"Failed to initialize Redis client: {e}")
                self.redis_client = None
        return self.redis_client

    async def _set_miner_task(self, miner_hotkey: str, task_id: str, task_type: str = None) -> bool:
        try:
            api_client = await self._get_miner_task_api_client()
            if api_client is None:
                return await self._set_miner_task_redis(miner_hotkey, task_id, task_type)
            
            success = await api_client.set_miner_task(
                miner_hotkey=miner_hotkey,
                task_id=task_id,
                validator_hotkey=self.validator_ss58_address,
                task_type=task_type
            )
            
            if success:
                return True
            else:
                return await self._set_miner_task_redis(miner_hotkey, task_id, task_type)
            
        except Exception as e:
            return await self._set_miner_task_redis(miner_hotkey, task_id, task_type)

    async def _set_miner_task_redis(self, miner_hotkey: str, task_id: str, task_type: str = None) -> bool:
        try:
            redis_client = await self._get_redis_client()
            if redis_client is None:
                self.miner_tasks[miner_hotkey] = task_id
                return True
            
            key = f"miner_task:{miner_hotkey}"
            task_data = {
                'task_id': task_id,
                'allocated_at': datetime.now().isoformat(),
                'validator_hotkey': self.validator_ss58_address,
                'task_type': task_type
            }
            
            await redis_client.setex(
                key, 
                self.miner_task_expire_time, 
                json.dumps(task_data)
            )
            return True
            
        except Exception as e:
            self.miner_tasks[miner_hotkey] = task_id
            return True

    async def _get_miner_task(self, miner_hotkey: str) -> Optional[str]:
        try:
            api_client = await self._get_miner_task_api_client()
            if api_client is None:
                return await self._get_miner_task_redis(miner_hotkey)
            
            task_data = await api_client.get_miner_task(miner_hotkey)
            
            if task_data:
                task_id = task_data.get('task_id')
                return task_id
            else:
                return None
                
        except Exception as e:
            return await self._get_miner_task_redis(miner_hotkey)

    async def _get_miner_task_redis(self, miner_hotkey: str) -> Optional[str]:
        try:
            redis_client = await self._get_redis_client()
            if redis_client is None:
                return self.miner_tasks.get(miner_hotkey)
            
            key = f"miner_task:{miner_hotkey}"
            task_data_str = await redis_client.get(key)
            
            if task_data_str:
                task_data = json.loads(task_data_str)
                task_id = task_data.get('task_id')
                return task_id
            else:
                return None
                
        except Exception as e:
            return self.miner_tasks.get(miner_hotkey)

    async def _remove_miner_task(self, miner_hotkey: str) -> bool:
        try:
            api_client = await self._get_miner_task_api_client()
            if api_client is None:
                return await self._remove_miner_task_redis(miner_hotkey)
            
            success = await api_client.remove_miner_task(miner_hotkey)
            
            if success:
                logging.debug(f"Removed miner task via API: {miner_hotkey}")
            else:
                return await self._remove_miner_task_redis(miner_hotkey)
            
            if miner_hotkey in self.miner_tasks:
                del self.miner_tasks[miner_hotkey]
            
            return True
            
        except Exception as e:
            return await self._remove_miner_task_redis(miner_hotkey)

    async def _remove_miner_task_redis(self, miner_hotkey: str) -> bool:
        try:
            redis_client = await self._get_redis_client()
            if redis_client is None:
                if miner_hotkey in self.miner_tasks:
                    del self.miner_tasks[miner_hotkey]
                return True
            
            key = f"miner_task:{miner_hotkey}"
            result = await redis_client.delete(key)

            if miner_hotkey in self.miner_tasks:
                del self.miner_tasks[miner_hotkey]
            
            return True
            
        except Exception as e:
            if miner_hotkey in self.miner_tasks:
                del self.miner_tasks[miner_hotkey]
            return True

    async def _check_miner_has_task(self, miner_hotkey: str) -> bool:
        try:
            api_client = await self._get_miner_task_api_client()
            if api_client is None:
                return await self._check_miner_has_task_redis(miner_hotkey)
            
            has_task = await api_client.check_miner_has_task(miner_hotkey)
            return has_task
            
        except Exception as e:
            return await self._check_miner_has_task_redis(miner_hotkey)

    async def _check_miner_has_task_redis(self, miner_hotkey: str) -> bool:
        try:
            redis_client = await self._get_redis_client()
            if redis_client is None:
                return miner_hotkey in self.miner_tasks
            
            key = f"miner_task:{miner_hotkey}"
            exists = await redis_client.exists(key)
            has_task = exists > 0
            return has_task
            
        except Exception as e:
            return miner_hotkey in self.miner_tasks

    async def get_contenders_for_task(self, task_type: str, top_x: int = 5) -> List[Dict[str, Any]]:
        try:
            contenders = await self.contender_client.get_contenders_for_task(task_type, top_x)
            
            if not contenders:
                return []
            
            return contenders
            
        except Exception as e:
            return []
    
    async def allocate_task_to_contender(self, task: Dict[str, Any], contender: Dict[str, Any]) -> bool:

        try:
            task_id = task.get('task_id')
            contender_id = contender.get('contender_id')
            miner_hotkey = contender.get('node_hotkey')
            
            has_task = await self._check_miner_has_task(miner_hotkey)
            if has_task:
                existing_task = await self._get_miner_task(miner_hotkey)
                return False
            
            task_type = task.get('task_type', 'unknown')
            success = await self._set_miner_task(miner_hotkey, task_id, task_type)
            if not success:
                return False
            
            if task_id not in self.task_history:
                self.task_history[task_id] = {
                    'task': task,
                    'contender': contender,
                    'allocated_at': datetime.now(),
                    'status': 'allocated'
                }
            
            return True
            
        except Exception as e:
            return False
    
    async def process_task_with_contender(self, task: Dict[str, Any], contender: Dict[str, Any]) -> bool:
        try:
            task_id = task.get('task_id')
            task_type = task.get('task_type')
            miner_hotkey = contender.get('node_hotkey')
            payload = task.get('query_payload', {})
            
            task_config = await self._get_task_config(task_type)
            if task_config is None:
                return False

            type = task_config.get("type")

            if type == 'image-to-image' and not payload['init_image']:
                project_root = PathUtils.get_project_root()
                test_image_path = project_root / 'assets' / 'img-to-img.png'
                with open(test_image_path, 'rb') as f:
                    image_data = f.read()
                    image_b64 = base64.b64encode(image_data).decode('utf-8')

                payload['init_image'] = image_b64

            is_stream = payload.get('stream', False)
            
            start_time = time.time()
            
            await self._update_contender_requests_made(contender)
            
            success = False
            
            try:
                if is_stream:
                    success = await self._handle_stream_query(task, contender, payload, start_time)
                else:
                    success = await self._handle_nonstream_query(task, contender, payload, start_time)
                
            except Exception as e:
                success = False
            
            if success:
                logging.info(f"Task {task_id} processed successfully with contender {contender.get('contender_id')}")
                
                if task_id in self.task_history:
                    self.task_history[task_id]['status'] = 'completed'
                    self.task_history[task_id]['completed_at'] = datetime.now()
                
                await self._update_contender_stats(contender, success=True)
                
                await self._remove_miner_task(miner_hotkey)
            else:

                if task_id in self.task_history:
                    self.task_history[task_id]['status'] = 'failed'
                    self.task_history[task_id]['failed_at'] = datetime.now()
                
                await self._update_contender_stats(contender, success=False)
                
                await self._remove_miner_task(miner_hotkey)
            
            return success
            
        except Exception as e:
            logging.error(f"Error processing task with contender: {e}")
            return False
    
    async def _get_task_config(self, task_type: str) -> Optional[Dict[str, Any]]:
        try:
            task_config = await self.task_config_client.get_task_config(task_type)
            
            if task_config:
                return task_config
            else:
                return None
                
        except Exception as e:
            return self._get_default_task_config(task_type)
    
    def _get_default_task_config(self, task_type: str) -> Optional[Dict[str, Any]]:
        default_configs = {
            'chat-llama-3-2-3b': {
                'is_stream': True,
                'endpoint': '/chat/completions',
                'timeout': 10,
                'response_model': 'text',
                'task_type': 'text',
                'description': 'Chat Llama 3 2.3B',
                'max_capacity': 1.0,
                'weight': 1.0,
                'enabled': True,
                'display_name': 'Chat Llama 3 2.3B',
                'is_reasoning': False
            },
            'chat-llama-3-8b': {
                'is_stream': True,
                'endpoint': '/chat/completions',
                'timeout': 10,
                'response_model': 'text',
                'task_type': 'text',
                'description': 'Chat Llama 3 8B',
                'max_capacity': 1.0,
                'weight': 1.0,
                'enabled': True,
                'display_name': 'Chat Llama 3 8B',
                'is_reasoning': False
            },
            'text_to_image': {
                'is_stream': False,
                'endpoint': '/text-to-image',
                'timeout': 10,
                'response_model': 'image',
                'task_type': 'image',
                'description': 'Text to Image',
                'max_capacity': 1.0,
                'weight': 1.0,
                'enabled': True,
                'display_name': 'Text to Image',
                'is_reasoning': False
            },
            'image_to_image': {
                'is_stream': False,
                'endpoint': '/image-to-image',
                'timeout': 60,
                'response_model': 'image',
                'task_type': 'image',
                'description': 'Image to Image',
                'max_capacity': 1.0,
                'weight': 1.0,
                'enabled': True,
                'display_name': 'Image to Image',
                'is_reasoning': False
            },
            'avatar': {
                'is_stream': False,
                'endpoint': '/avatar',
                'timeout': 45,
                'response_model': 'image',
                'task_type': 'image',
                'description': 'Avatar Generation',
                'max_capacity': 1.0,
                'weight': 1.0,
                'enabled': True,
                'display_name': 'Avatar Generation',
                'is_reasoning': False
            },
            'vl': {
                'is_stream': False,
                'endpoint': '/vl',
                'timeout': 30,
                'response_model': 'text',
                'task_type': 'text',
                'description': 'Visual Language',
                'max_capacity': 1.0,
                'weight': 1.0,
                'enabled': True,
                'display_name': 'Visual Language',
                'is_reasoning': True
            }
        }
        
        return default_configs.get(task_type)
    
    async def _update_contender_requests_made(self, contender: Dict[str, Any]):

        try:
            contender_id = contender.get('contender_id')
            if not contender_id:
                return
            
            current_requests = contender.get('total_requests_made', 0)
            contender['total_requests_made'] = current_requests + 1
            
            current_synthetic_requests = contender.get('synthetic_requests_made', 0)
            contender['synthetic_requests_made'] = current_synthetic_requests + 1
            
        except Exception as e:
            logging.error(f"Error updating contender requests made: {e}")
    
    async def _handle_stream_query(self, task: Dict[str, Any], contender: Dict[str, Any], payload: Dict[str, Any], start_time: float) -> bool:
        try:
            task_id = task.get('task_id')
            task_type = task.get('task_type')
            miner_hotkey = contender.get('node_hotkey')
            
            from soulx.validator.query.streaming import query_node_stream, consume_generator
            
            config = self._create_config_for_query()
            if config is None:
                return False
            
            node = await self._create_node_for_query(contender, config)
            if node is None:
                return False
            
            contender_obj = await self._create_contender_obj(contender)
            if contender_obj is None:
                return False
            
            job_id = f"task_{task_id}_{int(start_time)}"
            
            task_config = await self._get_task_config(task_type)
            if task_config is None:
                return False
            
            generator = await query_node_stream(config, contender_obj, node, payload, task_config)
            
            if generator is None:
                return False
            
            success = await consume_generator(
                config=config,
                generator=generator,
                job_id=job_id,
                synthetic_query=True,
                contender=contender_obj,
                node=node,
                payload=payload,
                start_time=start_time,
                task_config=task_config
            )
            
            if success:
                response_time = time.time() - start_time
                logging.info(f"Stream query successful for task {task_id} with contender {contender.get('contender_id')} - time: {response_time:.2f}s")
            else:
                logging.warning(f"Stream query failed for task {task_id} with contender {contender.get('contender_id')}")
            
            return success
            
        except Exception as e:
            logging.error(f"Error in stream query: {e}")
            return False
    
    async def _handle_nonstream_query(self, task: Dict[str, Any], contender: Dict[str, Any], payload: Dict[str, Any], start_time: float) -> bool:
        try:
            task_id = task.get('task_id')
            task_type = task.get('task_type')
            miner_hotkey = contender.get('node_hotkey')
            
            logging.debug(f"Querying contender {contender.get('contender_id')} for task {task_type} with payload: {payload}")
            
            from soulx.validator.query.nonstream import query_nonstream
            from soulx.core.models.payload_models import ImageResponse
            
            config = self._create_config_for_query()
            if config is None:
                logging.error("Failed to create config for query")
                return False
            
            node = await self._create_node_for_query(contender, config)
            if node is None:
                logging.error("Failed to create node for query")
                return False
            
            contender_obj = await self._create_contender_obj(contender)
            if contender_obj is None:
                logging.error("Failed to create contender object")
                return False
            
            job_id = f"task_{task_id}_{int(start_time)}"

            task_config = await self._get_task_config(task_type)
            if task_config is None:
                return False
            
            success, query_result = await query_nonstream(
                config=config,
                contender=contender_obj,
                node=node,
                payload=payload,
                synthetic_query=True,
                job_id=job_id,
                task_config=task_config
            )
            
            if success:
                response_time = time.time() - start_time
            else:
                logging.warning(f"Non-stream query failed for task  with contender {contender.get('contender_id')}")
            
            return success
            
        except Exception as e:
            logging.error(f"Error in non-stream query: {e}")
            return False

    def load_hotkey_keypair_from_seed(self,secret_seed: str) -> Keypair:
        try:
            keypair = Keypair.create_from_seed(secret_seed)
            return keypair
        except Exception as e:
            raise ValueError(f"Failed to load keypair: {str(e)}")


    def _create_config_for_query(self):
        try:
            from soulx.validator.query.query_config import Config
            from fiber import Keypair
            from redis.asyncio import Redis
            import httpx
            
            redis_db = Redis(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=int(os.getenv('REDIS_PORT', 6379)),
                password=os.getenv('REDIS_PASSWORD'),
                decode_responses=True
            )
            
            keypair = Keypair.create_from_uri("//Alice")
            wallet_name = os.getenv("BT_WALLET_NAME", "default")
            hotkey_name = os.getenv("BT_WALLET_HOTKEY", "default")
            try:
                keypair = chain_utils.load_hotkey_keypair(wallet_name=wallet_name, hotkey_name=hotkey_name)
            except (ValueError, FileNotFoundError) as e:
                secret_seed = os.getenv("WALLET_SECRET_SEED", None)
                if secret_seed:
                    try:
                        keypair = self.load_hotkey_keypair_from_seed(secret_seed)
                    except Exception as e:
                        logging.error(f"Failed to load keypair from seed: {str(e)}")
                        raise ValueError(f"Invalid secret seed provided: {str(e)}")
                else:
                    logging.error("WALLET_SECRET_SEED environment variable not set")
                    raise ValueError(
                        f"Could not load wallet from path and WALLET_SECRET_SEED env var is not set. Original error: {str(e)}")
            except Exception as e:
                logging.error(f"Unexpected error loading hotkey from wallet: {str(e)}")
                raise

            httpx_client = httpx.AsyncClient(timeout=30)
            
            config = Config(
                keypair=keypair,
                redis_db=redis_db,
                ss58_address=self.validator_ss58_address,
                netuid=int(os.getenv('NETUID', 0)),
                httpx_client=httpx_client,
                # central_server_url=os.getenv('CENTRAL_SERVER_URL', 'http://localhost:8000'),
                # central_server_token=os.getenv('CENTRAL_SERVER_TOKEN'),
                replace_with_localhost=os.getenv('REPLACE_WITH_LOCALHOST', 'false').lower() == 'true',
                replace_with_docker_localhost=os.getenv('REPLACE_WITH_DOCKER_LOCALHOST', 'false').lower() == 'true'
            )
            
            return config
            
        except Exception as e:
            logging.error(f"Error creating config for query: {e}")
            return None
    
    async def _create_node_for_query(self, contender: Dict[str, Any], config):
        try:
            from fiber.encrypted.networking.models import NodeWithFernet as Node
            from cryptography.fernet import Fernet
            import uuid
            
            node_hotkey = contender.get('node_hotkey')
            if not node_hotkey:
                return None

            node_data = await config.get_node_by_hotkey(node_hotkey)
            if not node_data:
                return None

            handshake_data = self.node_handshake_data.get(node_hotkey)
            if handshake_data and handshake_data.get('handshake_success', False):
                try:
                    symmetric_key = handshake_data.get('symmetric_key')
                    symmetric_key_uid = handshake_data.get('symmetric_key_uid')

                    if symmetric_key and symmetric_key_uid:
                        if isinstance(symmetric_key, str):
                            fernet_key = symmetric_key.encode()
                        else:
                            fernet_key = symmetric_key

                        fernet = Fernet(fernet_key)

                        node = Node(
                            node_id=node_data.get('node_id', 0),
                            hotkey=node_hotkey,
                            coldkey=node_data.get('coldkey'),
                            incentive=node_data.get('incentive'),
                            netuid=node_data.get('netuid', 0),
                            trust=node_data.get('trust'),
                            vtrust=node_data.get('vtrust'),
                            stake=node_data.get('stake', 0.0),
                            ip=node_data.get('ip', '127.0.0.1'),
                            ip_type=node_data.get('ip_type', 'ipv4'),
                            port=node_data.get('port', 8091),
                            protocol=node_data.get('protocol', 0),
                            last_updated=node_data.get('last_updated', 0.0),
                            fernet=fernet,
                            symmetric_key_uuid=symmetric_key_uid
                        )

                        logging.info(f"Created Node using handshake data for {node_hotkey}")
                        return node

                except Exception as e:
                    logging.warning(f"Failed to create Node using handshake data for {node_hotkey}: {e}")

            node_data = await config.get_node_by_hotkey(node_hotkey)
            if not node_data:
                return None


            fernet_key = Fernet.generate_key()
            fernet = Fernet(fernet_key)

            node = Node(
                node_id=node_data.get('node_id', 0),
                hotkey=node_hotkey,
                coldkey=node_data.get('coldkey'),
                incentive=node_data.get('incentive'),
                netuid=node_data.get('netuid', 0),
                trust=node_data.get('trust'),
                vtrust=node_data.get('vtrust'),
                stake=node_data.get('stake', 0.0),
                ip=node_data.get('ip', '127.0.0.1'),
                ip_type=node_data.get('ip_type', 'ipv4'),
                port=node_data.get('port', 8091),
                protocol=node_data.get('protocol', 0),
                last_updated=node_data.get('last_updated', 0.0),
                fernet=fernet,
                symmetric_key_uuid=str(uuid.uuid4())
            )

            return node
            
        except Exception as e:
            return None
    
    async def _create_contender_obj(self, contender: Dict[str, Any]):
        try:
            from soulx.validator.models import Contender
            
            contender_obj = Contender(
                contender_id=contender.get('contender_id', ''),
                node_hotkey=contender.get('node_hotkey', ''),
                validator_hotkey=contender.get('validator_hotkey', ''),
                task=contender.get('task', ''),
                node_id=contender.get('node_id', 0),
                netuid=contender.get('netuid', 0),
                capacity=contender.get('capacity', 0.0),
                raw_capacity=contender.get('raw_capacity', 0.0),
                capacity_to_score=contender.get('capacity_to_score', 0.0),
                total_requests_made=contender.get('total_requests_made', 0),
                requests_429=contender.get('requests_429', 0),
                requests_500=contender.get('requests_500', 0),
                period_score=contender.get('period_score', 0.0)
            )
            
            return contender_obj
            
        except Exception as e:
            return None
    
    async def _update_contender_stats(self, contender: Dict[str, Any], success: bool):
        try:
            contender_id = contender.get('contender_id')
            if not contender_id:
                return
            
            stats = {
                'total_requests_made': contender.get('total_requests_made', 0),
                'requests_429': contender.get('requests_429', 0),
                'requests_500': contender.get('requests_500', 0),
                'period_score': contender.get('period_score', 0.0)
            }
            
            if not success:
                stats['requests_500'] += 1
            
            await self.contender_client.update_contender_stats(contender_id, stats)
            
        except Exception as e:
            logging.error(f"Error updating contender stats: {e}")
    
    async def process_task_with_contenders(self, task: Dict[str, Any], contenders: List[Dict[str, Any]]) -> bool:

        task_id = task.get('task_id')
        max_retries = 3
        retry_delay = 30
        
        for attempt in range(max_retries):

            contender_results = {}
            successful_contenders = []
            
            for i, contender in enumerate(contenders):
                contender_id = contender.get('contender_id')
                miner_hotkey = contender.get('node_hotkey')
                
                has_task = await self._check_miner_has_task(miner_hotkey)
                if has_task:
                    existing_task = await self._get_miner_task(miner_hotkey)
                    contender_results[contender_id] = "skipped_busy"
                    continue
                
                allocated = await self.allocate_task_to_contender(task, contender)
                if not allocated:
                    contender_results[contender_id] = False
                    continue
                
                success = await self.process_task_with_contender(task, contender)
                contender_results[contender_id] = success
                
                if success:
                    successful_contenders.append(contender_id)
                else:
                    logging.warning(f" Contender {contender_id} failed to process task {task_id}")
                
                await asyncio.sleep(0.1)
            
            if successful_contenders:
                logging.info(f"All contender results: {contender_results}")
                return True
            
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
        
        return False
    
    async def _wait_for_contender_availability(self, contenders: List[Dict[str, Any]], timeout: int = 30) -> bool:

        start_time = time.time()
        check_interval = 1
        
        while time.time() - start_time < timeout:
            available_contenders = []
            for contender in contenders:
                miner_hotkey = contender.get('node_hotkey')
                has_task = await self._check_miner_has_task(miner_hotkey)
                if not has_task:
                    available_contenders.append(contender)
            
            if available_contenders:
                return True
            
            await asyncio.sleep(check_interval)
        
        return False
    
    async def get_allocation_stats(self) -> Dict[str, Any]:

        total_tasks = len(self.task_history)
        completed_tasks = len([t for t in self.task_history.values() if t['status'] == 'completed'])
        failed_tasks = len([t for t in self.task_history.values() if t['status'] == 'failed'])
        
        active_miners = 0
        try:
            api_client = await self._get_miner_task_api_client()
            if api_client is not None:
                active_miners_list = await api_client.get_all_active_miners()
                active_miners = len(active_miners_list)
            else:
                active_miners = await self._get_active_miners_count_redis()
        except Exception as e:
            logging.error(f"Error getting active miners count via API: {e}, falling back to Redis")
            active_miners = await self._get_active_miners_count_redis()

    async def _get_active_miners_count_redis(self) -> int:
        try:
            redis_client = await self._get_redis_client()
            if redis_client is not None:
                keys = await redis_client.keys("miner_task:*")
                return len(keys)
            else:
                return len(self.miner_tasks)
        except Exception as e:
            logging.error(f"Error getting active miners count from Redis: {e}")
            return len(self.miner_tasks)
        
        return {
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'failed_tasks': failed_tasks,
            'success_rate': completed_tasks / total_tasks if total_tasks > 0 else 0,
            'active_miners': active_miners,
            'api_enabled': self.miner_task_api_client is not None
        }

    async def cleanup(self):
        try:
            if self.miner_task_api_client is not None:
                await self.miner_task_api_client.close()
                logging.info("Miner task API client connection closed")
        except Exception as e:
            logging.error(f"Error closing miner task API client: {e}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()
