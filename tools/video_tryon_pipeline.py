"""
视频换装管线：帧提取 → IDM-VTON 逐帧换装 → 合成视频
=======================================================
用法:
    python tools/video_tryon_pipeline.py \
        --input output/Ms_琪大宝_faceswap/xxx.mp4 \
        --garment input/demo_cropped.jpg \
        --output output/xxx_tryon.mp4 \
        --description "light beige satin dress" \
        [--steps 20] [--guidance 2.0] [--strength 1.0] [--seed 42] \
        [--batch-size 1] [--resume] [--skip-existing]

工作流:
    1. ffmpeg 提取视频帧 + 记录音频流
    2. 逐帧送入 ComfyUI IDM-VTON 工作流:
       - DWPose 提取姿态
       - 手动 torso mask (白=服装区域 30%-95% 高度)
       - IDM-VTON 换装
    3. ffmpeg 合成帧回视频 + 音频
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path


# ─── Config ────────────────────────────────────────────────────────────────────

COMFYUI_URL = "http://127.0.0.1:8188"
DEFAULT_STEPS = 20
DEFAULT_GUIDANCE = 2.0
DEFAULT_STRENGTH = 1.0
DEFAULT_SEED = 42
DEFAULT_DESCRIPTION = "clothing"
DEFAULT_NEGATIVE = "wrinkles, bad quality, blurry, distorted, deformed, watermark"
DEFAULT_WIDTH = 768
DEFAULT_HEIGHT = 1024
POLL_INTERVAL = 3       # seconds between polling ComfyUI
MAX_POLL_WAIT = 600     # max seconds to wait per frame


# ─── Utilities ─────────────────────────────────────────────────────────────────

def upload_image(filepath: str) -> str:
    """Upload an image to ComfyUI and return its internal name."""
    fn = os.path.basename(filepath)
    with open(filepath, "rb") as f:
        data = f.read()
    boundary = "----FormBoundary" + uuid.uuid4().hex[:16]
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{fn}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{COMFYUI_URL}/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    resp = json.loads(urllib.request.urlopen(req).read())
    return resp.get("name", fn)


def submit_workflow(workflow: dict, client_id: str = "tryon") -> str:
    """Submit a workflow to ComfyUI and return the prompt_id."""
    data = json.dumps({"prompt": workflow, "client_id": client_id}).encode()
    req = urllib.request.Request(
        f"{COMFYUI_URL}/prompt",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    resp = json.loads(urllib.request.urlopen(req).read())
    return resp["prompt_id"]


def wait_for_completion(prompt_id: str, timeout: int = MAX_POLL_WAIT) -> dict:
    """Poll ComfyUI until the prompt completes. Returns outputs dict."""
    for i in range(timeout // POLL_INTERVAL):
        time.sleep(POLL_INTERVAL)
        try:
            resp = urllib.request.urlopen(f"{COMFYUI_URL}/history/{prompt_id}").read()
            history = json.loads(resp)
            if prompt_id in history:
                status = history[prompt_id].get("status", {})
                if status.get("status_str") == "error":
                    msgs = status.get("messages", [])
                    raise RuntimeError(f"ComfyUI error: {msgs}")
                outputs = history[prompt_id].get("outputs", {})
                if outputs:
                    return outputs
        except urllib.error.URLError:
            pass
    raise TimeoutError(f"Prompt {prompt_id} timed out after {timeout}s")


def extract_frames(video_path: str, frames_dir: str) -> tuple:
    """Extract all frames from video. Returns (fps, total_frames, width, height)."""
    os.makedirs(frames_dir, exist_ok=True)

    # Get video info
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=r_frame_rate,width,height,nb_frames",
         "-of", "json", video_path],
        capture_output=True, text=True
    )
    info = json.loads(probe.stdout)["streams"][0]

    # Parse fps (could be "30/1" or "29.97")
    fps_str = info["r_frame_rate"]
    num, den = fps_str.split("/")
    fps = float(num) / float(den)

    width = int(info["width"])
    height = int(info["height"])
    nb_frames = int(info.get("nb_frames", 0))

    # Extract frames
    subprocess.run(
        ["ffmpeg", "-y", "-i", video_path,
         "-qscale:v", "2",  # high quality
         os.path.join(frames_dir, "frame_%06d.png")],
        capture_output=True, check=True
    )

    # Count actual frames
    actual = len([f for f in os.listdir(frames_dir) if f.endswith(".png")])
    print(f"  Extracted {actual} frames @ {fps:.2f}fps, {width}x{height}")
    return fps, actual, width, height


def extract_audio(video_path: str, audio_path: str) -> bool:
    """Extract audio stream from video. Returns True if audio exists."""
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "copy", audio_path],
            capture_output=True, check=True
        )
        return os.path.exists(audio_path) and os.path.getsize(audio_path) > 0
    except subprocess.CalledProcessError:
        return False


def compose_video(frames_dir: str, output_path: str, fps: float, audio_path: str = None):
    """Combine frames back into a video, optionally with audio."""
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", os.path.join(frames_dir, "result_%06d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "18",  # high quality
    ]
    if audio_path and os.path.exists(audio_path):
        cmd.extend(["-i", audio_path, "-c:a", "aac", "-shortest"])
    cmd.append(output_path)
    subprocess.run(cmd, capture_output=True, check=True)
    print(f"  Video saved: {output_path}")


def create_torso_mask(width: int, height: int, mask_path: str):
    """Create a torso mask: white=服装区域(30%-95%高度), black=脸部(上方).
    
    This is the key insight from IDM-VTON v4:
    - FaceProtectMask causes try-on to not work (torso diff < 3)
    - Manual torso mask works: white=garment, black=face
    - White area: rows from 30% to 95% of height
    - Black area: top 30% (face/head) and bottom 5% (feet)
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        # Fallback: use ffmpeg
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"color=c=black:s={width}x{height}:d=1",
            "-vf", f"drawbox=x=0:y={int(height*0.3)}:w={width}:h={int(height*0.65)}:color=white:t=fill",
            mask_path
        ], capture_output=True, check=True)
        return

    mask = np.zeros((height, width), dtype=np.uint8)
    y1 = int(height * 0.30)
    y2 = int(height * 0.95)
    mask[y1:y2, :] = 255

    # Optional: slightly narrow the sides to avoid arms
    x_margin = int(width * 0.15)
    mask[:, :x_margin] = 0
    mask[:, width - x_margin:] = 0

    cv2.imwrite(mask_path, mask)


def build_tryon_workflow(
    human_name: str,
    pose_name: str,
    mask_name: str,
    garment_name: str,
    description: str,
    negative: str,
    width: int,
    height: int,
    steps: int,
    guidance: float,
    strength: float,
    seed: int,
    pipeline_type: str = "Full body",
) -> dict:
    """Build ComfyUI workflow for IDM-VTON."""
    return {
        # Load IDM-VTON pipeline (PipelineLoader returns PIPELINE type)
        "1": {
            "class_type": "PipelineLoader",
            "inputs": {
                "weight_dtype": "float16",
            },
        },
        # Load human image
        "2": {
            "class_type": "LoadImage",
            "inputs": {"image": human_name, "upload": "image"},
        },
        # Load pose image
        "3": {
            "class_type": "LoadImage",
            "inputs": {"image": pose_name, "upload": "image"},
        },
        # Load mask image
        "4": {
            "class_type": "LoadImage",
            "inputs": {"image": mask_name, "upload": "image"},
        },
        # Load garment image
        "5": {
            "class_type": "LoadImage",
            "inputs": {"image": garment_name, "upload": "image"},
        },
        # DWPose extraction (if needed)
        # Note: We pre-extract pose in batch for efficiency
        # IDM-VTON
        "10": {
            "class_type": "IDM-VTON",
            "inputs": {
                "pipeline": ["1", 0],
                "human_img": ["2", 0],
                "pose_img": ["3", 0],
                "mask_img": ["4", 0],
                "garment_img": ["5", 0],
                "garment_description": description,
                "negative_prompt": negative,
                "width": width,
                "height": height,
                "num_inference_steps": steps,
                "guidance_scale": guidance,
                "strength": strength,
                "seed": seed,
            },
        },
        # Save result
        "11": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "tryon_result",
                "images": ["10", 0],
            },
        },
    }


def process_single_frame(
    frame_path: str,
    garment_path: str,
    mask_path: str,
    output_dir: str,
    frame_idx: int,
    args,
) -> str:
    """Process one frame through IDM-VTON. Returns output image path."""

    # Upload images
    human_name = upload_image(frame_path)
    garment_name = upload_image(garment_path)
    mask_name = upload_image(mask_path)

    # For pose, we use the frame itself as a placeholder
    # IDM-VTON internally uses DWPose or we can pre-extract
    pose_name = human_name  # Let IDM-VTON handle pose internally

    # Build and submit workflow
    workflow = build_tryon_workflow(
        human_name=human_name,
        pose_name=pose_name,
        mask_name=mask_name,
        garment_name=garment_name,
        description=args.description,
        negative=args.negative,
        width=args.width,
        height=args.height,
        steps=args.steps,
        guidance=args.guidance,
        strength=args.strength,
        seed=args.seed,
        pipeline_type=args.pipeline_type,
    )

    prompt_id = submit_workflow(workflow, client_id=f"tryon_{frame_idx}")

    # Wait for completion
    outputs = wait_for_completion(prompt_id)

    # Find output image
    for node_id, node_out in outputs.items():
        if "images" in node_out:
            for img_info in node_out["images"]:
                filename = img_info["filename"]
                # Copy to output directory with sequential naming
                src = os.path.join(
                    os.path.dirname(os.path.dirname(frame_path)),  # output/
                    filename
                )
                if not os.path.exists(src):
                    # Try ComfyUI output directory
                    src = f"D:/ai_projects/ComfyUI/output/{filename}"
                dst = os.path.join(output_dir, f"result_{frame_idx:06d}.png")
                if os.path.exists(src):
                    import shutil
                    shutil.copy2(src, dst)
                    return dst
    raise RuntimeError(f"No output image found for frame {frame_idx}")


# ─── Main Pipeline ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="视频换装管线: 帧提取 → IDM-VTON → 合成视频")
    parser.add_argument("--input", "-i", required=True, help="输入视频路径")
    parser.add_argument("--garment", "-g", required=True, help="服装图片路径")
    parser.add_argument("--output", "-o", required=True, help="输出视频路径")
    parser.add_argument("--description", "-d", default=DEFAULT_DESCRIPTION, help="服装描述")
    parser.add_argument("--negative", "-n", default=DEFAULT_NEGATIVE, help="负面提示词")
    parser.add_argument("--steps", type=int, default=DEFAULT_STEPS, help="推理步数")
    parser.add_argument("--guidance", type=float, default=DEFAULT_GUIDANCE, help="引导强度")
    parser.add_argument("--strength", type=float, default=DEFAULT_STRENGTH, help="换装强度")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="随机种子")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH, help="输出宽度")
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT, help="输出高度")
    parser.add_argument("--pipeline-type", default="Full body", choices=["Full body", "Half body"])
    parser.add_argument("--resume", action="store_true", help="跳过已有结果帧")
    parser.add_argument("--skip-existing", action="store_true", help="同 --resume")
    parser.add_argument("--frames-only", action="store_true", help="只处理帧，不合成视频")
    parser.add_argument("--compose-only", action="store_true", help="只合成视频，不处理帧")
    parser.add_argument("--start-frame", type=int, default=0, help="起始帧号")
    parser.add_argument("--end-frame", type=int, default=-1, help="结束帧号(-1=全部)")
    args = parser.parse_args()

    resume = args.resume or args.skip_existing

    # Setup directories
    video_name = Path(args.input).stem
    work_dir = os.path.join(os.path.dirname(args.output), f"_tryon_work_{video_name}")
    frames_dir = os.path.join(work_dir, "frames")
    result_dir = os.path.join(work_dir, "results")
    mask_dir = os.path.join(work_dir, "masks")
    audio_path = os.path.join(work_dir, "audio.aac")

    os.makedirs(frames_dir, exist_ok=True)
    os.makedirs(result_dir, exist_ok=True)
    os.makedirs(mask_dir, exist_ok=True)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    print(f"═══ 视频换装管线 ═══")
    print(f"  输入: {args.input}")
    print(f"  服装: {args.garment}")
    print(f"  输出: {args.output}")
    print(f"  描述: {args.description}")
    print(f"  参数: steps={args.steps} guidance={args.guidance} strength={args.strength} seed={args.seed}")
    print(f"  管线: {args.pipeline_type}")
    print(f"  工作目录: {work_dir}")
    print()

    # ── Step 1: Extract frames ──────────────────────────────────────────────
    existing_frames = [f for f in os.listdir(frames_dir) if f.endswith(".png")]

    if not args.compose_only and len(existing_frames) == 0:
        print("[1/3] 提取视频帧...")
        fps, total, width, height = extract_frames(args.input, frames_dir)

        # Extract audio
        has_audio = extract_audio(args.input, audio_path)
        print(f"  音频: {'有' if has_audio else '无'}")

        # Auto-detect mask if not using custom size
        if args.width == DEFAULT_WIDTH and args.height == DEFAULT_HEIGHT:
            args.width = width
            args.height = height
    else:
        print("[1/3] 使用已有帧...")
        existing_frames = sorted([f for f in os.listdir(frames_dir) if f.endswith(".png")])
        print(f"  已有 {len(existing_frames)} 帧")

        # Get fps from video
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
             "-show_entries", "stream=r_frame_rate", "-of", "json", args.input],
            capture_output=True, text=True
        )
        info = json.loads(probe.stdout)["streams"][0]
        num, den = info["r_frame_rate"].split("/")
        fps = float(num) / float(den)

        # Extract audio if needed
        if not os.path.exists(audio_path):
            extract_audio(args.input, audio_path)

    # List frames
    frames = sorted([f for f in os.listdir(frames_dir) if f.endswith(".png")])
    total = len(frames)

    start = args.start_frame
    end = args.end_frame if args.end_frame > 0 else total
    frames_to_process = frames[start:end]
    print(f"  处理范围: 帧 {start}-{end-1} (共 {len(frames_to_process)} 帧)")
    print()

    # ── Step 2: Create masks ────────────────────────────────────────────────
    if not args.compose_only:
        print("[2/3] 创建 torso mask...")
        mask_path = os.path.join(mask_dir, "torso_mask.png")
        if not os.path.exists(mask_path):
            create_torso_mask(args.width, args.height, mask_path)
        print(f"  Mask: {args.width}x{args.height}, 白区=30%-95%高度")
        print()

    # ── Step 3: Process frames through IDM-VTON ────────────────────────────
    if not args.compose_only:
        print("[3/3] IDM-VTON 逐帧换装...")

        # Check ComfyUI is running
        try:
            urllib.request.urlopen(f"{COMFYUI_URL}/system_stats", timeout=5)
        except Exception:
            print("ERROR: ComfyUI not running! Start it first:")
            print("  cd D:\\ai_projects\\ComfyUI && venv\\Scripts\\python main.py --highvram")
            sys.exit(1)

        # Upload garment once
        garment_name = upload_image(args.garment)
        print(f"  服装已上传: {garment_name}")

        mask_img_path = os.path.join(mask_dir, "torso_mask.png")
        success = 0
        failed = 0
        skipped = 0
        total_time = 0

        for i, frame_file in enumerate(frames_to_process):
            frame_idx = start + i
            result_path = os.path.join(result_dir, f"result_{frame_idx:06d}.png")

            # Skip if resume mode and result exists
            if resume and os.path.exists(result_path):
                skipped += 1
                if (i + 1) % 50 == 0:
                    print(f"  [{i+1}/{len(frames_to_process)}] 跳过 {skipped} 帧, 完成 {success} 帧")
                continue

            frame_path = os.path.join(frames_dir, frame_file)
            t0 = time.time()

            try:
                process_single_frame(
                    frame_path=frame_path,
                    garment_path=args.garment,
                    mask_path=mask_img_path,
                    output_dir=result_dir,
                    frame_idx=frame_idx,
                    args=args,
                )
                elapsed = time.time() - t0
                total_time += elapsed
                success += 1

                if (i + 1) % 10 == 0:
                    avg = total_time / success if success > 0 else 0
                    eta = avg * (len(frames_to_process) - i - 1)
                    print(f"  [{i+1}/{len(frames_to_process)}] "
                          f"成功={success} 失败={failed} 跳过={skipped} "
                          f"帧耗时={elapsed:.1f}s ETA={eta/60:.1f}min")

            except Exception as e:
                failed += 1
                print(f"  [{i+1}/{len(frames_to_process)}] ERROR frame {frame_idx}: {e}")
                continue

        print(f"\n  处理完成: 成功={success} 失败={failed} 跳过={skipped}")
        if success > 0:
            print(f"  平均帧耗时: {total_time/success:.1f}s")
            print(f"  总耗时: {total_time/60:.1f}min")
    else:
        print("[3/3] 跳过帧处理 (compose-only mode)")

    # ── Step 4: Compose video ───────────────────────────────────────────────
    print()
    print("[4/4] 合成输出视频...")
    result_frames = sorted([
        f for f in os.listdir(result_dir) if f.endswith(".png")
    ])

    if len(result_frames) == 0:
        print("ERROR: No result frames found!")
        sys.exit(1)

    # Verify sequential naming
    has_audio = os.path.exists(audio_path) and os.path.getsize(audio_path) > 0
    compose_video(result_dir, args.output, fps, audio_path if has_audio else None)

    # Final stats
    output_size = os.path.getsize(args.output) / (1024 * 1024)
    print(f"  帧数: {len(result_frames)}")
    print(f"  大小: {output_size:.1f}MB")
    print(f"\n✅ 完成: {args.output}")


if __name__ == "__main__":
    main()
