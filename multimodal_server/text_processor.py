#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import httpx
import json
import logging
import os
from typing import Dict, List, Optional, Any, AsyncGenerator
from loguru import logger
from dotenv import load_dotenv

load_dotenv('.multimodal_server.example')

class TextProcessor:

    def __init__(self, vllm_host: str = None, vllm_port: int = None):
        self.vllm_host = vllm_host or os.getenv('VLLM_HOST', '127.0.0.1')
        self.vllm_port = vllm_port or int(os.getenv('VLLM_PORT', '8000'))
        self.base_url = f"http://{self.vllm_host}:{self.vllm_port}"
        self.client = httpx.AsyncClient(timeout=120.0)
        logger.info(f"Text generation base_url: {self.base_url}")

        
    async def check_vllm_status(self) -> bool:
        try:
            response = await self.client.get(f"{self.base_url}/v1/models", timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"vLLM service not ready: {e}")
            return False
    
    async def get_available_models(self) -> List[str]:
        try:
            response = await self.client.get(f"{self.base_url}/v1/models")
            if response.status_code == 200:
                data = response.json()
                return [model['id'] for model in data.get('data', [])]
            return []
        except Exception as e:
            logger.error(f"Failed to get models: {e}")
            return []
    
    async def generate_text(
        self,
        prompt: str,
        model: str = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stop: List[str] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        try:
            if model is None:
                models = await self.get_available_models()
                if not models:
                    raise ValueError("No models available")
                model = models[0]
            
            payload = {
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "stream": stream
            }
            
            if stop:
                payload["stop"] = stop
            
            response = await self.client.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "text": data["choices"][0]["message"]["content"],
                    "model": model,
                    "usage": data.get("usage", {}),
                    "finish_reason": data["choices"][0].get("finish_reason", "stop")
                }
            else:
                logger.error(f"Text generation failed: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Text generation error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_text_stream(
        self,
        prompt: str,
        model: str = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stop: List[str] = None
    ) -> AsyncGenerator[str, None]:
        try:
            if model is None:
                models = await self.get_available_models()
                if not models:
                    raise ValueError("No models available")
                model = models[0]
            
            payload = {
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "stream": True
            }
            
            if stop:
                payload["stop"] = stop
            
            async with self.client.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                json=payload
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.strip():

                        if "data: " in line:
                            parts = line.split("data: ")
                            for part in parts:
                                if part.strip():
                                    yield f"data: {part.strip()}\n"
                        else:
                            yield line
                            
        except Exception as e:
            logger.error(f"Text stream generation error: {e}")
            yield f"Error: {str(e)}"
    
    async def generate_text_completion_stream(
        self,
        prompt: str,
        model: str = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stop: List[str] = None
    ) -> AsyncGenerator[str, None]:
        try:
            if model is None:
                models = await self.get_available_models()
                if not models:
                    raise ValueError("No models available")
                model = models[0]
            
            payload = {
                "model": model,
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "stream": True
            }
            
            if stop:
                payload["stop"] = stop
            
            async with self.client.stream(
                "POST",
                f"{self.base_url}/v1/completions",
                json=payload
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.strip():
                        if "data: " in line:
                            parts = line.split("data: ")
                            for part in parts:
                                if part.strip():
                                    yield f"data: {part.strip()}\n"
                        else:
                            yield line
                            
        except Exception as e:
            logger.error(f"Text completion stream error: {e}")
            yield f"Error: {str(e)}"
    
    async def generate_text_completion(
        self,
        prompt: str,
        model: str = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stop: List[str] = None
    ) -> Dict[str, Any]:
        try:
            if model is None:
                models = await self.get_available_models()
                if not models:
                    raise ValueError("No models available")
                model = models[0]
            
            payload = {
                "model": model,
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p
            }
            
            if stop:
                payload["stop"] = stop
            
            response = await self.client.post(
                f"{self.base_url}/v1/completions",
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "text": data["choices"][0]["text"],
                    "model": model,
                    "usage": data.get("usage", {}),
                    "finish_reason": data["choices"][0].get("finish_reason", "stop")
                }
            else:
                logger.error(f"Text completion failed: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Text completion error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def batch_generate_text(
        self,
        prompts: List[str],
        model: str = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        top_p: float = 0.9
    ) -> List[Dict[str, Any]]:
        tasks = []
        for prompt in prompts:
            task = self.generate_text(
                prompt=prompt,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p
            )
            tasks.append(task)
        
        return await asyncio.gather(*tasks)
    
    async def close(self):
        await self.client.aclose()

text_processor = TextProcessor()


async def get_text_processor() -> TextProcessor:

    if not await text_processor.check_vllm_status():
        logger.warning("vLLM service not available, but returning processor anyway")
    return text_processor 