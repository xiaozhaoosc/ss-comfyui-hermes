#!/usr/bin/env python3
"""(自动生成) 云霄·古风手势舞 — H3 4 段生成流水线
由 tools/h3_prompt_gen.py 生成，可直接改 PROMPTS 或重新生成。
用法: python tools/h3_gen_yunxiao_gesture.py [--segs N]
"""
import argparse, json, os, subprocess, sys, time, urllib.request, urllib.error, uuid

BASE = "http://127.0.0.1:8188"
COMFY = r"D:\ai_projects\ComfyUI"
INPUT_ROOT = os.path.join(COMFY, "input")
OUT_DIR = os.path.join(COMFY, "output", "2026-09-12/yunxiao_gesture")
PREFIX = "2026-09-12/yunxiao_gesture"
TMP_DIR = os.path.join(INPUT_ROOT, "yunxiao_gesture_frames")
W, H = 544, 960
FRAMES = [90, 90, 90, 90]
STEPS, SHIFT_V, SHIFT_A = 34, 14.0, 3.5
SEED_BASE = 20261300
REF_IMG = None
NAME = 'yunxiao_gesture'
NEG = "Avoid: " + ('outfit change, face change' or "") + " distorted face, deformed hands, extra fingers, extra limbs, bad anatomy, melted limbs, blurry, watermark, text overlay, oversharpened, plastic skin, outfit change, face change."
COMMON = 'Style: photorealistic live-action cosplay cinematography, real human actress, ultra high detail, cinematic night lighting with a violet-blue color grade, mystical and dreamy fairy atmosphere, realistic skin texture, realistic hair strands, realistic silk and gauze fabric physics, shallow depth of field, subtle film grain. Character: a young East Asian woman in her early twenties, delicate oval face, fair luminous skin, long straight violet-purple hair reaching her waist with wispy air bangs and softly curled ends, elegant ancient-Chinese makeup with slender thin brows, violet eyeshadow, long lashes and matte red lips, a gorgeous black hair crown with sharp spike ornaments on top of her head, a slim collarbone necklace, a black wrist guard on her left wrist. Costume: a pale lavender deep-V cross-collar hanfu with silk sleeves, a matching sheer gauze shawl draped over her arms, a wide black belt decorated with golden patterns cinching her waist, and a slit skirt that reveals her leg when she moves. Setting: night in an ancient Chinese garden, deep blue-violet night sky, faint mist drifting close to the ground, distant silhouetted trees, soft moonlight rimming her hair and shoulders, a quiet exotic and romantic atmosphere. '
SEG = [
 {
  "camera": "Camera: fixed camera, eye level, medium shot framing her upper body and part of her legs, centered composition with her in the middle of the frame, no camera movement, no pull or push, no cuts, the whole take is continuous. ",
  "motion": "Action: she presses both palms together in front of her chest, then slowly separates her hands and lifts them upward until her fingertips point toward each other above her head, sleeves sliding down her forearms, her body swaying softly to the rhythm. ",
  "audio": "Audio: a light catchy Chinese female pop song, a young woman singing in Mandarin the hook line \"亲爱的，你是否还记得\", soft airy voice over an easy mid-tempo pop beat with plucked strings and light electronic percussion, romantic and sweet, no other voices. ",
  "micro": "She smiles gently and keeps her gaze lively and sweet, chin slightly lifted, eyes on the camera."
 },
 {
  "camera": "Camera: fixed camera, eye level, medium shot framing her upper body and part of her legs, centered composition, no camera movement and no cuts. ",
  "motion": "Action: her hands roll in a smooth wave in front of her chest, wrists loose, then her right hand sweeps outward to the side while her left hand comes up to support her chin, her head tilting slightly. ",
  "audio": "Audio: the same female Mandarin pop song continues smoothly, her vocal melody riding the light beat, guzheng and synth accents behind it, sweet and dreamy, no other speech. ",
  "micro": "Her eyes stay bright and a little flirtatious, a small smile on her lips, a quick soft blink as she tilts her head."
 },
 {
  "camera": "Camera: fixed camera, eye level, medium shot framing her upper body and part of her legs, centered composition, no camera movement and no cuts. ",
  "motion": "Action: both hands cross in front of her chest, then open outward to the two sides with palms facing out, the gauze shawl spreading with the movement, her waist twisting gently. ",
  "audio": "Audio: the song keeps its gentle groove, the female vocal carrying the chorus, soft percussion and strings, warm and romantic night mood, no other speech. ",
  "micro": "Her expression stays confident and charming with a soft smile, chin level, eyes holding the camera."
 },
 {
  "camera": "Camera: fixed camera, eye level, medium shot framing her upper body and part of her legs, centered composition, no camera movement and no cuts. ",
  "motion": "Action: her hands draw back toward her chest with fingers curled like soft claws, then close into loose fists that rise up to the sides of her cheeks while she twists her upper body slightly to the beat. ",
  "audio": "Audio: the same female Mandarin pop song reaches its final sweet phrase and ends on a soft sustained note with the beat tapering out, no other speech. ",
  "micro": "Her eyes sparkle, ending with a sweet bright smile facing the camera, chin tucked a little, mouth corners lifted."
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
