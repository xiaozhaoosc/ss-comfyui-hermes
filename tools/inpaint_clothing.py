#!/usr/bin/env python3
"""
使用 SDXL Inpaint 去除原服装
在 IDM-VTON 换装前，先用 inpaint 把服装区域涂成皮肤色
"""
import os
import sys
import json
import time
import requests
from pathlib import Path

COMFY_ROOT = r'D:\ai_projects\ComfyUI'
sys.path.insert(0, COMFY_ROOT)

class ComfyAPI:
    def __init__(self, host='127.0.0.1', port=8188):
        self.base = f'http://{host}:{port}'
    
    def queue_prompt(self, prompt, client_id='inpaint'):
        """提交 prompt 到 ComfyUI"""
        resp = requests.post(f'{self.base}/prompt', json={
            'prompt': prompt,
            'client_id': client_id
        })
        return resp.json()['prompt_id']
    
    def wait_result(self, prompt_id, timeout=300):
        """等待结果"""
        start = time.time()
        while time.time() - start < timeout:
            resp = requests.get(f'{self.base}/history/{prompt_id}')
            data = resp.json()
            if prompt_id in data:
                return data[prompt_id]
            time.sleep(0.5)
        raise TimeoutError('ComfyUI timeout')

def inpaint_clothing(image_path, mask_path, output_path, 
                     prompt="bare skin, naked torso, smooth skin texture, natural body color",
                     negative_prompt="clothing, fabric, wrinkles, seams, pattern, texture",
                     steps=30, cfg=7.5, seed=42,
                     comfy_host='127.0.0.1', comfy_port=8188):
    """
    使用 SDXL Inpaint 去除服装区域
    
    Args:
        image_path: 输入图片路径
        mask_path: 遮罩路径（白色区域为需要去除的服装）
        output_path: 输出路径
        prompt: 正面提示词
        negative_prompt: 负面提示词
        steps: 采样步数
        cfg: CFG scale
        seed: 随机种子
        comfy_host: ComfyUI 主机
        comfy_port: ComfyUI 端口
    """
    client = ComfyAPI(comfy_host, comfy_port)
    
    # 构建 prompt
    prompt_data = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}
        },
        "2": {
            "class_type": "LoadImage",
            "inputs": {"image": os.path.basename(image_path)}
        },
        "3": {
            "class_type": "LoadImage", 
            "inputs": {"image": os.path.basename(mask_path)}
        },
        "4": {
            "class_type": "ImageToMask",
            "inputs": {"image": ["3", 0], "channel": "red"}
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["1", 1]}
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative_prompt, "clip": ["1", 1]}
        },
        "7": {
            "class_type": "VAEEncode",
            "inputs": {"pixels": ["2", 0], "vae": ["1", 2]}
        },
        "8": {
            "class_type": "SetLatentNoiseMask",
            "inputs": {"samples": ["7", 0], "mask": ["4", 0]}
        },
        "9": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["5", 0],
                "negative": ["6", 0],
                "latent_image": ["8", 0],
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0
            }
        },
        "10": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["9", 0], "vae": ["1", 2]}
        },
        "11": {
            "class_type": "SaveImage",
            "inputs": {"images": ["10", 0], "filename_prefix": "inpaint"}
        }
    }
    
    # 提交 prompt
    prompt_id = client.queue_prompt(prompt_data)
    print(f'  [API] Inpaint prompt {prompt_id} queued')
    
    # 等待结果
    result = client.wait_result(prompt_id)
    
    # 获取输出图片
    outputs = result.get('outputs', {})
    for node_id, node_output in outputs.items():
        if 'images' in node_output:
            for img_info in node_output['images']:
                img_path = os.path.join(COMFY_ROOT, 'output', img_info['subfolder'], img_info['filename'])
                if os.path.exists(img_path):
                    import shutil
                    shutil.copy2(img_path, output_path)
                    return output_path
    
    raise RuntimeError('No inpaint output found')

def inpaint_keyframes(frames_dir, masks_dir, output_dir, kf_indices,
                      prompt="bare skin, naked torso, smooth skin texture",
                      steps=30, cfg=7.5, seed=42,
                      comfy_host='127.0.0.1', comfy_port=8188):
    """
    批量处理关键帧的 inpaint
    """
    os.makedirs(output_dir, exist_ok=True)
    
    for i, kf_idx in enumerate(kf_indices):
        output_path = os.path.join(output_dir, f'inpaint_{i:04d}.png')
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            print(f'  [{i+1}/{len(kf_indices)}] Frame {kf_idx} → 已存在，跳过')
            continue
        
        # 找原始帧
        all_f = sorted(Path(frames_dir).glob('frame_*.png'))
        frame_path = str(all_f[kf_idx]) if kf_idx < len(all_f) else str(all_f[-1])
        mask_path = os.path.join(masks_dir, f'mask_{i:04d}.png')
        
        if not os.path.exists(mask_path):
            print(f'  [{i+1}/{len(kf_indices)}] Frame {kf_idx} → 无遮罩，跳过')
            continue
        
        print(f'  [{i+1}/{len(kf_indices)}] Frame {kf_idx}...')
        try:
            result = inpaint_clothing(
                frame_path, mask_path, output_path,
                prompt=prompt, steps=steps, cfg=cfg, seed=seed,
                comfy_host=comfy_host, comfy_port=comfy_port
            )
            print(f'    ✓')
        except Exception as e:
            print(f'    ❌ {e}，用原帧')
            import shutil
            shutil.copy2(frame_path, output_path)
    
    return output_dir

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--frames-dir', required=True)
    parser.add_argument('--masks-dir', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--prompt', default='bare skin, naked torso, smooth skin texture')
    parser.add_argument('--steps', type=int, default=30)
    parser.add_argument('--cfg', type=float, default=7.5)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--comfy-host', default='127.0.0.1')
    parser.add_argument('--comfy-port', type=int, default=8188)
    args = parser.parse_args()
    
    # 获取关键帧索引
    state_file = os.path.join(os.path.dirname(args.output_dir), '.pipeline_state.json')
    if os.path.exists(state_file):
        with open(state_file) as f:
            state = json.load(f)
        kf_indices = state['stages']['2_extract']['outputs']['kf_indices']
    else:
        # 默认每秒一个关键帧
        frames = sorted(Path(args.frames_dir).glob('frame_*.png'))
        kf_indices = list(range(0, len(frames), 25))  # 25fps
    
    inpaint_keyframes(
        args.frames_dir, args.masks_dir, args.output_dir, kf_indices,
        prompt=args.prompt, steps=args.steps, cfg=args.cfg, seed=args.seed,
        comfy_host=args.comfy_host, comfy_port=args.comfy_port
    )
