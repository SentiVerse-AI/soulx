#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import time
import threading
import signal
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
import requests
import json
from loguru import logger


class ServiceManager:

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.processes: Dict[str, subprocess.Popen] = {}
        self.services_status: Dict[str, bool] = {}
        self.running = False

        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        self.work_dir = Path(config.get('work_dir', './workspace'))
        self.work_dir.mkdir(exist_ok=True)

        self.vllm_config = config.get('vllm', {})
        self.vllm_port = self.vllm_config.get('port', 8000)
        self.vllm_host = self.vllm_config.get('host', '127.0.0.1')


    def start_vllm(self) -> bool:
        try:
            self.logger.info("=" * 60)
            self.logger.info("Starting vLLM service...")
            self.logger.info(f"vLLM Host: {self.vllm_host}")
            self.logger.info(f"vLLM Port: {self.vllm_port}")
            self.logger.info(f"Work Directory: {self.work_dir}")

            model_name = self.vllm_config.get('model', 'Qwen/Qwen3-32B')
            model_path = self.vllm_config.get('model_path', None)

            self.logger.info(f"vLLM Model: {model_path if model_path else model_name}")
            self.logger.info(f"vLLM Tensor Parallel Size: {self.vllm_config.get('tensor_parallel_size', 1)}")
            self.logger.info(f"vLLM GPU Memory Utilization: {self.vllm_config.get('gpu_memory_utilization', 0.9)}")
            self.logger.info(f"vLLM Max Model Length: {self.vllm_config.get('max_model_len', 4096)}")

            current_dir = Path.cwd() / "vllm"
            self.logger.info(f"Current directory for vLLM: {current_dir}")

            cmd = [
                sys.executable,  "vllm/entrypoints/openai/api_server.py",
                "--model", model_path if model_path else model_name,
                "--host", self.vllm_host,
                "--port", str(self.vllm_port),
                "--max-model-len", str(self.vllm_config.get('max_model_len', 2048)),
                "--max-num-batched-tokens", str(self.vllm_config.get('max_num_batched_tokens', 4096))
            ]

            self.logger.info(f"vLLM start command: {' '.join(cmd)}")

            self.logger.info("Launching vLLM process...")
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=current_dir
            )

            self.processes['vllm'] = process
            self.logger.info(f" vLLM process started with PID: {process.pid}")

            self.logger.info("Waiting for vLLM service to be ready...")
            if self.wait_for_service(f"http://{self.vllm_host}:{self.vllm_port}/v1/models", "vLLM"):
                self.services_status['vllm'] = True
                self.logger.info(" vLLM service started successfully!")
                return True
            else:
                try:
                    out, err = process.communicate(timeout=5)
                    self.logger.error(f" vLLM failed to start within timeout")
                    self.logger.error(f"vLLM stdout: {out}")
                    self.logger.error(f"vLLM stderr: {err}")
                except subprocess.TimeoutExpired:
                    self.logger.error(" vLLM process communication timeout")
                return False

        except Exception as e:
            self.logger.error(f" Exception while starting vLLM: {e}")
            import traceback
            self.logger.error(f"vLLM startup traceback: {traceback.format_exc()}")
            return False

    def wait_for_service(self, url: str, service_name: str, timeout: int = 60) -> bool:
        self.logger.info(f"Waiting for {service_name} service to start at {url}...")

        start_time = time.time()
        attempt_count = 0

        while time.time() - start_time < timeout:
            attempt_count += 1
            elapsed_time = time.time() - start_time

            try:
                self.logger.debug(
                    f"Attempt {attempt_count}: Checking {service_name} at {url} (elapsed: {elapsed_time:.1f}s)")
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    self.logger.info(f" {service_name} service is ready! (took {elapsed_time:.1f}s)")
                    return True
                else:
                    self.logger.debug(f"{service_name} returned status code: {response.status_code}")
            except requests.exceptions.ConnectionError as e:
                self.logger.debug(f"{service_name} connection error: {e}")
            except requests.exceptions.Timeout as e:
                self.logger.debug(f"{service_name} timeout: {e}")
            except requests.exceptions.RequestException as e:
                self.logger.debug(f"{service_name} request error: {e}")
            except Exception as e:
                self.logger.debug(f"{service_name} unexpected error: {e}")

            if attempt_count % 5 == 0:
                self.logger.info(
                    f"Still waiting for {service_name}... (attempt {attempt_count}, elapsed {elapsed_time:.1f}s)")

            time.sleep(2)

        self.logger.error(f" {service_name} service failed to start within {timeout} seconds")
        return False

    def start_services(self) -> bool:

        self.running = True

        self.logger.info("Starting vLLM service...")
        if not self.start_vllm():
            self.logger.error(" vLLM service failed to start")
            return False
        self.logger.info(" vLLM service started successfully")

        return True

    def stop_service(self, service_name: str):
        if service_name in self.processes:
            process = self.processes[service_name]
            self.logger.info(f"Stopping {service_name} service (PID: {process.pid})")

            try:
                self.logger.info(f"Sending SIGTERM to {service_name} process...")
                process.terminate()
                process.wait(timeout=10)
                self.logger.info(f" {service_name} service stopped gracefully")
            except subprocess.TimeoutExpired:
                self.logger.warning(f"  {service_name} service didn't stop gracefully, force killing...")
                process.kill()
                process.wait()
                self.logger.info(f" {service_name} service force killed")

            self.services_status[service_name] = False
            del self.processes[service_name]
            self.logger.info(f" {service_name} service cleanup completed")
        else:
            self.logger.info(f" {service_name} service not found in running processes")

    def stop_all_services(self):
        self.logger.info("=" * 60)
        self.logger.info(" Stopping  backend services...")
        self.logger.info("=" * 60)

        self.running = False

        if not self.processes:
            self.logger.info(" No services are currently running")
            return

        for service_name in list(self.processes.keys()):
            self.stop_service(service_name)

        self.logger.info("=" * 60)
        self.logger.info("  services stopped successfully!")
        self.logger.info("=" * 60)

    def get_service_status(self) -> Dict[str, Any]:
        self.logger.debug(" Getting service status...")

        status = {
            'running': self.running,
            'services': {}
        }

        if not self.processes:
            self.logger.debug(" No services are currently running")
            return status

        for service_name, process in self.processes.items():
            if process.poll() is None:
                status['services'][service_name] = {
                    'running': True,
                    'pid': process.pid
                }
                self.logger.debug(f" {service_name} is running (PID: {process.pid})")
            else:
                status['services'][service_name] = {
                    'running': False,
                    'exit_code': process.returncode
                }
                self.logger.debug(f"{service_name} is not running (exit code: {process.returncode})")

        self.logger.debug(f" Service status: {status}")
        return status

    def check_service_health(self) -> bool:

        try:

            vllm_healthy = False
            if 'vllm' in self.services_status and self.services_status['vllm']:
                try:
                    self.logger.debug(f"Checking vLLM health at http://{self.vllm_host}:{self.vllm_port}/v1/models")
                    response = requests.get(f"http://{self.vllm_host}:{self.vllm_port}/v1/models", timeout=30)
                    vllm_healthy = response.status_code == 200

                except Exception as e:
                    self.logger.warning(f" vLLM health check failed: {e}")
            else:
                self.logger.info("  vLLM not in services status")

            overall_healthy =  vllm_healthy

            return overall_healthy

        except Exception as e:
            self.logger.error(f" Health check failed: {e}")
            import traceback
            self.logger.error(f"Health check traceback: {traceback.format_exc()}")
            return False

    def __enter__(self):
        if not self.start_services():
            raise RuntimeError("Failed to start services")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_all_services()


DEFAULT_CONFIG = {
    'work_dir': './workspace',
    'vllm': {
        'host': '127.0.0.1',
        'port': 8198,
        'model': 'Qwen/Qwen3-32B',
        'model_path': None,
        'tensor_parallel_size': 1,
        'gpu_memory_utilization': 0.85,
        "max-num-batched-tokens": 2048,
        "max-num-seqs": 16,
        'max_model_len': 4096
    }
}


def create_service_manager(config: Optional[Dict[str, Any]] = None) -> ServiceManager:
    if config is None:
        config = DEFAULT_CONFIG

    return ServiceManager(config)