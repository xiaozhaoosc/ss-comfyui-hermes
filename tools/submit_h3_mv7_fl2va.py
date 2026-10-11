#!/usr/bin/env python3
"""H3 女团 MV 7 段批量生成（fl2va 首尾帧串联版）

用法:
  python tools/submit_h3_mv7_fl2va.py --smoke   # 只跑 1 段冒烟
  python tools/submit_h3_mv7_fl2va.py           # 跑全部 7 段

链路（与 ref2va 验证一致 + fl2va 首尾帧锚定）:
  UNETLoader(fl2va) → [可选 SageAttentionPatch] → MiniMaxH3SigmaShift(12/3)
  → MiniMaxH3ImageToVideo(first_frame=P002, last_frame=上一段尾帧)
  → KSampler(euler/simple, cfg=1.0, steps=20, seed 固定)
  → VAEDecode + VAEDecodeAudio → VHS_VideoCombine(h264-mp4)
"""
import json, urllib.request, time, os, sys, shutil

BASE = "http://127.0.0.1:8188"
INPUT_DIR = r"D:\ai_projects\ComfyUI\input"
OUT_PREFIX = "h3_mv7"

# 分镜（从网页版 7 段降级适配：5.16s × 本地能力，保留三人固定站位/风格/动作提示）
SEGMENTS = [
    {"id": "seg01", "name": "前奏", "prompt": """A three-member adult K-pop girl group performs on a futuristic concert stage with red, white, silver and black styling. Burgundy-haired performer left, black-bob performer center, silver-haired performer right. Low-lit medium group shot from mid-thigh upward, three separated silhouettes. Layered stage lighting reveals their faces, white ceiling beams, red rectangular graphics expand behind them. Relaxed closed lips, direct eye focus, synchronized chin lift. Camera controlled forward glide. Cinematic high detail.""",
     "first": "P002_v1_00002_.png", "last": ""},
    {"id": "seg02", "name": "主歌1", "prompt": """Three-member K-pop girl group on stage, close-range edit-driven verse. Chest-up medium close-ups sampling left, center, right performers in turn with fast whip transitions, then reunite in compact group shot. Direct eye contact, sharp upper-body choreography, red-white LED graphics, glossy reflective floor. Relaxed closed lips, stable identity matching. Vertical cinematic.""",
     "first": "", "last": ""},
    {"id": "seg03", "name": "主歌2", "prompt": """Three-member K-pop girl group, camera-motion-driven second verse, diagonal depth formation: burgundy-haired near-left foreground, black-bob center midground, silver-haired right-rear layer. Traveling footwork, torso curves, strong parallax as camera slides, oversized red-white typography, glossy black stage with red beams. Relaxed closed lips. Cinematic high detail.""",
     "first": "", "last": ""},
    {"id": "seg04", "name": "预副歌", "prompt": """Three-member K-pop girl group, rising pre-chorus, waist-up to chest-up escalating compositions. Alternating solo close-ups and compact group shots, red LED bars, white light frames, converging spotlights. Controlled body rises, synchronized shoulder locks, Dutch tilt. Relaxed closed lips. Full-frame light impact builds toward chorus.""",
     "first": "", "last": ""},
    {"id": "seg05", "name": "副歌", "prompt": """Three-member K-pop girl group, high-energy chorus, diagonal stage formation with traveling footwork and staggered depth changes. Slightly low-angle mid-thigh shots, heel-toe steps, hip shifts, bent-knee landings, strong camera parallax. Oversized red-white kinetic typography, glossy reflective floor, red beams. Relaxed closed lips. High-energy cinematic.""",
     "first": "", "last": ""},
    {"id": "seg06", "name": "副歌2", "prompt": """Three-member K-pop girl group, compact triangular formation: center performer forward, left and right behind shoulders, waist-up compositions. Synchronized lateral steps, two-count upper-body hits, red-white LED field expanding, spotlights. Relaxed closed lips, direct eye contact. Cinematic high detail.""",
     "first": "", "last": ""},
    {"id": "seg07", "name": "结尾", "prompt": """Three-member K-pop girl group, final stage reveal, complete stage visible with full lighting array: glossy black floor, red-black-white graphics, white light frames, red beams fanning out. Three performers in final pose, confident expressions, relaxed closed lips, camera slow pull-back revealing the whole stage. Cinematic grand finale.""",
     "first": "", "last": ""},
]


def post(path, payload):
    req = urllib.request.Request(f"{BASE}{path}", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=120).read())


def copy_to_input(src, name):
    dst = os.path.join(INPUT_DIR, name)
    if os.path.exists(src) and not os.path.exists(dst):
        shutil.copy2(src, dst)
        print(f"  📋 {os.path.basename(src)} → {name}")
    return name


def build(seg, first_img, last_img, seed):
    wf = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_fl2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_minimax_h3_int8_convrot.safetensors", "type": "minimax"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_int8_convrot.safetensors"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
        "5": {"class_type": "LoadImage", "inputs": {"image": first_img}},
        "8": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
            "clip": ["2", 0], "vae": ["3", 0],
            "first_frame": ["5", 0],
            "prompt": seg["prompt"], "width": 672, "height": 1152, "length": 124}},
        "9": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["1", 0], "shift_video": 12, "shift_audio": 3}},
        "10": {"class_type": "KSampler", "inputs": {
            "model": ["9", 0], "positive": ["8", 0], "negative": ["8", 0], "latent_image": ["8", 1],
            "seed": seed, "steps": 20, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "11": {"class_type": "VAEDecode", "inputs": {"samples": ["10", 0], "vae": ["3", 0]}},
        "12": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["10", 0], "vae": ["4", 0]}},
        "13": {"class_type": "VHS_VideoCombine", "inputs": {
            "images": ["11", 0], "audio": ["12", 0],
            "frame_rate": 24, "loop_count": 0,
            "filename_prefix": f"{OUT_PREFIX}/{seg['id']}",
            "format": "video/h264-mp4", "pingpong": False, "save_output": True}},
    }
    if last_img:
        wf["6"] = {"class_type": "LoadImage", "inputs": {"image": last_img}}
        wf["8"]["inputs"]["last_frame"] = ["6", 0]
    return wf


def main():
    smoke = "--smoke" in sys.argv
    segs = SEGMENTS[:1] if smoke else SEGMENTS

    # 首帧：P002（seg01 用）
    p002_src = r"D:\ai_projects\ComfyUI\output\fp8_hazy_lazy\P002_v1_00002_.png"
    p002_name = copy_to_input(p002_src, "mv7_p002_first.png")

    prev_last = None
    pids = []
    for i, seg in enumerate(segs):
        first = p002_name if i == 0 else prev_last
        last = None  # 7 段各自独立生成，段间用下一段 first=上一段尾帧实现衔接（需抽帧）
        seed = 20260901 + i * 7
        wf = build(seg, first, last, seed)
        try:
            r = post("/prompt", {"prompt": wf})
            pid = r.get("prompt_id")
            pids.append({"seg": seg["id"], "pid": pid, "seed": seed})
            print(f"[{seg['id']}] {seg['name']} → pid={pid}")
        except Exception as e:
            print(f"[{seg['id']}] ❌ 提交失败: {e}")
        if i < len(segs) - 1:
            time.sleep(1)

    with open(r"D:\ai_projects\ComfyUI\tools\h3_mv7_pids.json", "w") as f:
        json.dump({"pids": pids, "mode": "smoke" if smoke else "full"}, f, indent=1)
    print(f"\n{'冒烟' if smoke else '全部'}提交完成, pids 已存")


if __name__ == "__main__":
    main()
