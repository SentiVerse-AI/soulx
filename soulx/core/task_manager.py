import os
import random
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from bittensor import logging
import ijson

from soulx.core.storage.base_storage import BaseStorage
from soulx.core.constants import DEFAULT_TASK_POOL_SIZE, MAX_TASK_POOL_SIZE, MAX_VALIDATOR_BLOCKS
from soulx.core.task_type import TaskType
import asyncio
from functools import lru_cache
import markovify
from datasets import load_dataset
import base64
from PIL import Image
from io import BytesIO
import glob

@dataclass
class TaskData:
    task_id: str
    text: str
    metadata: Dict[str, Any]
    ground_truth: Optional[float] = None
    difficulty: float = 1.0
    completed: bool = False

class TaskManager:

    def __init__(self, storage: BaseStorage, task_data_path: str, max_tasks: int = DEFAULT_TASK_POOL_SIZE):
        self.storage = storage
        self.task_data_path = task_data_path
        self.max_tasks = max_tasks
        
        self.task_pool: Dict[str, TaskData] = {}
        self.assigned_tasks: Dict[str, Dict[str, List[str]]] = {}  # {miner_hotkey: {validator_hotkey: [task_ids]}}
        
        self.file_positions: Dict[str, int] = {}  # {file_path: current_position}
        self.used_task_ids: set = set()
        self.file_task_counts: Dict[str, int] = {}
        self.total_blocks_run: int = 0
        
        self._load_state()
        self._load_tasks()
        
    def _count_tasks_in_file(self, file_path: str) -> int:
        try:
            if file_path in self.file_task_counts:
                return self.file_task_counts[file_path]
                
            count = 0
            with open(file_path, 'r',  encoding="utf-8") as f:
                parser = ijson.parse(f)
                for prefix, event, value in parser:
                    if prefix.endswith('.task_id'):
                        count += 1
                        
            self.file_task_counts[file_path] = count
            return count
        except Exception as e:
            logging.error(f"Error counting tasks in file {file_path}: {e}")
            return 0
        
    def _load_tasks(self):
        try:
            if not os.path.exists(self.task_data_path):
                logging.warning(f"Task data path not found: {self.task_data_path}")
                return
                
            check_max_blocks = os.getenv("CHECK_MAX_BLOCKS", "false").lower() == "true"
            
            self.task_pool.clear()
            self.reset_all_assignments()
                
            if os.path.isfile(self.task_data_path):

                self._load_task_file(self.task_data_path, check_max_blocks)
            elif os.path.isdir(self.task_data_path):
                for filename in os.listdir(self.task_data_path):
                    if filename.endswith('.json'):
                        file_path = os.path.join(self.task_data_path, filename)
                        if not check_max_blocks and len(self.task_pool) >= self.max_tasks:
                            break
                        self._load_task_file(file_path, check_max_blocks)
                        
            logging.info(f"Loaded {len(self.task_pool)} tasks from {self.task_data_path}")
            
        except Exception as e:
            logging.error(f"Error loading task data: {e}")
            
    def _load_task_file(self, file_path: str, check_max_blocks: bool):
        try:
            total_tasks = self._count_tasks_in_file(file_path)
            if total_tasks == 0:
                return
                
            current_position = self.file_positions.get(file_path, 0)
            
            if current_position >= total_tasks:
                current_position = 0
                
            remaining_slots = self.max_tasks - len(self.task_pool)
            if remaining_slots <= 0:
                return
                
            tasks_loaded = 0
            skipped_tasks = 0
            
            with open(file_path, 'r',  encoding="utf-8") as f:
                parser = ijson.items(f, 'item')
                
                for task in parser:
                    if skipped_tasks < current_position:
                        skipped_tasks += 1
                        continue
                        
                    if tasks_loaded >= remaining_slots:
                        break
                        
                    if not check_max_blocks and task['task_id'] in self.used_task_ids:
                        continue
                        
                    task_data = TaskData(
                        task_id=task['task_id'],
                        text=task['text'],
                        metadata=task.get('metadata', {}),
                        ground_truth=task.get('ground_truth'),
                        difficulty=task.get('difficulty', 1.0)
                    )
                    self.task_pool[task_data.task_id] = task_data
                    tasks_loaded += 1

            new_position = current_position + tasks_loaded
            if new_position >= total_tasks:
                new_position = 0

            self.file_positions[file_path] = new_position

            logging.info(
                f"Loaded {tasks_loaded} tasks from {file_path} "
                f"(position: {current_position} -> {new_position}, "
                f"total tasks: {total_tasks})"
            )
            self._save_state()
                
        except Exception as e:
            logging.error(f"Error loading task file {file_path}: {e}")
            
    def _load_state(self):
        try:
            state = self.storage.get("task_state", {})
            self.assigned_tasks = state.get("assigned_tasks", {})
            self.file_positions = state.get("file_positions", {})
            self.used_task_ids = set(state.get("used_task_ids", []))
            self.file_task_counts = state.get("file_task_counts", {})
            self.total_blocks_run = state.get("total_blocks_run", 0)
            
            completed_tasks = state.get("completed_tasks", {})
            for task_id, completed in completed_tasks.items():
                if task_id in self.task_pool:
                    self.task_pool[task_id].completed = completed
                    
        except Exception as e:
            logging.error(f"Failed to load task state: {e}")
            
    def _save_state(self):
        try:
            completed_tasks = {
                task_id: task.completed 
                for task_id, task in self.task_pool.items()
            }
            
            state = {
                "assigned_tasks": self.assigned_tasks,
                "completed_tasks": completed_tasks,
                "file_positions": self.file_positions,
                "used_task_ids": list(self.used_task_ids),
                "file_task_counts": self.file_task_counts,
                "total_blocks_run": self.total_blocks_run
            }
            self.storage.set("task_state", state)
        except Exception as e:
            logging.error(f"Failed to save task state: {e}")
            
    def update_blocks_run(self, blocks: int):
        self.total_blocks_run = blocks
        self._save_state()
            
    def reset_all_assignments(self):
        self.assigned_tasks.clear()
        self._save_state()
        logging.info("Reset all task assignments")
            
    def get_task_for_miner(self, miner_hotkey: str, validator_hotkey: str) -> Optional[TaskData]:
        print("get_task_for_miner start.....")
        try:
            check_max_blocks = os.getenv("CHECK_MAX_BLOCKS", "false").lower() == "true"
            logging.info(f"get_task_for_miner check_max_blocks {check_max_blocks} ,total_blocks_run: {self.total_blocks_run}")
            if check_max_blocks and self.total_blocks_run >= MAX_VALIDATOR_BLOCKS:
                logging.info(f"Reached maximum validator blocks ({MAX_VALIDATOR_BLOCKS}), no more tasks will be provided")
                return None
            
            available_tasks = [
                task for task in self.task_pool.values()
                if not task.completed
            ]
            
            if not available_tasks:
                logging.info(f"get_task_for_miner available_tasks")
                self.task_pool.clear()
                
                if not check_max_blocks:
                    self.reset_all_assignments()
                    state = self.storage.get("task_state", {})
                    state["completed_tasks"] = {}
                    self.storage.set("task_state", state)
                    
                self._load_tasks()
                
                available_tasks = [
                    task for task in self.task_pool.values()
                    if not task.completed
                ]
                logging.info(f"get_task_for_miner available_tasks: {len(available_tasks)}")
                if not available_tasks:
                    logging.warning("No available tasks after reload")
                return None
                
            miner_tasks = self.assigned_tasks.get(miner_hotkey, {})
            validator_tasks = miner_tasks.get(validator_hotkey, [])
            
            unassigned_tasks = [
                task for task in available_tasks
                if task.task_id not in validator_tasks
            ]
            
            logging.info(f"get_task_for_miner unassigned_tasks: {len(unassigned_tasks)}")
            if not unassigned_tasks:
                logging.warning(f"No unassigned tasks for miner {miner_hotkey}")
                return None
                
            task = random.choice(unassigned_tasks)
            
            logging.info(f"get_task_for_miner task: {task}")
            if miner_hotkey not in self.assigned_tasks:
                self.assigned_tasks[miner_hotkey] = {}
            if validator_hotkey not in self.assigned_tasks[miner_hotkey]:
                self.assigned_tasks[miner_hotkey][validator_hotkey] = []
                
            self.assigned_tasks[miner_hotkey][validator_hotkey].append(task.task_id)
            
            if not check_max_blocks:
                self.used_task_ids.add(task.task_id)
            
            self._save_state()
            logging.info(f"get_task_for_miner return task: {task}")
            return task
            
        except Exception as e:
            logging.error(f"Error getting task for miner: {e}")
            return None
            
    def mark_task_completed(self, task_id: str, success: bool = True):
        if task_id in self.task_pool:
            self.task_pool[task_id].completed = success
            self._save_state()
            
    def get_task_stats(self) -> Dict[str, Any]:
        total_tasks = len(self.task_pool)
        completed_tasks = len([t for t in self.task_pool.values() if t.completed])
        
        return {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "completion_rate": completed_tasks / total_tasks if total_tasks > 0 else 0,
            "assigned_miners": len(self.assigned_tasks),
            "used_tasks": len(self.used_task_ids)
        }
        
    def reset_miner_tasks(self, miner_hotkey: str):
        if miner_hotkey in self.assigned_tasks:
            del self.assigned_tasks[miner_hotkey]
            self._save_state() 

    def add_task(self, task_data: TaskData):
        self.task_pool[task_data.task_id] = task_data
        self._save_state()

    def add_tasks(self, tasks: list):
        for task_data in tasks:
            self.task_pool[task_data.task_id] = task_data
        self._save_state() 

    @lru_cache(maxsize=1)
    def get_cached_markov_model(self):
        try:
            dataset = load_dataset("assets/caption_data/data")
        except FileNotFoundError:
            dataset = load_dataset("validator/control_node/assets/caption_data/data")
        text = [i["query"] for i in dataset["train"]]
        return markovify.Text(" ".join(text))

    async def markov_model_factory(self):
        return await asyncio.to_thread(self.get_cached_markov_model)

    async def _get_markov_sentence(self, max_words: int = 10) -> str:
        markov_text_generation_model = await self.markov_model_factory()
        text = None
        while text is None:
            text = markov_text_generation_model.make_sentence(max_words=max_words)
        return text

    async def generate_text_task(self, max_words: int = 10) -> TaskData:
        text = await self._get_markov_sentence(max_words=max_words)
        return TaskData(
            task_id=f"markov_{hash(text)}",
            text=text,
            metadata={"category": TaskType.TEXT_CLASSIFICATION.value},
            ground_truth=None,
            difficulty=1.0
        )

    async def generate_text2img_task(self, max_words: int = 10) -> TaskData:
        text = await self._get_markov_sentence(max_words=max_words)
        return TaskData(
            task_id=f"text2img_{hash(text)}",
            text=text,
            metadata={"category": TaskType.SENTIMENT_ANALYSIS.value, "type": "text2img"},
            ground_truth=None,
            difficulty=1.2
        )

    def get_default_images(self, image_dir: str = "assets/default_images") -> list:
        image_paths = glob.glob(f"{image_dir}/*.png") + glob.glob(f"{image_dir}/*.jpg") + glob.glob(f"{image_dir}/*.jpeg")
        return image_paths

    def pil_to_base64(self, pil_image: Image.Image) -> str:
        buffered = BytesIO()
        pil_image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()

    def alter_image(self, pil_image: Image.Image) -> str:
        for _ in range(3):
            rand_x, rand_y = (
                random.randint(0, pil_image.width - 1),
                random.randint(0, pil_image.height - 1),
            )
            pixel = list(pil_image.getpixel((rand_x, rand_y)))
            for i in range(3):
                change = random.choice([-1, 1])
                pixel[i] = max(0, min(255, pixel[i] + change))
            pil_image.putpixel((rand_x, rand_y), tuple(pixel))
        if pil_image.mode == "RGBA":
            pil_image = pil_image.convert("RGB")
        return self.pil_to_base64(pil_image)

    async def generate_img2img_task(self) -> TaskData:
        # 随机选取一张默认图片
        image_paths = self.get_default_images()
        if not image_paths:
            raise ValueError("未找到默认图片")
        image_path = random.choice(image_paths)
        pil_image = Image.open(image_path)
        base64_img = self.alter_image(pil_image)
        return TaskData(
            task_id=f"img2img_{hash(base64_img)}",
            text="[Image2Image task]",
            metadata={"category": TaskType.SCENE_UNDERSTANDING.value, "type": "img2img", "base64_image": base64_img},
            ground_truth=None,
            difficulty=1.5
        )

    async def generate_tasks(self, task_type: TaskType, count: int = 1, max_words: int = 10) -> list:
        tasks = []
        for _ in range(count):
            if task_type == TaskType.TEXT_CLASSIFICATION:
                task = await self.generate_text_task(max_words=max_words)
            elif task_type == TaskType.SENTIMENT_ANALYSIS:
                task = await self.generate_text2img_task(max_words=max_words)
            elif task_type == TaskType.SCENE_UNDERSTANDING:
                task = await self.generate_img2img_task()
            else:
                raise ValueError("不支持的任务类型")
            tasks.append(task)
        self.add_tasks(tasks)
        return tasks 