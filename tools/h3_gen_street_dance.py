#!/usr/bin/env python3
"""(自动生成) 自信女生的活力街舞 — H3 3 段生成流水线
由 tools/h3_prompt_gen.py 生成，可直接改 PROMPTS 或重新生成。
用法: python tools/h3_gen_street_dance.py [--segs N]
"""
import argparse, json, os, subprocess, sys, time, urllib.request, urllib.error, uuid

BASE = "http://127.0.0.1:8188"
COMFY = r"D:\ai_projects\ComfyUI"
INPUT_ROOT = os.path.join(COMFY, "input")
OUT_DIR = os.path.join(COMFY, "output", "2026-09-12/street_dance")
PREFIX = "2026-09-12/street_dance"
TMP_DIR = os.path.join(INPUT_ROOT, "street_dance_frames")
W, H = 544, 960
FRAMES = [124, 124, 124]
STEPS, SHIFT_V, SHIFT_A = 34, 14.0, 3.5
SEED_BASE = 20261200
REF_IMG = 'gemini_ken1/C02_PADDED.png'
NAME = 'street_dance'
NEG = "Avoid: " + ('changing outfit, changing face, wobbling background' or "") + " distorted face, deformed hands, extra fingers, extra limbs, bad anatomy, melted limbs, blurry, watermark, text overlay, oversharpened, plastic skin, outfit change, face change."
COMMON = 'Style: realistic street-dance performance shot on a standard lens, medium shot at eye level, fixed camera, centered composition, bright and fresh color grading, medium saturation, clean crisp image, shallow depth of field, subtle film grain, realistic skin texture. Character: the same young East Asian woman as the reference image, identical face and body, delicate features, refined light makeup with defined eye area and natural nude-pink lips, fair luminous skin, black long hair pulled up into a neat high bun with a few soft strands loose at her temples, no jewelry, no accessories. Outfit: a fitted purple short-sleeve t-shirt with a slightly cropped hem and a gray high-waisted bodycon mini skirt that hugs her hips and ends at mid-thigh, the purple cotton fabric stretching with her movement, a slim defined waist, hot-girl casual street-dance styling, black ankle socks and white low-top sneakers. Setting: a bright clean indoor space with a plain light wall behind her and a smooth floor under her feet, soft even daylight from the front, no props, no other people, the background softly blurred so she stays the single visual focus. '
SEG = [
 {
  "camera": "Camera: fixed camera, eye level, medium shot on a standard lens, she stays centered in the frame with her whole body from the head down to the sneakers inside the frame, the camera does not move, no cuts except a hard cut at the start. ",
  "motion": "Action: hip-hop freestyle groove. She starts on the beat with a light bounce in her knees, her shoulders loose, both hands rolling in a smooth wave in front of her chest, one hand after the other, her hips swinging gently in counter-rotation to her chest; then her arms open outward and her head nods slightly to the rhythm. ",
  "audio": "Audio: high-energy electronic dance music, dense punchy drum pattern on a steady fast four-on-the-floor beat, driving bass line, bright synth stabs, purely instrumental with no vocals and no speech; the movement hits the beat. ",
  "micro": "She smiles the whole time and keeps her eyes locked on the camera with calm confidence, chin relaxed, the corners of her mouth lifted."
 },
 {
  "camera": "Camera: fixed camera, eye level, medium shot on a standard lens, she stays centered in the frame with her whole body inside the frame, the camera does not move and there are no cuts. ",
  "motion": "Action: the groove continues without a break and grows bigger — her right arm shoots forward and snaps back to her chest, her left arm sweeps out behind her, her weight bounces from one foot to the other with small quick steps in place, her torso twisting and dipping, the purple t-shirt and the gray skirt following the motion, her bun staying neat while loose strands swing. ",
  "audio": "Audio: the same energetic electronic dance track keeps rolling with a dense beat and bass groove, instrumental only, no vocals; her body stays locked to the drums. ",
  "micro": "Her expression stays bright, smiling, chin up, eyes on the camera, a quick blink on the accent beat."
 },
 {
  "camera": "Camera: fixed camera, eye level, medium shot on a standard lens, centered composition, the camera does not move and there are no cuts. ",
  "motion": "Action: she pushes the tempo harder — both arms pump up and down in alternating waves above shoulder height, her body rocking front and back with quick footwork in place, hips circling once, then she lands the last beat with a confident finishing pose, feet apart, one hand on her hip, the other arm hanging loose, chest lifted. ",
  "audio": "Audio: the dance track drives to its peak with louder drums and a short snappy fill on the final beat, still instrumental, no vocals, then cuts off cleanly at the end. ",
  "micro": "She finishes facing the camera with a big genuine smile, eyes crinkling slightly, chin lifted with quiet pride."
 }
]
PROMPTS = [COMMON + s["camera"] + s["motion"] + ((s.get("micro") or "").rstrip() + " " if s.get("micro") else "") + s["audio"] + NEG for s in SEG]



def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=60).read())
    except urllib.error.HTTPError as e:
        print("HTTP %d: %s" % (e.code, e.read().decode(errors="replace")[:800])); raise


def wait_done(pid, timeout=3600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(BASE + "/history/" + pid, timeout=30) as r:
                h = json.loads(r.read().decode()).get(pid)
        except Exception:
            h = None
        if h:
            st = h.get("status", {})
            if st.get("completed"):
                return True
            if st.get("status_str") == "error":
                print("  出错:", json.dumps([m for k, m in st.get("messages", []) if k == "execution_error"][:1], ensure_ascii=False)[:300])
                return False
        el = int(time.time() - t0)
        if el % 120 < 20:
            print("   ⏱ %dm%02ds" % (el // 60, el % 60), flush=True)
        time.sleep(20)
    return False


def build(prompt, seed, prefix, first_frame=None, last_frame=None):
    n = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors", "type": "minimax"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
        "5": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["1", 0], "shift_video": SHIFT_V, "shift_audio": SHIFT_A}},
        "6": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {"clip": ["2", 0], "vae": ["3", 0], "prompt": prompt, "width": W, "height": H, "length": LEN}},
        "7": {"class_type": "KSampler", "inputs": {"model": ["5", 0], "seed": seed, "steps": STEPS, "cfg": 1.0, "sampler_name": "euler",
                                                    "scheduler": "simple", "positive": ["6", 0], "negative": ["6", 0], "latent_image": ["6", 1], "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["7", 0], "vae": ["4", 0]}},
        "10": {"class_type": "SaveAudio", "inputs": {"audio": ["9", 0], "filename_prefix": prefix + "_aud"}},
        "11": {"class_type": "VHS_VideoCombine", "inputs": {"images": ["8", 0], "audio": ["9", 0], "frame_rate": 24.0, "loop_count": 0,
                                                            "filename_prefix": prefix, "format": "video/h264-mp4", "pingpong": False, "save_output": True}},
        "13": {"class_type": "LoadImage", "inputs": {"image": first_frame or REF_IMG or "gemini_ken1/C02_PADDED.png"}},
    }
    if first_frame or REF_IMG:
        n["6"]["inputs"]["first_frame"] = ["13", 0]
    if last_frame:
        n["14"] = {"class_type": "LoadImage", "inputs": {"image": last_frame}}
        n["6"]["inputs"]["last_frame"] = ["14", 0]
    return n


def extract_last(mp4, png):
    subprocess.run(["ffmpeg", "-y", "-sseof", "-0.3", "-i", mp4.replace("\\", "/"), "-q:v", "2", "-frames:v", "1",
                    "-pix_fmt", "yuvj420p", "-strict", "unofficial", png.replace("\\", "/")], check=True, capture_output=True)
    return png


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--segs", type=int, default=len(PROMPTS)); a = ap.parse_args()
    n = min(a.segs, len(PROMPTS))
    os.makedirs(OUT_DIR, exist_ok=True); os.makedirs(TMP_DIR, exist_ok=True)
    print("%s: %d 段 | %dx%d | frames=%s | steps=%d shift=%s:%s" % (PREFIX, n, W, H, FRAMES, STEPS, SHIFT_V, SHIFT_A), flush=True)
    segf = {}
    for i in range(1, n + 1):
        tag = "%s_s%02d" % i
        c = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR) if f.startswith(tag) and f.endswith(".mp4") and "audio" not in f], key=os.path.getmtime)
        if c:
            segf[i] = c[-1]; print("[%d/%d] %s 已存在,跳过" % (i, n, tag), flush=True); continue
        LEN = FRAMES[i - 1] if isinstance(FRAMES, list) else FRAMES
        first = REF_IMG if i == 1 else os.path.relpath(extract_last(segf[i - 1], os.path.join(TMP_DIR, "%s_s%02d_last.png" % (i - 1))), INPUT_ROOT).replace("\\", "/")
        r = post("/prompt", {"prompt": build(PROMPTS[i - 1], SEED_BASE + i, PREFIX + "/" + tag, first), "client_id": str(uuid.uuid4())})
        pid = r.get("prompt_id"); print("[%d/%d] %s pid=%s" % (i, n, tag, pid), flush=True)
        if not wait_done(pid):
            print("  失败"); sys.exit(1)
        c = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR) if f.startswith(tag) and f.endswith(".mp4") and "audio" not in f], key=os.path.getmtime)
        segf[i] = c[-1]; print("  ✓ %s" % os.path.basename(c[-1]), flush=True)
    ordered = [os.path.join(os.path.dirname(segf[i]), os.path.basename(segf[i]).replace(".mp4", "-audio.mp4")) if os.path.exists(os.path.join(os.path.dirname(segf[i]), os.path.basename(segf[i]).replace(".mp4", "-audio.mp4"))) else segf[i] for i in sorted(segf)]
    lf = os.path.join(OUT_DIR, "concat_list.txt")
    open(lf, "w", encoding="utf-8").write("".join("file '%s'\n" % p.replace(os.sep, "/") for p in ordered))
    out = os.path.join(OUT_DIR, "%s_%dseg.mp4" % (NAME, len(ordered)))
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lf.replace("\\", "/"), "-c", "copy", "-movflags", "+faststart", out.replace("\\", "/")], check=True, capture_output=True)
    print("✅ 成片:", out, flush=True)
    print("H3-GEN-DONE", flush=True)
