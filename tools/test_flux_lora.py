# -*- coding: utf-8 -*-
"""FLUX LoRA 效果测试脚本
测试 D:\OLLAMA_MODELS\models\loras 中新加入的 LoRA 在 FLUX 上的生成表现
"""
import os
import json
import time
import urllib.request
import uuid

HOST = "http://127.0.0.1:8188"
OUT_PREFIX = "2026-09-08/flux_lora_test"

PROMPT_ZH = (
    "电影极简主义肖像画中，一位美丽的年轻东亚女子独自站在一望无际的蓝天下开放的野花草地上，"
    "闭着或半睁着眼睛向上凝视，仿佛拥抱着风。长长的、自然凌乱的黑色在脸上自由地流淌，"
    "柔软的瓷肌，精致的五官，微妙自然的妆容，平静内省的表情。秋季多层次穿搭——深色大廓形羊毛外套"
    "搭配针织毛衣、复古衬衫，或柔和大地色调的柔软碎花连衣裙。金色的干草和野花环绕着她，"
    "营造出宁静的乡村氛围。从低角度视角拍摄，具有丰富的负空间和广阔的天空填充了大部分画面。"
    "柔和的电影日光，微风自然地移动 hair 和服装，梦幻般的色彩分级，温暖的泥土色调与凉爽的蓝天混合，"
    "微妙的胶片 grain，浅景深，奶油色背景散景，柯达 Portra 400 美学，情感编辑时尚摄影，"
    "斯堪的纳维亚极简主义，日本电影情绪，自然采光， 85mm镜头，f/1.8，超真实皮肤纹理，"
    "精细hair details，高动态范围，杂志品质的构图，安静忧郁的氛围，获奖摄影，8K，超detailed，没有文字，没有水印。"
)

PROMPT_EN = (
    "cinematic minimalist portrait, a beautiful young East Asian woman standing alone in an open meadow of "
    "wildflowers under an endless blue sky, eyes closed or half-open gazing upwards, embracing the wind. "
    "Long naturally messy black hair flowing freely across face, soft porcelain skin, delicate facial features, "
    "subtle natural makeup, calm introspective expression. Autumn layered outfit: dark oversized wool coat paired "
    "with knit sweater and vintage shirt, or soft floral dress in muted earth tones. Golden dry grass and wildflowers "
    "surround her, serene rural countryside mood. Low angle perspective, abundant negative space with vast sky "
    "filling most of frame. Soft cinematic daylight, gentle breeze naturally moving hair and clothes, dreamy color grading, "
    "warm earthy tones blended with cool blue sky, subtle film grain, shallow depth of field, creamy background bokeh, "
    "Kodak Portra 400 aesthetic, emotional editorial fashion photography, Scandinavian minimalism, Japanese cinematic mood, "
    "natural lighting, 85mm lens, f/1.8, ultra-realistic skin texture, fine hair details, high dynamic range, "
    "magazine quality composition, quiet melancholic atmosphere, award-winning photography, 8k, ultra-detailed, no text, no watermark"
)

def build_workflow(lora_name=None, lora_strength=0.9, prompt_text=PROMPT_ZH, prefix="test", seed=42, steps=25):
    """构建用于测试的 FLUX + LoRA 工作流"""
    wf = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "flux1-dev-fp8.safetensors",
                "weight_dtype": "default"
            }
        },
        "2": {
            "class_type": "DualCLIPLoader",
            "inputs": {
                "clip_name1": "t5xxl_fp8_e4m3fn.safetensors",
                "clip_name2": "clip_l.safetensors",
                "type": "flux"
            }
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "flux-vae-bf16.safetensors"
            }
        },
        "8": {
            "class_type": "BasicScheduler",
            "inputs": {
                "scheduler": "simple",
                "steps": steps,
                "denoise": 1.0,
                "model": ["1", 0]
            }
        },
        "9": {
            "class_type": "KSamplerSelect",
            "inputs": {
                "sampler_name": "euler"
            }
        },
        "10": {
            "class_type": "RandomNoise",
            "inputs": {
                "noise_seed": seed
            }
        },
        "11": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {
                "width": 768,
                "height": 1152,
                "batch_size": 1
            }
        },
        "12": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["10", 0],
                "guider": ["7", 0],
                "sampler": ["9", 0],
                "sigmas": ["8", 0],
                "latent_image": ["11", 0]
            }
        },
        "13": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["12", 0],
                "vae": ["3", 0]
            }
        },
        "14": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": prefix,
                "images": ["13", 0]
            }
        }
    }

    if lora_name:
        wf["4"] = {
            "class_type": "LoraLoader",
            "inputs": {
                "model": ["1", 0],
                "clip": ["2", 0],
                "lora_name": lora_name,
                "strength_model": lora_strength,
                "strength_clip": lora_strength
            }
        }
        wf["5"] = {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": prompt_text,
                "clip": ["4", 1]
            }
        }
        wf["6"] = {
            "class_type": "FluxGuidance",
            "inputs": {
                "guidance": 3.5,
                "conditioning": ["5", 0]
            }
        }
        wf["7"] = {
            "class_type": "BasicGuider",
            "inputs": {
                "model": ["4", 0],
                "conditioning": ["6", 0]
            }
        }
        wf["8"]["inputs"]["model"] = ["4", 0]
    else:
        wf["5"] = {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": prompt_text,
                "clip": ["2", 0]
            }
        }
        wf["6"] = {
            "class_type": "FluxGuidance",
            "inputs": {
                "guidance": 3.5,
                "conditioning": ["5", 0]
            }
        }
        wf["7"] = {
            "class_type": "BasicGuider",
            "inputs": {
                "model": ["1", 0],
                "conditioning": ["6", 0]
            }
        }
        wf["8"]["inputs"]["model"] = ["1", 0]

    return wf

if __name__ == "__main__":
    wf = build_workflow("hinaFluxDevAsianMix_v12.safetensors", 0.9, PROMPT_ZH, "test_prefix")
    print(f"Workflow nodes count: {len(wf)}")
    print("Workflow constructed successfully.")
