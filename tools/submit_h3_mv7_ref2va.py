#!/usr/bin/env python3
"""H3 女团 MV 7 段批量生成 — ref2va 快速通道（已验证 3min/段）

为什么用 ref2va 而不是 fl2va：
- fl2va 无 SageAttention 在 16GB 卡上极慢（30+ min/段，lowvram 卸载循环）
- ref2va 已验证 3 min/段，first_frame 锚定人物一致性（2026-08-31 冒烟成功）
- 段间衔接：每段生成后抽尾帧 → 作为下一段 first_frame（fl2va 首尾帧的替代方案）

用法:
  python tools/submit_h3_mv7_ref2va.py --smoke  # 1 段冒烟
  python tools/submit_h3_mv7_ref2va.py          # 全部 7 段
"""
import json, urllib.request, time, os, sys, shutil

BASE = "http://127.0.0.1:8188"
INPUT_DIR = r"D:\ai_projects\ComfyUI\input"

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


def build(seg, first_img, seed):
    """ref2va 已验证链路：heretic CLIP + fp16 VAE + SigmaShift + KSampler"""
    wf = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors", "type": "minimax"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
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
            "filename_prefix": f"h3_mv7/{seg['id']}",
            "format": "video/h264-mp4", "pingpong": False, "save_output": True}},
    }
    return wf


def main():
    smoke = "--smoke" in sys.argv
    segs = SEGMENTS[:1] if smoke else SEGMENTS

    # P002 首帧
    p002_src = r"D:\ai_projects\ComfyUI\output\mv7_three_members_00001_.png"
    p002_name = "mv7_three_first.png"
    dst = os.path.join(INPUT_DIR, p002_name)
    if not os.path.exists(dst) and os.path.exists(p002_src):
        shutil.copy2(p002_src, dst)
        print(f"📋 P002 → {p002_name}")

    prev_last = None
    pids = []
    for i, seg in enumerate(segs):
        # 统一用三人首帧锚定（段间衔接由 stitch 工具抽尾帧处理）
        first = p002_name
        seed = 20260901 + i * 7
        wf = build(seg, first, seed)
        try:
            r = post("/prompt", {"prompt": wf})
            pid = r.get("prompt_id")
            pids.append({"seg": seg["id"], "pid": pid, "seed": seed, "first": first})
            print(f"[{seg['id']}] {seg['name']} → pid={pid}, first={first}")
        except Exception as e:
            print(f"[{seg['id']}] ❌ 提交失败: {e}")
        # 下一段 first = 本段尾帧（需在生成后抽帧；此处先占位）
        prev_last = f"mv7_{seg['id']}_last.png"
        time.sleep(0.5)

    with open(r"D:\ai_projects\ComfyUI\tools\h3_mv7_ref2va_pids.json", "w") as f:
        json.dump({"pids": pids, "mode": "smoke" if smoke else "full"}, f, indent=1)
    print(f"\n{'冒烟' if smoke else '全部'}提交完成")


if __name__ == "__main__":
    main()
