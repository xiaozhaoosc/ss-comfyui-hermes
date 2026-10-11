#!/usr/bin/env python3
"""变装走秀 - A 白西装黑裙 → B 红色金花旗袍（双段独立，中间闪斩转场）

走秀路线：平视机位 + 全身像为主 + 中央偏右构图 + 三分法 + 背景纵深
造型 A：白色短款西装外套 + 黑色高开叉吊带连衣裙 + 金色简约项链
造型 B：红色旗袍式长裙 + 金色花纹 + 高开叉 + 同款金项链
发型：黑色长直发披散（柔顺垂坠感）
妆容：纤细眉 + 轻烟熏眼妆 + 饱满唇
音频：节奏感强烈的电子舞曲

两段独立用同一参考图 C02_PADDED 起手（不用末帧链式），
中间 ffmpeg 后期闪斩转场（快速颜色闪烁 + 白闪 cut）
采样参数：组2 锐化版（steps=34, shift_video=14.0, shift_audio=3.5）
"""
import json, urllib.request, uuid, time, os, sys, subprocess, math, argparse

BASE = "http://127.0.0.1:8188"
FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
FFPROBE = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffprobe.exe"
INPUT_ROOT = r"D:\ai_projects\ComfyUI\input"
OUT_DIR = r"D:\ai_projects\ComfyUI\output\browse_show"
REF_IMG = "gemini_ken1/C02_PADDED.png"

STYLE_A = (
    "realistic cinematic photography, ultra high detail, fresh bright clean lighting, "
    "cool modern color palette with soft highlights, shallow depth of field, film "
    "grain, glossy healthy skin. "
)
STYLE_B = (
    "realistic cinematic photography, ultra high detail, warm rich saturated lighting, "
    "deep crimson and gold color palette with dramatic warm highlights, shallow depth "
    "of field, film grain, glossy healthy skin. "
)

CHARACTER_BASE = (
    "The same young East Asian woman as the reference image, same face and body, "
    "delicate elegant features, slim-shaped eyebrows, light smoky eye makeup, full "
    "lips, porcelain-fair luminous skin. Long straight black hair flowing down her "
    "back with silky smooth texture and perfect drape. She has a statuesque hourglass "
    "figure with nine-heads-tall proportion: long slender straight legs, cinched "
    "waist flowing into softly rounded hips, graceful swan-like neck, clear "
    "collarbones, poised upright upper body. A simple gold pendant necklace sits "
    "against her collarbone. "
)

OUTFIT_A = (
    "Outfit A: a crisp white cropped blazer jacket over a form-fitting black "
    "spaghetti-strap slip dress with a daring high slit up one side revealing the "
    "leg curve, black pointed high heels. "
)
OUTFIT_B = (
    "Outfit B: a floor-length red qipao-style gown adorned with intricate gold floral "
    "embroidery, traditional mandarin collar with ornate gold trim, one side slit "
    "high up to mid-thigh revealing the leg, elegant red silk clinging to every curve, "
    "matching red or gold heels. "
)

SETTING_A = (
    "A bright modern fashion runway: white glossy floor, soft white lights, blurred "
    "modern cityscape in the background, cool high-key atmosphere, narrow depth of "
    "field creating bokeh. "
)
SETTING_B = (
    "A dramatic warm-red Oriental runway: deep crimson curtains, golden lantern "
    "accents, rich warm amber spotlight, blurred impression of a classical Chinese "
    "palace interior in the background, glamorous cinematic depth. "
)

CAMERA = (
    "Fixed camera at eye-level, full body centered slightly right of frame following "
    "the rule of thirds, enough background depth behind her to suggest runway depth. "
)

WALK = (
    "She walks confidently down the runway toward the camera with perfect runway "
    "posture: chin up, shoulders relaxed back, hips swaying subtly with each step, "
    "core engaged, arms swinging naturally at her sides or one hand lightly grazing "
    "the dress slit, decisive steady strides on pointed heels. She smiles gently "
    "with calm magnetic confidence, eyes locked forward, occasionally casting a "
    "captivating sidelong glance at the camera with a hint of allure. Slow-mo feel "
    "on leg reveal through the slit. "
)

AUDIO = (
    " High-energy electronic dance music with a strong punchy beat, deep bass, sharp "
    "synthesizer hits, tempo matching her stride, no vocals — pure driving EDM "
    "runway music."
)

NEG = (
    "anime, cartoon, 3D render, illustration, distorted face, deformed hands, "
    "extra fingers, extra limbs, bad anatomy, melted limbs, blurry, watermark, "
    "text overlay, oversharpened, dull skin, bent legs, broken heels"
)

SEG_PROMPTS = {
    "A_outfit": STYLE_A + CHARACTER_BASE + OUTFIT_A + SETTING_A + CAMERA + WALK + AUDIO + " Avoid: " + NEG,
    "B_outfit": STYLE_B + CHARACTER_BASE + OUTFIT_B + SETTING_B + CAMERA + WALK + AUDIO + " Avoid: " + NEG,
}

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

def probe_duration(mp4):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", mp4], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 5.17

def flash_merge(a_mp4, b_mp4, out_mp4, flash_sec=0.15, fps=24):
    """A→闪黑→闪白→B (light-flash 切换 0.3s)"""
    flash_frames = int(flash_sec * fps)
    fc = (
        f"[0:v]format=yuv420p[va];"
        f"color=black:size=544x960:duration={flash_sec}:rate={fps}[black];"
        f"color=white:size=544x960:duration={flash_sec}:rate={fps}[white];"
        f"[va][black][white][1:v]concat=n=4:v=1:a=0[vout];"
        f"[vout]format=yuv420p[vfinal]"
    )
    cmd = [FFMPEG, "-y",
           "-i", a_mp4, "-i", b_mp4,
           "-filter_complex", fc,
           "-map", "[vfinal]",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", str(fps),
           "-movflags", "+faststart", out_mp4]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0 and os.path.exists(out_mp4), r

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seg_len", type=int, default=124)
    ap.add_argument("--steps", type=int, default=34)
    ap.add_argument("--shift_video", type=float, default=14.0)
    ap.add_argument("--shift_audio", type=float, default=3.5)
    ap.add_argument("--flash_sec", type=float, default=0.15, help="单边 0.15s 黑0.15白=总0.3s 闪斩")
    args = ap.parse_args()
    W, H = 544, 960
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"变装走秀 A白+B红 双段 (steps={args.steps}, shift={args.shift_video}/{args.shift_audio})")
    print(f"闪斩转场 {args.flash_sec*2:.2f}s（黑+白）")

    files = {}
    for k in ["A_outfit", "B_outfit"]:
        tag = f"browse_{k}"
        cands = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                        if f.startswith(tag) and f.endswith(".mp4")])
        if cands:
            files[k] = cands[-1]; print(f"[{k}] 已存在，跳过"); continue
        seed = 20261210 + (1 if k == "A_outfit" else 2)
        wf = build_segment(SEG_PROMPTS[k], None, seed, f"browse_show/{tag}",
                           W, H, args.seg_len, REF_IMG,
                           steps=args.steps, shift_video=args.shift_video,
                           shift_audio=args.shift_audio)
        r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
        pid = r.get("prompt_id")
        print(f"[{k}] {tag} pid={pid} (首帧=C02_PADDED)", flush=True)
        if not wait_done(pid):
            print(f"  {k} 失败"); sys.exit(1)
        cands = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                        if f.startswith(tag) and f.endswith(".mp4")], key=os.path.getmtime)
        files[k] = cands[-1]
        print(f"  ✓ {os.path.basename(cands[-1])}", flush=True)

    out_name = os.path.join(OUT_DIR, "browse_show_9x16_A_B_flash_260906.mp4")
    ok, r = flash_merge(files["A_outfit"], files["B_outfit"], out_name, args.flash_sec)
    print("闪斩拼接退出码:", r.returncode)
    if not ok:
        print((r.stderr or "")[-800:])
        print("❌ 拼接失败"); sys.exit(1)
    print(f"\n✅ 成片: {out_name} ({os.path.getsize(out_name)/1024/1024:.1f} MB)")

if __name__ == '__main__':
    main()
