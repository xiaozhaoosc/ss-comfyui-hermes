#!/usr/bin/env python3
"""《妖精的尾巴》艾露莎 Cosplay 变身 + 女团律动舞蹈 - H3 竖屏 9:16
2 段链式：SEG1 日常少女→魔法闪光变身→艾露莎战斗服；SEG2 艾露莎随 Cry Cry 节拍女团舞
首帧：C02_PADDED（cosplayer 本体脸部，变身前后同一张脸）
"""
import json, urllib.request, uuid, time, os, sys, subprocess, argparse

BASE = "http://127.0.0.1:8188"
FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
FFPROBE = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffprobe.exe"
INPUT_ROOT = r"D:\ai_projects\ComfyUI\input"
OUT_DIR = r"D:\ai_projects\ComfyUI\output\erza_cosplay"
TMP_DIR = os.path.join(INPUT_ROOT, "erza_frames")
REF_IMG = "gemini_ken1/C02_PADDED.png"

STYLE = (
    "realistic cinematic photography, ultra high detail, bright clear lighting, medium "
    "saturation, shallow depth of field, film grain, glossy healthy skin, centered "
    "composition, fixed camera, eye-level, medium-to-close shot showing full body and "
    "facial expression."
)

CHARACTER_BEFORE = (
    "The same young East Asian woman as the reference image (a cosplayer), same face "
    "and body, delicate features, light sweet clean-girl makeup. Brown long straight "
    "hair flowing down, wearing black thin-frame glasses. Casual outfit: a deep-blue "
    "spaghetti-strap halter top with denim shorts. Casual, everyday look."
)

ERZA_AFTER = (
    "She now wears the battle outfit of Erza Scarlet from 'Fairy Tail', an anime "
    "cosplay: vivid red high ponytail with a small blue hair-tie accent, white "
    "strapless bustier crop top, wine-red shorts with white binding straps around the "
    "waist, and blue magic-circle tattoos/patterns on her arms. Confident, spirited "
    "and heroic vibe, refined and dimensional makeup."
)

CAMERA = (
    "Fixed camera, eye-level, centered composition, person in the middle of the frame, "
    "no push-pull-pan-tilt, single continuous unbroken shot, no transitions except an "
    "in-scene magic flash."
)

AUDIO = (
    " Energetic K-pop girl-group dance track with a driving beat and a rhythmic "
    "'ching ching ching ching cry cry' hook, punchy bass, no vocals speech except the "
    "song; music only."
)

NEG = (
    "anime, cartoon, 3D render, illustration, distorted face, deformed hands, extra "
    "fingers, extra limbs, bad anatomy, melted limbs, blurry, watermark, text overlay, "
    "oversharpened, dull skin, jerky movement"
)

SEG1 = (
    STYLE + CHARACTER_BEFORE + CAMERA +
    "0-3 seconds: the girl stands centered facing the camera, calm and sweet with "
    "brown straight hair and glasses, then she claps her hands together in a magic "
    "hand-seal gesture in front of her chest and mouths a spell, a swirl of glowing "
    "magic light and sparkles rises around her, a brilliant flash bursts — and in one "
    "transformation moment she becomes " + ERZA_AFTER +
    " the flash settles and she stands in Erza's battle outfit, now with red ponytail. "
    "Seamless magical transformation. " + AUDIO + " Avoid: " + NEG
)
SEG2 = (
    STYLE + ERZA_AFTER + CAMERA +
    "3-11 seconds, continuing after the transformation: as Erza Scarlet she moves to "
    "the beat with a light lively girl-group rhythm dance for about 8 seconds — "
    "confident hip sway, sharp arm pops, side stepping and confident runway moves and "
    "poses synced to the 'ching ching ching ching cry cry' hook, bright smile, "
    "spirited heroic and dazzling, dynamic but smooth and lively, ending on a bold "
    "confident final pose holding the magic-seal hand gesture. "
    + AUDIO + " Avoid: " + NEG
)

SEG_PROMPTS = [SEG1, SEG2]

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
    ap.add_argument("--len1", type=int, default=72)   # SEG1 变身 ~3s
    ap.add_argument("--len2", type=int, default=192)  # SEG2 舞蹈 ~8s
    ap.add_argument("--steps", type=int, default=34)
    ap.add_argument("--shift_video", type=float, default=14.0)
    args = ap.parse_args()
    W, H = 544, 960
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)
    print("艾露莎Cosplay变身：2段（变身 %dfram  +  舞蹈 %dfram）共约 %.1fs" % (
        args.len1, args.len2, (args.len1 + args.len2) / 24))
    print("steps=%d, shift_video=%s, REF=%s" % (args.steps, args.shift_video, REF_IMG))

    lengths = [args.len1, args.len2]
    seg_files = {}
    for i in (1, 2):
        tag = "erza_s%02d" % i
        cands = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                        if f.startswith(tag) and f.endswith(".mp4")])
        if cands:
            seg_files[i] = cands[-1]; print("[%d/2] %s exists, skip" % (i, tag)); continue
        first_img = None
        if i == 1:
            first_img = REF_IMG
        elif (i - 1) in seg_files:
            first_img = os.path.relpath(extract_last_frame(seg_files[i-1], os.path.join(TMP_DIR, "erza_s%02d_last.png" % (i-1))), INPUT_ROOT).replace("\\", "/")
        seed = 20261016 + i
        wf = build_segment(SEG_PROMPTS[i-1], first_img, seed, "erza_cosplay/%s" % tag,
                           W, H, lengths[i-1], args.steps, args.shift_video)
        r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
        pid = r.get("prompt_id")
        print("[%d/2] %s pid=%s（首帧=%s）" % (i, tag, pid, first_img), flush=True)
        if not wait_done(pid):
            print("  %s failed" % tag); sys.exit(1)
        cands = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                        if f.startswith(tag) and f.endswith(".mp4")], key=os.path.getmtime)
        seg_files[i] = cands[-1]
        print("  ✓ %s" % os.path.basename(cands[-1]), flush=True)

    ordered = [seg_files[i] for i in sorted(seg_files)]
    out_name = os.path.join(OUT_DIR, "erza_cosplay_9x16_2seg.mp4")
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