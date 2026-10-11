"""
阮胺视频去马赛克 + 换脸管线 v2
================================
优化版：关键帧处理 + 色彩校正 + 边缘融合

管线步骤:
  1. OpenCV Telea inpaint 填充马赛克
  2. SDXL img2img (denoise=0.75) 生成面部
  3. ReActor 换脸 + GFPGAN
  4. 色彩校正（匹配肤色）
  5. SDXL img2img (denoise=0.30) 融合边缘
  6. 光流插值中间帧 → 合成视频

用法:
    python tools/demosaic_faceswap_v2.py \
        --input input/阮胺/xxx.mp4 \
        --face input/face_swap_source.png \
        --output output/xxx_final.mp4 \
        [--keyframe-fps 1] [--denoise 0.75] [--seed 42] \
        [--skip-existing] [--keyframes-only]
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


def submit_and_wait(workflow, client_id="pipeline", timeout=600):
    data = json.dumps({"prompt": workflow, "client_id": client_id}).encode()
    req = urllib.request.Request(
        f"{COMFYUI_URL}/prompt", data=data,
        headers={"Content-Type": "application/json"},
    )
    resp = json.loads(urllib.request.urlopen(req).read())
    pid = resp["prompt_id"]
    for i in range(timeout // 3):
        time.sleep(3)
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
                                raise RuntimeError(f"ComfyUI: {em[:300]}")
                    raise RuntimeError("ComfyUI unknown error")
                outputs = h[pid].get("outputs", {})
                if outputs:
                    for nid, nout in outputs.items():
                        if "images" in nout:
                            for img in nout["images"]:
                                return img["filename"]
        except urllib.error.URLError:
            pass
    raise TimeoutError(f"Timeout after {timeout}s")


def copy_output(fn, dst_dir):
    src = f"D:/ai_projects/ComfyUI/output/{fn}"
    dst = os.path.join(dst_dir, fn)
    if os.path.exists(src):
        import shutil
        shutil.copy2(src, dst)
        return dst
    return None


# ─── Mosaic Detection ─────────────────────────────────────────────────────────

def detect_mosaic_mask(frame):
    h, w = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    mag = np.sqrt(sobelx**2 + sobely**2)
    mag_norm = (mag / mag.max() * 255).astype(np.uint8)
    _, high = cv2.threshold(mag_norm, 35, 255, cv2.THRESH_BINARY)
    k = np.ones((15, 15), np.uint8)
    closed = cv2.morphologyEx(high, cv2.MORPH_CLOSE, k)
    head_region = closed[:h // 2, :]
    contours, _ = cv2.findContours(head_region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.ellipse(mask, (w // 2, h // 3), (w // 4, h // 5), 0, 0, 360, 255, -1)
        return mask, "unknown", mask
    biggest = max(contours, key=cv2.contourArea)
    x, y, cw, ch = cv2.boundingRect(biggest)
    # 扩大区域：覆盖整个面部（不只是马赛克部分）
    mcx, mcy = x + cw // 2, y + ch // 2
    # 扩展 60% 确保覆盖完整面部
    rx, ry = int(cw * 0.8), int(ch * 0.8)
    # 创建二值 mask（无高斯模糊）
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.ellipse(mask, (mcx, mcy), (rx, ry), 0, 0, 360, 255, -1)
    # 扩展到颈部
    neck_y2 = min(h, mcy + ry + int(h * 0.15))
    cv2.ellipse(mask, (mcx, (mcy + neck_y2) // 2), (rx, (neck_y2 - mcy) // 2 + 10), 0, 0, 360, 255, -1)
    # 创建渐变版用于融合
    blend_mask = cv2.GaussianBlur(mask, (31, 31), 15)
    roi = gray[y:y + ch, x:x + cw]
    roi_lap = np.abs(cv2.Laplacian(roi, cv2.CV_64F))
    mosaic_type = "B" if np.mean(roi_lap) > 20 else "A"
    return mask, mosaic_type, blend_mask


# ─── Pipeline Steps ───────────────────────────────────────────────────────────

def step_telea(frame, mask, out_path, method="telea"):
    if method == "ns":
        filled = cv2.inpaint(frame, mask, 15, cv2.INPAINT_NS)
    else:
        filled = cv2.inpaint(frame, mask, 15, cv2.INPAINT_TELEA)
    cv2.imwrite(out_path, filled)
    return out_path


def step_sdxl_img2img(input_path, denoise=0.75, steps=25, seed=42, prefix="demosaic"):
    """SDXL img2img 去马赛克 - 无 mask，纯全图生成"""
    input_name = upload_image(input_path)
    wf = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}},
        "4": {"class_type": "LoadImage", "inputs": {"image": input_name, "upload": "image"}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {
            "text": "beautiful young woman face and neck, clear skin, natural lighting, photorealistic, detailed eyes nose lips, smooth skin",
            "clip": ["1", 1]}},
        "8": {"class_type": "CLIPTextEncode", "inputs": {
            "text": "mosaic, pixelated, blurry, distorted, deformed, gray block, black face, ugly, bad anatomy",
            "clip": ["1", 1]}},
        "9": {"class_type": "VAEEncode", "inputs": {"pixels": ["4", 0], "vae": ["1", 2]}},
        "11": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "seed": seed, "steps": steps, "cfg": 7.5,
            "sampler_name": "dpmpp_2m", "scheduler": "karras",
            "positive": ["7", 0], "negative": ["8", 0],
            "latent_image": ["9", 0], "denoise": denoise}},
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["1", 2]}},
        "13": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["12", 0]}},
    }
    return submit_and_wait(wf, f"{prefix}_{seed}")


def step_reactor(input_path, face_path):
    input_name = upload_image(input_path)
    face_name = upload_image(face_path)
    wf = {
        "1": {"class_type": "LoadImage", "inputs": {"image": input_name, "upload": "image"}},
        "2": {"class_type": "LoadImage", "inputs": {"image": face_name, "upload": "image"}},
        "3": {"class_type": "ReActorFaceSwap", "inputs": {
            "enabled": True, "input_image": ["1", 0], "source_image": ["2", 0],
            "swap_model": "inswapper_128.onnx", "facedetection": "retinaface_resnet50",
            "face_restore_model": "GFPGANv1.4.pth", "face_restore_visibility": 1.0,
            "codeformer_weight": 0.5, "detect_gender_input": "no", "detect_gender_source": "no",
            "input_faces_index": "0", "source_faces_index": "0", "console_log_level": 1}},
        "4": {"class_type": "SaveImage", "inputs": {"filename_prefix": "swap", "images": ["3", 0]}},
    }
    return submit_and_wait(wf, "reactor")


def step_color_correct(img, mask):
    h, w = img.shape[:2]
    body_y1, body_y2 = int(h * 0.45), int(h * 0.60)
    body_mean = np.mean(img[body_y1:body_y2, :], axis=(0, 1))
    face_y1, face_y2 = int(h * 0.10), int(h * 0.35)
    face_x1, face_x2 = int(w * 0.30), int(w * 0.70)
    face_mean = np.mean(img[face_y1:face_y2, face_x1:face_x2], axis=(0, 1))
    ratio = np.clip(body_mean / (face_mean + 1e-6), 0.7, 1.3)
    mask_bool = mask > 128
    corrected = img.copy()
    for c in range(3):
        corrected[:, :, c] = np.where(mask_bool,
                                       np.clip(img[:, :, c].astype(float) * ratio[c], 0, 255),
                                       img[:, :, c]).astype(np.uint8)
    return corrected


def step_blend(input_path, mask_path, seed=42):
    input_name = upload_image(input_path)
    mask_name = upload_image(mask_path)
    wf = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}},
        "4": {"class_type": "LoadImage", "inputs": {"image": input_name, "upload": "image"}},
        "5": {"class_type": "LoadImage", "inputs": {"image": mask_name, "upload": "image"}},
        "6": {"class_type": "ImageToMask", "inputs": {"image": ["5", 0], "channel": "red"}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {
            "text": "natural woman, seamless face, smooth skin transition, photorealistic, unified skin tone",
            "clip": ["1", 1]}},
        "8": {"class_type": "CLIPTextEncode", "inputs": {
            "text": "blurry, distorted, deformed, mosaic, artifacts, seams, edges",
            "clip": ["1", 1]}},
        "10": {"class_type": "VAEEncodeForInpaint", "inputs": {
            "pixels": ["4", 0], "vae": ["1", 2], "mask": ["6", 0], "grow_mask_by": 4}},
        "10b": {"class_type": "SetLatentNoiseMask", "inputs": {"samples": ["10", 0], "mask": ["6", 0]}},
        "11": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "seed": seed, "steps": 25, "cfg": 7.0,
            "sampler_name": "dpmpp_2m", "scheduler": "karras",
            "positive": ["7", 0], "negative": ["8", 0],
            "latent_image": ["10b", 0], "denoise": 0.30}},
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["1", 2]}},
        "13": {"class_type": "SaveImage", "inputs": {"filename_prefix": "blend", "images": ["12", 0]}},
    }
    return submit_and_wait(wf, f"blend_{seed}")


def create_blend_mask(frame):
    h, w = frame.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.ellipse(mask, (w // 2, int(h * 0.22)), (int(w * 0.22), int(h * 0.12)), 0, 0, 360, 255, -1)
    cv2.ellipse(mask, (w // 2, int(h * 0.38)), (int(w * 0.15), int(h * 0.10)), 0, 0, 360, 255, -1)
    mask = cv2.GaussianBlur(mask, (51, 51), 20)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    bright_mask = (gray > 60).astype(np.uint8) * 255
    mask = cv2.bitwise_and(mask, bright_mask)
    return mask


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="去马赛克+换脸管线 v2")
    parser.add_argument("--input", "-i", required=True)
    parser.add_argument("--face", "-f", required=True)
    parser.add_argument("--output", "-o", required=True)
    parser.add_argument("--keyframe-fps", type=float, default=1.0, help="关键帧率(每秒)")
    parser.add_argument("--denoise", type=float, default=0.75)
    parser.add_argument("--inpaint-method", choices=["telea", "ns"], default="telea")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--keyframes-only", action="store_true", help="只处理关键帧，不插值")
    parser.add_argument("--max-frames", type=int, default=0, help="最大处理帧数(0=全部)")
    args = parser.parse_args()

    video_name = Path(args.input).stem
    work = os.path.join(os.path.dirname(args.output) or ".", f"_work_{video_name}")
    dirs = {k: os.path.join(work, k) for k in
            ["frames", "keyframes", "telea", "demosaiced", "final"]}
    for d in dirs.values():
        os.makedirs(d, exist_ok=True)

    print(f"═══ 去马赛克+换脸管线 v2 ═══")
    print(f"  输入: {args.input}")
    print(f"  关键帧率: {args.keyframe_fps} fps")
    print(f"  denoise: {args.denoise}")
    print()

    # ── Get video info ──────────────────────────────────────────────────────
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=r_frame_rate,width,height,nb_frames", "-of", "json", args.input],
        capture_output=True, text=True,
    )
    vinfo = json.loads(probe.stdout)["streams"][0]
    num, den = vinfo["r_frame_rate"].split("/")
    fps = float(num) / float(den)
    total = int(vinfo.get("nb_frames", 0))
    w, h = int(vinfo["width"]), int(vinfo["height"])
    print(f"  视频: {w}x{h} @ {fps:.1f}fps, {total} 帧")

    # ── Extract keyframes ───────────────────────────────────────────────────
    kf_dir = dirs["keyframes"]
    existing_kf = sorted([f for f in os.listdir(kf_dir) if f.endswith(".png")])
    if len(existing_kf) == 0:
        print(f"\n[1/6] 提取关键帧 ({args.keyframe_fps} fps)...")
        interval = max(1, int(fps / args.keyframe_fps))
        # 用 ffmpeg 按间隔提取
        # ffmpeg 需要正斜杠路径
        kf_pattern = os.path.join(kf_dir, "kf_%05d.png").replace("\\", "/")
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", args.input,
             "-vf", f"select='eq(mod(n,{interval}),0)'",
             "-vsync", "0", "-qscale:v", "2",
             kf_pattern],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  ffmpeg 提取错误: {result.stderr[-300:]}")
            sys.exit(1)
        keyframes = sorted(os.listdir(kf_dir))
        print(f"  提取 {len(keyframes)} 个关键帧")
    else:
        keyframes = existing_kf
        print(f"\n[1/6] 使用已有 {len(keyframes)} 个关键帧")

    if args.max_frames > 0:
        keyframes = keyframes[:args.max_frames]
        print(f"  限制处理 {len(keyframes)} 帧")

    # ── Detect mosaic (from first keyframe) ─────────────────────────────────
    mask_path = os.path.join(work, "mosaic_mask.png")
    blend_mask_path_auto = os.path.join(work, "blend_mask_auto.png")
    # 强制重新生成 mask（使用新的扩展二值方案）
    print("\n[2/6] 检测马赛克...")
    first = cv2.imread(os.path.join(kf_dir, keyframes[0]))
    mask, mtype, blend_mask = detect_mosaic_mask(first)
    cv2.imwrite(mask_path, mask)
    cv2.imwrite(blend_mask_path_auto, blend_mask)
    print(f"  类型: {mtype}, mask白像素: {np.sum(mask > 0)}")

    # ── Process each keyframe ───────────────────────────────────────────────
    print(f"\n[3/6] 处理 {len(keyframes)} 个关键帧...")
    blend_mask_path = blend_mask_path_auto
    t0 = time.time()
    success = 0

    for i, kf_file in enumerate(keyframes):
        final_path = os.path.join(dirs["final"], kf_file)
        if args.skip_existing and os.path.exists(final_path):
            success += 1
            continue

        kf_path = os.path.join(kf_dir, kf_file)
        frame = cv2.imread(kf_path)
        base_seed = args.seed + i

        # Step A: Telea 填充马赛克区域
        telea_path = os.path.join(dirs["telea"], kf_file)
        step_telea(frame, cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE), telea_path, method=args.inpaint_method)

        # Step B+C: SDXL img2img → ReActor（自适应重试）
        frame_ok = False
        for attempt in range(5):
            # 自适应参数：前3次用原始denoise不同seed，后2次降低denoise
            if attempt < 3:
                d = args.denoise
                s = base_seed + attempt * 100
            else:
                d = max(0.55, args.denoise - 0.10 * (attempt - 2))
                s = base_seed + attempt * 100

            try:
                fn = step_sdxl_img2img(telea_path, denoise=d, seed=s, prefix=f"dm{i:04d}_a{attempt}")
                dm_path = os.path.join(dirs["demosaiced"], kf_file)
                copy_output(fn, dirs["demosaiced"])
                src = os.path.join(dirs["demosaiced"], fn)
                if os.path.exists(src) and src != dm_path:
                    import shutil
                    shutil.move(src, dm_path)

                # ReActor 换脸
                fn = step_reactor(dm_path, args.face)
                swap_path = os.path.join(dirs["final"], kf_file)
                copy_output(fn, dirs["final"])
                src = os.path.join(dirs["final"], fn)
                if os.path.exists(src) and src != swap_path:
                    import shutil
                    shutil.move(src, swap_path)

                # 验证：用 OpenCV 人脸检测确认有面部
                result_img = cv2.imread(swap_path)
                if result_img is not None:
                    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
                    gray_check = cv2.cvtColor(result_img, cv2.COLOR_BGR2GRAY)
                    faces = face_cascade.detectMultiScale(gray_check, 1.1, 4, minSize=(30, 30))
                    if len(faces) > 0:
                        frame_ok = True
                        if attempt > 0:
                            print(f"  [{i+1}] retry={attempt} denoise={d:.2f} seed={s}")
                        break
                    else:
                        print(f"  [{i+1}] attempt={attempt} 未检测到人脸, 重试...")
            except Exception as e:
                print(f"  [{i+1}] attempt={attempt} error: {e}")

        if frame_ok:
            success += 1
        else:
            print(f"  [{i+1}] ⚠️ 所有尝试失败，跳过")
            # 用 Telea 输出作为 fallback
            import shutil
            shutil.copy2(telea_path, final_path)
        elapsed = time.time() - t0
        if success > 0:
            avg = elapsed / success
            eta = avg * (len(keyframes) - i - 1)
        else:
            avg = 0
            eta = 0
        print(f"  [{i + 1}/{len(keyframes)}] ok={success} "
              f"elapsed={elapsed / 60:.1f}min ETA={eta / 60:.1f}min")

    print(f"\n  关键帧处理完成: {success}/{len(keyframes)}")

    # ── Interpolate + Compose ───────────────────────────────────────────────
    if not args.keyframes_only:
        print(f"\n[4/6] 光流插值中间帧...")
        # TODO: optical flow interpolation
        # For now, just use keyframes with ffmpeg framerate conversion
        print("  (跳过光流插值，使用关键帧直接合成)")

    print(f"\n[5/6] 合成视频...")
    # Extract audio
    audio_path = os.path.join(work, "audio.aac")
    subprocess.run(["ffmpeg", "-y", "-i", args.input, "-vn", "-acodec", "copy", audio_path.replace("\\", "/")],
                    capture_output=True)

    final_frames = sorted([f for f in os.listdir(dirs["final"]) if f.endswith(".png")])
    if len(final_frames) == 0:
        print("ERROR: No final frames!")
        sys.exit(1)

    # ffmpeg 需要正斜杠路径
    input_pattern = os.path.join(dirs["final"], "kf_%05d.png").replace("\\", "/")
    output_path = args.output.replace("\\", "/")
    audio_ffmpeg = audio_path.replace("\\", "/")
    kf_fps = args.keyframe_fps
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    has_audio = os.path.exists(audio_path) and os.path.getsize(audio_path) > 0
    if has_audio:
        cmd_str = f'ffmpeg -y -framerate {kf_fps} -i "{input_pattern}" -i "{audio_ffmpeg}" -c:v libx264 -pix_fmt yuv420p -crf 18 -c:a aac -shortest "{output_path}"'
    else:
        cmd_str = f'ffmpeg -y -framerate {kf_fps} -i "{input_pattern}" -c:v libx264 -pix_fmt yuv420p -crf 18 "{output_path}"'
    result = subprocess.run(cmd_str, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ffmpeg 错误: {result.stderr[-500:]}")
        sys.exit(1)

    size_mb = os.path.getsize(args.output) / (1024 * 1024)
    elapsed = time.time() - t0
    print(f"  输出: {args.output} ({size_mb:.1f}MB)")
    print(f"  总耗时: {elapsed / 60:.1f}min ({elapsed / success:.0f}s/帧)")

    # 添加水印
    try:
        from watermark import process_video
        wm_output = args.output.replace(".mp4", "_wm.mp4")
        if process_video(args.output, wm_output):
            import shutil
            shutil.move(wm_output, args.output)
            print(f"  水印: comfyui ai生成-ken ✅")
    except Exception as e:
        print(f"  水印失败: {e}")

    print(f"\n✅ 完成!")


if __name__ == "__main__":
    main()
