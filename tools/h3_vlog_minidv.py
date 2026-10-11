#!/usr/bin/env python3
"""Seedance2.5 风格真实感 Vlog - H3 分段衔接生成（9:16 竖屏，参考人物 gemini_ken1/C02_PADDED）

提示词来源：2026-09-06 用户提供的 AI Vlog 要素解析（MiniDV/老旧生活区/白色吊带裙/侧马尾）
英文转译 + 分层人物描述（替代关键词堆叠）+ 段场景锚点。
3 段 × 124 帧（≈5.17s/段）≈ 15.5s 总时长，段间末帧链式衔接。
"""
import json, urllib.request, uuid, time, os, sys, subprocess, math, argparse

BASE = "http://127.0.0.1:8188"
FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
FFPROBE = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffprobe.exe"
INPUT_ROOT = r"D:\ai_projects\ComfyUI\input"
OUT_DIR = r"D:\ai_projects\ComfyUI\output\vlog_minidv"
TMP_DIR = os.path.join(INPUT_ROOT, "vlog_minidv_frames")
REF_IMG = "gemini_ken1/C02_PADDED.png"

STYLE = (
    "early-2000s consumer MiniDV handheld camcorder footage: strong handheld shake and "
    "casual reframing, occasional autofocus hunting and subtle lens breathing, slight "
    "exposure fluctuation; low contrast faded washed-out look with mild digital noise and "
    "light compression artifacts; absolutely no modern stabilization and no commercial "
    "color grading. "
)

SCENE = (
    "A quiet old residential neighborhood: narrow cement alleyways, low houses with small "
    "terraces, a clothesline and potted plants in the yard, bicycles and motorbikes parked "
    "casually, lush trees, and a dense web of overhead power lines. Pure authentic "
    "lived-in streetscape, no shops or commercial elements. "
)

CHARACTER = (
    "The same young East Asian woman as the reference image, delicate elegant features, "
    "porcelain-fair luminous skin, long black hair tied in a fresh side ponytail. She has a "
    "statuesque hourglass figure with nine-heads-tall proportion: long slender straight "
    "legs, a cinched waist flowing into softly rounded hips, a graceful swan-like neck and "
    "clear collarbones, poised upright upper body. She wears a simple white spaghetti-strap "
    "mini dress, no jewelry. Serene natural expression. "
)

AUDIO = (
    " Ambient location sound only, no background music at all: morning birdsong, breeze "
    "rustling tree leaves, a distant motorbike engine, footsteps on cement, soft cat "
    "meows, a coffee cup clinking."
)

NEG = (
    "modern electronic stabilization, gimbal look, commercial color grading, shop signs, "
    "dancing, background music, jewelry, deformed face, extra fingers, extra limbs, "
    "oversharpened, cartoon, anime, illustration look, blurry, watermark, text overlay"
)

SEG_PROMPTS = [
    # 00:00-00:05 小巷相遇
    STYLE + SCENE + CHARACTER +
    "Eye-level handheld shot: she sits on the cement ground by the alley tidying her hair, "
    "then stands up, turns and walks deeper into the alley. As a breeze lifts her hair her "
    "smile relaxes naturally; the moment she looks up she gives a sincere gentle smile with "
    "clear tender eyes." + AUDIO + " Avoid: " + NEG,
    # 00:05-00:10 院落日常
    STYLE + SCENE + CHARACTER +
    "Continuing with the same woman, same face, same white dress: she reaches up for items "
    "on a balcony, walks into the yard to hang laundry on the clothesline, then sits quietly "
    "on the terrace holding a coffee cup; she waves warmly to an off-camera neighbor, "
    "smiling brighter with bright eyes. Partly high-angle view for a lived-in spatial feel." +
    AUDIO + " Avoid: " + NEG,
    # 00:10-00:15 街道漫步
    STYLE + SCENE + CHARACTER +
    "The same woman, same face, same white dress, strolling leisurely down the quiet street "
    "with a coffee cup in hand; noticing the camera she turns her head slightly and gives a "
    "soft calm smile, eyes gentle, completely natural with no posed stiffness." +
    AUDIO + " Avoid: " + NEG,
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

def build_segment(prompt, first_frame_img, seed, prefix, width, height, length, ref_img):
    n = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors", "type": "minimax"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "4": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["1", 0], "shift_video": 12.0, "shift_audio": 3.0}},
        "5": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
            "clip": ["2", 0], "vae": ["3", 0], "prompt": prompt,
            "width": width, "height": height, "length": length}},
        "6": {"class_type": "KSampler", "inputs": {
            "model": ["4", 0], "seed": seed, "steps": 28, "cfg": 1.0,
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
    ap.add_argument("--start_seg", type=int, default=1)
    args = ap.parse_args()

    W, H = 544, 960
    segs = len(SEG_PROMPTS)
    seg_dur = args.seg_len / 24.0
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)
    print(f"Seedance 风格 Vlog：{segs} 段 × {seg_dur:.2f}s ≈ {seg_dur*segs:.1f}s，{W}×{H} 9:16")
    print(f"首帧：{REF_IMG}；输出：{OUT_DIR}")

    seg_files = {}
    for i in range(1, segs + 1):
        tag = f"vlog_s{i:02d}"
        cands = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                        if f.startswith(tag) and f.endswith(".mp4")])
        if cands and i < args.start_seg:
            seg_files[i] = cands[-1]
            print(f"[{i}/{segs}] {tag} 已存在，跳过（复用 {os.path.basename(cands[-1])}）")
            continue
        first_img = None
        if i > 1:
            prev_tag = f"vlog_s{i-1:02d}"
            if i - 1 not in seg_files:
                prev = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                               if f.startswith(prev_tag) and f.endswith(".mp4")])
                seg_files[i-1] = prev[-1] if prev else None
            if seg_files.get(i-1):
                last_png = extract_last_frame(seg_files[i-1], os.path.join(TMP_DIR, f"{prev_tag}_last.png"))
                first_img = os.path.relpath(last_png, INPUT_ROOT).replace("\\", "/")
        seed = 20260906 + i
        wf = build_segment(SEG_PROMPTS[i-1], first_img, seed, f"vlog_minidv/{tag}", W, H, args.seg_len, REF_IMG)
        r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
        pid = r.get("prompt_id")
        print(f"[{i}/{segs}] {tag} 提交 pid={pid}（首帧={'末帧' if first_img else 'C02_PADDED'}）", flush=True)
        if not wait_done(pid):
            print("  段失败，中止"); sys.exit(1)
        cands = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                        if f.startswith(tag) and f.endswith(".mp4")],
                       key=os.path.getmtime)
        seg_files[i] = cands[-1]
        print(f"  ✓ {os.path.basename(cands[-1])}", flush=True)

    # 拼接成片
    ordered = [seg_files[i] for i in sorted(seg_files)]
    out_name = os.path.join(OUT_DIR, "vlog_minidv_9x16_3seg_260906.mp4")
    cd = args.xfade
    if len(ordered) > 1 and cd > 0:
        inputs = []
        for p in ordered:
            inputs += ["-i", p]
        durs = [probe_duration(p) for p in ordered]
        chain, prev, acc = [], "0:v", durs[0]
        for i in range(1, len(ordered)):
            off = max(0.0, acc - cd)
            chain.append(f"[{prev}][{i}:v]xfade=transition=fade:duration={cd}:offset={off:.3f}[vx{i}];")
            prev = f"vx{i}"
            acc = acc + durs[i] - cd
        fc = "".join(chain) + f"[{prev}]format=yuv420p[vout]"
        cmd = [FFMPEG, "-y"] + inputs + ["-filter_complex", fc, "-map", "[vout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", "24",
            "-movflags", "+faststart", out_name]
    else:
        listfile = os.path.join(OUT_DIR, "concat_list.txt")
        with open(listfile, "w", encoding="utf-8") as f:
            for p in ordered:
                f.write(f"file '{p.replace(os.sep, '/')}'\n")
        cmd = [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", listfile, "-c", "copy",
               "-movflags", "+faststart", out_name]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print("ffmpeg 退出码:", r.returncode)
    if not os.path.exists(out_name):
        print((r.stderr or "")[-800:])
        print("❌ 拼接失败"); sys.exit(1)
    print(f"\n✅ 成片: {out_name} ({os.path.getsize(out_name)/1024/1024:.1f} MB)")

if __name__ == '__main__':
    main()
