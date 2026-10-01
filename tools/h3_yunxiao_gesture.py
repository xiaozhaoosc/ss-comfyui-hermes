#!/usr/bin/env python3
"""云霄·古风手势舞（《亲爱的》卡点）— H3 竖屏 544×960 × 4 段链式 ≈15s，含原生音频

按解析的 4 个节拍段一一对应：
  seg1 00-03s 双手合十胸前→缓缓分开上举、指尖相对
  seg2 03-07s 胸前波浪摆动→右手向外挥出、左手托下巴
  seg3 07-10s 双手胸前交叉→向两侧打开、掌心朝外
  seg4 10-13s 收回胸前、手指弯曲呈爪状→双拳举至脸颊两侧 + 轻微扭动
首帧: 纯 t2va（沿用上一条《云霄·月夜独舞》的角色与夜色世界观）；段2起末帧链式。
音频: H3 原生生成 — 女声华语流行歌《亲爱的》风格（轻快抓耳、歌词"亲爱的，你是否还记得"）。

用法: python tools/h3_yunxiao_gesture.py            # 全跑（断点续跑）
      python tools/h3_yunxiao_gesture.py --segs 2   # 只跑前 2 段
"""
import argparse, json, os, subprocess, sys, time, urllib.request, urllib.error, uuid

BASE = "http://127.0.0.1:8188"
COMFY = r"D:\ai_projects\ComfyUI"
INPUT_ROOT = os.path.join(COMFY, "input")
OUT_DIR = os.path.join(COMFY, "output", "2026-09-12", "yunxiao_gesture")
PREFIX = "2026-09-12/yunxiao_gesture"
TMP_DIR = os.path.join(INPUT_ROOT, "yunxiao_gesture_frames")
W, H, LEN, STEPS, SHIFT_V, SHIFT_A = 544, 960, 90, 34, 14.0, 3.5
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(TMP_DIR, exist_ok=True)

NEG = ("Avoid: anime, cartoon, 3D render, illustration, cel shading, distorted face, deformed hands, "
       "extra fingers, extra limbs, bad anatomy, melted limbs, blurry, watermark, text overlay, "
       "oversharpened, plastic skin, outfit change, face change.")

STYLE = ("Style: photorealistic live-action cosplay cinematography, real human actress, ultra high detail, "
         "cinematic night lighting with a violet-blue color grade, mystical and dreamy fairy atmosphere, "
         "realistic skin texture, realistic hair strands, realistic silk and gauze fabric physics, "
         "shallow depth of field, subtle film grain. ")

CHARACTER = ("Character: a young East Asian woman in her early twenties, delicate oval face, fair luminous skin, "
             "long straight violet-purple hair reaching her waist with wispy air bangs and softly curled ends, "
             "elegant ancient-Chinese makeup with slender thin brows, violet eyeshadow, long lashes and matte red "
             "lips, a gorgeous black hair crown with sharp spike ornaments on top of her head, a slim collarbone "
             "necklace, a black wrist guard on her left wrist. ")

OUTFIT = ("Costume: a pale lavender deep-V cross-collar hanfu with silk sleeves, a matching sheer gauze shawl "
          "draped over her arms, a wide black belt decorated with golden patterns cinching her waist, "
          "and a slit skirt that reveals her leg when she moves. ")

SETTING = ("Setting: night in an ancient Chinese garden, deep blue-violet night sky, faint mist drifting close to "
           "the ground, distant silhouetted trees, soft moonlight rimming her hair and shoulders, a quiet exotic "
           "and romantic atmosphere. ")

CAMERA = ("Camera: fixed camera, eye level, medium shot framing her upper body and part of her legs, centered "
          "composition with her in the middle of the frame, no camera movement, no pull or push, no cuts, "
          "the whole take is continuous. ")

MOTION = [
    ("Action: she presses both palms together in front of her chest, then slowly separates her hands and lifts "
     "them upward until her fingertips point toward each other above her head, sleeves sliding down her forearms, "
     "her body swaying softly to the rhythm. She smiles gently and keeps her gaze lively and sweet. "),
    ("Action: her hands roll in a smooth wave in front of her chest, wrists loose, then her right hand sweeps "
     "outward to the side while her left hand comes up to support her chin, her head tilting slightly, her eyes "
     "bright and a little flirtatious, a small smile on her lips. "),
    ("Action: both hands cross in front of her chest, then open outward to the two sides with palms facing out, "
     "the gauze shawl spreading with the movement, her waist twisting gently, her expression confident and "
     "charming with a soft smile. "),
    ("Action: her hands draw back toward her chest with fingers curled like soft claws, then close into loose "
     "fists that rise up to the sides of her cheeks while she twists her upper body slightly to the beat, "
     "eyes sparkling, ending with a sweet bright smile facing the camera. "),
]

MUSIC = [
    ("Audio: a light catchy Chinese female pop song, a young woman singing in Mandarin the hook line "
     "\"亲爱的，你是否还记得\", soft airy voice over an easy mid-tempo pop beat with plucked strings and light "
     "electronic percussion, romantic and sweet, no other voices. "),
    ("Audio: the same female Mandarin pop song continues smoothly, her vocal melody riding the light beat, "
     "guzheng and synth accents behind it, sweet and dreamy, no other speech. "),
    ("Audio: the song keeps its gentle groove, the female vocal carrying the chorus, soft percussion and strings, "
     "warm and romantic night mood, no other speech. "),
    ("Audio: the same female Mandarin pop song reaches its final sweet phrase and ends on a soft sustained note "
     "with the beat tapering out, no other speech. "),
]

SEG_PROMPTS = [STYLE + CHARACTER + OUTFIT + SETTING + CAMERA + MOTION[i] + MUSIC[i] + NEG for i in range(4)]


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segs", type=int, default=len(SEG_PROMPTS))
    a = ap.parse_args()
    n = min(a.segs, len(SEG_PROMPTS))
    print("云霄手势舞 %d 段 × %.2fs ≈ %.1fs | %dx%d steps=%d shift=%.1f:%.1f"
          % (n, LEN / 24, LEN / 24 * n, W, H, STEPS, SHIFT_V, SHIFT_A), flush=True)
    seg_file = {}
    for i in range(1, n + 1):
        tag = "yg_s%02d" % i
        cands = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                        if f.startswith(tag) and f.endswith(".mp4") and "audio" not in f], key=os.path.getmtime)
        if cands:
            seg_file[i] = cands[-1]
            print("[%d/%d] %s 已存在，跳过" % (i, n, tag), flush=True)
            continue
        first = None
        if i > 1:
            png = extract_last_frame(seg_file[i - 1], os.path.join(TMP_DIR, "yg_s%02d_last.png" % (i - 1)))
            first = os.path.relpath(png, INPUT_ROOT).replace("\\", "/")
        wf = build(SEG_PROMPTS[i - 1], 20261300 + i, "%s/%s" % (PREFIX, tag), first)
        r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
        pid = r.get("prompt_id")
        print("[%d/%d] %s pid=%s 首帧=%s" % (i, n, tag, pid, first), flush=True)
        if not wait_done(pid):
            print("  %s 失败" % tag); sys.exit(1)
        cands = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                        if f.startswith(tag) and f.endswith(".mp4") and "audio" not in f], key=os.path.getmtime)
        seg_file[i] = cands[-1]
        print("  ✓ %s" % os.path.basename(cands[-1]), flush=True)

    def audio_of(p):
        a_ = os.path.join(os.path.dirname(p), os.path.basename(p).replace(".mp4", "-audio.mp4"))
        return a_ if os.path.exists(a_) else p
    ordered = [audio_of(seg_file[i]) for i in sorted(seg_file)]
    listfile = os.path.join(OUT_DIR, "concat_list.txt")
    with open(listfile, "w", encoding="utf-8") as f:
        for p in ordered:
            f.write("file '%s'\n" % p.replace(os.sep, "/"))
    out = os.path.join(OUT_DIR, "云霄_古风手势舞_%dseg.mp4" % len(ordered))
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile.replace("\\", "/"),
                    "-c", "copy", "-movflags", "+faststart", out.replace("\\", "/")], check=True, capture_output=True)
    print("✅ 成片:", out, "(%.1f MB)" % (os.path.getsize(out) / 1024 / 1024), flush=True)
    pr = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration:stream=codec_type,codec_name,sample_rate,channels",
                         "-of", "json", out.replace("\\", "/")], capture_output=True, encoding="utf-8")
    print(pr.stdout, flush=True)
    for t in (0.5, 5.0, 9.0, 13.0):
        fr = os.path.join(OUT_DIR, "frame_%ss.jpg" % t)
        subprocess.run(["ffmpeg", "-y", "-ss", str(t), "-i", out.replace("\\", "/"), "-frames:v", "1", "-q:v", "3",
                        "-pix_fmt", "yuvj420p", "-strict", "unofficial", fr.replace("\\", "/")], capture_output=True)
    print("YUNXIAO-GESTURE-DONE", flush=True)


if __name__ == "__main__":
    main()
