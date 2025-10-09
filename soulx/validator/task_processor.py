# -*- coding: utf-8 -*-

import asyncio
import json
from bittensor import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from soulx.validator.task_client import CognifyTaskClient

class CognifyTaskProcessor:

    def __init__(self, task_client: CognifyTaskClient, queue_manager=None):
        self.task_client = task_client
        self.queue_manager = queue_manager
        self.running = False
    
    async def construct_synthetic_query_message(self, task: Dict[str, Any]) -> Dict[str, Any]:

        try:
            query_payload = task.get('query_payload', {})
            task_type = task.get('task_type', 'unknown')
            
            message = {
                'query_payload': query_payload,
                'query_type': 'SYNTHETIC',
                'task': task_type,
                'job_id': uuid.uuid4().hex,
                'task_id': task.get('task_id'),
                'task_type': task_type,
                'validator_hotkey': task.get('validator_hotkey'),
                'miner_hotkey': task.get('miner_hotkey')
            }

            return message
            
        except Exception as e:
            logging.error(f"Error constructing synthetic query message: {e}")
            return {}
    
    async def process_synthetic_task(self, task: Dict[str, Any]) -> bool:

        try:
            task_id = task.get('task_id')
            task_type = task.get('task_type')
            
            message = await self.construct_synthetic_query_message(task)
            if not message:
                logging.error(f"Failed to construct message for task {task_id}")
                return False
            

            success = await self._handle_task_execution(message, task)

        except Exception as e:
            logging.error(f"Error processing synthetic task {task.get('task_id')}: {e}")
            await self.task_client.update_task_status(
                task.get('task_id'), 
                "failed", 
                error_message=str(e)
            )
            return False
    
    async def _handle_task_execution(self, message: Dict[str, Any], task: Dict[str, Any]) -> bool:
        try:
            if not self.queue_manager:
                await asyncio.sleep(1)
                import random
                success = random.random() > 0.1
                return success
            
            success = await self.queue_manager.add_task_to_queue(message)
            
            if success:
                return True
            else:
                return False
            
        except Exception as e:
            logging.error(f"Error in task execution: {e}")
            return False
    
    async def run_task_processor(self, batch_size: int = 40, sleep_interval: int = 60):
        logging.info(f"Starting Soulx task processor")
        self.running = True
        
        while self.running:
            try:
                queue_length = await self.queue_manager.get_queue_length()
                if queue_length == 0:
                    tasks = await self.task_client.get_pending_tasks(limit=batch_size)

                    if not tasks:
                        logging.debug(f"No pending tasks, sleeping for {sleep_interval} seconds")
                        await asyncio.sleep(sleep_interval)
                        continue

                    processing_tasks = []
                    for task in tasks:
                        task_coro = self.process_synthetic_task(task)
                        processing_tasks.append(asyncio.create_task(task_coro))

                    if processing_tasks:
                        results = await asyncio.gather(*processing_tasks, return_exceptions=True)

                        successful = sum(1 for result in results if result is True)
                        failed = len(results) - successful

                    await asyncio.sleep(1)
                
            except Exception as e:
                logging.error(f"Error in task processor: {e}")
                await asyncio.sleep(10)
    
    def stop(self):
        self.running = False
        logging.info("Task processor stopped")