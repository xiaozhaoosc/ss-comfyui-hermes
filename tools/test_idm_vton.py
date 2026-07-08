#!/usr/bin/env python3
"""IDM-VTON test workflow for ComfyUI API"""
import json
import urllib.request
import urllib.error
import time
import sys

# API format workflow
prompt = {
    "1": {
        "class_type": "LoadImage",
        "inputs": {
            "image": "human.jpg",
            "upload": "image"
        }
    },
    "2": {
        "class_type": "LoadImage",
        "inputs": {
            "image": "garment.jpg",
            "upload": "image"
        }
    },
    "3": {
        "class_type": "DensePosePreprocessor",
        "inputs": {
            "image": ["1", 0],
            "model": "densepose_r50_fpn_dl.torchscript",
            "cmap": "Viridis (MagicAnimate)",
            "resolution": 512
        }
    },
    "4": {
        "class_type": "FaceProtectMask",
        "inputs": {
            "image": ["1", 0],
            "clothing_labels": "4,7,8",
            "protect_labels": "2,3,11",
            "protect_expand": 10,
            "feather": 5
        }
    },
    "5": {
        "class_type": "PipelineLoader",
        "inputs": {
            "weight_dtype": "float16"
        }
    },
    "6": {
        "class_type": "IDM-VTON",
        "inputs": {
            "pipeline": ["5", 0],
            "human_img": ["1", 0],
            "pose_img": ["3", 0],
            "mask_img": ["4", 0],
            "garment_img": ["2", 0],
            "garment_description": "a casual shirt",
            "negative_prompt": "bad quality, blurry, distorted",
            "width": 768,
            "height": 1024,
            "num_inference_steps": 30,
            "guidance_scale": 2.0,
            "strength": 1.0,
            "seed": 42
        }
    },
    "7": {
        "class_type": "PreviewImage",
        "inputs": {
            "images": ["6", 0]
        }
    }
}

# Queue the workflow
url = "http://127.0.0.1:8188/prompt"
data = json.dumps({"prompt": prompt}).encode('utf-8')

try:
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
        print(f"Queued: {result}")
except urllib.error.URLError as e:
    print(f"Error: {e}")
    sys.exit(1)
