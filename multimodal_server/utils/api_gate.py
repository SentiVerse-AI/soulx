import io
import json
import time
import urllib.parse
import urllib.request
import uuid

from PIL import Image

import websocket

from loguru import logger

import os
from dotenv import load_dotenv

load_dotenv('.multimodal_server.example')

COMFYUI_HOST = os.getenv('COMFYUI_HOST', 'comfyui')
COMFYUI_PORT = os.getenv('COMFYUI_PORT', '8188')
COMFYUI_HOST = "comfyui"
server_address = f"{COMFYUI_HOST}:{COMFYUI_PORT}"
logger.info(f"ComfyUI WebSocket server_address：{server_address}")
client_id = str(uuid.uuid4())
ws = None

def initialize_websocket():
    global ws
    ws = websocket.WebSocket()
    
    while True:
        try:
            ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))
            logger.info("Successfully connected to ComfyUI WebSocket")
            break
        except ConnectionRefusedError:
            logger.error(f"Could not connect to ComfyUI {COMFYUI_HOST} because it is not up yet. Sleeping for 2 seconds before trying again.")
            time.sleep(2)
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            time.sleep(2)

def queue_prompt(prompt):
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode("utf-8")
    req = urllib.request.Request("http://{}/prompt".format(server_address), data=data)
    try:
        prompt_json =  json.loads(urllib.request.urlopen(req).read())
        return prompt_json;
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")


def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen("http://{}/view?{}".format(server_address, url_values)) as response:
        return response.read()


def get_history(prompt_id):
    with urllib.request.urlopen("http://{}/history/{}".format(server_address, prompt_id)) as response:
        return json.loads(response.read())


def get_images(ws, prompt):
    prompt_id = queue_prompt(prompt)["prompt_id"]
    output_images = {}
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message["type"] == "executing":
                data = message["data"]
                if data["node"] is None and data["prompt_id"] == prompt_id:
                    break  # Execution is done
        else:
            continue  # previews are binary data

    history = get_history(prompt_id)[prompt_id]
    for o in history["outputs"]:
        for node_id in history["outputs"]:
            node_output = history["outputs"][node_id]
            if "images" in node_output:
                images_output = []
                for image in node_output["images"]:
                    image_data = get_image(image["filename"], image["subfolder"], image["type"])
                    images_output.append(image_data)
            output_images[node_id] = images_output

    return output_images


def generate(payload):
    global ws
    
    if ws is None:
        logger.warning("WebSocket not initialized, attempting to initialize...")
        try:
            initialize_websocket()
        except Exception as e:
            logger.error(f"Failed to initialize WebSocket: {e}")
            return []
    
    img_list = []
    try:
        images = get_images(ws, payload)
        for node_id in images:
            for image_data in images[node_id]:
                image = Image.open(io.BytesIO(image_data))
                img_list.append(image)
    except Exception as e:
        logger.error(f"Error generating images: {e}")
        return []

    return img_list
