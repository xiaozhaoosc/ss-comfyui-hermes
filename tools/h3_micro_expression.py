#!/usr/bin/env python3
"""超写实微表情演绎 - 9:16 10秒 85-100mm 面部特写
5 段 × 2s（48帧）链式衔接，节拍严格对齐提示词 0-2s/2-4s/4-6s/6-8s/8-10s
首帧：C02_PADDED，后续段：上段末帧
采样：组2 锐化（steps=34, shift_video=14.0, shift_audio=3.5）
"""
import json, urllib.request, uuid, time, os, sys, subprocess, math, argparse

BASE = "http://127.0.0.1:8188"
FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
FFPROBE = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffprobe.exe"
INPUT_ROOT = r"D:\ai_projects\ComfyUI\input"
OUT_DIR = r"D:\ai_projects\ComfyUI\output\micro_expr"
TMP_DIR = os.path.join(INPUT_ROOT, "micro_expr_frames")
REF_IMG = "gemini_ken1/C02_PADDED.png"

STYLE = (
    "hyper-realistic cinematic portrait photography, 4K HDR, extreme macro detail, "
    "authentic skin texture with subtle pores and natural fine lines, realistic eyeball "
    "refraction with environment reflections, true tear-film physics, individual hair "
    "strands visible, film-grade portrait cinematography. "
)

CHARACTER = (
    "The same young East Asian woman as the reference image, 20 years old, a slender "
    "soft oval face, fair translucent porcelain skin with subtle natural pores. Long "
    "black hair naturally draping on both sides of her face, the top combed back "
    "revealing her full forehead. Large pale grey-blue eyes with crisp iris texture, "
    "realistic moist eyeballs reflecting the environment, long lashes, soft pink "
    "eyeshadow, fine long slightly upturned black eyeliner. Naturally soft eyebrows, "
    "delicate slim nose bridge, small refined nose tip, plump pale-pink glassy "
    "glossy lips. Pure and alluring K-beauty clean-girl vibe. "
)

CAMERA = (
    "Fixed camera, extreme close-up frontal facial portrait at 85-100mm lens equivalent, "
    "her face nearly filling the frame, eyes as the absolute visual center, shallow "
    "depth of field with creamy bokeh. Background: a soft grey-blue interior, "
    "completely blurred out. Lighting: soft frontal beauty light plus window diffused "
    "natural light, face evenly lit, eyes catching natural rectangular catchlights, "
    "delicate highlights on the nose bridge and lips. Only an extremely subtle natural "
    "push-in over the whole clip, no pans, no noticeable camera movement."
)

NEG = (
    "anime, cartoon, 3D render, illustration, distorted face, asymmetrical eyes, "
    "deformed hands, extra fingers, blurry, oversharpened, watermark, text overlay, "
    "doll-like skin, plastic texture, exaggerated expression, wide-angle distortion, "
    "heavy tears, overacting, jerky head movement"
)

SEG_PROMPTS = [
    # 0-2s 惊讶
    STYLE + CHARACTER + CAMERA +
    "0-2 seconds: she looks directly into the camera, her eyes widen slightly, lips "
    "part just a touch, as if she has just heard something unexpected — a subtle "
    "startled, caught-off-guard feeling. Her breath is calm and natural, eyeballs "
    "drift very slightly, she blinks exactly once, head stays nearly still. "
    "Micro-expression only, no overacting. Avoid: " + NEG,
    # 2-4s 失落
    STYLE + CHARACTER + CAMERA +
    "2-4 seconds, continuing: she slowly lowers her gaze, eyes drifting downward away "
    "from the camera, head tipping down just barely with the gaze. Her lips slowly "
    "press closed, mood sinking from startled into hurt and wounded. Her brows "
    "tighten imperceptibly inward, the corner of her mouth shifts almost invisibly. "
    "Micro-expression, restrained, absolutely no exaggerated frowning. Avoid: " + NEG,
    # 4-6s 眼眶湿润
    STYLE + CHARACTER + CAMERA +
    "4-6 seconds, continuing: she slowly lifts her eyes back to the camera, brows "
    "knitting the faintest degree, wounded look deepening. Her eyes begin to glisten "
    "— a fine film of moisture building on the eyeballs, as if fighting back tears. "
    "Subtle eyelid tremble, pupils drifting slightly, her breath shallow and natural. "
    "Tears NOT yet falling, just the pre-tear sheen. Avoid: " + NEG,
    # 6-8s 手托下巴
    STYLE + CHARACTER + CAMERA +
    "6-8 seconds, continuing: a hand (someone else's, elegant knuckles, natural skin "
    "tone) enters slowly from the bottom-right of the frame and gently cradles her "
    "chin and right cheek, the motion continuous and smooth, no sudden grab. She "
    "does not pull away, keeps watching the camera, brows knit a micro-degree deeper, "
    "her gaze now visibly fragile. Avoid: " + NEG,
    # 8-10s 忍泪定格
    STYLE + CHARACTER + CAMERA +
    "8-10 seconds, continuing: the hand keeps cradling her chin. Her eye rims grow "
    "visibly pink and moist, the pale grey-blue irises forming delicate tear-light "
    "reflections, a tiny bead of tears gathering under the lower lashes — but NOT "
    "freely crying. She tilts her eyes up slightly meeting the camera directly, "
    "lips pressed tight — the held-back sob look: hurt, vulnerable, restrained. "
    "Hold the pose. Avoid: " + NEG,
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

def build_segment(prompt, first_frame_img, seed, prefix, W, H, length,
                  steps, shift_v, shift_a):
    n = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors", "type": "minimax"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "4": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["1", 0], "shift_video": shift_v, "shift_audio": shift_a}},
        "5": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
            "clip": ["2", 0], "vae": ["3", 0], "prompt": prompt,
            "width": W, "height": H, "length": length}},
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
    if first_frame_img:
        n["9"] = {"class_type": "LoadImage", "inputs": {"image": first_frame_img}}
        n["5"]["inputs"]["first_frame"] = ["9", 0]
    return n

def extract_last_frame(mp4, out_png):
    subprocess.run([FFMPEG, "-y", "-sseof", "-0.3", "-i", mp4, "-q:v", "2",
                    "-frames:v", "1", out_png], check=True, capture_output=True)
    return out_png

def probe_duration(mp4):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", mp4], capture_output=True, text=True)
    try: return float(r.stdout.strip())
    except Exception: return 2.0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--length", type=int, default=53, help="帧数；53 = 向上取整到 17k+5 ≈ 2.2s")
    ap.add_argument("--steps", type=int, default=34)
    ap.add_argument("--shift_video", type=float, default=14.0)
    ap.add_argument("--shift_audio", type=float, default=3.5)
    args = ap.parse_args()
    W, H = 544, 960
    segs = len(SEG_PROMPTS)
    seg_dur = args.length / 24.0
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)
    print(f"微表情演绎：{segs}段 × ~{seg_dur:.2f}s（目标总时长≈{seg_dur*segs:.1f}s）")
    print(f"steps={args.steps}, shift={args.shift_video}/{args.shift_audio}, 首帧={REF_IMG}")

    seg_files = {}
    for i in range(1, segs + 1):
        tag = f"me_s{i:02d}"
        cands = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                        if f.startswith(tag) and f.endswith(".mp4")])
        if cands:
            seg_files[i] = cands[-1]; print(f"[{i}/{segs}] {tag} 已存在，跳过"); continue
        first_img = None
        if i > 1 and i-1 in seg_files:
            prev_tag = f"me_s{i-1:02d}"
            last_png = extract_last_frame(seg_files[i-1], os.path.join(TMP_DIR, f"{prev_tag}_last.png"))
            first_img = os.path.relpath(last_png, INPUT_ROOT).replace("\\", "/")
        elif i == 1:
            first_img = REF_IMG
        seed = 20261230 + i
        wf = build_segment(SEG_PROMPTS[i-1], first_img, seed, f"micro_expr/{tag}",
                           W, H, args.length, args.steps, args.shift_video, args.shift_audio)
        r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
        pid = r.get("prompt_id")
        print(f"[{i}/{segs}] {tag} pid={pid}（首帧={'末帧' if (i>1 and first_img) else 'C02'}）", flush=True)
        if not wait_done(pid):
            print(f"  {tag} 失败"); sys.exit(1)
        cands = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                        if f.startswith(tag) and f.endswith(".mp4")], key=os.path.getmtime)
        seg_files[i] = cands[-1]
        print(f"  ✓ {os.path.basename(cands[-1])}", flush=True)

    ordered = [seg_files[i] for i in sorted(seg_files)]
    out_name = os.path.join(OUT_DIR, "micro_expr_9x16_5seg_260907.mp4")
    listfile = os.path.join(OUT_DIR, "concat_list.txt")
    with open(listfile, "w", encoding="utf-8") as f:
        for p in ordered: f.write(f"file '{p.replace(os.sep, '/')}'\n")
    r = subprocess.run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", listfile,
                        "-c", "copy", "-movflags", "+faststart", out_name],
                       capture_output=True, text=True)
    print("ffmpeg 退出码:", r.returncode)
    if os.path.exists(out_name):
        print(f"\n✅ 成片: {out_name} ({os.path.getsize(out_name)/1024/1024:.1f} MB)")

if __name__ == '__main__':
    main()
