#!/usr/bin/env python3
"""
LTX 生成 + 换脸管道
流程: LTX-2.3 生成视频 → insightface 换脸 → 输出最终视频
"""
import os
import sys
import json
import time
import subprocess
import argparse
import requests
from pathlib import Path

# 配置
COMFYUI_URL = "http://127.0.0.1:8188"
OUTPUT_DIR = "output"
TEMP_DIR = "temp_pipeline"

# LTX 生成参数
LTX_CONFIG = {
    "prompt": "A person talking to the camera, close-up shot, natural lighting, studio background",
    "negative_prompt": "blurry, low quality, distorted face, ugly",
    "width": 512,
    "height": 320,
    "num_frames": 33,  # ~1.3s at 25fps
    "fps": 25,
    "steps": 16,
    "cfg": 3.0,
    "seed": -1  # 随机
}

def ensure_dirs():
    """确保目录存在"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)

def start_comfyui():
    """启动 ComfyUI 服务器"""
    print("检查 ComfyUI 状态...")
    try:
        resp = requests.get(f"{COMFYUI_URL}/system_stats", timeout=2)
        if resp.status_code == 200:
            print("ComfyUI 已运行")
            return True
    except:
        pass
    
    print("启动 ComfyUI...")
    # 这里假设 ComfyUI 已经在后台运行
    # 如果需要启动，可以取消注释以下代码
    # subprocess.Popen([...])
    return False

def submit_ltx_workflow(config):
    """提交 LTX 生成工作流"""
    import random
    
    seed = config["seed"] if config["seed"] >= 0 else random.randint(0, 2**32)
    
    workflow = {
        "prompt": {
            "1": {
                "class_type": "UnetLoaderGGUF",
                "inputs": {
                    "unet_name": "ltx-2.3-22b-dev-Q2_K.gguf"
                }
            },
            "2": {
                "class_type": "VAELoader",
                "inputs": {
                    "vae_name": "vae_with_config_fixed.safetensors"
                }
            },
            "3": {
                "class_type": "LTXVGemmaCLIPModelLoader",
                "inputs": {
                    "gemma_path": "gemma_3_12B_it.safetensors",
                    "ltxv_path": "ltx-2.3-22b-dev.safetensors",
                    "max_length": 1024
                }
            },
            "4": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": config["prompt"],
                    "clip": ["3", 0]
                }
            },
            "5": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": config["negative_prompt"],
                    "clip": ["3", 0]
                }
            },
            "6": {
                "class_type": "LTXVConditioning",
                "inputs": {
                    "positive": ["4", 0],
                    "negative": ["5", 0],
                    "frame_rate": config["fps"]
                }
            },
            "7": {
                "class_type": "EmptyLTXVLatentVideo",
                "inputs": {
                    "width": config["width"],
                    "height": config["height"],
                    "length": config["num_frames"],
                    "batch_size": 1
                }
            },
            "10": {
                "class_type": "RandomNoise",
                "inputs": {
                    "noise_seed": seed
                }
            },
            "11": {
                "class_type": "BasicGuider",
                "inputs": {
                    "model": ["1", 0],
                    "conditioning": ["6", 0]
                }
            },
            "12": {
                "class_type": "KSamplerSelect",
                "inputs": {
                    "sampler_name": "euler_ancestral_cfg_pp"
                }
            },
            "13": {
                "class_type": "LTXVScheduler",
                "inputs": {
                    "steps": config["steps"],
                    "max_shift": 2.05,
                    "base_shift": 0.95,
                    "stretch": 1.0,
                    "terminal": 0.1
                }
            },
            "14": {
                "class_type": "SamplerCustomAdvanced",
                "inputs": {
                    "noise": ["10", 0],
                    "guider": ["11", 0],
                    "sampler": ["12", 0],
                    "sigmas": ["13", 0],
                    "latent_image": ["7", 0]
                }
            },
            "15": {
                "class_type": "LTXVTiledVAEDecode",
                "inputs": {
                    "vae": ["2", 0],
                    "latents": ["14", 0],
                    "horizontal_tiles": 2,
                    "vertical_tiles": 2,
                    "overlap": 8,
                    "last_frame_fix": False
                }
            },
            "16": {
                "class_type": "CreateVideo",
                "inputs": {
                    "images": ["15", 0],
                    "fps": config["fps"]
                }
            },
            "17": {
                "class_type": "SaveVideo",
                "inputs": {
                    "video": ["16", 0],
                    "filename_prefix": "ltx_pipeline",
                    "format": "mp4",
                    "codec": "h264"
                }
            }
        }
    }
    
    print(f"提交 LTX 生成任务...")
    print(f"  提示词: {config['prompt']}")
    print(f"  分辨率: {config['width']}x{config['height']}")
    print(f"  帧数: {config['num_frames']}")
    print(f"  步数: {config['steps']}")
    print(f"  种子: {seed}")
    
    resp = requests.post(f"{COMFYUI_URL}/api/prompt", json=workflow)
    if resp.status_code != 200:
        print(f"错误: {resp.text}")
        return None
    
    prompt_id = resp.json()['prompt_id']
    print(f"任务已提交: {prompt_id}")
    return prompt_id

def wait_for_ltx(prompt_id, timeout=600):
    """等待 LTX 生成完成"""
    print("等待生成完成...")
    start = time.time()
    
    while time.time() - start < timeout:
        resp = requests.get(f"{COMFYUI_URL}/history/{prompt_id}")
        if resp.status_code == 200:
            data = resp.json()
            if prompt_id in data:
                outputs = data[prompt_id].get('outputs', {})
                # 查找生成的视频
                for node_id, node_output in outputs.items():
                    if 'images' in node_output:
                        for img in node_output['images']:
                            if img.get('type') == 'output':
                                filename = img['filename']
                                print(f"\n生成完成: {filename}")
                                return filename
        
        elapsed = int(time.time() - start)
        print(f"\r  等待中... {elapsed}s", end='', flush=True)
        time.sleep(2)
    
    print("\n错误: 生成超时")
    return None

def download_video(filename):
    """下载生成的视频"""
    url = f"{COMFYUI_URL}/view?filename={filename}&type=output"
    output_path = os.path.join(TEMP_DIR, "ltx_generated.mp4")
    
    print(f"下载视频: {filename}")
    resp = requests.get(url)
    if resp.status_code == 200:
        with open(output_path, 'wb') as f:
            f.write(resp.content)
        print(f"已保存: {output_path}")
        return output_path
    else:
        print(f"下载失败: {resp.status_code}")
        return None

def convert_webp_to_mp4(webp_path):
    """将 WEBP 转换为 MP4"""
    mp4_path = webp_path.replace('.webp', '.mp4')
    cmd = [
        'ffmpeg', '-i', webp_path,
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart',
        mp4_path, '-y'
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return mp4_path

def faceswap_video(video_path, source_face_path, output_path):
    """对视频执行换脸"""
    import cv2
    from insightface.app import FaceAnalysis
    from insightface.model_zoo import get_model
    
    print("初始化换脸模型...")
    
    # 初始化人脸分析
    app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
    app.prepare(ctx_id=0, det_size=(640, 640))
    
    # 加载换脸模型
    swapper = get_model('models/insightface/inswapper_128.onnx')
    
    # 读取源人脸
    print(f"读取源人脸: {source_face_path}")
    source_img = cv2.imread(source_face_path)
    if source_img is None:
        print(f"错误: 无法读取源图片")
        return None
    
    source_faces = app.get(source_img)
    if len(source_faces) == 0:
        print("错误: 源图片未检测到人脸")
        return None
    
    source_face = source_faces[0]
    print(f"源人脸检测成功")
    
    # 创建临时目录
    frames_dir = os.path.join(TEMP_DIR, "frames")
    output_frames_dir = os.path.join(TEMP_DIR, "faceswap_frames")
    os.makedirs(frames_dir, exist_ok=True)
    os.makedirs(output_frames_dir, exist_ok=True)
    
    # 提取视频帧
    print("提取视频帧...")
    cmd = [
        'ffmpeg', '-i', video_path,
        '-vf', 'fps=25',
        os.path.join(frames_dir, 'frame_%04d.png'),
        '-y'
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    frames = sorted(Path(frames_dir).glob('frame_*.png'))
    print(f"提取了 {len(frames)} 帧")
    
    # 逐帧换脸
    print("逐帧换脸...")
    for i, frame_path in enumerate(frames):
        print(f"\r  处理帧 {i+1}/{len(frames)}", end='', flush=True)
        
        target_img = cv2.imread(str(frame_path))
        if target_img is None:
            continue
        
        # 检测目标人脸
        target_faces = app.get(target_img)
        if len(target_faces) == 0:
            # 没有检测到人脸，直接复制原帧
            output_path_frame = os.path.join(output_frames_dir, f'frame_{i:04d}.png')
            cv2.imwrite(output_path_frame, target_img)
            continue
        
        # 对每个目标人脸执行换脸
        result = target_img.copy()
        for target_face in target_faces:
            result = swapper.get(result, target_face, source_face, paste_back=True)
        
        output_path_frame = os.path.join(output_frames_dir, f'frame_{i:04d}.png')
        cv2.imwrite(output_path_frame, result)
    
    print("\n换脸完成")
    
    # 合成视频
    print("合成视频...")
    cmd = [
        'ffmpeg', '-framerate', '25',
        '-i', os.path.join(output_frames_dir, 'frame_%04d.png'),
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        output_path,
        '-y'
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"视频已保存: {output_path}")
    
    return output_path

def main():
    parser = argparse.ArgumentParser(description='LTX 生成 + 换脸管道')
    parser.add_argument('--source', '-s', required=True, help='源人脸图片路径')
    parser.add_argument('--prompt', '-p', default=LTX_CONFIG['prompt'], help='LTX 生成提示词')
    parser.add_argument('--width', '-W', type=int, default=LTX_CONFIG['width'], help='视频宽度')
    parser.add_argument('--height', '-H', type=int, default=LTX_CONFIG['height'], help='视频高度')
    parser.add_argument('--frames', '-f', type=int, default=LTX_CONFIG['num_frames'], help='帧数')
    parser.add_argument('--steps', type=int, default=LTX_CONFIG['steps'], help='采样步数')
    parser.add_argument('--seed', type=int, default=LTX_CONFIG['seed'], help='随机种子')
    parser.add_argument('--output', '-o', default=None, help='输出文件名')
    args = parser.parse_args()
    
    # 检查源人脸图片
    if not os.path.exists(args.source):
        print(f"错误: 源图片不存在: {args.source}")
        return 1
    
    # 设置输出路径
    if args.output:
        output_path = os.path.join(OUTPUT_DIR, args.output)
    else:
        timestamp = int(time.time())
        output_path = os.path.join(OUTPUT_DIR, f"ltx_faceswap_{timestamp}.mp4")
    
    print("=" * 60)
    print("LTX 生成 + 换脸管道")
    print("=" * 60)
    print(f"源人脸: {args.source}")
    print(f"提示词: {args.prompt}")
    print(f"分辨率: {args.width}x{args.height}")
    print(f"帧数: {args.frames}")
    print(f"输出: {output_path}")
    print("=" * 60)
    
    ensure_dirs()
    
    # 1. 检查 ComfyUI
    if not start_comfyui():
        print("错误: ComfyUI 未运行")
        return 1
    
    # 2. 提交 LTX 生成任务
    config = LTX_CONFIG.copy()
    config['prompt'] = args.prompt
    config['width'] = args.width
    config['height'] = args.height
    config['num_frames'] = args.frames
    config['steps'] = args.steps
    config['seed'] = args.seed
    
    prompt_id = submit_ltx_workflow(config)
    if not prompt_id:
        return 1
    
    # 3. 等待生成完成
    filename = wait_for_ltx(prompt_id)
    if not filename:
        return 1
    
    # 4. 下载生成的视频
    video_path = download_video(filename)
    if not video_path:
        return 1
    
    # 5. 如果是 WEBP 格式，转换为 MP4
    if video_path.endswith('.webp'):
        print("转换 WEBP 到 MP4...")
        video_path = convert_webp_to_mp4(video_path)
    
    # 6. 执行换脸
    print("\n" + "=" * 60)
    print("开始换脸处理")
    print("=" * 60)
    
    result = faceswap_video(video_path, args.source, output_path)
    if not result:
        return 1
    
    print("\n" + "=" * 60)
    print("✅ 管道完成!")
    print("=" * 60)
    print(f"生成视频: {video_path}")
    print(f"换脸结果: {result}")
    print(f"文件大小: {os.path.getsize(result) / 1024:.1f} KB")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
