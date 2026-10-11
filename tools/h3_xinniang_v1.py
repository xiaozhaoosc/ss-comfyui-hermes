#!/usr/bin/env python3
"""古风新娘 Cosplay V1 - H3 分段衔接生成（9:16 竖屏，人脸参考 gemini_ken1）

相对 h3_xinniang_cosplay.py 的改进：
  1. 人脸/形象一致性：seg1 首帧 = input/gemini_ken1/C02_BODY_FRONT.png（i2v 起手，锁定人物/服装/身材）
  2. 手动总时长：--seconds N，自动分成多段（每段≈5.17s），首尾帧衔接（上段末帧→下段首帧），ffmpeg 拼接
  3. 音频：低优先级，默认不处理（H3 输出无音轨）
  4. NSFW 模型边界探索：提示词突出女性柔美/身材曲线但保持写实优雅
  5. 清晰度：--res 480p（544×960，默认，VRAM 安全）| 720p（736×1280，需 20G+ 显存，有 OOM 风险）
  6. 保留与原 t2v 一致的服装造型，仅强调体态与柔美

用法:
  python tools/h3_xinniang_v1.py --seconds 10 --res 480p
  python tools/h3_xinniang_v1.py --seconds 15 --res 720p    # 注意 OOM 风险
"""
import json, urllib.request, uuid, time, os, sys, subprocess, math, argparse

BASE = "http://127.0.0.1:8188"
FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
FFPROBE = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffprobe.exe"

INPUT_ROOT = r"D:\ai_projects\ComfyUI\input"
INPUT_REF = os.path.join(INPUT_ROOT, "gemini_ken1")
OUT_DIR = r"D:\ai_projects\ComfyUI\output\xinniang_cosplay_v1"
TMP_DIR = os.path.join(INPUT_ROOT, "xinniang_v1_frames")   # 末帧放 input 下才能被 LoadImage 加载

REF_IMG = "gemini_ken1/C02_BODY_FRONT.png"   # 全身体素，锁定人脸+服装+身材

STYLE_SUFFIX = (", real photography, ultra high detail, cinematic lighting, "
                "soft warm light, saturated colors, shallow depth of field, "
                "film grain, high-class fashion showcase, glossy skin, "
                "no AI artifacts, no deformed hands, no extra limbs, clean composition")

BASE_PROMT = (
    "A beautiful young East Asian bride with the same face as the reference image, "
    "soft delicate features, long glossy black hair flying over her shoulders, fair luminous "
    "skin, elegant slender body with feminine curves. She wears a red strapless corset gown "
    "with intricate golden flower brocade on the chest and a deep sweetheart neckline that "
    "accentuates her collarbones and shoulders, a form-fitting bodice cinching her waist, "
    "a matching red short skirt with golden tassels at the hem, flesh-toned thigh-high "
    "stockings with black garter straps on her outer thigh, an ornate red phoenix crown "
    "headdress studded with white flowers and bead strings, and a simple pendant necklace. "
    "Her slim waist, long smooth legs and graceful curves are elegantly emphasized. "
    "She stands in a confident yet coquettish catwalk pose, body gently tilted to one side, "
    "one hand resting softly on her abdomen, weight shifted onto one leg making her hip "
    "curve gracefully, a sweet playful smile with bright luminous eyes. "
    "Luxurious traditional Chinese wedding chamber with warm golden light and soft silks, "
    "dreamy romantic atmosphere. Background music is a cheerful female-sung Japanese pop "
    "song, light and upbeat with a strong rhythm."
) + STYLE_SUFFIX

SEG2_SUFFIX = (
    ", same woman and same outfit continuing, camera slowly pushing in, "
    "subtle smile deepening and gentle graceful glances, smooth continuous motion"
) + STYLE_SUFFIX

NEG = "blurry, low quality, deformed, cartoon, anime style, extra fingers, extra limbs, watermark, text, jitter, flicker"

def post(path, payload):
    req = urllib.request.Request(f"{BASE}{path}", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode(errors='replace')[:800]}")
        raise

def wait_done(pid, timeout=3600, poll=15):
    print(f"  等待 pid={pid[:13]} ...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            h = json.loads(urllib.request.urlopen(f"{BASE}/history/{pid}", timeout=15).read())
            rec = h.get(pid)
            if rec:
                st = rec.get("status", {})
                if st.get("completed") or rec.get("outputs"):
                    return True
                if "exec_err" in st or st.get("status_str") == "error":
                    print("  执行出错:", json.dumps(st, ensure_ascii=False)[:500]); return False
        except Exception as e:
            print("  查询异常:", e)
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
    # seg1 用参考图作首帧锁定人物；后续段用上一段末帧作首帧保证衔接
    img = first_frame_img if first_frame_img else ref_img
    if img:
        n["9"] = {"class_type": "LoadImage", "inputs": {"image": img}}
        n["5"]["inputs"]["first_frame"] = ["9", 0]
    return n

def extract_last_frame(mp4, out_png):
    cmd = [FFMPEG, "-y", "-sseof", "-0.3", "-i", mp4, "-q:v", "2", "-frames:v", "1", out_png]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_png

def probe_streams(mp4):
    r = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,codec_name,r_frame_rate",
        "-of", "json", mp4], capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {}

def probe_duration(mp4):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", mp4], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 5.17

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=10, help="目标时长(秒)，默认10")
    ap.add_argument("--res", choices=["480p", "720p"], default="480p", help="竖屏分辨率，默认480p")
    ap.add_argument("--seg_len", type=int, default=124, help="每段帧数(默认124≈5.17s)")
    ap.add_argument("--xfade", type=float, default=0.3, help="分段交叉淡入淡出时长(秒)，0=关闭")
    args = ap.parse_args()

    seg_dur = args.seg_len / 24.0
    segs = max(1, math.ceil(args.seconds / seg_dur))
    if args.res == "480p":
        W, H = 544, 960
    else:
        W, H = 736, 1280
        print("⚠️ 720p 需要 20G+ 显存，16G 可能 OOM")

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)

    total_run = seg_dur * segs
    print(f"古风新娘 V1：{segs} 段 × {seg_dur:.2f}s ≈ 目标{args.seconds}s（实际{total_run:.1f}s），{W}×{H} 9:16 竖屏")
    print(f"参考人物：{REF_IMG}；输出目录：{OUT_DIR}")

    seg_files = []
    prev_last_img = None   # LoadImage 用相对 input 目录的路径字符串
    for i in range(1, segs + 1):
        tag = f"xinniang_v1_s{i:02d}"
        if i == 1:
            prompt = BASE_PROMT
        else:
            prompt = ("the same woman with exactly the same face, hairstyle and red brocade "
                      "costume continuing her elegant pose" + SEG2_SUFFIX)
        seed = 20260905 + i
        wf = build_segment(prompt, prev_last_img, seed, f"xinniang_cosplay_v1/{tag}", W, H, args.seg_len, REF_IMG)
        r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
        pid = r.get("prompt_id")
        print(f"[{i}/{segs}] 段{tag} 已提交 pid={pid} (~{int(args.seg_len/24)}s)")
        if not wait_done(pid):
            print("  段失败，中止"); sys.exit(1)
        # 定位生成的 mp4
        cand = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                       if f.startswith(tag) and f.endswith(".mp4")])
        seg_files.append(cand[-1])
        print(f"  ✓ {os.path.basename(cand[-1])}")
        # 末帧存到 input 下，返回相对路径供下段 LoadImage
        last_png = extract_last_frame(cand[-1], os.path.join(TMP_DIR, f"{tag}_last.png"))
        prev_last_img = os.path.relpath(last_png, INPUT_ROOT).replace("\\", "/")
        print(f"  ↳ 抽取末帧供下段衔接: {prev_last_img}")

    # 拼接成片（多段用 xfade 交叉淡入淡出，弱化拼接跳帧）
    out_name = os.path.join(OUT_DIR, f"xinniang_9x16_{args.res}_{segs}seg_260905_v1.mp4")
    cd = args.xfade
    if segs > 1 and cd > 0:
        inputs = []
        for p in seg_files:
            inputs += ["-i", p]
        durs = [probe_duration(p) for p in seg_files]
        chain, prev, acc = [], "0:v", durs[0]
        for i in range(1, segs):
            off = max(0.0, acc - cd)
            chain.append(f"[{prev}][{i}:v]xfade=transition=fade:duration={cd}:offset={off:.3f}[vx{i}];")
            prev = f"vx{i}"
            acc = acc + durs[i] - cd
        fc = "".join(chain) + f"[{prev}]format=yuv420p[vout]"
        cmd = [FFMPEG, "-y"] + inputs + [
            "-filter_complex", fc, "-map", "[vout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", "24",
            "-movflags", "+faststart", out_name]
    else:
        listfile = os.path.join(OUT_DIR, "concat_list.txt")
        with open(listfile, "w", encoding="utf-8") as f:
            for p in seg_files:
                f.write(f"file '{p.replace(os.sep, '/')}'\n")
        cmd = [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", listfile, "-c", "copy", "-movflags", "+faststart", out_name]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print("--- ffmpeg 拼接 stderr 末尾 ---")
    print((r.stderr or "")[-800:])
    print("退出码:", r.returncode)

    if os.path.exists(out_name):
        probes = probe_streams(out_name)
        streams = probes.get("streams", [{}])
        s = streams[0]
        print(f"\n✅ 成片: {out_name}")
        print(f"   尺寸 {s.get('width')}×{s.get('height')} 编码 {s.get('codec_name')} 帧率 {s.get('r_frame_rate')}")
        print(f"   文件大小 ≈ {os.path.getsize(out_name)/1024/1024:.1f} MB")

if __name__ == '__main__':
    main()