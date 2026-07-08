"""
阮胺视频去马赛克 + 换脸管线
===========================
两步法去马赛克 + ReActor 换脸

用法:
    python tools/demosaic_faceswap_pipeline.py \
        --input input/阮胺/xxx.mp4 \
        --face input/face_swap_source.png \
        --output output/xxx_demosaic.mp4 \
        [--frames 10] [--skip-existing] [--demosaic-only] [--faceswap-only]
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

import cv2
import numpy as np

COMFYUI_URL = "http://127.0.0.1:8188"
POLL_INTERVAL = 3
MAX_POLL_WAIT = 600


# ─── ComfyUI API ──────────────────────────────────────────────────────────────

def upload_image(filepath):
    fn = os.path.basename(filepath)
    with open(filepath, "rb") as f:
        data = f.read()
    boundary = "----FB" + uuid.uuid4().hex[:16]
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{fn}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{COMFYUI_URL}/upload/image", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    return json.loads(urllib.request.urlopen(req).read()).get("name", fn)


def submit_and_wait(workflow, client_id="pipeline"):
    data = json.dumps({"prompt": workflow, "client_id": client_id}).encode()
    req = urllib.request.Request(
        f"{COMFYUI_URL}/prompt", data=data,
        headers={"Content-Type": "application/json"},
    )
    resp = json.loads(urllib.request.urlopen(req).read())
    pid = resp["prompt_id"]

    for i in range(MAX_POLL_WAIT // POLL_INTERVAL):
        time.sleep(POLL_INTERVAL)
        try:
            h = json.loads(urllib.request.urlopen(f"{COMFYUI_URL}/history/{pid}").read())
            if pid in h:
                st = h[pid].get("status", {})
                if st.get("status_str") == "error":
                    msgs = st.get("messages", [])
                    for m in msgs:
                        if isinstance(m, list) and len(m) > 1 and isinstance(m[1], dict):
                            em = m[1].get("exception_message", "")
                            if em:
                                raise RuntimeError(f"ComfyUI error: {em[:300]}")
                    raise RuntimeError("ComfyUI unknown error")
                outputs = h[pid].get("outputs", {})
                if outputs:
                    for nid, nout in outputs.items():
                        if "images" in nout:
                            for img in nout["images"]:
                                return img["filename"]
        except urllib.error.URLError:
            pass
    raise TimeoutError(f"Prompt {pid} timed out")


# ─── Mosaic Detection ─────────────────────────────────────────────────────────

def detect_mosaic_mask(frame):
    """检测马赛克区域并生成 mask。
    返回: (mask, mosaic_type) where mask is binary, mosaic_type is 'A' or 'B'
    """
    h, w = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # 检测高梯度区域（棋盘格/马赛克特征）
    sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    mag = np.sqrt(sobelx**2 + sobely**2)
    mag_norm = (mag / mag.max() * 255).astype(np.uint8)

    # 高梯度 = 马赛克边缘
    _, high = cv2.threshold(mag_norm, 35, 255, cv2.THRESH_BINARY)

    # 形态学：闭合间隙
    k = np.ones((15, 15), np.uint8)
    closed = cv2.morphologyEx(high, cv2.MORPH_CLOSE, k)

    # 只在头部区域检测（上方40%）
    head_region = closed[:h // 2, :]
    contours, _ = cv2.findContours(head_region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        # 没有检测到马赛克，用默认头部区域
        mask = np.zeros((h, w), dtype=np.uint8)
        mx1, mx2 = int(w * 0.30), int(w * 0.70)
        my1, my2 = int(h * 0.10), int(h * 0.40)
        cv2.ellipse(mask, ((mx1 + mx2) // 2, (my1 + my2) // 2),
                    ((mx2 - mx1) // 2, (my2 - my1) // 2), 0, 0, 360, 255, -1)
        return mask, "unknown"

    # 找最大的高密度区域
    biggest = max(contours, key=cv2.contourArea)
    x, y, cw, ch = cv2.boundingRect(biggest)

    # 创建椭圆形 mask（比检测区域大一点）
    mask = np.zeros((h, w), dtype=np.uint8)
    mcx = x + cw // 2
    mcy = y + ch // 2
    rx = cw // 2 + 15
    ry = ch // 2 + 15
    cv2.ellipse(mask, (mcx, mcy), (rx, ry), 0, 0, 360, 255, -1)

    # 扩展包含颈部
    neck_y2 = min(h, mcy + ry + int(h * 0.10))
    cv2.ellipse(mask, (mcx, (mcy + neck_y2) // 2), (rx, (neck_y2 - mcy) // 2 + 10), 0, 0, 360, 255, -1)

    # 羽化边缘
    mask = cv2.GaussianBlur(mask, (21, 21), 10)

    # 判断马赛克类型
    roi = gray[y:y + ch, x:x + cw]
    # 棋盘格有更多高频成分
    roi_lap = np.abs(cv2.Laplacian(roi, cv2.CV_64F))
    if np.mean(roi_lap) > 20:
        mosaic_type = "B"  # 棋盘格
    else:
        mosaic_type = "A"  # 白色圆形

    return mask, mosaic_type


# ─── Pipeline Steps ───────────────────────────────────────────────────────────

def step_telea_inpaint(frame, mask, output_path):
    """Step 1: OpenCV Telea inpaint 填充马赛克区域"""
    filled = cv2.inpaint(frame, mask, 15, cv2.INPAINT_TELEA)
    cv2.imwrite(output_path, filled)
    return filled


def step_sdxl_img2img(input_path, mask_path, output_dir, seed=42, denoise=0.55, steps=25):
    """Step 2: SDXL img2img 生成面部特征"""
    input_name = upload_image(input_path)
    mask_name = upload_image(mask_path)

    workflow = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}},
        "4": {"class_type": "LoadImage", "inputs": {"image": input_name, "upload": "image"}},
        "5": {"class_type": "LoadImage", "inputs": {"image": mask_name, "upload": "image"}},
        "6": {"class_type": "ImageToMask", "inputs": {"image": ["5", 0], "channel": "red"}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {
            "text": "beautiful young woman face and neck, clear skin, natural lighting, photorealistic, detailed eyes nose lips, smooth neck transition, natural skin tone",
            "clip": ["1", 1],
        }},
        "8": {"class_type": "CLIPTextEncode", "inputs": {
            "text": "mosaic, pixelated, blurry, distorted, deformed, ugly, checkerboard, bad anatomy, extra limbs, disfigured",
            "clip": ["1", 1],
        }},
        "10": {"class_type": "VAEEncodeForInpaint", "inputs": {
            "pixels": ["4", 0], "vae": ["1", 2], "mask": ["6", 0], "grow_mask_by": 12,
        }},
        "10b": {"class_type": "SetLatentNoiseMask", "inputs": {"samples": ["10", 0], "mask": ["6", 0]}},
        "11": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "seed": seed, "steps": steps, "cfg": 7.0,
            "sampler_name": "dpmpp_2m", "scheduler": "karras",
            "positive": ["7", 0], "negative": ["8", 0],
            "latent_image": ["10b", 0], "denoise": denoise,
        }},
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["1", 2]}},
        "13": {"class_type": "SaveImage", "inputs": {"filename_prefix": "demosaic", "images": ["12", 0]}},
    }

    output_fn = submit_and_wait(workflow, f"demosaic_{seed}")
    # Find the output file
    output_path = os.path.join(output_dir, os.path.basename(output_fn))
    comfy_output = f"D:/ai_projects/ComfyUI/output/{output_fn}"
    if os.path.exists(comfy_output):
        import shutil
        shutil.copy2(comfy_output, output_path)
        return output_path
    return None


def step_reactor_faceswap(input_path, face_source_path, output_dir):
    """Step 3: ReActor 换脸"""
    input_name = upload_image(input_path)
    face_name = upload_image(face_source_path)

    workflow = {
        "1": {"class_type": "LoadImage", "inputs": {"image": input_name, "upload": "image"}},
        "2": {"class_type": "LoadImage", "inputs": {"image": face_name, "upload": "image"}},
        "3": {"class_type": "ReActorFaceSwap", "inputs": {
            "enabled": True, "input_image": ["1", 0], "source_image": ["2", 0],
            "swap_model": "inswapper_128.onnx", "facedetection": "retinaface_resnet50",
            "face_restore_model": "GFPGANv1.4.pth", "face_restore_visibility": 1.0,
            "codeformer_weight": 0.5, "detect_gender_input": "no", "detect_gender_source": "no",
            "input_faces_index": "0", "source_faces_index": "0", "console_log_level": 1,
        }},
        "4": {"class_type": "SaveImage", "inputs": {"filename_prefix": "swapped", "images": ["3", 0]}},
    }

    output_fn = submit_and_wait(workflow, "faceswap")
    output_path = os.path.join(output_dir, os.path.basename(output_fn))
    comfy_output = f"D:/ai_projects/ComfyUI/output/{output_fn}"
    if os.path.exists(comfy_output):
        import shutil
        shutil.copy2(comfy_output, output_path)
        return output_path
    return None


# ─── Main Pipeline ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="阮胺视频去马赛克+换脸管线")
    parser.add_argument("--input", "-i", required=True, help="输入视频")
    parser.add_argument("--face", "-f", required=True, help="换脸源图")
    parser.add_argument("--output", "-o", required=True, help="输出视频")
    parser.add_argument("--frames", type=int, default=0, help="处理帧数(0=全部)")
    parser.add_argument("--denoise", type=float, default=0.55, help="img2img denoise")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--demosaic-only", action="store_true")
    parser.add_argument("--faceswap-only", action="store_true")
    parser.add_argument("--compose-only", action="store_true")
    args = parser.parse_args()

    video_name = Path(args.input).stem
    work_dir = os.path.join(os.path.dirname(args.output), f"_work_{video_name}")
    frames_dir = os.path.join(work_dir, "frames")
    demosaic_dir = os.path.join(work_dir, "demosaiced")
    swap_dir = os.path.join(work_dir, "swapped")
    mask_path = os.path.join(work_dir, "mask.png")

    for d in [frames_dir, demosaic_dir, swap_dir]:
        os.makedirs(d, exist_ok=True)

    print(f"═══ 去马赛克+换脸管线 ═══")
    print(f"  输入: {args.input}")
    print(f"  换脸源: {args.face}")
    print(f"  输出: {args.output}")
    print(f"  工作目录: {work_dir}")
    print()

    # ── Step 1: Extract frames ──────────────────────────────────────────────
    if not args.compose_only and not args.faceswap_only:
        existing = [f for f in os.listdir(frames_dir) if f.endswith(".png")]
        if len(existing) == 0:
            print("[1/4] 提取视频帧...")
            probe = subprocess.run(
                ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
                 "-show_entries", "stream=r_frame_rate,nb_frames", "-of", "json", args.input],
                capture_output=True, text=True,
            )
            info = json.loads(probe.stdout)["streams"][0]
            num, den = info["r_frame_rate"].split("/")
            fps = float(num) / float(den)
            total = int(info.get("nb_frames", 0))

            limit = args.frames if args.frames > 0 else total
            subprocess.run(
                ["ffmpeg", "-y", "-i", args.input, "-vframes", str(limit),
                 "-qscale:v", "2", os.path.join(frames_dir, "frame_%05d.png")],
                capture_output=True, check=True,
            )
            frames = sorted(os.listdir(frames_dir))
            print(f"  提取 {len(frames)} 帧 @ {fps:.1f}fps")
        else:
            frames = sorted(existing)
            print(f"[1/4] 使用已有 {len(frames)} 帧")

    # ── Step 2: Create mask ─────────────────────────────────────────────────
    if not args.compose_only and not args.faceswap_only:
        if not os.path.exists(mask_path):
            print("[2/4] 检测马赛克并创建 mask...")
            first_frame = cv2.imread(os.path.join(frames_dir, sorted(os.listdir(frames_dir))[0]))
            mask, mosaic_type = detect_mosaic_mask(first_frame)
            cv2.imwrite(mask_path, mask)
            print(f"  马赛克类型: {mosaic_type}, mask 已保存")
        else:
            print("[2/4] 使用已有 mask")

    # ── Step 3: Demosaic all frames ─────────────────────────────────────────
    if not args.compose_only and not args.faceswap_only:
        print("[3/4] 去马赛克（Telea + SDXL img2img）...")
        frames = sorted([f for f in os.listdir(frames_dir) if f.endswith(".png")])
        mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)

        success = 0
        failed = 0
        t0 = time.time()

        for i, frame_file in enumerate(frames):
            demosaic_path = os.path.join(demosaic_dir, frame_file)
            if args.skip_existing and os.path.exists(demosaic_path):
                success += 1
                continue

            frame_path = os.path.join(frames_dir, frame_file)

            # Step 3a: Telea inpaint
            telea_path = os.path.join(work_dir, "telea_" + frame_file)
            step_telea_inpaint(cv2.imread(frame_path), mask, telea_path)

            # Step 3b: SDXL img2img
            try:
                result = step_sdxl_img2img(
                    telea_path, mask_path, demosaic_dir,
                    seed=args.seed + i, denoise=args.denoise, steps=25,
                )
                if result:
                    # Rename to sequential name
                    final_path = os.path.join(demosaic_dir, frame_file)
                    if result != final_path:
                        import shutil
                        shutil.move(result, final_path)
                    success += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"  ERROR frame {i}: {e}")
                failed += 1

            if (i + 1) % 5 == 0:
                elapsed = time.time() - t0
                avg = elapsed / (success + failed) if (success + failed) > 0 else 0
                eta = avg * (len(frames) - i - 1)
                print(f"  [{i + 1}/{len(frames)}] ok={success} fail={failed} "
                      f"avg={avg:.0f}s ETA={eta / 60:.0f}min")

        elapsed = time.time() - t0
        print(f"  完成: {success} 成功, {failed} 失败, 耗时 {elapsed / 60:.1f}min")

    # ── Step 4: ReActor face swap ───────────────────────────────────────────
    if not args.compose_only and not args.demosaic_only:
        print("[4/4] ReActor 换脸...")
        demosaic_frames = sorted([f for f in os.listdir(demosaic_dir) if f.endswith(".png")])

        success = 0
        t0 = time.time()

        for i, frame_file in enumerate(demosaic_frames):
            swap_path = os.path.join(swap_dir, frame_file)
            if args.skip_existing and os.path.exists(swap_path):
                success += 1
                continue

            demosaic_path = os.path.join(demosaic_dir, frame_file)
            try:
                result = step_reactor_faceswap(demosaic_path, args.face, swap_dir)
                if result:
                    final_path = os.path.join(swap_dir, frame_file)
                    if result != final_path:
                        import shutil
                        shutil.move(result, final_path)
                    success += 1
            except Exception as e:
                print(f"  ERROR frame {i}: {e}")

            if (i + 1) % 5 == 0:
                elapsed = time.time() - t0
                print(f"  [{i + 1}/{len(demosaic_frames)}] ok={success} elapsed={elapsed:.0f}s")

        print(f"  换脸完成: {success} 帧")

    # ── Step 5: Compose video ───────────────────────────────────────────────
    print("[5/5] 合成视频...")
    result_dir = swap_dir if not args.demosaic_only else demosaic_dir
    result_frames = sorted([f for f in os.listdir(result_dir) if f.endswith(".png")])

    if len(result_frames) == 0:
        print("ERROR: No result frames!")
        sys.exit(1)

    # Get fps
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=r_frame_rate", "-of", "json", args.input],
        capture_output=True, text=True,
    )
    info = json.loads(probe.stdout)["streams"][0]
    num, den = info["r_frame_rate"].split("/")
    fps = float(num) / float(den)

    # Extract audio
    audio_path = os.path.join(work_dir, "audio.aac")
    subprocess.run(
        ["ffmpeg", "-y", "-i", args.input, "-vn", "-acodec", "copy", audio_path],
        capture_output=True,
    )

    # Compose
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-framerate", str(fps),
        "-i", os.path.join(result_dir, "frame_%05d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
    ]
    if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
        cmd.extend(["-i", audio_path, "-c:a", "aac", "-shortest"])
    cmd.append(args.output)
    subprocess.run(cmd, capture_output=True, check=True)

    size_mb = os.path.getsize(args.output) / (1024 * 1024)
    print(f"  输出: {args.output} ({size_mb:.1f}MB, {len(result_frames)} 帧)")
    print(f"\n✅ 完成!")


if __name__ == "__main__":
    main()
