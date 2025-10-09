# -*- coding: utf-8 -*-

import asyncio
import json
from bittensor import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

import requests

class CognifyTaskClient:

    def __init__(self, base_url: str, validator_hotkey: str, token: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.validator_hotkey = validator_hotkey
        self.token = token
        self.session = requests.Session()
        self._setup_session()
    
    def _setup_session(self):
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Hotkey': self.validator_hotkey
        })
        
        if self.token:
            self.session.headers.update({
                'Authorization': f'Bearer {self.token}'
            })
        
        self.session.timeout = 30
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def ensure_session(self):
        pass
    
    async def close(self):
        pass
    
    def _get_headers(self) -> Dict[str, str]:
        headers = {
            'Content-Type': 'application/json',
            'Hotkey': self.validator_hotkey
        }
        
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        
        return headers
    
    async def get_pending_tasks(self, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        try:
            url = f"{self.base_url}/tasks/pending"
            params = {
                'limit': limit,
                'offset': offset
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            if data.get('success'):
                return data.get('tasks', [])
            else:
                return []
                    
        except requests.exceptions.RequestException as e:
            return []
        except Exception as e:
            return []
    
    async def update_task_status(
        self,
        task_id: str,
        status: str,
        error_message: Optional[str] = None,
        result_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        try:
            url = f"{self.base_url}/tasks/{task_id}/status"
            data = {
                'status': status
            }
            
            if error_message is not None:
                data['error_message'] = error_message
            
            if result_data is not None:
                data['result_data'] = result_data
            
            response = self.session.put(url, json=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result.get('success', False)
                    
        except requests.exceptions.RequestException as e:
            logging.error(f"Request error updating task status: {e}")
            return False
        except Exception as e:
            logging.error(f"Error updating task status: {e}")
            return False
    
    async def complete_task(self, task_id: str, result_data: Optional[Dict[str, Any]] = None) -> bool:
        try:
            url = f"{self.base_url}/tasks/{task_id}/complete"
            data = {}
            
            if result_data is not None:
                data['result_data'] = result_data
            
            response = self.session.post(url, json=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result.get('success', False)
                    
        except requests.exceptions.RequestException as e:
            logging.error(f"Request error completing task: {e}")
            return False
        except Exception as e:
            logging.error(f"Error completing task: {e}")
            return False
    
    async def process_task(self, task: Dict[str, Any]) -> bool:
        task_id = task['task_id']
        task_type = task['task_type']
        
        try:
            logging.info(f"Processing task {task_id} of type {task_type}")
            
            await self.update_task_status(task_id, "processing")
            
            result = {
                'type': task_type,
                'task_id': task_id,
                'timestamp': datetime.now().isoformat(),
                'status': 'completed'
            }
            
            success = await self.complete_task(task_id, result)
            
            if success:
                logging.info(f"Successfully processed task {task_id}")
            else:
                logging.error(f"Failed to complete task {task_id}")
            
            return success
            
        except Exception as e:
            await self.update_task_status(task_id, "failed", error_message=str(e))
            return False
    
    async def run_task_processor(self, batch_size: int = 10, sleep_interval: int = 5):
        logging.info(f"Starting task processor for validator {self.validator_hotkey}")
        
        while True:
            try:
                tasks = await self.get_pending_tasks(limit=batch_size)
                
                if not tasks:
                    logging.debug(f"No pending tasks, sleeping for {sleep_interval} seconds")
                    await asyncio.sleep(sleep_interval)
                    continue
                
                for task in tasks:
                    success = await self.process_task(task)
                    if success:
                        logging.debug(f"Task {task['task_id']} processed successfully")
                    else:
                        logging.warning(f"Task {task['task_id']} processing failed")
                
                await asyncio.sleep(1)
                
            except Exception as e:
                logging.error(f"Error in task processor: {e}")
                await asyncio.sleep(10)
