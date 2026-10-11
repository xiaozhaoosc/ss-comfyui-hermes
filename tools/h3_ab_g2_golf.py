#!/usr/bin/env python3
"""H3 对照实验·组2（运动锐化）：steps=34, shift_video=14.0, shift_audio=3.5
高尔夫挥杆动作切片验证 - 两段式 Chunk Generation

实验目的：消除复杂动作（高尔夫挥杆 / 猫步）末端拖影与肢体融化
参数修正：
  - sampler=euler / scheduler=simple（flow matching 配置，与组1基线一致，仅动 steps+shift）
  - cfg=1.0 固定（H3 flow matching 无 CFG）
  - shift_video:shift_audio 严格保 4:1（14:3.5）

切片设计：
  Phase 1 蓄力段（124帧 ≈5.17s）：站位 → 上杆顶点
  Phase 2 下杆段（124帧 ≈5.17s）：Phase1末帧作为首帧 → 击球+收杆定格

观察要点：
  - 挥杆末端/收杆定格的球杆是否弯折
  - 手腕翻转处的拖影是否锐化
  - 腰跨旋转时下肢是否融合
"""
import json, urllib.request, uuid, time, os, sys, subprocess, math, argparse

BASE = "http://127.0.0.1:8188"
FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
FFPROBE = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffprobe.exe"
INPUT_ROOT = r"D:\ai_projects\ComfyUI\input"
OUT_DIR = r"D:\ai_projects\ComfyUI\output\h3_ab_g2_golf"
TMP_DIR = os.path.join(INPUT_ROOT, "h3_ab_g2_frames")
REF_IMG = "gemini_ken1/C02_PADDED.png"

STYLE = (
    "realistic cinematic photography, ultra high detail, professional sports broadcast "
    "lighting, shallow depth of field, film grain, glossy healthy skin, clean composition. "
)

CHARACTER = (
    "The same young East Asian woman as the reference image, same face and body, "
    "delicate elegant features, porcelain-fair luminous skin. Statuesque hourglass "
    "figure with nine-heads-tall proportion: long slender straight legs, cinched waist "
    "flowing into softly rounded hips, graceful poised upper body. "
    "Golf outfit: white sleeveless form-fitting polo top, pleated white golf skort, "
    "white golf shoes, white golf glove on left hand. Long black hair tied in a high "
    "ponytail, white visor cap. Holding a modern driver golf club. "
)

SETTING = (
    "A professional golf driving range on a clear sunny morning, green turf stretching "
    "into the distance, a few white target flags, soft morning light. "
)

CAMERA = (
    "Fixed camera, front side-angle at belt height, full body in frame, subject centered. "
)

AUDIO = (
    " Ambient driving range sound: distant birdsong, a soft breeze over the turf, "
    "the sharp metallic 'crack' of the club making contact, a gentle thud as the ball "
    "lands far away, subtle fabric swish, no background music."
)

NEG = (
    "anime, cartoon, illustration, 2D style, distorted face, deformed hands, extra "
    "fingers, extra limbs, bent club, broken club, two clubs, melted arms, blurry, "
    "watermark, text overlay, oversharpened"
)

SEG_PROMPTS = [
    # Phase1 蓄力：站位 → 上杆顶点
    STYLE + CHARACTER + SETTING + CAMERA +
    "Phase 1 — the wind-up: she addresses the ball in a professional golf setup stance, "
    "feet shoulder-width apart, knees slightly bent, gaze locked on the ball, both hands "
    "gripping the club low. She then draws the club back smoothly in a fluid takeaway, "
    "rotating her shoulders and hips in perfect coil, arms fully extended at the top of "
    "the backswing. The motion is controlled and gradual, classic professional form, "
    "no jerky movement. Hold at the top for a beat." + AUDIO + " Avoid: " + NEG,
    # Phase2 下杆：击球 → 收杆定格
    STYLE + CHARACTER + SETTING + CAMERA +
    "Phase 2 — the downswing and finish: continuing directly from the previous top-of-"
    "backswing pose, she unleashes a powerful downswing — hips leading the rotation, "
    "waist snapping through, arms extending through impact with a crisp metallic crack "
    "as the club strikes the ball. Follow-through is long and flowing, the club arcing "
    "up and over her left shoulder, ending in a perfectly balanced finish pose held "
    "for a beat, eyes tracking the ball down the fairway, calm confident expression." +
    AUDIO + " Avoid: " + NEG,
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

def build_segment(prompt, first_frame_img, seed, prefix, width, height, length, ref_img,
                  steps=34, shift_video=14.0, shift_audio=3.5):
    """组2 修正参数：steps=34, shift_video=14.0, shift_audio=3.5（保4:1耦合）"""
    n = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors", "type": "minimax"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "4": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["1", 0], "shift_video": shift_video, "shift_audio": shift_audio}},
        "5": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
            "clip": ["2", 0], "vae": ["3", 0], "prompt": prompt,
            "width": width, "height": height, "length": length}},
        "6": {"class_type": "KSampler", "inputs": {
            "model": ["4", 0], "seed": seed, "steps": steps, "cfg": 1.0,
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
    ap.add_argument("--steps", type=int, default=34, help="组2=34, 组1=28")
    ap.add_argument("--shift_video", type=float, default=14.0, help="组2=14, 组1=12")
    ap.add_argument("--shift_audio", type=float, default=3.5, help="组2=3.5, 组1=3.0")
    ap.add_argument("--tag", default="g2", help="输出文件名前缀")
    args = ap.parse_args()
    W, H = 544, 960
    segs = len(SEG_PROMPTS)
    seg_dur = args.seg_len / 24.0
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)
    print(f"H3 组{args.tag.upper()} 高尔夫切片：{segs}段 × {seg_dur:.2f}s, "
          f"steps={args.steps}, shift_v={args.shift_video}, shift_a={args.shift_audio} (比例{args.shift_video/args.shift_audio:.1f}:1)")
    print(f"首帧:{REF_IMG} 输出:{OUT_DIR}")
    seg_files = {}
    for i in range(1, segs + 1):
        tag = f"golf_{args.tag}_s{i:02d}"
        cands = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                        if f.startswith(tag) and f.endswith(".mp4")])
        if cands:
            seg_files[i] = cands[-1]
            print(f"[{i}/{segs}] {tag} 已存在，跳过")
            continue
        first_img = None
        if i > 1 and i-1 in seg_files:
            prev_tag = f"golf_{args.tag}_s{i-1:02d}"
            last_png = extract_last_frame(seg_files[i-1], os.path.join(TMP_DIR, f"{prev_tag}_last.png"))
            first_img = os.path.relpath(last_png, INPUT_ROOT).replace("\\", "/")
        seed = 20261101 + i
        wf = build_segment(SEG_PROMPTS[i-1], first_img, seed,
                           f"h3_ab_g2_golf/{tag}", W, H, args.seg_len, REF_IMG,
                           steps=args.steps, shift_video=args.shift_video,
                           shift_audio=args.shift_audio)
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
    out_name = os.path.join(OUT_DIR, f"golf_ab_{args.tag}_9x16_{segs}seg_steps{args.steps}_sv{int(args.shift_video)}_260906.mp4")
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
