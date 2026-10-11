#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
batch_split_and_upscale.py
==========================
全自动多宫格图像智能切分、画幅自适应与 2K 扩散高清化批处理脚本。

功能特性：
1. OpenCV 智能投影与方差分析，自适应识别 4/6/8/9 等任意宫格并剔除白边/黑边间隙。
2. 画幅方向自适应：高>宽自动转 9:16，宽>高自动转 16:9；1:1 正方形默认判定为人像 9:16，采用镜像羽化延展补全画幅（不裁切人像）。
3. 2K 高清化支持双通道：
   - 通道 A (ComfyUI API 队列): SD1.5 + Tile ControlNet 微重绘发丝肤质 + RealESRGAN 放大至 2K (1440x2560 / 2560x1440)。
   - 通道 B (本地极速超分): 使用本地 RealESRGAN 神经网络模型直跑 2K (适合 ComfyUI 队列繁忙时秒级产出)。
4. 严格遵循项目归档规范，产物分类存放在 output/YYYY-MM-DD/cropped/ 与 output/YYYY-MM-DD/upscaled/。
"""

import os
import sys
import time
import json
import argparse
import datetime
import urllib.request
import urllib.error
import cv2
import numpy as np

# 强制终端输出 UTF-8
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass


def cv2_imread_utf8(path):
    """Windows UTF-8 兼容图像读取"""
    with open(path, 'rb') as f:
        bytes_data = bytearray(f.read())
    return cv2.imdecode(np.asarray(bytes_data, dtype=np.uint8), cv2.IMREAD_COLOR)


def cv2_imwrite_utf8(path, img):
    """Windows UTF-8 兼容图像保存"""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    ext = os.path.splitext(path)[1]
    if not ext:
        ext = '.png'
        path += ext
    ret, buf = cv2.imencode(ext, img)
    if ret:
        with open(path, 'wb') as f:
            f.write(buf)
        return True
    return False


def detect_and_split_grid(img, target_grid=None):
    """
    自适应检测多宫格并去除分割白边/黑边。
    返回切片列表：[{ 'image': np.ndarray, 'row': int, 'col': int }, ...]
    """
    h, w, _ = img.shape

    if target_grid and target_grid != 'auto':
        try:
            r_cnt, c_cnt = map(int, target_grid.lower().split('x'))
        except Exception:
            r_cnt, c_cnt = 3, 3
    else:
        r_cnt, c_cnt = None, None

    # 计算水平与垂直方向的色差方差
    row_stds = np.std(img, axis=1).mean(axis=1)
    col_stds = np.std(img, axis=0).mean(axis=1)

    # 缝隙判定：方差极小 (< 18.0)
    is_gutter_row = row_stds < 18.0
    is_gutter_col = col_stds < 18.0

    def find_intervals(mask):
        intervals = []
        in_interval = False
        start = 0
        for i, val in enumerate(mask):
            if val and not in_interval:
                in_interval = True
                start = i
            elif not val and in_interval:
                in_interval = False
                intervals.append((start, i))
        if in_interval:
            intervals.append((start, len(mask)))
        return intervals

    row_gutters = find_intervals(is_gutter_row)
    col_gutters = find_intervals(is_gutter_col)

    # 仅保留处于中间区域且具有合理宽度的缝隙 (2px ~ 60px)
    mid_row_gutters = [g for g in row_gutters if 20 < g[0] and g[1] < h - 20 and (g[1] - g[0]) >= 2]
    mid_col_gutters = [g for g in col_gutters if 20 < g[0] and g[1] < w - 20 and (g[1] - g[0]) >= 2]

    # 构建行切割区间
    if r_cnt is not None:
        r_step = h // r_cnt
        row_bounds = [(i * r_step, (i + 1) * r_step) for i in range(r_cnt)]
    else:
        if len(mid_row_gutters) == 2:
            row_bounds = [(0, mid_row_gutters[0][0]), (mid_row_gutters[0][1], mid_row_gutters[1][0]), (mid_row_gutters[1][1], h)]
        elif len(mid_row_gutters) == 1:
            row_bounds = [(0, mid_row_gutters[0][0]), (mid_row_gutters[0][1], h)]
        elif len(mid_row_gutters) == 3:
            row_bounds = [(0, mid_row_gutters[0][0]), (mid_row_gutters[0][1], mid_row_gutters[1][0]),
                          (mid_row_gutters[1][1], mid_row_gutters[2][0]), (mid_row_gutters[2][1], h)]
        else:
            # 默认保底 3 均分
            r_step = h // 3
            row_bounds = [(0, r_step), (r_step, 2 * r_step), (2 * r_step, h)]

    # 构建列切割区间
    if c_cnt is not None:
        c_step = w // c_cnt
        col_bounds = [(i * c_step, (i + 1) * c_step) for i in range(c_cnt)]
    else:
        if len(mid_col_gutters) == 2:
            col_bounds = [(0, mid_col_gutters[0][0]), (mid_col_gutters[0][1], mid_col_gutters[1][0]), (mid_col_gutters[1][1], w)]
        elif len(mid_col_gutters) == 1:
            col_bounds = [(0, mid_col_gutters[0][1]), (mid_col_gutters[0][1], w)]
        elif len(mid_col_gutters) == 3:
            col_bounds = [(0, mid_col_gutters[0][0]), (mid_col_gutters[0][1], mid_col_gutters[1][0]),
                          (mid_col_gutters[1][1], mid_col_gutters[2][0]), (mid_col_gutters[2][1], w)]
        else:
            # 默认保底 3 均分
            c_step = w // 3
            col_bounds = [(0, c_step), (c_step, 2 * c_step), (2 * c_step, w)]

    tiles = []
    margin = 2  # 关键去白边：向内收缩 2px，彻底切除任何中缝残留白边/黑边
    for r_idx, (r1, r2) in enumerate(row_bounds):
        for c_idx, (c1, c2) in enumerate(col_bounds):
            sub_r1 = min(r1 + margin, r2 - 1)
            sub_r2 = max(r2 - margin, sub_r1 + 1)
            sub_c1 = min(c1 + margin, c2 - 1)
            sub_c2 = max(c2 - margin, sub_c1 + 1)
            tile = img[sub_r1:sub_r2, sub_c1:sub_c2]
            tiles.append({
                'row': r_idx,
                'col': c_idx,
                'image': tile
            })

    return tiles, len(row_bounds), len(col_bounds)


def adapt_aspect_ratio(img, aspect_mode='1:1'):
    """
    画幅方向识别与扩展：
    - 1:1: 原生正方形 2K (2048x2048)，中心裁切保真，绝无镜像重影
    - 9:16: 竖屏 2K (1440x2560)
    - 16:9: 横屏 2K (2560x1440)
    - auto: 比例 > 1.15 转 16:9，< 0.85 转 9:16，其余保持 1:1 正片
    """
    h, w, _ = img.shape
    aspect = w / float(h)

    if aspect_mode == '1:1':
        target_name = '1:1'
        side = min(w, h)
        cx, cy = w // 2, h // 2
        square = img[cy - side // 2 : cy + side // 2, cx - side // 2 : cx + side // 2]
        base_w, base_h = 1024, 1024
        final_w, final_h = 2048, 2048
        base_img = cv2.resize(square, (base_w, base_h), interpolation=cv2.INTER_LANCZOS4)
        return base_img, target_name, base_w, base_h, final_w, final_h

    elif aspect_mode == 'auto':
        if aspect > 1.15:
            target_name = '16:9'
            target_ratio = 16.0 / 9.0
        elif aspect < 0.85:
            target_name = '9:16'
            target_ratio = 9.0 / 16.0
        else:
            # 接近正方形默认 1:1 正片
            return adapt_aspect_ratio(img, aspect_mode='1:1')
    elif aspect_mode == '16:9':
        target_name = '16:9'
        target_ratio = 16.0 / 9.0
    else:
        target_name = '9:16'
        target_ratio = 9.0 / 16.0

    current_ratio = w / float(h)

    if current_ratio < target_ratio:
        # 需水平扩充 (左右加边)
        target_w = int(round(h * target_ratio))
        pad_total = target_w - w
        pad_left = pad_total // 2
        pad_right = pad_total - pad_left
        pad_top = 0
        pad_bottom = 0
    else:
        # 需垂直扩充 (上下加边)
        target_h = int(round(w / target_ratio))
        pad_total = target_h - h
        pad_top = pad_total // 2
        pad_bottom = pad_total - pad_top
        pad_left = 0
        pad_right = 0

    padded = cv2.copyMakeBorder(
        img,
        top=pad_top,
        bottom=pad_bottom,
        left=pad_left,
        right=pad_right,
        borderType=cv2.BORDER_REFLECT_101
    )

    if pad_top > 0 or pad_bottom > 0 or pad_left > 0 or pad_right > 0:
        blur_padded = cv2.GaussianBlur(padded, (25, 25), 0)
        mask = np.zeros((padded.shape[0], padded.shape[1]), dtype=np.float32)
        mask[pad_top:pad_top + h, pad_left:pad_left + w] = 1.0
        mask = cv2.GaussianBlur(mask, (15, 15), 0)[:, :, np.newaxis]
        padded = (padded * mask + blur_padded * (1.0 - mask)).astype(np.uint8)

    if target_name == '9:16':
        base_w, base_h = 720, 1280
        final_w, final_h = 1440, 2560
    else:
        base_w, base_h = 1280, 720
        final_w, final_h = 2560, 1440

    base_img = cv2.resize(padded, (base_w, base_h), interpolation=cv2.INTER_LANCZOS4)
    return base_img, target_name, base_w, base_h, final_w, final_h


def apply_skin_realism_pipeline(img, mole='lip-bottom', grain_intensity=0.012, micro_texture=0.40, sss_strength=0.08):
    """
    工业级人像真实皮肤质感处理管线：
    1. 嘴角下方美人痣 (有机黑色素双层高斯羽化融合)
    2. 高低频分离微观毛孔与角质纹理重塑
    3. 次表面散射真皮层毛细血管微血色透光 (消除死灰蜡像感)
    4. 摄影传感器/胶片亮度自适应微颗粒 (打破塑料均匀平滑)
    """
    res = img.copy()

    # 1. 美人痣处理
    if mole == 'lip-bottom':
        h, w, _ = res.shape
        # 使用 OpenCV 级联检测器定位面部与嘴角
        face_cascade_path = os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
        cx, cy = int(w * 0.672), int(h * 0.421) # 默认回退坐标
        if os.path.exists(face_cascade_path):
            gray = cv2.cvtColor(res, cv2.COLOR_BGR2GRAY)
            face_cascade = cv2.CascadeClassifier(face_cascade_path)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(int(w*0.15), int(h*0.15)))
            if len(faces) > 0:
                fx, fy, fw, fh = faces[0]
                cx = fx + int(fw * 0.60)
                cy = fy + int(fh * 0.77)

        # 渲染有机美人痣
        radius = 4.2
        opacity = 0.82
        res_float = res.astype(np.float32)
        y, x = np.ogrid[:h, :w]
        dist_sq = (x - cx)**2 + (y - cy)**2
        sigma_core = radius / 1.8
        sigma_halo = radius * 1.3
        mask_core = np.exp(-dist_sq / (2 * (sigma_core**2)))
        mask_halo = np.exp(-dist_sq / (2 * (sigma_halo**2))) * 0.25
        mask = np.clip(mask_core * 0.85 + mask_halo, 0, 1) * opacity
        mask = mask[:, :, np.newaxis]

        y_min, y_max = max(0, int(cy - 15)), min(h, int(cy + 15))
        x_min, x_max = max(0, int(cx - 15)), min(w, int(cx + 15))
        local_skin = np.median(res_float[y_min:y_max, x_min:x_max], axis=(0, 1))
        melanin = np.array([float(local_skin[0]) * 0.22, float(local_skin[1]) * 0.20, float(local_skin[2]) * 0.28], dtype=np.float32)
        res = np.clip(res_float * (1.0 - mask) + melanin * mask, 0, 255).astype(np.uint8)

    # 2. 高低频分离微观毛孔
    if micro_texture > 0.01:
        f_img = res.astype(np.float32)
        low_freq = cv2.GaussianBlur(f_img, (0, 0), 1.2)
        high_freq = f_img - low_freq
        res = np.clip(f_img + high_freq * micro_texture, 0, 255).astype(np.uint8)

    # 3. 次表面散射微血色
    if sss_strength > 0.01:
        f_img = res.astype(np.float32)
        gray = cv2.cvtColor(res, cv2.COLOR_BGR2GRAY).astype(np.float32)
        penumbra = np.clip(1.0 - np.abs(gray - 145.0) / 75.0, 0, 1)[:, :, np.newaxis]
        b, g, r = cv2.split(f_img)
        r_warm = r + 16.0 * sss_strength * penumbra[:, :, 0]
        g_warm = g + 4.0 * sss_strength * penumbra[:, :, 0]
        b_cool = b - 4.0 * sss_strength * penumbra[:, :, 0]
        res = np.clip(cv2.merge([b_cool, g_warm, r_warm]), 0, 255).astype(np.uint8)

    # 4. 真实感光微颗粒 (Film Grain)
    if grain_intensity > 0.001:
        f_img = res.astype(np.float32) / 255.0
        gray = cv2.cvtColor(res, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        grain_weight = (1.0 - np.abs(gray - 0.45) * 1.2).clip(0.2, 1.0)[:, :, np.newaxis]
        np.random.seed(42)
        noise = np.random.normal(0, grain_intensity, f_img.shape).astype(np.float32)
        noise = cv2.GaussianBlur(noise, (3, 3), 0.5)
        out = f_img + noise * grain_weight
        res = np.clip(out * 255.0, 0, 255).astype(np.uint8)

    return res



def build_comfyui_prompt(image_subpath, final_w, final_h, save_prefix, denoise=0.32, steps=20, cfg=7.0):
    """构建 ComfyUI API 工作流执行图"""
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": "v1-5-pruned-emaonly.safetensors"
            }
        },
        "2": {
            "class_type": "ControlNetLoader",
            "inputs": {
                "control_net_name": "control_v11f1e_sd15_tile.pth"
            }
        },
        "3": {
            "class_type": "LoadImage",
            "inputs": {
                "image": image_subpath.replace('\\', '/')
            }
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "masterpiece, best quality, ultra highres, sharp focus, detailed skin texture, delicate eyes, natural lighting",
                "clip": ["1", 1]
            }
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "blurry, low quality, artifacts, watermark, distorted, ugly, bad anatomy, deformed eyes, extra limbs",
                "clip": ["1", 1]
            }
        },
        "6": {
            "class_type": "ControlNetApplyAdvanced",
            "inputs": {
                "strength": 0.85,
                "start_percent": 0.0,
                "end_percent": 1.0,
                "positive": ["4", 0],
                "negative": ["5", 0],
                "control_net": ["2", 0],
                "image": ["3", 0]
            }
        },
        "7": {
            "class_type": "VAEEncode",
            "inputs": {
                "pixels": ["3", 0],
                "vae": ["1", 2]
            }
        },
        "8": {
            "class_type": "KSampler",
            "inputs": {
                "seed": int(time.time() * 1000) % 100000000,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler_ancestral",
                "scheduler": "karras",
                "denoise": denoise,
                "model": ["1", 0],
                "positive": ["6", 0],
                "negative": ["6", 1],
                "latent_image": ["7", 0]
            }
        },
        "9": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["8", 0],
                "vae": ["1", 2]
            }
        },
        "10": {
            "class_type": "UpscaleModelLoader",
            "inputs": {
                "model_name": "RealESRGAN_x4plus.pth"
            }
        },
        "11": {
            "class_type": "ImageUpscaleWithModel",
            "inputs": {
                "upscale_model": ["10", 0],
                "image": ["9", 0]
            }
        },
        "12": {
            "class_type": "ImageScale",
            "inputs": {
                "upscale_method": "lanczos",
                "width": final_w,
                "height": final_h,
                "crop": "disabled",
                "image": ["11", 0]
            }
        },
        "13": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": save_prefix.replace('\\', '/'),
                "images": ["12", 0]
            }
        }
    }


def build_flux_prompt(image_subpath, final_w, final_h, save_prefix, denoise=0.22, steps=20):
    """构建 Flux.1-dev Abliterated GGUF-Q8 深度写实重绘执行图"""
    return {
        "1": {
            "class_type": "UnetLoaderGGUF",
            "inputs": {
                "unet_name": "T8-flux.1-dev-abliterated-V2-GGUF-Q8_0.gguf"
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
        "4": {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": "hinaFluxDevAsianMix_v12.safetensors",
                "strength_model": 0.70,
                "strength_clip": 0.70,
                "model": ["1", 0],
                "clip": ["2", 0]
            }
        },
        "5": {
            "class_type": "LoadImage",
            "inputs": {
                "image": image_subpath.replace('\\', '/')
            }
        },
        "6": {
            "class_type": "VAEEncode",
            "inputs": {
                "pixels": ["5", 0],
                "vae": ["3", 0]
            }
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "masterpiece, raw candid photo of a beautiful young asian woman, delicate smile, realistic natural skin texture, visible microscopic pores, soft lighting, natural eyes, 8k uhd, highly detailed, photorealistic",
                "clip": ["4", 1]
            }
        },
        "8": {
            "class_type": "FluxGuidance",
            "inputs": {
                "guidance": 3.5,
                "conditioning": ["7", 0]
            }
        },
        "9": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "bad anatomy, blurry, plastic doll, airbrushed, cartoon, anime, low quality, artifacts",
                "clip": ["4", 1]
            }
        },
        "10": {
            "class_type": "KSampler",
            "inputs": {
                "seed": int(time.time() * 1000) % 100000000,
                "steps": steps,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": denoise,
                "model": ["4", 0],
                "positive": ["8", 0],
                "negative": ["9", 0],
                "latent_image": ["6", 0]
            }
        },
        "11": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["10", 0],
                "vae": ["3", 0]
            }
        },
        "12": {
            "class_type": "ImageScale",
            "inputs": {
                "upscale_method": "lanczos",
                "width": final_w,
                "height": final_h,
                "crop": "disabled",
                "image": ["11", 0]
            }
        },
        "13": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": save_prefix.replace('\\', '/'),
                "images": ["12", 0]
            }
        }
    }


def build_qwen_prompt(image_subpath, final_w, final_h, save_prefix, denoise=0.22, steps=8):
    """构建 Qwen-Image 2.1 UC 深度东方写实重绘执行图"""
    return {
        "1": {
            "class_type": "UnetLoaderGGUF",
            "inputs": {
                "unet_name": "qwen-image-2.1-UC-Q4_K_M.gguf"
            }
        },
        "2": {
            "class_type": "CLIPLoaderGGUF",
            "inputs": {
                "clip_name": "qwen3vl_8b_heretic-Q4_K_M.gguf",
                "type": "qwen_image"
            }
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "qwen_image_2.1_vae_bf16.safetensors"
            }
        },
        "4": {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": "Qwen-Image-Lightning-4steps-V2.0.safetensors",
                "strength_model": 1.0,
                "strength_clip": 1.0,
                "model": ["1", 0],
                "clip": ["2", 0]
            }
        },
        "5": {
            "class_type": "LoadImage",
            "inputs": {
                "image": image_subpath.replace('\\', '/')
            }
        },
        "6": {
            "class_type": "VAEEncode",
            "inputs": {
                "pixels": ["5", 0],
                "vae": ["3", 0]
            }
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "一个年轻漂亮的亚洲女性，室内温馨自拍，精致五官，生动眼神，微距真实自然皮肤，毛孔细节，水润通透，8K超清真实摄影",
                "clip": ["4", 1]
            }
        },
        "8": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "畸形，塑料娃娃假面，模糊，低质量，过度磨皮，动漫",
                "clip": ["4", 1]
            }
        },
        "9": {
            "class_type": "KSampler",
            "inputs": {
                "seed": int(time.time() * 1000) % 100000000,
                "steps": steps,
                "cfg": 1.5,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": denoise,
                "model": ["4", 0],
                "positive": ["7", 0],
                "negative": ["8", 0],
                "latent_image": ["6", 0]
            }
        },
        "10": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["9", 0],
                "vae": ["3", 0]
            }
        },
        "11": {
            "class_type": "ImageScale",
            "inputs": {
                "upscale_method": "lanczos",
                "width": final_w,
                "height": final_h,
                "crop": "disabled",
                "image": ["10", 0]
            }
        },
        "12": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": save_prefix.replace('\\', '/'),
                "images": ["11", 0]
            }
        }
    }


def build_sdxl_prompt(image_subpath, final_w, final_h, save_prefix, denoise=0.28, steps=25, cfg=5.0):
    """构建 SDXL 真实摄影路线 (RealVisXL V4.0 + TTPlanet Tile ControlNet + sdxl_vae)"""
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": "RealVisXL_V4.0.safetensors"
            }
        },
        "2": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "sdxl_vae.safetensors"
            }
        },
        "3": {
            "class_type": "ControlNetLoader",
            "inputs": {
                "control_net_name": "TTPLANET_Controlnet_Tile_realistic_v2_fp16.safetensors"
            }
        },
        "4": {
            "class_type": "LoadImage",
            "inputs": {
                "image": image_subpath.replace('\\', '/')
            }
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "masterpiece, raw candid photo of a beautiful young asian woman, delicate smile, realistic natural skin texture, visible microscopic pores, soft natural lighting, natural eyes, 8k uhd, highly detailed, photorealistic, shot on 85mm f1.4",
                "clip": ["1", 1]
            }
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "blurry, low quality, plastic doll, airbrushed, cartoon, anime, smooth skin, bad anatomy, deformed eyes, 3d render",
                "clip": ["1", 1]
            }
        },
        "7": {
            "class_type": "ControlNetApplyAdvanced",
            "inputs": {
                "strength": 0.75,
                "start_percent": 0.0,
                "end_percent": 0.90,
                "positive": ["5", 0],
                "negative": ["6", 0],
                "control_net": ["3", 0],
                "image": ["4", 0]
            }
        },
        "8": {
            "class_type": "VAEEncode",
            "inputs": {
                "pixels": ["4", 0],
                "vae": ["2", 0]
            }
        },
        "9": {
            "class_type": "KSampler",
            "inputs": {
                "seed": int(time.time() * 1000) % 100000000,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "dpmpp_2m_sde",
                "scheduler": "karras",
                "denoise": denoise,
                "model": ["1", 0],
                "positive": ["7", 0],
                "negative": ["7", 1],
                "latent_image": ["8", 0]
            }
        },
        "10": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["9", 0],
                "vae": ["2", 0]
            }
        },
        "11": {
            "class_type": "ImageScale",
            "inputs": {
                "upscale_method": "lanczos",
                "width": final_w,
                "height": final_h,
                "crop": "disabled",
                "image": ["10", 0]
            }
        },
        "12": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": save_prefix.replace('\\', '/'),
                "images": ["11", 0]
            }
        }
    }


_LOADED_UPSCALE_MODEL = None

def get_upscale_model(model_path):
    global _LOADED_UPSCALE_MODEL
    if _LOADED_UPSCALE_MODEL is None:
        import torch
        import spandrel
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model_desc = spandrel.ModelLoader().load_from_file(model_path)
        _LOADED_UPSCALE_MODEL = (model_desc.model.to(device).eval(), device)
    return _LOADED_UPSCALE_MODEL


def run_local_realesrgan(input_img, target_w, target_h, model_path):
    """使用本地 RealESRGAN 模型直接超分 (高效缓存单例)"""
    import torch
    model, device = get_upscale_model(model_path)
    
    # 格式转换
    img_rgb = cv2.cvtColor(input_img, cv2.COLOR_BGR2RGB)
    img_tensor = torch.from_numpy(img_rgb).permute(2, 0, 1).float().unsqueeze(0) / 255.0
    img_tensor = img_tensor.to(device)
    
    with torch.no_grad():
        out_tensor = model(img_tensor)
        
    out_img = out_tensor.squeeze(0).permute(1, 2, 0).clamp(0, 1).cpu().numpy()
    out_bgr = cv2.cvtColor((out_img * 255.0).astype(np.uint8), cv2.COLOR_RGB2BGR)
    
    # 精确调整至 2K
    final_img = cv2.resize(out_bgr, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)
    return final_img


def main():
    parser = argparse.ArgumentParser(description="多宫格智能切分与自适应 1:1/9:16/16:9 2K 扩散高清化批处理脚本")
    parser.add_argument("--input", default=r"D:\ai_projects\ComfyUI\input\gpt_202610", help="输入目录或单张图像路径")
    parser.add_argument("--output-base", default=r"D:\ai_projects\ComfyUI\output", help="输出根目录")
    parser.add_argument("--date", default=datetime.datetime.now().strftime("%Y-%m-%d"), help="归档日期 (YYYY-MM-DD)")
    parser.add_argument("--grid", default="auto", help="强制宫格规格 (例如 3x3, 2x3, auto)")
    parser.add_argument("--aspect", default="1:1", choices=["1:1", "auto", "9:16", "16:9"], help="画幅适配模式 (默认 1:1 原生 2K 正片)")
    parser.add_argument("--mode", default="local-2k", choices=["local-2k", "qwen2.1", "flux", "sdxl", "enqueue", "wait", "crop-only"],
                        help="运行模式: local-2k(路线A本地超分+真实感), qwen2.1(路线B阿里千问深度重绘), flux(路线B Flux消融版重绘), sdxl(路线B SDXL RealVis摄影重绘), enqueue(SD1.5队列), crop-only(仅切图)")
    parser.add_argument("--mole", default="lip-bottom", choices=["lip-bottom", "none"], help="个性化美人痣选项 (默认嘴角下方)")
    parser.add_argument("--grain", type=float, default=0.012, help="真实胶片/传感器微质感强度 (0.0 为关闭)")
    parser.add_argument("--micro-texture", type=float, default=0.40, help="高低频微观毛孔与皮肤纹理强化系数 (0.0 为关闭)")
    parser.add_argument("--sss", type=float, default=0.08, help="次表面散射真皮层毛细血管微血色透光强度 (0.0 为关闭)")
    parser.add_argument("--server", default="127.0.0.1:8188", help="ComfyUI 服务地址")
    parser.add_argument("--denoise", type=float, default=0.22, help="扩散重绘微降噪度 (Flux/Qwen建议 0.20~0.25, SDXL建议 0.25~0.28)")
    parser.add_argument("--steps", type=int, default=25, help="KSampler 步数 (Qwen固定8步, SDXL建议25步)")
    parser.add_argument("--force", action="store_true", help="强制重新生成所有切片成片 (默认开启增量断点续跑，跳过已存在成片)")
    parser.add_argument("--max-images", type=int, default=None, help="最大处理图像张数 (用于测试)")
    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    date_str = args.date

    # 动态区分输出目录：qwen2.1 ➔ qwen21_2k/，flux ➔ flux_2k/，sdxl ➔ sdxl_2k/，local-2k ➔ local_2k/
    if args.mode == "qwen2.1":
        mode_dir_name = "qwen21_2k"
    elif args.mode == "flux":
        mode_dir_name = "flux_2k"
    elif args.mode == "sdxl":
        mode_dir_name = "sdxl_2k"
    elif args.mode == "local-2k":
        mode_dir_name = "local_2k"
    else:
        mode_dir_name = "upscaled"

    cropped_out_dir = os.path.join(args.output_base, date_str, "cropped")
    upscaled_out_dir = os.path.join(args.output_base, date_str, mode_dir_name)
    os.makedirs(cropped_out_dir, exist_ok=True)
    os.makedirs(upscaled_out_dir, exist_ok=True)

    # 收集待处理文件
    if os.path.isdir(input_path):
        valid_exts = ('.png', '.jpg', '.jpeg', '.webp')
        files = [os.path.join(input_path, f) for f in os.listdir(input_path) if f.lower().endswith(valid_exts)]
    elif os.path.isfile(input_path):
        files = [input_path]
    else:
        print(f"❌ 找不到输入路径: {input_path}")
        sys.exit(1)

    if args.max_images:
        files = files[:args.max_images]

    print(f"============================================================")
    print(f"🚀 开始执行多宫格智能切分与高清化管线")
    print(f"📁 输入路径: {input_path} (共 {len(files)} 张图像)")
    print(f"📅 归档日期: {date_str}")
    print(f"⚙️ 执行模式: {args.mode}")
    print(f"📐 目标画幅: {args.aspect} | 宫格识别: {args.grid}")
    print(f"✨ 皮肤写实配置: 美人痣={args.mole} | 胶片微质感={args.grain} | 毛孔高频={args.micro_texture} | SSS微血色={args.sss}")
    print(f"🛠️ 切分保存目录: {cropped_out_dir}")
    print(f"🎨 高清成片目录: {upscaled_out_dir}")
    print(f"============================================================")

    total_tiles_count = 0
    success_tiles_count = 0
    t0_all = time.time()
    queue_manifest = []

    # 准备 ComfyUI 内部加载临时目录
    comfy_input_root = r"D:\ai_projects\ComfyUI\input"
    temp_grid_dir = os.path.join(comfy_input_root, "temp_grid_crops")
    os.makedirs(temp_grid_dir, exist_ok=True)

    local_model_path = r"D:\ai_projects\ComfyUI\models\upscale_models\RealESRGAN_x4plus.pth"

    for f_idx, f_path in enumerate(files, 1):
        base_name = os.path.splitext(os.path.basename(f_path))[0]
        print(f"\n[{f_idx}/{len(files)}] 正在处理: {base_name} ...")

        img = cv2_imread_utf8(f_path)
        if img is None:
            print(f"  ⚠️ 无法读取图像: {f_path}，跳过。")
            continue

        # 1. 智能切分与去边框
        tiles, rows, cols = detect_and_split_grid(img, target_grid=args.grid)
        print(f"  🔍 成功识别并切分: {rows}行 x {cols}列 (共 {len(tiles)} 个单图切片)")

        for t_idx, tile_info in enumerate(tiles, 1):
            total_tiles_count += 1
            r, c = tile_info['row'], tile_info['col']
            tile_raw = tile_info['image']

            # 2. 画幅自适应扩展
            base_img, aspect_name, base_w, base_h, final_w, final_h = adapt_aspect_ratio(tile_raw, aspect_mode=args.aspect)

            tile_file_base = f"{base_name}_R{r+1}C{c+1}_{t_idx:02d}"
            crop_filename = f"{tile_file_base}_{aspect_name.replace(':', 'x')}.png"

            # 保存归档切片至 output/YYYY-MM-DD/cropped/
            crop_archived_path = os.path.join(cropped_out_dir, crop_filename)
            cv2_imwrite_utf8(crop_archived_path, base_img)

            # 保存至 ComfyUI input 临时加载目录
            comfy_temp_file = os.path.join(temp_grid_dir, crop_filename)
            cv2_imwrite_utf8(comfy_temp_file, base_img)

            print(f"    ➡️ 切片 #{t_idx:02d} (R{r+1}C{c+1}): 适配为 {aspect_name} (基础尺寸: {base_w}x{base_h})")

            # 智能断点续跑检测：若成片目录中已存在该切片的产物，则直接跳过避免重复计算
            existing_outputs = [
                f for f in os.listdir(upscaled_out_dir)
                if f.startswith(tile_file_base) and f.endswith(('.png', '.jpg', '.webp'))
            ] if os.path.exists(upscaled_out_dir) else []

            if existing_outputs and not args.force:
                print(f"      ⏭️ [断点续跑] 检测到已存在成片: {existing_outputs[0]}，跳过")
                success_tiles_count += 1
                continue

            if args.mode == "crop-only":
                success_tiles_count += 1
                continue

            elif args.mode == "local-2k":
                # 本地直接使用 RealESRGAN 生成 2K 成片
                final_2k_img = run_local_realesrgan(base_img, final_w, final_h, local_model_path)
                
                # 应用真实皮肤质感增强管线 (美人痣 + 高低频毛孔 + SSS微血色 + 胶片微质感)
                final_2k_img = apply_skin_realism_pipeline(
                    final_2k_img,
                    mole=args.mole,
                    grain_intensity=args.grain,
                    micro_texture=args.micro_texture,
                    sss_strength=args.sss
                )
                
                out_2k_name = f"{tile_file_base}_2k.png"
                out_2k_path = os.path.join(upscaled_out_dir, out_2k_name)
                cv2_imwrite_utf8(out_2k_path, final_2k_img)
                success_tiles_count += 1
                print(f"      ✅ [真实感2K成片] 已保存: {out_2k_name} ({final_w}x{final_h})")

            elif args.mode in ("qwen2.1", "flux", "sdxl", "enqueue", "wait"):
                # 提交 ComfyUI 队列任务
                rel_image_path = os.path.relpath(comfy_temp_file, comfy_input_root)
                save_prefix = f"{date_str}/{mode_dir_name}/{tile_file_base}_2k"

                if args.mode == "qwen2.1":
                    wf_prompt = build_qwen_prompt(rel_image_path, final_w, final_h, save_prefix, denoise=args.denoise, steps=8)
                elif args.mode == "flux":
                    wf_prompt = build_flux_prompt(rel_image_path, final_w, final_h, save_prefix, denoise=args.denoise, steps=args.steps)
                elif args.mode == "sdxl":
                    wf_prompt = build_sdxl_prompt(rel_image_path, final_w, final_h, save_prefix, denoise=args.denoise, steps=args.steps, cfg=5.0)
                else:
                    wf_prompt = build_comfyui_prompt(rel_image_path, final_w, final_h, save_prefix, denoise=args.denoise, steps=args.steps)

                prompt_payload = json.dumps({"prompt": wf_prompt}).encode('utf-8')
                req = urllib.request.Request(
                    f"http://{args.server}/prompt",
                    data=prompt_payload,
                    headers={'Content-Type': 'application/json'}
                )

                try:
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        resp_data = json.loads(resp.read().decode('utf-8'))
                        prompt_id = resp_data.get("prompt_id")
                        queue_manifest.append({
                            "prompt_id": prompt_id,
                            "source_image": base_name,
                            "tile_index": t_idx,
                            "grid": f"R{r+1}C{c+1}",
                            "aspect": aspect_name,
                            "target_res": f"{final_w}x{final_h}",
                            "output_prefix": save_prefix
                        })
                        print(f"      📡 已提交 ComfyUI 队列 [{args.mode}] (Prompt ID: {prompt_id})")
                        success_tiles_count += 1
                except Exception as e:
                    print(f"      ❌ 提交 ComfyUI 失败: {e}")
                    continue

                if args.mode == "wait":
                    from scratch.wait_for_prompt import wait_for_prompt
                    print(f"      ⏳ 等待任务完成...")

    # 保存队列清单
    if queue_manifest:
        manifest_path = os.path.join(args.output_base, date_str, f"queue_manifest_{args.mode}.json")
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(queue_manifest, f, ensure_ascii=False, indent=2)
        print(f"\n📋 已将所有已提交任务清单保存至: {manifest_path}")

    total_cost = time.time() - t0_all
    print(f"\n============================================================")
    print(f"🎉 全部任务执行完毕！")
    print(f"📊 总计切片数: {total_tiles_count} | 成功处理/排队: {success_tiles_count}")
    print(f"⏱️ 总耗时: {total_cost:.1f} 秒")
    print(f"📂 规整切片归档: {cropped_out_dir}")
    if args.mode == "local-2k":
        print(f"🖼️ 2K 高清成片归档: {upscaled_out_dir}")
    elif args.mode in ("qwen2.1", "flux", "sdxl", "enqueue"):
        print(f"🔄 2K 高清任务已全部进入 ComfyUI 渲染队列，将在后台逐个执行输出至: {upscaled_out_dir}")
    print(f"============================================================")


if __name__ == "__main__":
    main()
