#!/usr/bin/env python3
"""单边挑眉挑战展示 - 9:16 10秒 85-100mm 面部特写
5 段 × ~2.2s(53帧) 链式衔接：每段以上段末帧为首帧，保证人物/眉形连续
首段纯文生视频（无参考图），identity 由提示词定义
采样：组2 锐化（steps=34, shift_video=14.0, shift_audio=3.5）
末段带英文字幕 DO YOU LIKE MY 'EYEBROW'?
"""
import json, urllib.request, uuid, time, os, sys, subprocess, argparse

BASE = "http://127.0.0.1:8188"
FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
FFPROBE = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffprobe.exe"
INPUT_ROOT = r"D:\ai_projects\ComfyUI\input"
OUT_DIR = r"D:\ai_projects\ComfyUI\output\h3_eyebrow_seg"
TMP_DIR = os.path.join(INPUT_ROOT, "h3_eyebrow_seg_frames")

STYLE = (
    "hyper-realistic cinematic portrait photography, 4K HDR, extreme macro detail, "
    "authentic skin texture with subtle pores and natural fine lines, realistic eyeball "
    "refraction, natural eyebrow hairs visible individually, film-grade portrait cinematography. "
)

CHARACTER = (
    "A young East Asian woman in her early 20s, a slender soft oval face, fair translucent "
    "skin with subtle natural pores. Long black hair softly framing her face, combed back "
    "revealing her forehead. Large peach-brown eyes with crisp iris texture, moist eyeballs, "
    "long black lashes, delicate slightly smoky eyeshadow and fine upward eyeliner. "
    "Fresh trendy NATURAL 'wild-brow' eyebrows with an elegant soft arc and visible individual "
    "hair strokes, the signature focus of this clip. Soft pink glassy glossy lips. "
    "Playful confident clean-girl vibe. "
)

CAMERA = (
    "Fixed camera, extreme close-up frontal facial portrait at 85-100mm lens equivalent, "
    "her eyes and eyebrows near the upper-center third of the frame as the absolute focus, "
    "eyes the visual center, shallow depth of field with creamy bokeh. Background: a soft "
    "grey-blue interior, completely blurred out. Lighting: soft frontal beauty light, face "
    "evenly lit, eyes catching natural rectangular catchlights, subtle highlight on the "
    "nose bridge and brows. Only an extremely subtle natural push-in, no pans."
)

def seg_avoid(text_ok=False):
    base = (
        "anime, cartoon, 3D render, illustration, distorted face, asymmetrical eyes, "
        "deformed hands, extra fingers, blurry, oversharpened, glitch, doll-like skin, "
        "plastic texture, exaggerated wide-eyed overacting, heavy frown, jerky head movement, "
        "both brows raising at once"
    )
    if not text_ok:
        base += ", watermark, text overlay, subtitles"
    return base

SEG_PROMPTS = [
    # 0-2s 右眉单挑
    STYLE + CHARACTER + CAMERA +
    "0-2 seconds: she looks directly into the camera with relaxed neutral expression, then "
    "smoothly cocks only her RIGHT eyebrow up once — right brow lifts clean and single-sided, "
    "the left brow stays still. Her gaze is focused and a touch playful, the corner of her "
    "mouth twitches subtly up. A confident single-sided brow-raise challenge. Micro-expression "
    "only, no overacting. Avoid: " + seg_avoid(),
    # 2-4s 左眉单挑
    STYLE + CHARACTER + CAMERA +
    "2-4 seconds, continuing: she lowers the right brow back to neutral, then in the same "
    "playful style cocks only her LEFT eyebrow up once — left brow lifts clean and single-sided, "
    "right brow stays perfectly still. Eyes still pinned to the camera with a teasing sparkle, "
    "a faint sly smile. Single-sided brow-raise challenge. Micro-expression, restrained. Avoid: " + seg_avoid(),
    # 4-6s 左右交替
    STYLE + CHARACTER + CAMERA +
    "4-6 seconds, continuing: she does a quick alternating eyebrow challenge — right brow lifts, "
    "left brow lifts, right lifts again, quickly twitching each side in rhythm, both brows "
    "never rising together. A lively playful beat to the movement, slight amused smile, "
    "eyes sparkling at the camera. Micro-expression challenge, smooth not jerky. Avoid: " + seg_avoid(),
    # 6-8s 俏皮眨眼
    STYLE + CHARACTER + CAMERA +
    "6-8 seconds, continuing: the brows settle back to natural. She gives the camera one "
    "playful deliberate wink with her right eye while both brows lift a tiny encouraging "
    "degree, then returns to a calm confident look, lips curving in an assured smile. "
    "Self-possessed and a little coy. Micro-expression only. Avoid: " + seg_avoid(),
    # 8-10s 定格+字幕
    STYLE + CHARACTER + CAMERA +
    "8-10 seconds, continuing: she holds a final confident single-sided brow-raise on her "
    "right eyebrow, locking eyes straight into the camera with a poised slightly smug "
    "expression, face relaxed, brows held. Below the frame, bold clean white English text "
    "is overlaid reading 'DO YOU LIKE MY \'EYEBROW\'?'. Hold the pose and the text steady. "
    "Micro-expression, restrained. Avoid: " + seg_avoid(text_ok=True),
]

def post(path, payload):
    req = urllib.request.Request(f"{BASE}{path}", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode(errors='replace')[:800]}")
        raise

def wait_done(pid, timeout=3600, poll=20):
    print(f"  等待 pid={pid[:13]} ...", flush=True)
    t0 = time.time()
    while time.time() < t0 + timeout:
        try:
            h = json.loads(urllib.request.urlopen(f"{BASE}/history/{pid}", timeout=15).read())
            rec = h.get(pid)
            if rec:
                st = rec.get("status", {})
                if st.get("status_str") == "success" or st.get("completed") or rec.get("outputs"):
                    return True
                if st.get("status_str") == "error":
                    print("  执行出错:", json.dumps(st, ensure_ascii=False)[:500]); return False
        except Exception as e:
            print("  查询异常:", e)
        print(f"    ⏱ {int((time.time()-t0))//60}m{int(time.time()-t0)%60:02d}s", flush=True)
        time.sleep(poll)
    print("  超时"); return False

def build_segment(prompt, first_frame_img, seed, prefix, W, H, length, steps, shift_v):
    n = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors", "type": "minimax"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "4": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["1", 0], "shift_video": shift_v, "shift_audio": 3.5}},
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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--length", type=int, default=53, help="帧数；53≈2.2s")
    ap.add_argument("--steps", type=int, default=34)
    ap.add_argument("--shift_video", type=float, default=14.0)
    args = ap.parse_args()
    W, H = 544, 960
    segs = len(SEG_PROMPTS)
    seg_dur = args.length / 24.0
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)
    print(f"挑眉挑战：{segs}段 × ~{seg_dur:.2f}s（总时长≈{seg_dur*segs:.1f}s）")
    print(f"steps={args.steps}, shift_video={args.shift_video}, 首段纯文生视频, 后续段首帧=上段末帧")

    seg_files = {}
    for i in range(1, segs + 1):
        tag = f"eb_s{i:02d}"
        cands = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                        if f.startswith(tag) and f.endswith(".mp4")])
        if cands:
            seg_files[i] = cands[-1]; print(f"[{i}/{segs}] {tag} 已存在，跳过"); continue
        first_img = None
        if i > 1 and (i - 1) in seg_files:
            prev_tag = f"eb_s{i-1:02d}"
            last_png = extract_last_frame(seg_files[i-1], os.path.join(TMP_DIR, f"{prev_tag}_last.png"))
            first_img = os.path.relpath(last_png, INPUT_ROOT).replace("\\", "/")
        seed = 20260911 + i
        wf = build_segment(SEG_PROMPTS[i-1], first_img, seed, f"h3_eyebrow_seg/{tag}",
                           W, H, args.length, args.steps, args.shift_video)
        r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
        pid = r.get("prompt_id")
        print(f"[{i}/{segs}] {tag} pid={pid}（首帧={'上段末帧' if first_img else '无/文生视频'}）", flush=True)
        if not wait_done(pid):
            print(f"  {tag} 失败"); sys.exit(1)
        cands = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                        if f.startswith(tag) and f.endswith(".mp4")], key=os.path.getmtime)
        seg_files[i] = cands[-1]
        print(f"  ✓ {os.path.basename(cands[-1])}", flush=True)

    ordered = [seg_files[i] for i in sorted(seg_files)]
    out_name = os.path.join(OUT_DIR, "eyebrow_challenge_9x16_5seg.mp4")
    listfile = os.path.join(OUT_DIR, "concat_list.txt")
    with open(listfile, "w", encoding="utf-8") as f:
        for p in ordered:
            f.write(f"file '{p.replace(os.sep, '/')}'\n")
    r = subprocess.run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", listfile,
                        "-c", "copy", "-movflags", "+faststart", out_name],
                       capture_output=True, text=True)
    print("ffmpeg 退出码:", r.returncode)
    if os.path.exists(out_name):
        print(f"\n✅ 成片: {out_name} ({os.path.getsize(out_name)/1024/1024:.1f} MB)")

if __name__ == '__main__':
    main()