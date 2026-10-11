#!/usr/bin/env python3
"""MiniMax H3 · 动漫时尚短片（写实化版本）
10 姿势 × 15 秒，128 BPM 节奏，极简白色无影棚
切片 5 段 × ~2.6-3s（63 帧 ≈ 2.6s，末帧链式衔接）
首帧：C02_PADDED
造型参考：@[char ref] 由 C02_PADDED 提供（脸/身材/服装 = 之前参考图本身）
主题：缎面 x 散落样张纸 x 淡雾 x 闪光 x 光泽地面
"""
import json, urllib.request, uuid, time, os, sys, subprocess, math, argparse

BASE = "http://127.0.0.1:8188"
FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
FFPROBE = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffprobe.exe"
INPUT_ROOT = r"D:\ai_projects\ComfyUI\input"
OUT_DIR = r"D:\ai_projects\ComfyUI\output\fashion_10pose"
TMP_DIR = os.path.join(INPUT_ROOT, "fashion_frames")
REF_IMG = "gemini_ken1/C02_PADDED.png"

STYLE = (
    "realistic cinematic fashion photography, ultra high detail, strong studio strobe "
    "flash lighting, subtle atmospheric haze, glossy reflective floor, satin fabric "
    "draped nearby, scattered loose proof-sheet papers on the floor, minimalist white "
    "cyclorama studio with no visible seams, high contrast, film grain, glossy healthy "
    "skin, rhythmic dynamic motion."
)

CHARACTER = (
    "Use the same young East Asian woman from the reference image to fully define her "
    "face, body, wardrobe, accessories and styling — do NOT introduce any new "
    "accessories or change her look. Match the reference exactly. She has a statuesque "
    "hourglass figure with nine-heads-tall proportion, long slender straight legs, "
    "cinched waist flowing into softly rounded hips, graceful neck and clear "
    "collarbones, poised upright upper body."
)

CAMERA = (
    "The camera moves along a physically continuous path forward, accelerating "
    "quickly between poses and decelerating sharply to a stop at the moment each pose "
    "locks. Rhythmic pacing matched to 128 BPM."
)

AUDIO = (
    " 128 BPM electronic dance music, punchy studio strobe hits synced with the beat, "
    "no vocals, modern fashion runway energy."
)

NEG = (
    "anime, cartoon, 3D render, illustration, distorted face, deformed hands, extra "
    "fingers, extra limbs, bad anatomy, melted limbs, blurry, watermark, text overlay, "
    "oversharpened, dull skin, new accessories added, background objects copied from "
    "reference, jerky robotic motion"
)

SEG_PROMPTS = [
    # 段1 (0-3s): 姿势1 + 2
    STYLE + CHARACTER + CAMERA +
    "Pose 1 (0:00-0:01.5): Medium close-up, centered front. She faces the camera, one "
    "hand gently toying with a strand of hair by her ear, the camera pushing in slowly "
    "with restraint. "
    "Pose 2 (0:01.5-0:03.0): she turns to a three-quarter profile, chin slightly "
    "lifted. The camera sweeps down in a fast arc and then holds on her eyes." +
    AUDIO + " Avoid: " + NEG,
    # 段2 (3-6s): 姿势3 + 4 + 5
    STYLE + CHARACTER + CAMERA +
    "Pose 3 (continuing): she lowers her gaze, both hands settling softly near her "
    "collar and hair. "
    "Pose 4 (0:03.0-0:04.5): she rotates to a strict left-side profile. The camera "
    "sweeps past her cheek in a fast pass and then steadies in close. "
    "Pose 5: she rotates one shoulder forward, the edge of her robe sharply rimmed by "
    "side light." + AUDIO + " Avoid: " + NEG,
    # 段3 (6-9s): 姿势6 + 7 + 8
    STYLE + CHARACTER + CAMERA +
    "Pose 6 (0:04.5-0:06.0): she gently pinches a fold of her long robe at her waist, "
    "then releases it. "
    "Pose 7: she turns her mouth toward the camera, gaze looking back over her "
    "shoulder at the camera. The camera drops quickly to torso level and then rises "
    "past her face in close. "
    "Pose 8 (0:06.0-0:07.5): she sits low onto the satin fabric, one knee raised." +
    AUDIO + " Avoid: " + NEG,
    # 段4 (9-12s): 姿势9 + 10
    STYLE + CHARACTER + CAMERA +
    "Pose 9: she extends one bare foot toward the camera, occupying the main "
    "foreground. The camera rushes forward at ground level and locks on the dramatic "
    "forced-perspective pose. "
    "Pose 10 (0:07.5-0:09.0): she rises to a three-quarter side stance, one hand at "
    "her collarbone, the other touching her hair, the long robe gliding lightly over "
    "her thigh. The camera slides laterally across her waistline and then eases into "
    "a stable portrait framing." + AUDIO + " Avoid: " + NEG,
    # 段5 (12-15s): 终姿势 + 收尾
    STYLE + CHARACTER + CAMERA +
    "Final: she twists into a back three-quarter shoulder silhouette, then rotates "
    "slightly so her jawline and the robe's neckline catch the same flash of light. "
    "The camera sweeps from her shoulder toward her face in strong parallax, glides "
    "past her eyes and along the robe's neckline, then arcs outward while descending. "
    "She lands in a final dominant full-body pose, looking down at the camera, in "
    "total command." + AUDIO + " Avoid: " + NEG,
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
        except Exception:
            pass
        el = int(time.time() - t0)
        print(f"    ⏱ {el//60}m{el%60:02d}s", flush=True)
        time.sleep(poll)
    print("  超时"); return False

def build_segment(prompt, first_frame_img, seed, prefix, W, H, length, steps, shift_v, shift_a):
    n = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors", "type": "minimax"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "4": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["1", 0], "shift_video": shift_v, "shift_audio": shift_a}},
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

def probe_duration(mp4):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", mp4], capture_output=True, text=True)
    try: return float(r.stdout.strip())
    except Exception: return 2.6

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--length", type=int, default=63)  # 63 = 17*3+12 → 向上取整 17*4+5=73? 用 63 ≈ 2.6s
    ap.add_argument("--steps", type=int, default=34)
    ap.add_argument("--shift_video", type=float, default=14.0)
    ap.add_argument("--shift_audio", type=float, default=3.5)
    args = ap.parse_args()
    W, H = 544, 960
    segs = len(SEG_PROMPTS)
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)
    print(f"10 姿势时尚短片：{segs} 段 × {args.length}帧 ≈ {args.length/24*segs:.1f}s total")
    print(f"steps={args.steps}, shift={args.shift_video}/{args.shift_audio}, REF={REF_IMG}")
    seg_files = {}
    for i in range(1, segs + 1):
        tag = f"fas_s{i:02d}"
        cands = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                        if f.startswith(tag) and f.endswith(".mp4")])
        if cands:
            seg_files[i] = cands[-1]; print(f"[{i}/{segs}] {tag} exists, skip"); continue
        first_img = None
        if i > 1 and i-1 in seg_files:
            prev_tag = f"fas_s{i-1:02d}"
            last_png = extract_last_frame(seg_files[i-1], os.path.join(TMP_DIR, f"{prev_tag}_last.png"))
            first_img = os.path.relpath(last_png, INPUT_ROOT).replace("\\", "/")
        elif i == 1:
            first_img = REF_IMG
        seed = 20270105 + i
        wf = build_segment(SEG_PROMPTS[i-1], first_img, seed, f"fashion_10pose/{tag}",
                           W, H, args.length, args.steps, args.shift_video, args.shift_audio)
        r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
        pid = r.get("prompt_id")
        print(f"[{i}/{segs}] {tag} pid={pid}", flush=True)
        if not wait_done(pid):
            print(f"  {tag} failed"); sys.exit(1)
        cands = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                        if f.startswith(tag) and f.endswith(".mp4")], key=os.path.getmtime)
        seg_files[i] = cands[-1]
        print(f"  ✓ {os.path.basename(cands[-1])}", flush=True)
    ordered = [seg_files[i] for i in sorted(seg_files)]
    out_name = os.path.join(OUT_DIR, "fashion_10pose_9x16_5seg_260907.mp4")
    listfile = os.path.join(OUT_DIR, "concat_list.txt")
    with open(listfile, "w", encoding="utf-8") as f:
        for p in ordered: f.write(f"file '{p.replace(os.sep, '/')}'\n")
    r = subprocess.run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", listfile,
                        "-c", "copy", "-movflags", "+faststart", out_name],
                       capture_output=True, text=True)
    print("ffmpeg exit:", r.returncode)
    if os.path.exists(out_name):
        print(f"\n✅ 成片: {out_name} ({os.path.getsize(out_name)/1024/1024:.1f} MB)")

if __name__ == '__main__':
    main()
