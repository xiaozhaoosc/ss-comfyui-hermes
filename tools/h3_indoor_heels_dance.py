#!/usr/bin/env python3
"""室内性感慢摇舞蹈（Heels/Urban 慵懒都市风）- H3 竖屏 9:16
3 段链式：撩拨开场 → 扭腰摆臂中段 → 慢摇高潮定格
首帧：C02_PADDED（系列同一张脸）；咖啡馆/客厅沙发+落地灯背景
"""
import json, urllib.request, uuid, time, os, sys, subprocess, argparse

BASE = "http://127.0.0.1:8188"
FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
FFPROBE = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffprobe.exe"
INPUT_ROOT = r"D:\ai_projects\ComfyUI\input"
OUT_DIR = r"D:\ai_projects\ComfyUI\output\indoor_heels_dance"
TMP_DIR = os.path.join(INPUT_ROOT, "indoor_heels_frames")
REF_IMG = "gemini_ken1/C02_PADDED.png"

STYLE = (
    "realistic cinematic photography, ultra high detail, professional studio mood lighting, "
    "soft warm indoor glow, high contrast, shallow depth of field, film grain, glossy healthy "
    "skin, cinematic color grade."
)

CHARACTER = (
    "The same young East Asian woman as the reference image, same face and body, delicate "
    "elegant features, porcelain-fair luminous skin, statuesque hourglass figure with "
    "nine-heads-tall proportion: long slender legs, cinched waist flowing into softly rounded "
    "hips, graceful neck and clear collarbones, poised upright upper body. "
    "Hair: deep-brown long loose wavy curls naturally draped over her shoulders, alluring and "
    "elegant. Makeup: refined bold makeup — crisp eyeliner, full red lips, dimensional contour. "
    "Outfit: a form-fitting black spaghetti-strap lace slip dress with subtle floral-dot "
    "details and wavy lace trim, hugging and seductive. Black high heels with black sheer thin "
    "stockings that elongate her legs. A slim silver metal bracelet on her left wrist. "
)

CAMERA = (
    "Fixed camera, eye-level, medium shot with occasional moments to full body and face, "
    "rule-of-thirds composition with her centered slightly right of frame, a sofa and floor "
    "lamp creating rich background layers, single continuous unbroken shot."
)

MUSIC = (
    " Upbeat driving Japanese EDM with a bright synth melody and a seductive laid-back vibe, "
    "with a clear Japanese female vocal line 'watashi ga misete ageru kiss' ('I'll show you a "
    "kiss') interspersed; punchy beat, teasing atmosphere."
)

NEG = (
    "anime, cartoon, 3D render, illustration, distorted face, deformed hands, extra fingers, "
    "extra limbs, bad anatomy, melted limbs, blurry, watermark, text overlay, oversharpened, "
    "dull skin, jerky robotic movement, stiff posture"
)

SEG_PROMPTS = [
    # 段1 开场撩拨
    STYLE + CHARACTER + CAMERA +
    "A confident alluring girl begins a slow seductive dance: she stands smoothly, hands "
    "crossing over her chest then trailing down, one hand running through her deep-brown "
    "wavy hair, a teasing glance at the camera, subtle swaying of her hips, black dress and "
    "sliver bracelet catching warm light. Lazy, confident, inviting. " + MUSIC + " Avoid: " + NEG,
    # 段2 中段扭腰摆臂
    STYLE + CHARACTER + CAMERA +
    "Continuing the same woman, same deep-brown wavy hair and black lace dress: she flows "
    "into fluid waist-twisting and hip pulses synced to the beat, arms swaying and sweeping "
    "softly, fingertips gently brushing her cheek and collarbone, stepping small rhythmic "
    "steps, body undulating with the Japanese EDM, each move elegant and teasing." + MUSIC + " Avoid: " + NEG,
    # 段3 高潮定格
    STYLE + CHARACTER + CAMERA +
    "Continuing the same woman, same look: the climax of the slow-shake — a smooth slow bob "
    "and sway with arms tracing her silhouette, then a coy hand gesture toward the camera "
    "with index finger pointing, slight tilt of the head, eyes half-lidded enjoying the "
    "music, holding a confident alluring final heel-pose, dress and curls in motion, moody "
    "warm light." + MUSIC + " Avoid: " + NEG,
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
    print("室内性感慢摇舞：%d段 × %.2fs ≈ %.1fs total" % (segs, args.length/24, args.length/24*segs))
    print("steps=%d, shift_video=%s, REF=%s" % (args.steps, args.shift_video, REF_IMG))
    seg_files = {}
    for i in range(1, segs + 1):
        tag = "ih_s%02d" % i
        cands = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                        if f.startswith(tag) and f.endswith(".mp4")])
        if cands:
            seg_files[i] = cands[-1]; print("[%d/%d] %s exists, skip" % (i, segs, tag)); continue
        first_img = None
        if i == 1:
            first_img = REF_IMG
        elif (i - 1) in seg_files:
            first_img = os.path.relpath(extract_last_frame(seg_files[i-1], os.path.join(TMP_DIR, "ih_s%02d_last.png" % (i-1))), INPUT_ROOT).replace("\\", "/")
        seed = 20261030 + i
        wf = build_segment(SEG_PROMPTS[i-1], first_img, seed, "indoor_heels_dance/%s" % tag,
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
    out_name = os.path.join(OUT_DIR, "indoor_heels_dance_9x16_3seg.mp4")
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