#!/usr/bin/env python3
"""网球裙扭腰卡点摇（校园风热舞）- H3 竖屏 9:16
3 段链式：胸前抚开+扭腰开场 → 连续扭臀摆臂+前行 → 双手合十致敬收尾
首帧：C02_PADDED（系列同一张脸）
"""
import json, urllib.request, uuid, time, os, sys, subprocess, argparse

BASE = "http://127.0.0.1:8188"
FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
FFPROBE = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffprobe.exe"
INPUT_ROOT = r"D:\ai_projects\ComfyUI\input"
OUT_DIR = r"D:\ai_projects\ComfyUI\output\2026-09-08\tennis_skirt_dance"
PREFIX = "2026-09-08/tennis_skirt_dance"
TMP_DIR = os.path.join(INPUT_ROOT, "tennis_skirt_frames")
REF_IMG = "gemini_ken1/C02_PADDED.png"

STYLE = (
    "realistic cinematic photography, ultra high detail, bright sunny daylight, vibrant "
    "colorful and fresh, medium saturation, shallow depth of field with blurred soft "
    "background, film grain, glossy healthy skin, clean composition."
)

CHARACTER = (
    "The same young East Asian woman as the reference image, same face and body, delicate "
    "youthful features, fresh light makeup emphasizing the eye area and rosy lips, "
    "porcelain-fair luminous skin, statuesque hourglass figure with nine-heads-tall "
    "proportion: long slender legs, cinched waist flowing into softly rounded hips, "
    "graceful neck and clear collarbones. "
    "Hair: deep-brown long hair tied up in a high ponytail, with a few soft face-framing "
    "strands. "
    "Outfit: a white short-sleeve polo shirt with thin black piping on the collar and "
    "cuffs, paired with a navy-blue pleated mini skirt, fresh vibrant campus-girl style, "
    "clean and sporty. "
)

CAMERA = (
    "Fixed camera, eye-level, medium shot with occasional cuts to close-up, person centered "
    "in frame with blurred background, camera mainly still while she moves, stepping and "
    "turning to fill the frame, hard cuts on beats."
)

MUSIC = (
    " High-energy driving electronic dance music with a strong beat and a repetitive "
    "English rap hook like 'sixteen sixteen all day', punchy bass, perfect for beat-synced "
    "bopping, no speech other than the song, pure instrumental vocal hook."
)

NEG = (
    "anime, cartoon, 3D render, illustration, distorted face, deformed hands, extra "
    "fingers, extra limbs, bad anatomy, melted limbs, blurry, watermark, text overlay, "
    "oversharpened, dull skin, jerky robotic movement"
)

SEG_PROMPTS = [
    # 段1 开场
    STYLE + CHARACTER + CAMERA +
    "A fresh vibrant campus girl starts a beat-synced waist-bopping dance: both hands "
    "lightly stroke her chest then spread open to both sides while she twists her waist, "
    "ponytail and navy pleated skirt swaying, confident smile, bright animated eyes. "
    "Sunny cheerful energy. " + MUSIC + " Avoid: " + NEG,
    # 段2 中段连续扭腰摆臀
    STYLE + CHARACTER + CAMERA +
    "Continuing the same woman, same high ponytail, white polo and navy pleated skirt: "
    "continuous rhythmic waist-twisting and hip pops synced tight to the beat, arms "
    "flowing in wave-like sweeps, hair casually flicked as she steps lightly forward, "
    "skirt fluttering, playful flirty-yet-vibrant smile, rhythmic and infectious. "
    + MUSIC + " Avoid: " + NEG,
    # 段3 结尾定格
    STYLE + CHARACTER + CAMERA +
    "Continuing the same woman, same look: she finishes the routine — hands clasp together "
    "in front of her chest, she gives a slight nod with a soft confident smile, holding "
    "the final beat-synced pose, ponytail settling, bright sunny energy, a neat bow-like "
    "ending to the dance." + MUSIC + " Avoid: " + NEG,
]

def post(path, payload):
    req = urllib.request.Request(f"{BASE}{path}", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        print("HTTP %d: %s" % (e.code, e.read().decode(errors='replace')[:800]))
        raise

def wait_done(pid, timeout=5400, poll=20):
    print("  等待 pid=%s ..." % pid[:13], flush=True)
    t0 = time.time()
    while time.time() < t0 + timeout:
        try:
            h = json.loads(urllib.request.urlopen("%s/history/%s" % (BASE, pid), timeout=15).read())
            rec = h.get(pid)
            if rec:
                st = rec.get("status", {})
                if st.get("status_str") == "success" or st.get("completed") or rec.get("outputs"):
                    return True
                if st.get("status_str") == "error":
                    print("  执行出错:", json.dumps(st, ensure_ascii=False)[:500]); return False
        except Exception:
            pass
        print("    ⏱ %dm%02ds" % (int(time.time()-t0)//60, int(time.time()-t0)%60), flush=True)
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
    ap.add_argument("--length", type=int, default=124)
    ap.add_argument("--steps", type=int, default=34)
    ap.add_argument("--shift_video", type=float, default=14.0)
    args = ap.parse_args()
    W, H = 544, 960
    segs = len(SEG_PROMPTS)
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)
    print("网球裙扭腰卡点摇：%d段 × %.2fs ≈ %.1fs total" % (segs, args.length/24, args.length/24*segs))
    print("steps=%d, shift_video=%s, REF=%s" % (args.steps, args.shift_video, REF_IMG))
    seg_files = {}
    for i in range(1, segs + 1):
        tag = "ts_s%02d" % i
        cands = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                        if f.startswith(tag) and f.endswith(".mp4")])
        if cands:
            seg_files[i] = cands[-1]; print("[%d/%d] %s exists, skip" % (i, segs, tag)); continue
        first_img = None
        if i == 1:
            first_img = REF_IMG
        elif (i - 1) in seg_files:
            first_img = os.path.relpath(extract_last_frame(seg_files[i-1], os.path.join(TMP_DIR, "ts_s%02d_last.png" % (i-1))), INPUT_ROOT).replace("\\", "/")
        seed = 20261045 + i
        wf = build_segment(SEG_PROMPTS[i-1], first_img, seed, "%s/%s" % (PREFIX, tag),
                           W, H, args.length, args.steps, args.shift_video)
        r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
        pid = r.get("prompt_id")
        print("[%d/%d] %s pid=%s（首帧=%s）" % (i, segs, tag, pid, first_img), flush=True)
        if not wait_done(pid):
            print("  %s failed" % tag); sys.exit(1)
        cands = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                        if f.startswith(tag) and f.endswith(".mp4")], key=os.path.getmtime)
        seg_files[i] = cands[-1]
        print("  ✓ %s" % os.path.basename(cands[-1]), flush=True)
    ordered = [seg_files[i] for i in sorted(seg_files)]
    out_name = os.path.join(OUT_DIR, "tennis_skirt_dance_9x16_3seg.mp4")
    listfile = os.path.join(OUT_DIR, "concat_list.txt")
    with open(listfile, "w", encoding="utf-8") as f:
        for p in ordered:
            f.write("file '%s'\n" % p.replace(os.sep, "/"))
    r = subprocess.run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", listfile,
                        "-c", "copy", "-movflags", "+faststart", out_name],
                       capture_output=True, text=True)
    print("ffmpeg exit:", r.returncode)
    if os.path.exists(out_name):
        print("\n✅ 成片: %s (%.1f MB)" % (out_name, os.path.getsize(out_name)/1024/1024))

if __name__ == '__main__':
    main()