import clip
import constants as cst
import os
import torch


def get_clip_device():
    device = os.getenv("DEVICE", cst.DEFAULT_DEVICE)
    
    if device.startswith("cuda:"):
        return device
    
    if device == "cuda":
        return "cuda:0"
    
    return device


class ClipEmbeddingsProcessor:
    def __init__(self):
        self.clip_device = get_clip_device()
        print(f"CLIP using device: {self.clip_device}")
        self._clip_model, self._clip_preprocess = clip.load("ViT-B/32", device=self.clip_device)

    def get_clip_resources(self):
        return self._clip_model, self._clip_preprocess
