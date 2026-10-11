#!/usr/bin/env python3
"""AI美女动感舞蹈 - H3 分段衔接生成（9:16 竖屏，真人写实）

要素来源：2026-09-06 用户提供的视频要素描述
  - 服装：白色紧身吊带背心 + 浅米色宽松短裤 + 黑色高跟鞋
  - 发型：深棕色齐肩短发 + 空气刘海，无饰品
  - 动作：胸前交替摆手 + 身体随节拍摇摆 + 小幅度脚步移动 + 胯部卡点
  - 镜头：固定机位正面平视全身
  - 音乐：节奏明快的电子舞曲（纯音乐）

3 段 × 124帧 ≈ 15.5s，末帧链式衔接
"""
import json, urllib.request, uuid, time, os, sys, subprocess, math, argparse

BASE = "http://127.0.0.1:8188"
FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
FFPROBE = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffprobe.exe"
INPUT_ROOT = r"D:\ai_projects\ComfyUI\input"
OUT_DIR = r"D:\ai_projects\ComfyUI\output\ai_dynamic_dance"
TMP_DIR = os.path.join(INPUT_ROOT, "ai_dance_frames")
REF_IMG = "gemini_ken1/C02_PADDED.png"

STYLE = (
    "realistic cinematic photography, ultra high detail, professional studio lighting, "
    "shallow depth of field, film grain, glossy healthy skin, clean composition. "
)

CHARACTER = (
    "The same young East Asian woman as the reference image, same face and body, "
    "delicate elegant features, porcelain-fair luminous skin. She has a statuesque "
    "hourglass figure with nine-heads-tall proportion: long slender straight legs, "
    "a cinched waist flowing into softly rounded hips, a graceful swan-like neck and "
    "clear collarbones, poised upright posture. "
    "Outfit: a white form-fitting spaghetti-strap tank top, light beige loose-fitting "
    "shorts, and black high heels. Deep brown shoulder-length bob with airy bangs, "
    "exquisite makeup, no jewelry. Full of youthful vitality and confident charm. "
)

CAMERA = (
    "Fixed camera, front-facing eye-level full-body framing, subject centered. "
)

MUSIC = (
    " Upbeat energetic electronic dance music, fast tempo, dense lively beats, "
    "pure instrumental track, perfect for dynamic dancing."
)

NEG = (
    "anime, cartoon, illustration, 2D style, distorted proportions, deformed hands, "
    "extra fingers, extra limbs, bad anatomy, blurry, watermark, text overlay, "
    "dull skin, disconnected limbs"
)

SEG_PROMPTS = [
    # 段1：胸前交替摆 + 身体摇摆 + 小踏步
    STYLE + CHARACTER + CAMERA +
    "She performs an energetic dance routine: alternating hand swings in front of her "
    "chest in rhythm, body swaying left and right with the beat, small precise steps "
    "on the spot in her high heels, hips subtly shifting, shoulders rolling, "
    "her deep brown bob bouncing with the motion, confident bright smile, "
    "eyes sparkling with energy. Fluid continuous motion, no abrupt cuts." +
    MUSIC + " Avoid: " + NEG,
    # 段2：wave下沉 + 转胯卡点 + 高跟鞋碾地
    STYLE + CHARACTER + CAMERA +
    "Continuing the same woman, same face, same white tank top and beige shorts, "
    "same deep brown bob: she drops into a fluid body wave pressing both hands "
    "downward, then pops her hips to the side in sharp rhythmic counts, "
    "pivoting on her high heels with precise footwork, waist twisting smoothly, "
    "shoulders staying level. Her smile widens with playful confidence, "
    "maintaining perfect rhythm with the pounding beat." +
    MUSIC + " Avoid: " + NEG,
    # 段3：加速碎步 + 收势定格
    STYLE + CHARACTER + CAMERA +
    "Continuing the same woman, same face, same white tank top and beige shorts, "
    "same deep brown bob: the finale — rapid small quick steps shifting weight "
    "between feet, arms opening upward in a rising V motion, then a sudden "
    "freeze with arms spread wide, chest raised, one leg slightly forward, "
    "head tilted in a confident glamorous end pose, smiling directly into camera, "
    "hair settling to rest." +
    MUSIC + " Avoid: " + NEG,
]

def post(path, payload):
    req = urllib.request.Request(f"{BASE}{path}", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode(errors='replace')[:800]}")
        raise

def wait_done(pid, timeout=3600, poll=15):
    print(f"  等待 pid={pid[:13]} ...", flush=True)
    t0 = time.time()
    deadline = t0 + timeout
    while time.time() < deadline:
        try:
            h = json.loads(urllib.request.urlopen(f"{BASE}/history/{pid}", timeout=15).read())
            rec = h.get(pid)
            if rec:
                st = rec.get("status", {})
                if st.get("status_str") == "success" or st.get("completed"):
                    return True
                if rec.get("outputs"):
                    return True
                if st.get("status_str") == "error":
                    print("  执行出错:", json.dumps(st, ensure_ascii=False)[:500]); return False
        except Exception as e:
            print("  查询异常:", e)
        el = int(time.time() - t0)
        print(f"    ⏱ {el//60}m{el%60:02d}s", flush=True)
        time.sleep(poll)
    print("  超时"); return False

def build_segment(prompt, first_frame_img, seed, prefix, width, height, length, ref_img):
    n = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors", "type": "minimax"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "4": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["1", 0], "shift_video": 12.0, "shift_audio": 3.0}},
        "5": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
            "clip": ["2", 0], "vae": ["3", 0], "prompt": prompt,
            "width": width, "height": height, "length": length}},
        "6": {"class_type": "KSampler", "inputs": {
            "model": ["4", 0], "seed": seed, "steps": 28, "cfg": 1.0,
            "sampler_name": "euler", "scheduler": "simple",
            "positive": ["5", 0], "negative": ["5", 0], "latent_image": ["5", 1], "denoise": 1.0}},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["3", 0]}},
        "8": {"class_type": "VHS_VideoCombine", "inputs": {
            "images": ["7", 0], "frame_rate": 24.0, "loop_count": 0,
            "filename_prefix": prefix, "format": "video/h264-mp4",
            "pingpong": False, "save_output": True}},
    }
    img = first_frame_img if first_frame_img else ref_img
    if img:
        n["9"] = {"class_type": "LoadImage", "inputs": {"image": img}}
        n["5"]["inputs"]["first_frame"] = ["9", 0]
    return n

def extract_last_frame(mp4, out_png):
    subprocess.run([FFMPEG, "-y", "-sseof", "-0.3", "-i", mp4, "-q:v", "2",
                    "-frames:v", "1", out_png], check=True, capture_output=True)
    return out_png

def probe_duration(mp4):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", mp4], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 5.17

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seg_len", type=int, default=124)
    ap.add_argument("--xfade", type=float, default=0.3)
    args = ap.parse_args()
    W, H = 544, 960
    segs = len(SEG_PROMPTS)
    seg_dur = args.seg_len / 24.0
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)
    print(f"AI动感舞蹈：{segs}段 × {seg_dur:.2f}s ≈ {seg_dur*segs:.1f}s, {W}×{H}")
    print(f"首帧:{REF_IMG} 输出:{OUT_DIR}")
    seg_files = {}
    for i in range(1, segs + 1):
        tag = f"dance_s{i:02d}"
        cands = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                        if f.startswith(tag) and f.endswith(".mp4")])
        if cands:
            seg_files[i] = cands[-1]
            print(f"[{i}/{segs}] {tag} 已存在，跳过")
            continue
        first_img = None
        if i > 1 and i-1 in seg_files:
            prev_tag = f"dance_s{i-1:02d}"
            last_png = extract_last_frame(seg_files[i-1], os.path.join(TMP_DIR, f"{prev_tag}_last.png"))
            first_img = os.path.relpath(last_png, INPUT_ROOT).replace("\\", "/")
        seed = 20260920 + i
        wf = build_segment(SEG_PROMPTS[i-1], first_img, seed, f"ai_dynamic_dance/{tag}", W, H, args.seg_len, REF_IMG)
        r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
        pid = r.get("prompt_id")
        print(f"[{i}/{segs}] {tag} pid={pid}（首帧={'末帧' if first_img else 'C02'}）", flush=True)
        if not wait_done(pid):
            print("  段失败，中止"); sys.exit(1)
        cands = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                        if f.startswith(tag) and f.endswith(".mp4")],
                       key=os.path.getmtime)
        seg_files[i] = cands[-1]
        print(f"  ✓ {os.path.basename(cands[-1])}", flush=True)
    ordered = [seg_files[i] for i in sorted(seg_files)]
    out_name = os.path.join(OUT_DIR, "ai_dynamic_dance_9x16_3seg_260906.mp4")
    cd = args.xfade
    if len(ordered) > 1 and cd > 0:
        inputs = []
        for p in ordered: inputs += ["-i", p]
        durs = [probe_duration(p) for p in ordered]
        chain, prev, acc = [], "0:v", durs[0]
        for i in range(1, len(ordered)):
            off = max(0.0, acc - cd)
            chain.append(f"[{prev}][{i}:v]xfade=transition=fade:duration={cd}:offset={off:.3f}[vx{i}];")
            prev = f"vx{i}"; acc = acc + durs[i] - cd
        fc = "".join(chain) + f"[{prev}]format=yuv420p[vout]"
        cmd = [FFMPEG, "-y"] + inputs + ["-filter_complex", fc, "-map", "[vout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", "24",
            "-movflags", "+faststart", out_name]
    else:
        listfile = os.path.join(OUT_DIR, "concat_list.txt")
        with open(listfile, "w", encoding="utf-8") as f:
            for p in ordered: f.write(f"file '{p.replace(os.sep, '/')}'\n")
        cmd = [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", listfile, "-c", "copy",
               "-movflags", "+faststart", out_name]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print("ffmpeg 退出码:", r.returncode)
    if os.path.exists(out_name):
        print(f"\n✅ 成片: {out_name} ({os.path.getsize(out_name)/1024/1024:.1f} MB)")

if __name__ == '__main__':
    main()
