#!/usr/bin/env python3
"""自信女生的活力街舞 — H3 竖屏 544×960 × 3 段链式（≈15.5s，含原生音频）

段1 起势律动 → 段2 手臂波浪+重心左右+碎步 → 段3 加速卡点+自信定格
首帧: gemini_ken1/C02_PADDED.png（沿用系列同一张脸）；后续段用上一段末帧链式。
音频: H3 原生生成的高能电子舞曲（鼓点密集、无人声），画面与音频同源卡点。

用法:
  python tools/h3_street_dance.py            # 全跑（断点续跑：已有段落自动跳过）
  python tools/h3_street_dance.py --segs 2   # 只跑前 2 段
"""
import argparse, json, os, subprocess, sys, time, urllib.request, urllib.error, uuid

BASE = "http://127.0.0.1:8188"
COMFY = r"D:\ai_projects\ComfyUI"
INPUT_ROOT = os.path.join(COMFY, "input")
OUT_DIR = os.path.join(COMFY, "output", "2026-09-12", "street_dance")
PREFIX = "2026-09-12/street_dance"
TMP_DIR = os.path.join(INPUT_ROOT, "street_dance_frames")
REF_IMG = "gemini_ken1/C02_PADDED.png"
W, H, LEN, STEPS, SHIFT_V, SHIFT_A = 544, 960, 124, 34, 14.0, 3.5
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(TMP_DIR, exist_ok=True)

NEG = ("Avoid: distorted face, deformed hands, extra fingers, extra limbs, bad anatomy, melted limbs, "
       "warped legs, blurry, watermark, text overlay, oversharpened, anime, cartoon, 3D render, "
       "wobbling background, changing outfit, changing face.")

STYLE = ("Style: realistic street-dance performance shot on a standard lens, medium shot at eye level, "
         "fixed camera, centered composition, bright and fresh color grading, medium saturation, "
         "clean crisp image, shallow depth of field, subtle film grain, realistic skin texture. ")

CHARACTER = ("Character: the same young East Asian woman as the reference image, identical face and body, "
             "delicate features, refined light makeup with defined eye area and natural nude-pink lips, "
             "fair luminous skin, black long hair pulled up into a neat high bun with a few soft strands "
             "loose at her temples, no jewelry, no accessories. ")

OUTFIT = ("Outfit: a fitted purple short-sleeve t-shirt with a slightly cropped hem and a gray high-waisted "
          "bodycon mini skirt that hugs her hips and ends at mid-thigh, the purple cotton fabric stretching "
          "with her movement, a slim defined waist, hot-girl casual street-dance styling, black ankle socks "
          "and white low-top sneakers. ")

SETTING = ("Setting: a bright clean indoor space with a plain light wall behind her and a smooth floor "
           "under her feet, soft even daylight from the front, no props, no other people, the background "
           "softly blurred so she stays the single visual focus. ")

CAMERA = ("Camera: fixed camera, eye level, medium shot on a standard lens, she stays centered in the frame "
          "with her whole body from the head down to the sneakers inside the frame, the camera does not move, "
          "no cuts except a hard cut at the start. ")

MOTION1 = ("Action: hip-hop freestyle groove. She starts on the beat with a light bounce in her knees, her "
           "shoulders loose, both hands rolling in a smooth wave in front of her chest, one hand after the "
           "other, her hips swinging gently in counter-rotation to her chest; then her arms open outward and "
           "her head nods slightly to the rhythm. She smiles the whole time and keeps her eyes locked on the "
           "camera with calm confidence. ")
MOTION2 = ("Action: the groove continues without a break and grows bigger — her right arm shoots forward and "
           "snaps back to her chest, her left arm sweeps out behind her, her weight bounces from one foot to "
           "the other with small quick steps in place, her torso twisting and dipping, the purple t-shirt and "
           "the gray skirt following the motion, her bun staying neat while loose strands swing. Her expression "
           "stays bright, smiling, chin up, eyes on the camera. ")
MOTION3 = ("Action: she pushes the tempo harder — both arms pump up and down in alternating waves above shoulder "
           "height, her body rocking front and back with quick footwork in place, hips circling once, then she "
           "lands the last beat with a confident finishing pose, feet apart, one hand on her hip, the other arm "
           "hanging loose, chest lifted, facing the camera with a big genuine smile. ")

MUSIC1 = ("Audio: high-energy electronic dance music, dense punchy drum pattern on a steady fast four-on-the-floor "
          "beat, driving bass line, bright synth stabs, purely instrumental with no vocals and no speech; the "
          "movement hits the beat. ")
MUSIC2 = ("Audio: the same energetic electronic dance track keeps rolling with a dense beat and bass groove, "
          "instrumental only, no vocals; her body stays locked to the drums. ")
MUSIC3 = ("Audio: the dance track drives to its peak with louder drums and a short snappy fill on the final beat, "
          "still instrumental, no vocals, then cuts off cleanly at the end. ")

SEG_PROMPTS = [
    STYLE + CHARACTER + OUTFIT + SETTING + CAMERA + MOTION1 + MUSIC1 + NEG,
    STYLE + CHARACTER + OUTFIT + SETTING + CAMERA + MOTION2 + MUSIC2 + NEG,
    STYLE + CHARACTER + OUTFIT + SETTING + CAMERA + MOTION3 + MUSIC3 + NEG,
]


def post(path, payload):
    req = urllib.request.Request(f"{BASE}{path}", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=60).read())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode(errors='replace')[:900]}")
        raise


def wait_done(pid, timeout=3600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(f"{BASE}/history/{pid}", timeout=30) as r:
                h = json.loads(r.read().decode()).get(pid)
        except Exception:
            h = None
        if h:
            st = h.get("status", {})
            if st.get("completed"):
                outs = []
                for o in h.get("outputs", {}).values():
                    outs += [f["filename"] for f in o.get("gifs", [])] + [f["filename"] for f in o.get("images", [])]
                return outs
            if st.get("status_str") == "error":
                print("  执行出错:", json.dumps([m for k, m in st.get("messages", []) if k == "execution_error"][:1],
                                              ensure_ascii=False)[:400], flush=True)
                return None
        el = int(time.time() - t0)
        if el % 120 < 20:
            print("   ⏱ %dm%02ds" % (el // 60, el % 60), flush=True)
        time.sleep(20)
    return None


def build(prompt, seed, prefix, first_frame=None):
    n = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors", "type": "minimax"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
        "5": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["1", 0], "shift_video": SHIFT_V, "shift_audio": SHIFT_A}},
        "6": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
            "clip": ["2", 0], "vae": ["3", 0], "prompt": prompt, "width": W, "height": H, "length": LEN}},
        "7": {"class_type": "KSampler", "inputs": {
            "model": ["5", 0], "seed": seed, "steps": STEPS, "cfg": 1.0, "sampler_name": "euler",
            "scheduler": "simple", "positive": ["6", 0], "negative": ["6", 0], "latent_image": ["6", 1], "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["7", 0], "vae": ["4", 0]}},
        "10": {"class_type": "SaveAudio", "inputs": {"audio": ["9", 0], "filename_prefix": prefix + "_aud"}},
        "11": {"class_type": "VHS_VideoCombine", "inputs": {
            "images": ["8", 0], "audio": ["9", 0], "frame_rate": 24.0, "loop_count": 0,
            "filename_prefix": prefix, "format": "video/h264-mp4", "pingpong": False, "save_output": True}},
    }
    if first_frame:
        n["12"] = {"class_type": "LoadImage", "inputs": {"image": first_frame}}
        n["6"]["inputs"]["first_frame"] = ["12", 0]
    return n


def extract_last_frame(mp4, out_png):
    subprocess.run(["ffmpeg", "-y", "-sseof", "-0.3", "-i", mp4.replace("\\", "/"),
                    "-q:v", "2", "-frames:v", "1", "-pix_fmt", "yuvj420p", "-strict", "unofficial",
                    out_png.replace("\\", "/")], check=True, capture_output=True)
    return out_png


def segs_with_audio():
    """VHS 直混输出: <tag>_0000N.mp4（纯视频）与 <tag>_0000N-audio.mp4（含音频）"""
    return sorted([f for f in os.listdir(OUT_DIR) if f.endswith("-audio.mp4")])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segs", type=int, default=len(SEG_PROMPTS))
    a = ap.parse_args()
    n = min(a.segs, len(SEG_PROMPTS))
    print("街舞 %d 段 × %.2fs ≈ %.1fs | %dx%d steps=%d shift=%.1f:%.1f | REF=%s"
          % (n, LEN / 24, LEN / 24 * n, W, H, STEPS, SHIFT_V, SHIFT_A, REF_IMG), flush=True)
    seg_file = {}
    for i in range(1, n + 1):
        tag = "sd_s%02d" % i
        cands = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                        if f.startswith(tag) and f.endswith(".mp4") and "audio" not in f], key=os.path.getmtime)
        if cands:
            seg_file[i] = cands[-1]
            print("[%d/%d] %s 已存在，跳过" % (i, n, tag), flush=True)
            continue
        first = REF_IMG
        if i > 1:
            if (i - 1) not in seg_file:
                print("缺上一段，无法链式"); sys.exit(1)
            png = extract_last_frame(seg_file[i - 1], os.path.join(TMP_DIR, "sd_s%02d_last.png" % (i - 1)))
            first = os.path.relpath(png, INPUT_ROOT).replace("\\", "/")
        wf = build(SEG_PROMPTS[i - 1], 20261200 + i, "%s/%s" % (PREFIX, tag), first)
        r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
        pid = r.get("prompt_id")
        print("[%d/%d] %s pid=%s 首帧=%s" % (i, n, tag, pid, first), flush=True)
        if not wait_done(pid):
            print("  %s 失败" % tag); sys.exit(1)
        cands = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                        if f.startswith(tag) and f.endswith(".mp4") and "audio" not in f], key=os.path.getmtime)
        seg_file[i] = cands[-1]
        print("  ✓ %s" % os.path.basename(cands[-1]), flush=True)

    # ---- 拼接:优先用 -audio.mp4 版（保音轨） ----
    def audio_of(p):
        ap_ = os.path.join(os.path.dirname(p), os.path.basename(p).replace(".mp4", "-audio.mp4"))
        return ap_ if os.path.exists(ap_) else p
    ordered = [audio_of(seg_file[i]) for i in sorted(seg_file)]
    listfile = os.path.join(OUT_DIR, "concat_list.txt")
    with open(listfile, "w", encoding="utf-8") as f:
        for p in ordered:
            f.write("file '%s'\n" % p.replace(os.sep, "/"))
    out = os.path.join(OUT_DIR, "街舞活力_自信女生_%dseg.mp4" % len(ordered))
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile.replace("\\", "/"),
                    "-c", "copy", "-movflags", "+faststart", out.replace("\\", "/")], check=True, capture_output=True)
    print("✅ 成片:", out, "(%.1f MB)" % (os.path.getsize(out) / 1024 / 1024), flush=True)
    pr = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration:stream=codec_type,codec_name,sample_rate,channels",
                         "-of", "json", out.replace("\\", "/")], capture_output=True, encoding="utf-8")
    print(pr.stdout, flush=True)
    for t in (0.5, 4.0, 9.0, 14.0):
        fr = os.path.join(OUT_DIR, "frame_%ss.jpg" % t)
        subprocess.run(["ffmpeg", "-y", "-ss", str(t), "-i", out.replace("\\", "/"), "-frames:v", "1", "-q:v", "3",
                        "-pix_fmt", "yuvj420p", "-strict", "unofficial", fr.replace("\\", "/")], capture_output=True)
    print("STREET-DANCE-DONE", flush=True)


if __name__ == "__main__":
    main()
