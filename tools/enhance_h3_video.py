#!/usr/bin/env python3
"""H3 成片后期增强：AI 超分到 720P + 补帧到 60fps。

三级路径（自动选择）：
  1) --vfi 且已安装 comfyui-vfi ：ComfyUI VFI(GridUpscale/RealESRGAN) AI 超分到目标分辨率
     + ffmpeg minterpolate 补帧到目标fps  【画质最好，需先装好新人则先装节点包】
  2) 默认(零依赖)：ffmpeg lanczos 超分 + minterpolate 运动补偿补帧  【立即可用】
  3) --fast：快速抽帧式补帧

用法:
  python tools/enhance_h3_video.py <video.mp4> --to 720:1280 --fps 60
  python tools/enhance_h3_video.py <video.mp4> --vfi            # 用 VFI AI 超分(需已装)
  python tools/enhance_h3_video.py <video.mp4> --fast           # 快速试看

手动装载时机: comfyui-vfi(ZIP 解压到 custom_nodes\\ComfyUI-VFI\\ → 重启 ComfyUI)。
网络恢复后我会直接 clone 并在此自动使用。
"""
import subprocess, sys, os, argparse, json, time, uuid

import urllib.request

from h3_xinniang_v1 import BASE, post, wait_done, probe_streams, probe_duration

FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
OUT_ROOT = r"D:\ai_projects\ComfyUI\output"

_oi = {}
def oi(cn):
    if cn not in _oi:
        r = json.loads(urllib.request.urlopen(f"{BASE}/object_info/{cn}", timeout=30).read())
        _oi[cn] = r[cn]["input"]
    return _oi[cn]

def node_present(cn):
    try:
        oi(cn); return True
    except Exception:
        return False

def pick(options, hints=()):
    for h in hints:
        for o in options:
            if h.lower() in str(o).lower():
                return o
    return options[0]

def src_fps(video):
    try:
        s = probe_streams(video)["streams"][0]["r_frame_rate"]
        a, b = map(int, s.split("/")); return (a / b) if b else 24.0
    except Exception:
        return 24.0

def run_vfi_superres(video, W, H, prefix):
    """VFI：读视频 → GridUpscale AI 超分到 W×H → 存中间 mp4，返回其路径。"""
    # 1 读视频
    # 2 载超分模型
    # 3 GridUpscale 超分
    # 4 存中间结果
    hints_model = oi("UpscaleModelLoader")["required"]["model"]
    model = pick(hints_model[0], ["GridUpscale", "Grid", "grid"])
    g = oi("ImageGridUpscaleNode")["required"]
    igu = {"images": ["1", 0], "model": ["2", 0]}
    if "width" in g:
        igu["width"] = W
        igu["height"] = H
    if "scale_factor" in g and isinstance(g["scale_factor"][0], int):
        igu["scale_factor"] = 2
    if "interpolation" in g:
        igu["interpolation"] = pick(g["interpolation"][0])
    if "model_epoch" in g:
        igu["model_epoch"] = 0

    vc = {"images": ["3", 0], "frame_rate": int(src_fps(video)), "loop_count": 0,
          "filename_prefix": prefix, "format": "video/h264-mp4", "pingpong": False,
          "save_output": True}

    wf = {
        "1": {"class_type": "VHS_VideoLoader", "inputs": {"video": video}},
        "2": {"class_type": "UpscaleModelLoader", "inputs": {"model": model}},
        "3": {"class_type": "ImageGridUpscaleNode", "inputs": igu},
        "4": {"class_type": "VHS_VideoCombine", "inputs": vc},
    }
    r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
    pid = r.get("prompt_id")
    print(f"  VFI 超分中 pid={pid}...")
    if not wait_done(pid):
        print("  VFI 超分失败，改走 ffmpeg"); return None
    folder = os.path.join(OUT_ROOT, os.path.dirname(prefix).replace("\\", "/"))
    cand = []
    for f in os.listdir(folder):
        if f.startswith(os.path.basename(prefix)) and f.endswith(".mp4"):
            cand.append(os.path.join(folder, f))
    return cand[-1] if cand else None

def ffmpeg_fps(src, out, W, H, fps, fast):
    if fast:
        vf = f"scale={W}:{H}:flags=lanczos,setsar=1,fps={fps},format=yuv420p"
    else:
        vf = (f"scale={W}:{H}:flags=lanczos,setsar=1,"
              f"minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir,"
              f"format=yuv420p")
    cmd = [FFMPEG, "-y", "-i", src, "-vf", vf,
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-movflags", "+faststart", out]
    subprocess.run(cmd, capture_output=True, text=True)
    return os.path.exists(out)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", help="输入 mp4")
    ap.add_argument("--to", default="720:1280", help="目标分辨率 WxH")
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--vfi", action="store_true", help="优先用 ComfyUI VFI 做 AI 超分")
    ap.add_argument("--fast", action="store_true", help="快速模式：抽帧式补帧")
    args = ap.parse_args()

    src = args.video
    if not os.path.exists(src):
        print("错误: 输入不存在", src); sys.exit(1)
    W, H = map(int, args.to.split(":"))
    name, ext = os.path.splitext(src)
    out = f"{name}_en_{W}x{H}_{args.fps}fps.mp4"

    print("增强:", src, f"-> {W}×{H}@{args.fps}fps")

    use_vfi = args.vfi and node_present("ImageGridUpscaleNode")
    if args.vfi and not node_present("ImageGridUpscaleNode"):
        print("  ⚠️ 未检测到 comfyui-vfi，改走 ffmpeg 超分。装好后会自动启用。")

    if use_vfi:
        print("  使用 VFI 路线（AI 超分 → 补帧）")
        up = run_vfi_superres(src, W, H, "vfi_enhance/tmp_up")
        if not up:
            up = src
    else:
        up = src

    ok = ffmpeg_fps(up, out, W, H, args.fps, args.fast)
    if use_vfi and up != src:
        # 清理中间超分文件
        try: os.remove(up)
        except Exception: pass
    print("完成:", out, "|", (round(os.path.getsize(out) / 1024 / 1024, 2) if ok else "?"), "MB")

    print("\n=== 说明 ===")
    print("VFI 路线需要先安装 comfyui-vfi(ZIP 解压到 custom_nodes\\ComfyUI-VFI\\ 后重启 ComfyUI)")
    print("exact 60fps 由 minterpolate 保证；VFI 只负责更清晰的 AI 超分。")

if __name__ == "__main__":
    main()