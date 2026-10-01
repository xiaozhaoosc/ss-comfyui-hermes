#!/usr/bin/env python3
"""古风少女《小师妹》手势舞 - H3 分段衔接（真人写实）

造型：粉色碎花旗袍（短袖）+白色荷叶边围裙+白色花朵发饰+黑色双马尾盘发+蝴蝶结耳环
动作：手势舞
  - 开场亮相：双手交叉→向两侧打开+身体摇摆
  - 挥手互动：右手画弧挥动+左手呼应
  - 比心托腮：单手比心+另一手托腮+俏皮眼神
  - 手指点睛：食指交替上指→指尖相对→双手合十
  - 结束定格：双手叉腰+挺胸大笑
镜头：固定中近景，平视，聚焦上半身与手部动作
音频：欢快甜美女声唱词（含"杨柳依依"古风词句）
"""
import json, urllib.request, uuid, time, os, sys, subprocess, math, argparse

BASE = "http://127.0.0.1:8188"
FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
FFPROBE = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffprobe.exe"
INPUT_ROOT = r"D:\ai_projects\ComfyUI\input"
OUT_DIR = r"D:\ai_projects\ComfyUI\output\xiaoshimei_dance"
TMP_DIR = os.path.join(INPUT_ROOT, "xiaoshimei_frames")
REF_IMG = "gemini_ken1/C02_PADDED.png"

STYLE = (
    "realistic cinematic photography, ultra high detail, soft warm studio lighting with "
    "a pastel pink and cream color palette, shallow depth of field, film grain, glossy "
    "healthy skin, clean composition. "
)

CHARACTER = (
    "The same young East Asian woman as the reference image, same face, delicate sweet "
    "features, big sparkling eyes, gentle warm smile with soft rosy cheeks, porcelain-"
    "fair luminous skin. Statuesque hourglass figure with nine-heads-tall proportion: "
    "long slender legs, cinched waist, graceful swan neck, poised posture. "
    "Outfit: a short-sleeved pink qipao dress with a delicate red floral pattern, "
    "form-fitting silhouette with matching shorts underneath, the waist adorned with "
    "a white ruffled apron tied in a bow at the back. "
    "Hair: black hair styled in high twin tails with smooth shiny strands and a "
    "neatly tied top knot, a delicate white flower hair ornament crowning the bun, "
    "small white bow earrings dangling at her ears. Sweet girlish charm, innocent "
    "yet lively, like a beloved 'little shimei' (junior disciple) from a xianxia world."
)

SETTING = (
    "A softly lit traditional Chinese interior, warm ambient light, subtle classic "
    "wooden lattice in the background suggesting a Jiangnan courtyard, blurred "
    "pastel flowers in a vase nearby. "
)

CAMERA = "Fixed camera, eye-level, medium close-up framing on upper body and hands, stable and intimate. "

MUSIC = (
    " A bright cheerful Chinese-style pop song, a sweet youthful female voice singing "
    "ancient-style lyrics including the phrase 'willow branches swaying gently' "
    "(杨柳依依), light traditional instruments like dizi flute and guzheng interwoven "
    "with a modern bouncy beat, tempo fast and playful."
)

NEG = (
    "anime, cartoon, 3D render, Pixar style, illustration, distorted face, deformed "
    "hands, extra fingers, extra limbs, bad anatomy, melted arms, blurry, watermark, "
    "text overlay, oversharpened, dull skin"
)

SEG_PROMPTS = [
    # 段1：开场亮相 + 挥手互动
    STYLE + CHARACTER + SETTING + CAMERA +
    "Opening pose: she stands with hands crossed gently in front of her chest, then "
    "sweeps both arms open to the sides in a graceful sweeping gesture, body swaying "
    "gently left and right with confident charm, her pink qipao catching the light, "
    "the white apron ruffles fluttering. Then she raises her right hand and traces "
    "a smooth arc through the air in a playful waving gesture toward the camera, her "
    "left hand mirroring with a smaller responding gesture, twin tails swishing. "
    "Bright sweet smile, eyes sparkling with lively energy, soft rosy cheeks glowing." +
    MUSIC + " Avoid: " + NEG,
    # 段2：比心托腮 + 手指点睛
    STYLE + CHARACTER + SETTING + CAMERA +
    "Continuing the same girl, same face, same pink floral qipao with white apron and "
    "twin tails with flower ornament: she forms a heart shape with her right hand "
    "beside her cheek in an adorable 'bixin' gesture, then switches to resting her "
    "chin on her left hand in a playful coquettish pose, eyes darting to the camera "
    "with a mischievous glint. Then she raises both index fingers alternately upward "
    "in quick lively succession, brings the fingertips together above her head, and "
    "finally presses her palms together in front of her chest in a graceful closing "
    "hand gesture. Quick precise hand movements, rhythmic and dance-like, sweet smile "
    "never fading." + MUSIC + " Avoid: " + NEG,
    # 段3：双手叉腰大笑定格
    STYLE + CHARACTER + SETTING + CAMERA +
    "Continuing the same girl, same face, same pink floral qipao with white apron and "
    "twin tails with flower ornament: the grand finale — she places both hands firmly "
    "on her waist, chest lifted proudly, head tilted back slightly, and bursts into "
    "her brightest most dazzling smile, eyes crinkled with joy, absolutely radiant. "
    "She holds this triumphant end pose steadily, letting the white bows and flower "
    "ornament catch the light, hair swaying to rest. Perfect cute confident ending "
    "freeze-frame." + MUSIC + " Avoid: " + NEG,
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

def build_segment(prompt, first_frame_img, seed, prefix, width, height, length, ref_img,
                  steps=34, shift_video=14.0, shift_audio=3.5):
    n = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors", "type": "minimax"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "4": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["1", 0], "shift_video": shift_video, "shift_audio": shift_audio}},
        "5": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
            "clip": ["2", 0], "vae": ["3", 0], "prompt": prompt,
            "width": width, "height": height, "length": length}},
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
    ap.add_argument("--steps", type=int, default=34)
    ap.add_argument("--shift_video", type=float, default=14.0)
    ap.add_argument("--shift_audio", type=float, default=3.5)
    args = ap.parse_args()
    W, H = 544, 960
    segs = len(SEG_PROMPTS)
    seg_dur = args.seg_len / 24.0
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)
    print(f"小师妹手势舞：{segs}段 × {seg_dur:.2f}s (steps={args.steps}, shift={args.shift_video}/{args.shift_audio})")
    print(f"首帧:{REF_IMG} 输出:{OUT_DIR}")
    seg_files = {}
    for i in range(1, segs + 1):
        tag = f"xsm_s{i:02d}"
        cands = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                        if f.startswith(tag) and f.endswith(".mp4")])
        if cands:
            seg_files[i] = cands[-1]; print(f"[{i}/{segs}] {tag} 已存在，跳过"); continue
        first_img = None
        if i > 1 and i-1 in seg_files:
            prev_tag = f"xsm_s{i-1:02d}"
            last_png = extract_last_frame(seg_files[i-1], os.path.join(TMP_DIR, f"{prev_tag}_last.png"))
            first_img = os.path.relpath(last_png, INPUT_ROOT).replace("\\", "/")
        seed = 20261130 + i
        wf = build_segment(SEG_PROMPTS[i-1], first_img, seed, f"xiaoshimei_dance/{tag}",
                           W, H, args.seg_len, REF_IMG,
                           steps=args.steps, shift_video=args.shift_video, shift_audio=args.shift_audio)
        r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
        pid = r.get("prompt_id")
        print(f"[{i}/{segs}] {tag} pid={pid}（首帧={'末帧' if first_img else 'C02'}）", flush=True)
        if not wait_done(pid):
            print("  段失败，中止"); sys.exit(1)
        cands = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                        if f.startswith(tag) and f.endswith(".mp4")], key=os.path.getmtime)
        seg_files[i] = cands[-1]
        print(f"  ✓ {os.path.basename(cands[-1])}", flush=True)
    ordered = [seg_files[i] for i in sorted(seg_files)]
    out_name = os.path.join(OUT_DIR, "xiaoshimei_dance_9x16_3seg_260906.mp4")
    cd = args.xfade
    if len(ordered) > 1 and cd > 0:
        inputs = []
        for p in ordered: inputs += ["-i", p]
        durs = [probe_duration(p) for p in ordered]
        chain, prev, acc = [], "0:v", durs[0]
        for i in range(1, len(ordered)):
            off = max(0.0, acc - cd)
            chain.append(f"[{prev}][{i}:v]xfade=transition=fade:duration={cd}:offset={off:.3f}[vx{i}];")
            prev = f"vx{i}"; acc = acc + durs[i] - cd
        fc = "".join(chain) + f"[{prev}]format=yuv420p[vout]"
        cmd = [FFMPEG, "-y"] + inputs + ["-filter_complex", fc, "-map", "[vout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", "24",
            "-movflags", "+faststart", out_name]
    else:
        listfile = os.path.join(OUT_DIR, "concat_list.txt")
        with open(listfile, "w", encoding="utf-8") as f:
            for p in ordered: f.write(f"file '{p.replace(os.sep, '/')}'\n")
        cmd = [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", listfile, "-c", "copy",
               "-movflags", "+faststart", out_name]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print("ffmpeg 退出码:", r.returncode)
    if os.path.exists(out_name):
        print(f"\n✅ 成片: {out_name} ({os.path.getsize(out_name)/1024/1024:.1f} MB)")

if __name__ == '__main__':
    main()
