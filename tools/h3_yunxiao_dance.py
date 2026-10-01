#!/usr/bin/env python3
"""云霄·月夜古风独舞 — H3 t2va/i2va 2 段链式（544×960，每段 124 帧 ≈5.17s，共 10.3s）

段1: 中全景·起势起舞（t2va，含原生音频）
段2: 中近景·旋身手势特写（i2va，first_frame = 段1 末帧，末帧链式）

音频: 女声华语抒情歌（"亲爱的,你是否还记得"）+ 古筝/弦乐 + 夜环境声 — 与画面同源生成
用法:
  python tools/h3_yunxiao_dance.py seg1     # 提交段1
  python tools/h3_yunxiao_dance.py seg2     # 段1 完成后:抽末帧→提交段2
  python tools/h3_yunxiao_dance.py merge    # 拼接 + 抽帧
  python tools/h3_yunxiao_dance.py all      # 串行跑完
"""
import json, os, subprocess, sys, time, urllib.request, urllib.error, uuid

BASE = "http://127.0.0.1:8188"
COMFY = r"D:\ai_projects\ComfyUI"
OUTDIR = os.path.join(COMFY, "output", "yunxiao_dance")
INDIR = os.path.join(COMFY, "input")
PREFIX = "yunxiao_dance"
W, H, LEN = 544, 960, 124          # 竖版 544×960, 124 帧 ≈ 5.17s @24fps
STEPS = 34                          # 组2 锐化档(与 shift 严格 4:1 耦合)
SHIFT_V, SHIFT_A = 14.0, 3.5
SEED1, SEED2 = 20260912, 20260913
os.makedirs(OUTDIR, exist_ok=True)

# ------------------------------------------------------------------ 提示词
NEG = ("Avoid: anime, cartoon, 3D render, illustration, cel shading, distorted face, deformed hands, "
       "extra fingers, extra limbs, bad anatomy, melted limbs, blurry, watermark, text overlay, "
       "oversharpened, plastic skin, twin braids.")

STYLE = ("Style: photorealistic live-action cosplay cinematography, real human actress, ultra high detail, "
         "cinematic night lighting, realistic skin texture and pores, natural hair strands, realistic fabric "
         "physics, shallow depth of field, subtle film grain, professional costume photography. ")

CHARACTER = ("Character: a young East Asian woman in her early twenties, delicate oval face, fair luminous skin, "
             "long flowing violet-purple hair reaching her waist with loose strands moving in the night breeze, "
             "an ornate black horn-shaped headpiece with two curved horns rising from her hair, thin silver "
             "hairpins with small tassels, cool elegant ancient-Chinese makeup with soft violet eyeshadow, "
             "long lashes, softly defined brows and glossy rose lips. ")

OUTFIT = ("Costume: a layered pale-lavender translucent gauze dance robe over a fitted light purple under-dress, "
          "long wide flowing sleeves, silver-white embroidery of clouds and cranes along the collar and cuffs, "
          "a long trailing gauze sash, a jade pendant at her waist, sheer layers of chiffon that trail and "
          "flutter with every movement. ")

SETTING = ("Setting: night in an ancient Chinese garden courtyard, a huge full moon low in a deep blue-violet "
           "sky, silhouetted old pine trees and swaying branches, thin drifting mist close to the stone floor, "
           "a quiet stone terrace with faint moonlit reflections, cool blue-violet moonlight with soft warm "
           "lantern glow from the side, drifting fireflies. ")

CAMERA1 = ("Camera: fixed camera on a tripod at medium-full shot, slight low angle, the dancer centered with "
           "breathing room above her horns and below her trailing sash, her whole figure inside the frame. ")
CAMERA2 = ("Camera: fixed camera, medium close shot from slightly to the side, her upper body and flowing "
           "sleeves filling the frame, face clearly visible. ")

MOTION1 = ("Action: she gathers her sleeves, then begins a slow elegant classical Chinese dance — weight shifting "
           "from foot to foot, torso rotating smoothly, both arms tracing long continuous arcs through the air, "
           "the sheer sleeves trailing a beat behind her wrists, her long gauze sash and violet hair lifted and "
           "carried by her own turning motion, then a controlled spin on the ball of one foot with the hems of "
           "the robe swinging outward and settling. Her gaze stays calm and serene, chin slightly raised, a faint "
           "confident smile, eyes catching the moonlight for a brief glint. ")
MOTION2 = ("Action: continuing without a break, she turns her upper body toward the camera while one arm lifts in "
           "a slow circling gesture, the other sleeve falling in a long spiral, gauze fabric rippling and settling "
           "around her, hair swaying across her shoulder, then she lowers her gaze with a soft knowing smile and "
           "glances back up at the camera at the very end. Her expression stays serene with a hint of tenderness. ")

AUDIO1 = ("Audio: a gentle Chinese female vocal ballad, a young woman singing softly and emotionally in Mandarin "
          "the line \"亲爱的，你是否还记得\", accompanied by guzheng plucks, sustained erhu and warm string pads, "
          "slow romantic tempo, plus quiet night ambience of crickets and a faint breeze. ")
AUDIO2 = ("Audio: the same female Mandarin ballad continues seamlessly, voice carrying the melody over guzheng "
          "and strings, soft night ambience behind it, ending on a sustained soft note. ")

SEG1 = STYLE + CHARACTER + OUTFIT + SETTING + CAMERA1 + MOTION1 + AUDIO1 + NEG
SEG2 = STYLE + CHARACTER + OUTFIT + SETTING + CAMERA2 + MOTION2 + AUDIO2 + NEG


def post(path, payload):
    req = urllib.request.Request(f"{BASE}{path}", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=60).read())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode(errors='replace')[:900]}")
        raise


def history(pid):
    with urllib.request.urlopen(f"{BASE}/history/{pid}", timeout=30) as r:
        return json.loads(r.read().decode()).get(pid)


def wait_done(pid, timeout=3600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        h = history(pid)
        if h:
            st = h.get("status", {})
            if st.get("completed"):
                outs = []
                for o in h.get("outputs", {}).values():
                    outs += [f["filename"] for f in o.get("gifs", [])] + [f["filename"] for f in o.get("images", [])]
                return outs
            if st.get("status_str") == "error":
                print("ERR", json.dumps([m for k, m in st.get("messages", []) if k == "execution_error"][:1],
                                        ensure_ascii=False)[:400])
                return None
        time.sleep(15)
        el = int(time.time() - t0)
        if el % 120 < 15:
            print(f"    ...{el//60}m{el%60}s", flush=True)
    return None


def build(prompt, seed, prefix, first_frame=None):
    g = {
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
        "10": {"class_type": "SaveAudio", "inputs": {"audio": ["9", 0], "filename_prefix": f"{prefix}_audio"}},
        "11": {"class_type": "VHS_VideoCombine", "inputs": {
            "images": ["8", 0], "audio": ["9", 0], "frame_rate": 24.0, "loop_count": 0,
            "filename_prefix": prefix, "format": "video/h264-mp4", "pingpong": False, "save_output": True}},
    }
    if first_frame:
        g["12"] = {"class_type": "LoadImage", "inputs": {"image": first_frame}}
        g["6"]["inputs"]["first_frame"] = ["12", 0]
    return g


def submit(prompt, seed, prefix, first_frame=None):
    r = post("/prompt", {"prompt": build(prompt, seed, prefix, first_frame), "client_id": str(uuid.uuid4())})
    pid = r.get("prompt_id")
    print(f"✓ 已提交 {prefix}  pid={pid}")
    safe = prefix.replace("/", "_")
    json.dump({"pid": pid, "prefix": prefix}, open(os.path.join(OUTDIR, f"{safe}_pid.json"), "w"))
    return pid


def seg1():
    return submit(SEG1, SEED1, f"{PREFIX}/seg1")


def find_video(prefix):
    for f in sorted(os.listdir(OUTDIR), reverse=True):
        if f.startswith(prefix.replace("/", "_")) and f.endswith(".mp4") and "audio" not in f:
            return os.path.join(OUTDIR, f)
    # VHS 有时带编号前缀
    for f in sorted(os.listdir(OUTDIR), reverse=True):
        if f.startswith(prefix.split("/")[-1]) and f.endswith(".mp4") and "audio" not in f:
            return os.path.join(OUTDIR, f)
    return None


def seg2():
    v = find_video(f"{PREFIX}/seg1") or find_video("seg1")
    if not v:
        print("未找到段1 成片，先把 seg1 跑完"); return None
    last = os.path.join(INDIR, "yunxiao_seg1_last.png")
    subprocess.run(["ffmpeg", "-y", "-sseof", "-0.3", "-i", v.replace("\\", "/"),
                    "-frames:v", "1", "-q:v", "2", "-pix_fmt", "yuvj420p", "-strict", "unofficial",
                    last.replace("\\", "/")], check=True, capture_output=True)
    print(f"✓ 段1 末帧 → {last}")
    return submit(SEG2, SEED2, f"{PREFIX}/seg2", first_frame="yunxiao_seg1_last.png")


def probe(p):
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration:stream=codec_type,sample_rate,channels",
                        "-of", "json", p.replace("\\", "/")], capture_output=True, encoding="utf-8")
    return r.stdout


def merge():
    vids = [x for x in sorted(os.listdir(OUTDIR)) if x.startswith("seg") and x.endswith(".mp4") and "audio" not in x]
    if len(vids) < 2:
        print("段数不足:", vids); return
    lst = os.path.join(OUTDIR, "concat_list.txt")
    with open(lst, "w", encoding="utf-8") as fh:
        for v in vids:
            fh.write(f"file '{v}'\n")
    out = os.path.join(OUTDIR, "云霄_月夜独舞_10s.mp4")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst.replace("\\", "/"),
                    "-c", "copy", out.replace("\\", "/")], check=True, capture_output=True)
    print("✓ 合并 →", out)
    print(probe(out))
    for t in (0.5, 3.0, 6.0, 9.0):
        fr = os.path.join(OUTDIR, f"frame_{t}s.jpg")
        subprocess.run(["ffmpeg", "-y", "-ss", str(t), "-i", out.replace("\\", "/"), "-frames:v", "1", "-q:v", "3",
                        "-pix_fmt", "yuvj420p", "-strict", "unofficial", fr.replace("\\", "/")],
                       capture_output=True)
        print("  抽帧", fr)
    return out


if __name__ == "__main__":
    a = (sys.argv[1] if len(sys.argv) > 1 else "all").lower()
    if a == "seg1":
        pid = seg1(); print("WAIT", wait_done(pid))
    elif a == "seg2":
        pid = seg2()
        if pid:
            print("WAIT", wait_done(pid))
    elif a == "merge":
        merge()
    else:
        t0 = time.time()
        print(f"=== 云霄·月夜古风独舞 {W}x{H} {LEN}帧 steps={STEPS} shift={SHIFT_V}/{SHIFT_A} ===", flush=True)
        pid1 = seg1()
        r1 = wait_done(pid1)
        print("seg1 done:", r1, f"({(time.time()-t0)/60:.1f}min)", flush=True)
        if not r1:
            sys.exit(1)
        pid2 = seg2()
        r2 = wait_done(pid2) if pid2 else None
        print("seg2 done:", r2, f"({(time.time()-t0)/60:.1f}min)", flush=True)
        if r2:
            merge()
        print("YUNXIAO-DONE", flush=True)
