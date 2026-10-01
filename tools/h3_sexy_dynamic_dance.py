#!/usr/bin/env python3
"""真人写实动感舞蹈 - H3 分段衔接（卡通版改写为写实版）

原始提示词来自 3D 卡通版本，用户决定将风格改为真人写实 + 适合建模
造型：浅蓝色短袖衬衫下摆打结 + 同色系紧身包臀短裙 + 肉色丝袜
发型：棕色短卷发 + 头顶小丸子头
动作：扭胯、摆臂、女团热舞
镜头：固定机位中近景（平视，聚焦全身/上半身）
"""
import json, urllib.request, uuid, time, os, sys, subprocess, math, argparse

BASE = "http://127.0.0.1:8188"
FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
FFPROBE = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffprobe.exe"
INPUT_ROOT = r"D:\ai_projects\ComfyUI\input"
OUT_DIR = r"D:\ai_projects\ComfyUI\output\sexy_dynamic_dance"
TMP_DIR = os.path.join(INPUT_ROOT, "sexy_dance_frames")
REF_IMG = "gemini_ken1/C02_PADDED.png"

STYLE = (
    "realistic cinematic photography, ultra high detail, professional studio lighting, "
    "shallow depth of field, film grain, glossy healthy skin, clean composition. "
)

CHARACTER = (
    "The same young East Asian woman as the reference image, same face and body, "
    "delicate elegant features, porcelain-fair luminous skin. She has a statuesque "
    "hourglass figure with nine-heads-tall proportion: long slender straight legs, "
    "cinched waist flowing into softly rounded hips, graceful swan-like neck, clear "
    "collarbones, poised upright upper body. "
    "Outfit: a light blue short-sleeve button-up shirt tied in a knot at the waist "
    "exposing her toned abdomen, paired with a matching light blue form-fitting mini "
    "skirt that hugs her hips, and flesh-toned sheer pantyhose. No shoes visible in "
    "frame or simple flats. "
    "Hair: brown short wavy-bob with a small cute bun on top of the head. "
    "No jewelry. Confident youthful energy with a touch of sexiness, bright sparkling "
    "eyes, lively expression."
)

CAMERA = "Fixed camera, eye-level, medium shot with upper body focus, stable framing. "

MUSIC = (
    " High-energy electronic dance music, strong rhythmic synth drums and punchy bass, "
    "pure instrumental EDM, fast tempo, perfect for girl-group style dancing."
)

NEG = (
    "anime, cartoon, 3D render, Pixar style, illustration, distorted face, deformed "
    "hands, extra fingers, extra limbs, bad anatomy, melted limbs, blurry, watermark, "
    "text overlay, oversharpened, dull skin"
)

SEG_PROMPTS = [
    # 段1：扭胯热身 + 摆臂 + 踏步
    STYLE + CHARACTER + CAMERA +
    "She starts a dynamic girl-group style dance routine: hips swaying side to side in "
    "syncopated rhythm, arms sweeping outward and back in smooth rolling motions, "
    "small precise side-steps, shoulders grooving to the beat, the tied shirt hem "
    "bouncing with her hip movements, brown wavy bob bouncing, the small bun on her "
    "head bobbing playfully. Confident flirty smile, eyes bright and engaging, "
    "totally in control of the choreography." + MUSIC + " Avoid: " + NEG,
    # 段2：手臂波浪 + 扭腰 + 转身小碎步
    STYLE + CHARACTER + CAMERA +
    "Continuing the same woman, same face, same light blue tied shirt and matching "
    "mini skirt, same brown bob with bun: she flows through an arm wave starting "
    "from her right shoulder rolling down through her chest and out the left arm, "
    "then pivots on the spot with a quick shimmy of her hips, waist twisting fluidly, "
    "hands tracing the curve of her waist, pantyhose shimmering under the studio "
    "lights. Her smile grows bolder, a flash of pink on her cheeks, expression "
    "magnetic and confident." + MUSIC + " Avoid: " + NEG,
    # 段3：扭胯高潮 + 定格 pose
    STYLE + CHARACTER + CAMERA +
    "Continuing the same woman, same face, same light blue tied shirt and matching "
    "mini skirt, same brown bob with bun: the climax — a sequence of sharp hip pops "
    "left-right-left in perfect beat-sync, arms thrown up in a V then swept down to "
    "her hips, torso undulating through a body wave, then a sudden freeze: weight on "
    "one leg, the other leg extended forward slightly with heel up, one hand on "
    "her hip, the other arm extended pointing at the camera, head tilted with a "
    "triumphant dazzling smile, chest proudly raised, the tied shirt accentuating "
    "her curves." + MUSIC + " Avoid: " + NEG,
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
    ap.add_argument("--steps", type=int, default=34)
    ap.add_argument("--shift_video", type=float, default=14.0)
    ap.add_argument("--shift_audio", type=float, default=3.5)
    args = ap.parse_args()
    W, H = 544, 960
    segs = len(SEG_PROMPTS)
    seg_dur = args.seg_len / 24.0
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)
    print(f"真人动感舞蹈：{segs}段 × {seg_dur:.2f}s (steps={args.steps}, shift={args.shift_video}/{args.shift_audio})")
    print(f"首帧:{REF_IMG} 输出:{OUT_DIR}")
    seg_files = {}
    for i in range(1, segs + 1):
        tag = f"sexy_s{i:02d}"
        cands = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                        if f.startswith(tag) and f.endswith(".mp4")])
        if cands:
            seg_files[i] = cands[-1]; print(f"[{i}/{segs}] {tag} 已存在，跳过"); continue
        first_img = None
        if i > 1 and i-1 in seg_files:
            prev_tag = f"sexy_s{i-1:02d}"
            last_png = extract_last_frame(seg_files[i-1], os.path.join(TMP_DIR, f"{prev_tag}_last.png"))
            first_img = os.path.relpath(last_png, INPUT_ROOT).replace("\\", "/")
        seed = 20261120 + i
        wf = build_segment(SEG_PROMPTS[i-1], first_img, seed, f"sexy_dynamic_dance/{tag}",
                           W, H, args.seg_len, REF_IMG,
                           steps=args.steps, shift_video=args.shift_video, shift_audio=args.shift_audio)
        r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
        pid = r.get("prompt_id")
        print(f"[{i}/{segs}] {tag} pid={pid}（首帧={'末帧' if first_img else 'C02'}）", flush=True)
        if not wait_done(pid):
            print("  段失败，中止"); sys.exit(1)
        cands = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                        if f.startswith(tag) and f.endswith(".mp4")], key=os.path.getmtime)
        seg_files[i] = cands[-1]
        print(f"  ✓ {os.path.basename(cands[-1])}", flush=True)
    ordered = [seg_files[i] for i in sorted(seg_files)]
    out_name = os.path.join(OUT_DIR, "sexy_dynamic_dance_9x16_3seg_260906.mp4")
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
