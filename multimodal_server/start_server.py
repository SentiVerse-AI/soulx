#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import uvicorn
from pathlib import Path

current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

if "CUBLAS_WORKSPACE_CONFIG" not in os.environ:
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"

def main():
    parser = argparse.ArgumentParser(description='Multimodal Server')
    parser.add_argument('--host', default='0.0.0.0', help='Server host')
    parser.add_argument('--port', type=int, default=6919, help='Server port')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--workers', type=int, default=1, help='Number of workers')
    parser.add_argument('--reload', action='store_true', help='Enable auto reload')
    parser.add_argument('--start-services', action='store_true', help='Start backend services (ComfyUI and vLLM)')
    
    args = parser.parse_args()
    
    print(f"Starting Multimodal Server on {args.host}:{args.port}")
    print(f"Debug mode: {args.debug}")
    print(f"Workers: {args.workers}")
    print(f"Auto reload: {args.reload}")
    print(f"Start backend services: {args.start_services}")
    
    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers,
    )

if __name__ == "__main__":
    main() 