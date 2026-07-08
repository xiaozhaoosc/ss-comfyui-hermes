"""
基于 ComfyUI API 的批量换装处理脚本
对换脸视频的帧应用 IDM-VTON 换装
"""
import os
import sys
import json
import time
import uuid
import urllib.request
import urllib.parse
import subprocess
import shutil
from pathlib import Path

COMFYUI_URL = "http://127.0.0.1:8188"

def queue_prompt(workflow: dict) -> str:
    """提交工作流到 ComfyUI，返回 prompt_id"""
    data = json.dumps({"prompt": workflow, "client_id": str(uuid.uuid4())}).encode('utf-8')
    req = urllib.request.Request(f"{COMFYUI_URL}/prompt", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
    return result["prompt_id"]

def wait_for_completion(prompt_id: str, timeout: int = 600) -> dict:
    """等待工作流完成，返回输出信息"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(f"{COMFYUI_URL}/history/{prompt_id}") as resp:
                history = json.loads(resp.read())
            if prompt_id in history:
                status = history[prompt_id].get("status", {})
                if status.get("completed", False) or status.get("status_str") == "success":
                    return history[prompt_id]
                if status.get("status_str") == "error":
                    raise RuntimeError(f"Workflow error: {history[prompt_id]}")
        except urllib.error.HTTPError:
            pass
        time.sleep(2)
    raise TimeoutError(f"Workflow {prompt_id} timed out after {timeout}s")

def download_image(filename: str, subfolder: str, output_path: str):
    """从 ComfyUI 下载输出图片"""
    params = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": "output"})
    url = f"{COMFYUI_URL}/view?{params}"
    urllib.request.urlretrieve(url, output_path)

def make_tryon_workflow(person_image: str, garment_image: str, mask_image: str,
                         garment_desc: str, width: int, height: int,
                         steps: int, seed: int) -> dict:
    """构建 IDM-VTON 工作流（使用预生成 mask 替代 FaceProtectMask）"""
    return {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": person_image, "upload": "image"}
        },
        "2": {
            "class_type": "LoadImage",
            "inputs": {"image": garment_image, "upload": "image"}
        },
        "3": {
            "class_type": "LoadImage",
            "inputs": {"image": mask_image, "upload": "image"}
        },
        "5": {
            "class_type": "DensePosePreprocessor",
            "inputs": {"image": ["1", 0]}
        },
        "6": {
            "class_type": "PipelineLoader",
            "inputs": {"weight_dtype": "float16"}
        },
        "7": {
            "class_type": "IDM-VTON",
            "inputs": {
                "pipeline": ["6", 0],
                "human_img": ["1", 0],
                "pose_img": ["5", 0],
                "mask_img": ["3", 0],
                "garment_img": ["2", 0],
                "garment_description": garment_desc,
                "negative_prompt": "monochrome, lowres, bad anatomy, worst quality, low quality",
                "width": width,
                "height": height,
                "num_inference_steps": steps,
                "guidance_scale": 2.0,
                "strength": 1.0,
                "seed": seed
            }
        },
        "8": {
            "class_type": "SaveImage",
            "inputs": {"images": ["7", 0], "filename_prefix": "tryon_batch"}
        }
    }

def upload_image(image_path: str):
    """上传图片到 ComfyUI input 目录"""
    import multipart
    # Simple multipart upload
    boundary = uuid.uuid4().hex
    filename = os.path.basename(image_path)
    
    with open(image_path, 'rb') as f:
        file_data = f.read()
    
    body = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f'Content-Type: application/octet-stream\r\n\r\n'
    ).encode('utf-8') + file_data + f'\r\n--{boundary}--\r\n'.encode('utf-8')
    
    req = urllib.request.Request(
        f"{COMFYUI_URL}/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def upload_image_simple(image_path: str) -> str:
    """通过文件复制到 input 目录来 '上传' 图片"""
    comfy_input = r"D:\ai_projects\ComfyUI\input"
    dest = os.path.join(comfy_input, os.path.basename(image_path))
    if not os.path.exists(dest) or os.path.getmtime(image_path) > os.path.getmtime(dest):
        shutil.copy2(image_path, dest)
    return os.path.basename(image_path)

def extract_frames(video_path: str, output_dir: str, fps: float = None) -> int:
    """从视频中提取帧"""
    os.makedirs(output_dir, exist_ok=True)
    
    # Get source fps
    if fps is None:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-select_streams', 'v:0',
             '-show_entries', 'stream=r_frame_rate', '-of', 'csv=p=0', video_path],
            capture_output=True, text=True)
        fps_str = result.stdout.strip()
        if '/' in fps_str:
            num, den = fps_str.split('/')
            fps = float(num) / float(den)
        else:
            fps = float(fps_str) if fps_str else 25.0
    
    # Extract with frame skip (every 5th frame)
    subprocess.run([
        'ffmpeg', '-i', video_path, '-vf', f'fps={fps/5}',
        os.path.join(output_dir, 'frame_%06d.png'), '-y'
    ], capture_output=True)
    
    frames = sorted(Path(output_dir).glob('frame_*.png'))
    return len(frames)

def assemble_video(frames_dir: str, output_path: str, fps: float = 6.0):
    """将处理后的帧合成为视频"""
    subprocess.run([
        'ffmpeg', '-framerate', str(fps),
        '-i', os.path.join(frames_dir, 'tryon_%06d.png'),
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-crf', '18',
        output_path, '-y'
    ], capture_output=True, check=True)

def main():
    import argparse
    parser = argparse.ArgumentParser(description='ComfyUI API 批量换装')
    parser.add_argument('--input', required=True, help='输入换脸视频')
    parser.add_argument('--garment', required=True, help='服装图片')
    parser.add_argument('--output', required=True, help='输出视频路径')
    parser.add_argument('--mask', default=None, help='Mask图片（可选，不提供则用ATR自动解析）')
    parser.add_argument('--garment-desc', default='garment', help='服装描述')
    parser.add_argument('--width', type=int, default=768)
    parser.add_argument('--height', type=int, default=1024)
    parser.add_argument('--steps', type=int, default=30)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--start-frame', type=int, default=0, help='从第几帧开始（用于断点续传）')
    args = parser.parse_args()
    
    # Directories
    tmp_dir = args.output + '_tmp'
    frames_dir = os.path.join(tmp_dir, 'input_frames')
    output_frames_dir = os.path.join(tmp_dir, 'output_frames')
    os.makedirs(output_frames_dir, exist_ok=True)
    
    # Step 1: Extract frames
    print(f"[1/4] Extracting frames from {args.input}...")
    n_frames = extract_frames(args.input, frames_dir)
    frames = sorted(Path(frames_dir).glob('frame_*.png'))
    print(f"  Extracted {len(frames)} frames (every 5th frame)")
    
    # Step 2: Upload images
    print(f"[2/4] Uploading images...")
    garment_name = upload_image_simple(args.garment)
    print(f"  Garment: {garment_name}")
    
    mask_name = None
    if args.mask:
        mask_name = upload_image_simple(args.mask)
        print(f"  Mask: {mask_name}")
    
    # Step 3: Process frames via ComfyUI API
    print(f"[3/4] Processing {len(frames)} frames via ComfyUI API...")
    total = len(frames)
    times = []
    
    for i, frame_path in enumerate(frames):
        if i < args.start_frame:
            continue
        
        # Check if already processed
        out_path = os.path.join(output_frames_dir, f"tryon_{frame_path.stem.replace('frame_', '')}.png")
        if os.path.exists(out_path):
            print(f"  [{i+1}/{total}] Skip (already done): {frame_path.name}")
            continue
        
        t0 = time.time()
        
        # Upload frame
        frame_name = upload_image_simple(str(frame_path))
        
        # Build workflow
        if mask_name:
            workflow = make_tryon_workflow(
                frame_name, garment_name, mask_name,
                args.garment_desc, args.width, args.height,
                args.steps, args.seed)
        else:
            # Use FaceProtectMask + MaskToImage (no manual mask)
            workflow = make_tryon_workflow(
                frame_name, garment_name, "torso_mask.png",
                args.garment_desc, args.width, args.height,
                args.steps, args.seed)
        
        # Queue and wait
        try:
            prompt_id = queue_prompt(workflow)
            result = wait_for_completion(prompt_id, timeout=300)
            
            # Download result
            outputs = result.get("outputs", {})
            for node_id, node_out in outputs.items():
                if "images" in node_out:
                    for img_info in node_out["images"]:
                        download_image(img_info["filename"], img_info.get("subfolder", ""),
                                       out_path)
                        break
                    break
            
            elapsed = time.time() - t0
            times.append(elapsed)
            avg = sum(times[-10:]) / len(times[-10:])
            remaining = avg * (total - i - 1)
            print(f"  [{i+1}/{total}] {frame_path.name} → {elapsed:.1f}s "
                  f"(avg={avg:.1f}s, ETA={remaining/60:.0f}min)")
        except Exception as e:
            print(f"  [{i+1}/{total}] ERROR: {e}")
            # Save checkpoint
            print(f"  Resume from frame {i} with --start-frame {i}")
            sys.exit(1)
    
    # Step 4: Assemble video
    print(f"[4/4] Assembling video...")
    # Get output frames
    out_frames = sorted(Path(output_frames_dir).glob('tryon_*.png'))
    if not out_frames:
        print("ERROR: No output frames found!")
        sys.exit(1)
    
    # Calculate output fps (source fps / 5 for frame skip)
    assemble_video(output_frames_dir, args.output, fps=6.0)
    
    # Add audio from source
    audio_tmp = args.output + '_audio.mp4'
    try:
        subprocess.run([
            'ffmpeg', '-i', args.output, '-i', args.input,
            '-c:v', 'copy', '-c:a', 'aac', '-map', '0:v:0', '-map', '1:a:0?',
            '-shortest', audio_tmp, '-y'
        ], capture_output=True, check=True)
        os.replace(audio_tmp, args.output)
    except:
        pass  # No audio or merge failed
    
    size_mb = os.path.getsize(args.output) / 1e6
    print(f"\n✅ Done! Output: {args.output} ({size_mb:.1f}MB)")
    print(f"   Processed {len(out_frames)} frames")

if __name__ == "__main__":
    main()
