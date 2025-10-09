# -*- coding: utf-8 -*-

import asyncio
import json
from bittensor import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import threading
import hashlib

import redis.asyncio as redis
from redis.asyncio import BlockingConnectionPool
from redis.retry import Retry
from redis.backoff import ExponentialBackoff

from soulx.validator.task_client import CognifyTaskClient
from soulx.validator.contender_allocator import ContenderAllocator
from soulx.validator.contender_client import ContenderClient
from soulx.validator.task_config_client import TaskConfigClient
from soulx.core.validator_config import ValidatorConfig

QUERY_QUEUE_KEY = "COGNIFY_QUERY_QUEUE"
TASK_ID_SET_KEY = "COGNIFY_QUERY_TASK_IDS"
MAX_CONCURRENT_TASKS = 1

class RedisQueueManager:

    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379, redis_password: str = None):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_password = redis_password
        self.redis_db = None
        self.running = False
        self._loop = None
        self._thread_local = threading.local()
        
    def _get_current_loop(self):
        try:
            loop = asyncio.get_running_loop()
            return loop
        except RuntimeError:
            return None
    
    def _get_thread_redis_connection(self):
        if not hasattr(self._thread_local, 'redis_db'):
            self._thread_local.redis_db = None
            self._thread_local.loop = None
        return self._thread_local.redis_db, self._thread_local.loop
    
    def _set_thread_redis_connection(self, redis_db, loop):
        self._thread_local.redis_db = redis_db
        self._thread_local.loop = loop
    
    def _extract_task_id(self, task: Dict[str, Any], task_json: Optional[str] = None) -> Optional[str]:

        task_id = task.get("task_id")
        if task_id:
            return str(task_id)

    async def connect(self):

        try:

            current_loop = self._get_current_loop()
            if current_loop is not None:
                self._loop = current_loop
            else:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
            
            pool = self._create_redis_pool()
            redis_db = redis.Redis(connection_pool=pool)
            
            await redis_db.ping()
            
            self._set_thread_redis_connection(redis_db, self._loop)
            
            self.redis_db = redis_db
            
        except Exception as e:
            logging.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def _ensure_connection(self):
        try:
            thread_redis_db, thread_loop = self._get_thread_redis_connection()
            
            if not thread_redis_db:
                await self.connect()
            else:
                try:
                    await thread_redis_db.ping()
                except Exception:
                    logging.warning(f"Redis connection lost in thread {threading.current_thread().name}, reconnecting...")
                    await self.connect()
        except Exception as e:
            logging.error(f"Failed to ensure Redis connection: {e}")
            raise
    
    def _create_redis_pool(self) -> BlockingConnectionPool:
        pool_config = {
            "max_connections": 10,
            "socket_keepalive": True,
            "retry_on_timeout": True,
            "health_check_interval": 30,
            "retry": Retry(ExponentialBackoff(cap=10, base=1), 5),
            "timeout": 20,
            "socket_connect_timeout": 10,
            "socket_timeout": 10
        }
        
        if self.redis_password:
            pool_config["password"] = self.redis_password
        
        if "://" in self.redis_host:
            return BlockingConnectionPool.from_url(self.redis_host, **pool_config)
        else:
            return BlockingConnectionPool(
                host=self.redis_host, 
                port=self.redis_port, 
                **pool_config
            )
    
    async def add_task_to_queue(self, task: Dict[str, Any]) -> bool:
        try:
            await self._ensure_connection()
            
            thread_redis_db, _ = self._get_thread_redis_connection()
            
            task_json = json.dumps(task, ensure_ascii=False)
            task_id = self._extract_task_id(task, task_json)

            lua_script = """
            local added = redis.call('SADD', KEYS[1], ARGV[1])
            if added == 1 then
                return redis.call('RPUSH', KEYS[2], ARGV[2])
            else
                return 0
            end
            """
            result = await thread_redis_db.eval(lua_script, 2, TASK_ID_SET_KEY, QUERY_QUEUE_KEY, task_id, task_json)
            if isinstance(result, (int,)) and result == 0:
                # logging.info(f"Duplicate task ignored (task_id={task_id})")
                return False
            
            return True

        except Exception as e:
            logging.error(f"Failed to add task to queue: {e}")
            return False
    
    async def get_task_from_queue(self, timeout: int = 1) -> Optional[Dict[str, Any]]:

        try:
            await self._ensure_connection()
            
            thread_redis_db, _ = self._get_thread_redis_connection()

            result = await thread_redis_db.blpop(QUERY_QUEUE_KEY, timeout=timeout)
            
            if result:
                task_json = result[1]
                task = json.loads(task_json)
                task_id = self._extract_task_id(task, task_json)
                if task_id:
                    try:
                        await thread_redis_db.srem(TASK_ID_SET_KEY, task_id)
                    except Exception:
                        pass
                return task
            else:
                return None
                
        except Exception as e:
            logging.error(f"Failed to get task from queue: {e}")
            return None
    
    async def get_queue_length(self) -> int:
        try:
            await self._ensure_connection()
            
            thread_redis_db, _ = self._get_thread_redis_connection()
            
            length = await thread_redis_db.llen(QUERY_QUEUE_KEY)
            return length
            
        except Exception as e:
            logging.error(f"Failed to get queue length: {e}")
            return 0
    
    async def clear_queue(self) -> bool:
        try:
            await self._ensure_connection()
            
            thread_redis_db, _ = self._get_thread_redis_connection()
            
            await thread_redis_db.delete(QUERY_QUEUE_KEY)
            await thread_redis_db.delete(TASK_ID_SET_KEY)
            return True
            
        except Exception as e:
            logging.error(f"Failed to clear queue: {e}")
            return False
    
    async def close(self):
        try:
            thread_redis_db, _ = self._get_thread_redis_connection()
            if thread_redis_db:
                await thread_redis_db.close()
                self._set_thread_redis_connection(None, None)

            if self.redis_db:
                await self.redis_db.close()
                self.redis_db = None
        except Exception as e:
            logging.error(f"Error closing Redis connection: {e}")


class CognifyQueueProcessor:

    def __init__(self, queue_manager: RedisQueueManager, task_client: CognifyTaskClient, contender_client: ContenderClient,
                 task_config_client=None, node_handshake_data: Dict[str, Dict[str, Any], ] = None,
                 validator_config: ValidatorConfig = None):
        self.queue_manager = queue_manager
        self.task_client = task_client
        self.node_handshake_data = node_handshake_data or {}
        self.contender_allocator = ContenderAllocator(
            contender_client,
            task_config_client,
            redis_host=queue_manager.redis_host,
            redis_port=queue_manager.redis_port,
            redis_password=queue_manager.redis_password,
            node_handshake_data=self.node_handshake_data
        )
        self.running = False
        self.tasks: set[asyncio.Task] = set()
        self.validator_config = validator_config
    async def fetch_tasks_from_center(self, batch_size: int = 10) -> List[Dict[str, Any]]:
        try:
            tasks = await self.task_client.get_pending_tasks(limit=batch_size)
            return tasks
        except Exception as e:
            return []
    
    async def add_tasks_to_queue(self, tasks: List[Dict[str, Any]]) -> int:
        added_count = 0
        for task in tasks:
            if await self.queue_manager.add_task_to_queue(task):
                added_count += 1
        
        return added_count
    
    async def process_queue_task(self, task: Dict[str, Any]) -> bool:
        try:
            task_id = task.get('task_id')
            task_type = task.get('task_type')
            if not task_type :
                task_type = task.get('task')

            await self.task_client.update_task_status(task_id, "processing")
            
            if self.validator_config.replace_with_localhost:
                contenders = await self.contender_allocator.get_contenders_for_task(task_type, 1)
            else:
                contenders = await self.contender_allocator.get_contenders_for_task(task_type, -1)

            if not contenders:
                await self.task_client.update_task_status(
                    task_id, 
                    "failed", 
                    error_message="No contenders available"
                )
                return False
            
            success = await self.contender_allocator.process_task_with_contenders(task, contenders)
            
            if success:
                result_data = {
                    'type': task_type,
                    'task_id': task_id,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'completed',
                    'contenders_used': len(contenders)
                }
                
                await self.task_client.complete_task(task_id, result_data)
            else:
                await self.task_client.update_task_status(
                    task_id, 
                    "failed", 
                    error_message="All contenders failed to process task"
                )
                logging.error(f"Failed to process queue task {task_id} with all contenders")
            
            return success
            
        except Exception as e:
            logging.error(f"Error processing queue task {task.get('task_id')}: {e}")
            await self.task_client.update_task_status(
                task.get('task_id'), 
                "failed", 
                error_message=str(e)
            )
            return False
    
    async def listen_for_queue_tasks(self):
        logging.info("Listening for queue tasks...")
        while self.running:
            try:
                done = {t for t in self.tasks if t.done()}
                self.tasks.difference_update(done)
                for t in done:
                    await t
                
                while len(self.tasks) < MAX_CONCURRENT_TASKS:
                    task = await self.queue_manager.get_task_from_queue(timeout=5)
                    
                    if not task:
                        break
                    
                    try:
                        task_coro = self.process_queue_task(task)
                        asyncio_task = asyncio.create_task(task_coro)
                        self.tasks.add(asyncio_task)
                        
                    except Exception as e:
                        logging.error(f"Failed to create task for queue message: {e}")
                
                queue_length = await self.queue_manager.get_queue_length()
                if queue_length == 0:
                    await asyncio.sleep(90)
                    new_tasks = await self.fetch_tasks_from_center(batch_size=20)
                    if new_tasks:
                        await self.add_tasks_to_queue(new_tasks)
                    else:
                        await asyncio.sleep(5)
                
                await asyncio.sleep(0.01)
                
            except Exception as e:
                logging.error(f"Error in listen_for_queue_tasks: {e}")
                await asyncio.sleep(1)
    
    async def run_queue_processor(self, fetch_interval: int = 30):
        self.running = True
        
        try:
            current_loop = asyncio.get_running_loop()

            queue_length = await self.queue_manager.get_queue_length()
            if queue_length == 0:
                initial_tasks = await self.fetch_tasks_from_center(batch_size=20)
                if initial_tasks:
                    await self.add_tasks_to_queue(initial_tasks)
            
            await self.listen_for_queue_tasks()
            
        except Exception as e:
            logging.error(f"Error in queue processor: {e}")
        finally:
            self.running = False
    
    def stop(self):
        self.running = False
        logging.info("Queue processor stopped")


async def main():
    import os
    
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    redis_password = os.getenv("REDIS_PASSWORD", None)
    config_server_url = os.getenv("CONFIG_SERVER_URL", "http://config.asiatensor.xyz")
    validator_hotkey = os.getenv("VALIDATOR_HOTKEY")
    token = os.getenv("VALIDATOR_TOKEN")
    
    if not validator_hotkey:
        logging.error("VALIDATOR_HOTKEY environment variable is required")
        return
    
    queue_manager = RedisQueueManager(redis_host, redis_port, redis_password)
    await queue_manager.connect()
    
    async with CognifyTaskClient(config_server_url, validator_hotkey, token) as task_client:
        async with ContenderClient(config_server_url, validator_hotkey, token) as contender_client:
            task_config_client = TaskConfigClient(config_server_url, validator_hotkey, token)
            processor = CognifyQueueProcessor(queue_manager, task_client, contender_client, task_config_client)
            try:
                await processor.run_queue_processor()
            except KeyboardInterrupt:
                logging.info("Received interrupt signal, stopping...")
                processor.stop()
            finally:
                await queue_manager.close()


if __name__ == "__main__":
    asyncio.run(main()) 