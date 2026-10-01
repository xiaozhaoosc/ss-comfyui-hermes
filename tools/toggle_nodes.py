"""批量禁用/启用 ComfyUI 自定义节点。"""
import os
import sys
from pathlib import Path

BASE = Path(r"D:\ai_projects\ComfyUI\custom_nodes")

DISABLE = [
    "ComfyUI-Portrait-Maker",
    "ComfyUI-WanVideoWrapper",
    "ComfyUI-SeedVR2_VideoUpscaler",
    "WAS-Node-Suite-ComfyUI",
    "ComfyUI_LayerStyle",
    "ComfyUI-KJNodes",
    "ComfyUI-QwenVL",
    "ComfyUI-PuLID-Flux",
    "ComfyUI-OOTDiffusion",
    "ComfyUI-MagicAnimate",
    "ComfyUI-IDM-VTON",
    "ComfyUI-CatVTON",
    "CharacterFaceSwap",
    "ComfyUI-AnimateDiff-Evolved",
    "ComfyUI_IPAdapter_plus",
    "efficiency-nodes-comfyui",
    "ComfyUI-MimicMotionWrapper.backup",
    "ComfyUI-GGUF.backup",
]

for name in DISABLE:
    p = BASE / name
    if p.exists():
        dest = BASE / (name + ".disabled")
        if dest.exists():
            dest.rmdir()
        p.rename(dest)
        print(f"disabled: {name}")
    else:
        print(f"not found: {name}")
