import json
import constants as cst
from base_model import (
    ModelEnum,
    LoadModelRequest
)
from typing import Dict, Any, Tuple, List
from utils.base64_utils import base64_to_image
import os
from loguru import logger
from model_manager import model_manager
import copy
import random


class PayloadModifier:
    def __init__(self):
        self._payloads = {}
        self.supported_workflows = []
        self._load_workflows()
        self.model_manager = model_manager

    def _load_workflows(self):
        directory = cst.WORKFLOWS_DIR
        for filename in os.listdir(directory):
            if filename.endswith(".json"):
                self.supported_workflows.append(filename.split(".")[0])
                filepath = os.path.join(directory, filename)
                with open(filepath, "r") as file:
                    try:
                        data = json.load(file)
                        self._payloads[os.path.splitext(filename)[0]] = data
                    except json.JSONDecodeError as e:
                        logger.error(f"Error decoding JSON from {filename}: {e}")

    def is_valid_model_workflow(self, model: str) -> bool:
        return model in self.supported_workflows

    def is_valid_dynamic_string(self, model: str) -> bool:
        if "|" in model:
            repo_name, model_name = model.split("|", 1)
            return bool(model_name.strip()) and bool(repo_name.strip())
        return False
