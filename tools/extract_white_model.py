#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从真人视频提取「白模参考视频」(白模/法线驱动的标准前置步骤)。

分两段：
  Pass1 (GPU, ComfyUI 队列)：源视频 → ImageScaleBy 0.5 → MoGe 法线(normal_opengl)
                            → BiRefNet 抠图 mask → ImageCompositeMasked 合成 → 存成法线视频
  Pass2 (CPU, 本脚本)：把法线视频按 Lambert 着色转成白模(clay)视频，落到 input/ 供动作迁移当驱动视频

用法:
  python tools/extract_white_model.py --video "1todos/202610/xxx.mp4" --name wm_202610 --cap 124
  python tools/extract_white_model.py --video ... --name ... --submit-only   # 只提交不等结果

注意（踩过的坑）：
  1. ImageCompositeMasked 的输出批长 = destination 的批长。这里 destination 用「缩放后的帧序列」
     (#3)，所以不会塌成 1 帧；**不要**把 destination 换成 EmptyImage(batch_size=1)。
  2. VHS_LoadVideo 的下拉只列 input/ 根目录，但自定义校验只看文件是否存在，
     因此子目录相对路径（如 1todos/202610/xxx.mp4）可以直接用。
  3. 白模视频必须落到 input/ 根目录或可解析的相对路径，否则下游工作流校验会失败。
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

BASE = "http://127.0.0.1:8188"
# os.environ 里的代理会劫持 127.0.0.1:8188，必须显式绕开
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_prompt(video, cap, prefix):
    return {
        "2": {"class_type": "VHS_LoadVideo", "inputs": {
            "video": video, "force_rate": 24, "custom_width": 0, "custom_height": 0,
            "frame_load_cap": cap, "skip_first_frames": 0, "select_every_nth": 1,
            "format": "AnimateDiff"}},
        "3": {"class_type": "ImageScaleBy", "inputs": {
            "image": ["2", 0], "upscale_method": "lanczos", "scale_by": 0.5}},
        "4": {"class_type": "LoadMoGeModel", "inputs": {
            "model_name": "moge_3_vitg_fp16.safetensors"}},
        "5": {"class_type": "MoGeInference", "inputs": {
            "moge_model": ["4", 0], "image": ["3", 0], "resolution_level": 9,
            "fov_x_degrees": 0.0, "batch_size": 4, "force_projection": True,
            "apply_mask": True, "refine_steps": 3}},
        "6": {"class_type": "MoGeRender", "inputs": {
            "moge_geometry": ["5", 0], "output": "normal_opengl"}},
        "7": {"class_type": "LoadBackgroundRemovalModel", "inputs": {
            "bg_removal_name": "BiRefNet-general.safetensors"}},
        "8": {"class_type": "RemoveBackground", "inputs": {
            "bg_removal_model": ["7", 0], "image": ["3", 0]}},
        "9": {"class_type": "ImageCompositeMasked", "inputs": {
            "destination": ["3", 0], "source": ["6", 0], "x": 0, "y": 0,
            "resize_source": False, "mask": ["8", 0]}},
        "33": {"class_type": "VHS_VideoCombine", "inputs": {
            "images": ["9", 0], "frame_rate": 24, "loop_count": 0,
            "filename_prefix": prefix, "format": "video/h264-mp4", "pix_fmt": "yuv420p",
            "crf": 19, "save_metadata": False, "trim_to_audio": False,
            "pingpong": False, "save_output": True}},
    }


def submit(prompt, client_id):
    body = json.dumps({"prompt": prompt, "client_id": client_id}).encode("utf-8")
    req = urllib.request.Request(BASE + "/prompt", data=body,
                                headers={"Content-Type": "application/json"})
    try:
        with OPENER.open(req, timeout=300) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print("[提交失败] HTTP", e.code)
        try:
            err = json.loads(e.read().decode("utf-8"))
            print("error:", json.dumps(err.get("error", {}), ensure_ascii=False)[:1200])
            for k, v in (err.get("node_errors") or {}).items():
                for e2 in v.get("errors", []):
                    print("  节点 %s: %s %s | %s" % (k, e2.get("type"), e2.get("message"),
                                                   str(e2.get("details"))[:240]))
        except Exception as ex:
            print("raw:", ex)
        return None


def wait(pid, timeout):
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(5)
        try:
            with OPENER.open("%s/history/%s" % (BASE, pid), timeout=30) as r:
                hist = json.loads(r.read().decode("utf-8"))
        except Exception:
            continue
        if pid not in hist:
            el = int(time.time() - t0)
            if el % 60 < 5:
                print("  ...等待中 %ds" % el, flush=True)
            continue
        st = hist[pid].get("status", {})
        if st.get("status_str") == "error":
            for m in st.get("messages", []):
                if m[0] == "execution_error":
                    print("[执行报错]", json.dumps(m[1], ensure_ascii=False)[:1200])
            return None
        if st.get("completed"):
            return hist[pid].get("outputs", {})
    print("[超时] 未在 %ds 内完成" % timeout)
    return None


def normal_video_path(outputs):
    for v in (outputs or {}).values():
        for g in (v.get("gifs") or []):
            sub = (g.get("subfolder") or "").replace("/", os.sep)
            return os.path.join(ROOT, "output", sub, g["filename"])
    return None


def clay_convert(src, dst):
    """法线图 → 白模(clay)：Lambert 漫反射 + 环境光，三通道灰白。"""
    import cv2
    import numpy as np
    cap = cv2.VideoCapture(src)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out = cv2.VideoWriter(dst, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    light = np.array([0.2, 0.3, 0.9], dtype=np.float32)
    light /= np.linalg.norm(light)
    n = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        norm = frame.astype(np.float32) / 255.0
        v = (norm - 0.5) * 2.0
        diff = np.clip(np.sum(v * light, axis=-1), 0.0, 1.0) * 0.65 + 0.35
        out.write((np.stack([diff, diff, diff], axis=-1) * 255.0).astype(np.uint8))
        n += 1
    cap.release()
    out.release()
    print("[pass2] %d 帧 → %s (%dx%d @%.1ffps)" % (n, dst, w, h, fps))
    return n


def clay_convert_gpu(src, dst):
    """同上，但走 ffmpeg h264_nvenc（GPU 编码）；失败返回 False 由调用方回退 CPU。"""
    import subprocess
    import numpy as np
    import cv2
    import imageio_ffmpeg
    cap = cv2.VideoCapture(src)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    light = np.array([0.2, 0.3, 0.9], dtype=np.float32)
    light /= np.linalg.norm(light)
    p = subprocess.Popen(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "%dx%d" % (w, h), "-r", str(fps),
         "-i", "-", "-c:v", "h264_nvenc", "-pix_fmt", "yuv420p", "-b:v", "10M", dst],
        stdin=subprocess.PIPE)
    n = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            norm = frame.astype(np.float32) / 255.0
            v = (norm - 0.5) * 2.0
            diff = np.clip(np.sum(v * light, axis=-1), 0.0, 1.0) * 0.65 + 0.35
            p.stdin.write((np.stack([diff, diff, diff], axis=-1) * 255.0).astype(np.uint8).tobytes())
            n += 1
    except (BrokenPipeError, OSError):
        n = -1
    finally:
        cap.release()
        if p.stdin:
            p.stdin.close()
        rc = p.wait()
    if n <= 0 or rc != 0:
        print("[pass2] nvenc 编码失败 (n=%d rc=%s)，回退 CPU" % (n, rc))
        return False
    print("[pass2] %d 帧 → %s (%dx%d @%.1ffps) [GPU nvenc]" % (n, dst, w, h, fps))
    return True


def mux_audio(video_only, audio_src, dst):
    """把音轨并进白模视频。

    #117 VHS_LoadVideo 会对驱动视频抽音轨，纯视频会直接报
    "VHS failed to extract audio ... Output file does not contain any stream"。
    """
    import subprocess
    import imageio_ffmpeg
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [exe, "-y", "-loglevel", "error", "-i", video_only, "-i", audio_src,
           "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
           "-shortest", dst]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("[mux] ffmpeg 失败:\n", (r.stderr or "")[-800:])
        return False
    return True


def audio_source(video):
    """音轨取自源视频（--video，相对 input/ 的路径）。"""
    p = video if os.path.isabs(video) else os.path.join(ROOT, "input", video)
    return p if os.path.exists(p) else None


def white_model_out(normal_video, audio_src, name):
    """法线视频 → 白模视频（并音轨）→ input/<name>.mp4。"""
    tmpdir = os.path.join(ROOT, "temp")
    os.makedirs(tmpdir, exist_ok=True)
    tmp = os.path.join(tmpdir, "_wm_%s_video.mp4" % name)
    if not clay_convert_gpu(normal_video, tmp) and clay_convert(normal_video, tmp) == 0:
        print("[pass2] 转换失败")
        return None
    dst = os.path.join(ROOT, "input", name + ".mp4")
    if audio_src and mux_audio(tmp, audio_src, dst):
        os.remove(tmp)
        print("[mux] 已并入音轨:", audio_src)
    else:
        os.replace(tmp, dst)
        print("[mux] 未并入音轨（源无音轨或 ffmpeg 失败）")
    print("[完成] 白模参考视频 =", dst)
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True, help="源视频（相对 input/ 的路径，子目录用 / ）")
    ap.add_argument("--name", required=True, help="输出白模视频名（不含扩展名），落到 input/<name>.mp4")
    ap.add_argument("--cap", type=int, default=124, help="取多少帧（要与动作迁移的帧数一致）")
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--submit-only", action="store_true")
    ap.add_argument("--normal", default=None,
                    help="跳过 pass1，直接把已有的法线视频做 pass2 着色（不重复提交队列）")
    args = ap.parse_args()

    if args.normal:
        print("[pass2] 复用已有法线视频 =", args.normal)
        if white_model_out(args.normal, audio_source(args.video), args.name) is None:
            return 1
        return 0

    prefix = "2026-10-17/white_model/%s_normal" % args.name
    print("[pass1] 源视频 =", args.video)
    print("[pass1] 帧数 =", args.cap, "| 输出前缀 =", prefix)
    prompt = build_prompt(args.video, args.cap, prefix)
    res = submit(prompt, "extract-white-model")
    if not res:
        return 1
    pid = res.get("prompt_id")
    print("[pass1] prompt_id =", pid, "number =", res.get("number"))
    if args.submit_only:
        return 0

    outputs = wait(pid, args.timeout)
    if outputs is None:
        return 1
    src = normal_video_path(outputs)
    if not src or not os.path.exists(src):
        print("[pass1] 找不到产物视频:", src)
        return 1
    print("[pass1] 法线视频 =", src)

    if white_model_out(src, audio_source(args.video), args.name) is None:
        return 1
    print("       下一步: python tools/submit_h3_duozhi_fix.py --ref 5 --driver %s" % args.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
