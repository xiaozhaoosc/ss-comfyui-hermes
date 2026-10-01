#!/usr/bin/env python3
"""H3 提示词生成器 + 通用生成流水线（本机 4060Ti 16G 定稿参数）

输入一份 spec.json（视频拆解的结构化结果），输出：
  1) 每段可直接投喂 H3 的完整英文 prompt（公共四段 + 该段 CAMERA/MOTION/AUDIO + 微表情锚点 + 内嵌负面）
  2) 归档 markdown → workflows/v1/prompts/<日期>_<名>.md
  3) 可断点续跑的 runner 脚本 → tools/h3_gen_<name>.py
  4) --run 时直接排队生成：分段链式（末帧作首帧）→ VHS 直混音频 → concat(-audio.mp4) → 抽帧

spec.json 字段（* 必填）:
{
  "name": "street_dance",              * 用作出片名/目录名
  "title": "自信女生的活力街舞",         * 归档标题
  "date": "2026-09-12",                * 归档日期(默认今天)
  "style": "…",                        * 公共 STYLE 段(英文，含调色/氛围/画风)
  "character": "…",                    * 公共 CHARACTER 段
  "outfit": "…",                       * 公共 OUTFIT 段
  "setting": "…",                      * 公共 SETTING 段
  "neg": "…",                          额外负面词(会拼进 Avoid:)
  "width": 544, "height": 960,         画幅(32 倍数; 默认竖版 544x960)
  "frames": 90,                        每段帧数(自动吸附到 17k+5)
  "seg_frames": [90,124],              可选:每段单独帧数(优先级高于 frames)
  "steps": 34, "shift_video": 14.0, "shift_audio": 3.5,
  "seed_base": 20261300,               段 i 的 seed = seed_base + i
  "ref_image": "gemini_ken1/C02_PADDED.png",   可选:第1段 first_frame(相对 input/)
  "style_mode": "real",                 real | donghua (仅用于归档标注)
  "segments": [                        * 逐段
    {"camera": "…", "motion": "…", "audio": "…", "micro": "…", "last_frame": "…(可选)"}
  ]
}
用法:
  python tools/h3_prompt_gen.py --spec specs/street_dance.json --build
  python tools/h3_prompt_gen.py --spec specs/street_dance.json --run
"""
import argparse, datetime, json, os, subprocess, sys, time, urllib.request, urllib.error, uuid

BASE = "http://127.0.0.1:8188"
COMFY = r"D:\ai_projects\ComfyUI"
INPUT_ROOT = os.path.join(COMFY, "input")
PROMPT_ARCHIVE = os.path.join(COMFY, "workflows", "v1", "prompts")
TOOLS = os.path.join(COMFY, "tools")
DEFAULT_NEG = ("distorted face, deformed hands, extra fingers, extra limbs, bad anatomy, melted limbs, "
               "blurry, watermark, text overlay, oversharpened, plastic skin, outfit change, face change")


def snap_frames(n):
    """帧数吸附到 H3 时长网格 17k+5"""
    k = max(1, round((n - 5) / 17))
    return 17 * k + 5


def build_prompts(spec):
    """返回 [(段号, 帧数, 完整prompt)]"""
    neg = "Avoid: " + (spec.get("neg") or "") + (" " if spec.get("neg") else "") + DEFAULT_NEG + "."
    common = "%s%s%s%s" % (spec["style"], spec["character"], spec["outfit"], spec["setting"])
    segs = spec["segments"]
    out = []
    for i, s in enumerate(segs, 1):
        f = spec.get("seg_frames", [])[i - 1] if i <= len(spec.get("seg_frames", [])) else spec.get("frames", 124)
        body = s["camera"] + s["motion"]
        if s.get("micro"):
            body += s["micro"] if s["micro"].rstrip().endswith(" ") else s["micro"] + " "
        body += s["audio"]
        out.append((i, snap_frames(f), common + body + neg))
    return out


def write_archive(spec, prompts, run_dir_rel):
    os.makedirs(PROMPT_ARCHIVE, exist_ok=True)
    date = spec.get("date") or datetime.date.today().isoformat()
    path = os.path.join(PROMPT_ARCHIVE, "%s_%s.md" % (date, spec["name"]))
    lines = ["# %s — H3 生成方案（%s）" % (spec.get("title", spec["name"]), date), "",
             "## 方案摘要", "",
             "| 项 | 值 |", "|---|---|",
             "| 画风 | %s |" % ("真人写实" if spec.get("style_mode", "real") == "real" else "3D 国漫"),
             "| 段数 | %d |" % len(prompts),
             "| 每段帧数 | %s |" % ", ".join(str(f) for _, f, _ in prompts),
             "| 总时长 | %.2fs |" % (sum(f for _, f, _ in prompts) / 24.0),
             "| 画幅 | %d×%d |" % (spec.get("width", 544), spec.get("height", 960)),
             "| 采样 | euler/simple cfg=1.0 steps=%s shift=%s:%s |" % (spec.get("steps", 34), spec.get("shift_video", 14.0), spec.get("shift_audio", 3.5)),
             "| 首帧锚定 | %s |" % (spec.get("ref_image") or "无（纯 t2va）"),
             "| 音频 | H3 原生同源生成 |",
             "| 输出目录 | %s |" % run_dir_rel, "",
             "## 公共模块（全片共用）", "", "```", spec["style"].strip(), "", spec["character"].strip(), "",
             spec["outfit"].strip(), "", spec["setting"].strip(), "```", "",
             "## 分段", ""]
    for i, f, p in prompts:
        s = spec["segments"][i - 1]
        lines += ["### 段 %d（%d 帧 ≈ %.2fs）" % (i, f, f / 24.0), "",
                  "- CAMERA: `%s`" % s["camera"].strip()[:200],
                  "- MOTION: `%s`" % s["motion"].strip()[:260],
                  "- AUDIO: `%s`" % s["audio"].strip()[:200],
                  "- 微表情锚点: %s" % (s.get("micro", "（未单独给，已含在 MOTION 内）")), ""]
    lines += ["## 每段完整 prompt（可直接投喂）", ""]
    for i, f, p in prompts:
        lines += ["**段 %d**", "```", p.strip(), "```", ""]
    lines += ["## 后期清单（H3 生成不了，需 ffmpeg/剪映）", "",
              "- 字幕 / 文案标签 / 平台水印", "- 卡点剪辑与二次变速", "- 转场特效（叠化/闪白/闪黑/缩放）",
              "- 若需替换成指定商用 BGM：以 `-audio.mp4` 为画面源重新混音", ""]
    open(path, "w", encoding="utf-8").write("\n".join(lines))
    print("✓ 归档:", path)
    return path


def write_runner(spec, prompts):
    name = spec["name"]
    path = os.path.join(TOOLS, "h3_gen_%s.py" % name)
    segs = json.dumps([{"camera": s["camera"], "motion": s["motion"], "audio": s["audio"], "micro": s.get("micro", "")}
                       for s in spec["segments"]], ensure_ascii=False, indent=1)
    code = '''#!/usr/bin/env python3
"""(自动生成) %s — H3 %d 段生成流水线
由 tools/h3_prompt_gen.py 生成，可直接改 PROMPTS 或重新生成。
用法: python tools/h3_gen_%s.py [--segs N]
"""
import argparse, json, os, subprocess, sys, time, urllib.request, urllib.error, uuid

BASE = "http://127.0.0.1:8188"
COMFY = r"%s"
INPUT_ROOT = os.path.join(COMFY, "input")
OUT_DIR = os.path.join(COMFY, "output", "%s")
PREFIX = "%s"
TMP_DIR = os.path.join(INPUT_ROOT, "%s_frames")
W, H = %d, %d
FRAMES = %s
STEPS, SHIFT_V, SHIFT_A = %s, %s, %s
SEED_BASE = %s
REF_IMG = %r
NAME = %r
NEG = "Avoid: " + (%r or "") + " %s."
COMMON = %r
SEG = %s
PROMPTS = [COMMON + s["camera"] + s["motion"] + ((s.get("micro") or "").rstrip() + " " if s.get("micro") else "") + s["audio"] + NEG for s in SEG]

''' % (spec.get("title", name), len(prompts), name, COMFY,
       os.path.join(spec.get("date", datetime.date.today().isoformat()), name).replace("\\", "/"),
       os.path.join(spec.get("date", datetime.date.today().isoformat()), name).replace("\\", "/"),
       name, spec.get("width", 544), spec.get("height", 960),
       json.dumps([f for _, f, _ in prompts]), spec.get("steps", 34), spec.get("shift_video", 14.0),
       spec.get("shift_audio", 3.5), spec.get("seed_base", 20261300), spec.get("ref_image"), name,
       spec.get("neg", ""), DEFAULT_NEG, spec["style"] + spec["character"] + spec["outfit"] + spec["setting"],
       segs)
    code += '''

def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=60).read())
    except urllib.error.HTTPError as e:
        print("HTTP %%d: %%s" %% (e.code, e.read().decode(errors="replace")[:800])); raise


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
        if el %% 120 < 20:
            print("   ⏱ %%dm%%02ds" %% (el // 60, el %% 60), flush=True)
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
    subprocess.run(["ffmpeg", "-y", "-sseof", "-0.3", "-i", mp4.replace("\\\\", "/"), "-q:v", "2", "-frames:v", "1",
                    "-pix_fmt", "yuvj420p", "-strict", "unofficial", png.replace("\\\\", "/")], check=True, capture_output=True)
    return png


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--segs", type=int, default=len(PROMPTS)); a = ap.parse_args()
    n = min(a.segs, len(PROMPTS))
    os.makedirs(OUT_DIR, exist_ok=True); os.makedirs(TMP_DIR, exist_ok=True)
    print("%%s: %%d 段 | %%dx%%d | frames=%%s | steps=%%d shift=%%s:%%s" %% (PREFIX, n, W, H, FRAMES, STEPS, SHIFT_V, SHIFT_A), flush=True)
    segf = {}
    for i in range(1, n + 1):
        tag = "%s_s%%02d" %% i
        c = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR) if f.startswith(tag) and f.endswith(".mp4") and "audio" not in f], key=os.path.getmtime)
        if c:
            segf[i] = c[-1]; print("[%%d/%%d] %%s 已存在,跳过" %% (i, n, tag), flush=True); continue
        LEN = FRAMES[i - 1] if isinstance(FRAMES, list) else FRAMES
        first = REF_IMG if i == 1 else os.path.relpath(extract_last(segf[i - 1], os.path.join(TMP_DIR, "%s_s%%02d_last.png" %% (i - 1))), INPUT_ROOT).replace("\\\\", "/")
        r = post("/prompt", {"prompt": build(PROMPTS[i - 1], SEED_BASE + i, PREFIX + "/" + tag, first), "client_id": str(uuid.uuid4())})
        pid = r.get("prompt_id"); print("[%%d/%%d] %%s pid=%%s" %% (i, n, tag, pid), flush=True)
        if not wait_done(pid):
            print("  失败"); sys.exit(1)
        c = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR) if f.startswith(tag) and f.endswith(".mp4") and "audio" not in f], key=os.path.getmtime)
        segf[i] = c[-1]; print("  ✓ %%s" %% os.path.basename(c[-1]), flush=True)
    ordered = [os.path.join(os.path.dirname(segf[i]), os.path.basename(segf[i]).replace(".mp4", "-audio.mp4")) if os.path.exists(os.path.join(os.path.dirname(segf[i]), os.path.basename(segf[i]).replace(".mp4", "-audio.mp4"))) else segf[i] for i in sorted(segf)]
    lf = os.path.join(OUT_DIR, "concat_list.txt")
    open(lf, "w", encoding="utf-8").write("".join("file '%%s'\\n" %% p.replace(os.sep, "/") for p in ordered))
    out = os.path.join(OUT_DIR, "%%s_%%dseg.mp4" %% (NAME, len(ordered)))
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lf.replace("\\\\", "/"), "-c", "copy", "-movflags", "+faststart", out.replace("\\\\", "/")], check=True, capture_output=True)
    print("✅ 成片:", out, flush=True)
    print("H3-GEN-DONE", flush=True)
'''
    code = code.replace("%%", "%")   # 第二段模板未走 % 格式化，这里统一还原字面量 %
    open(path, "w", encoding="utf-8").write(code)
    print("✓ runner:", path)
    return path


def run_pipeline(spec, prompts, out_dir, prefix, tmp_dir):
    """在当前进程内直接生成（分段链式 + 音频 + concat）"""
    os.makedirs(out_dir, exist_ok=True); os.makedirs(tmp_dir, exist_ok=True)
    W, H = spec.get("width", 544), spec.get("height", 960)
    steps, sv, sa = spec.get("steps", 34), spec.get("shift_video", 14.0), spec.get("shift_audio", 3.5)
    ref = spec.get("ref_image")
    segf = {}
    for i, frames, prompt in prompts:
        tag = "%s_s%02d" % (spec["name"], i)
        c = sorted([os.path.join(out_dir, f) for f in os.listdir(out_dir)
                    if f.startswith(tag) and f.endswith(".mp4") and "audio" not in f], key=os.path.getmtime)
        if c:
            segf[i] = c[-1]; print("[%d] %s 已存在,跳过" % (i, tag), flush=True); continue
        first = None
        if i == 1:
            first = ref
        else:
            png = os.path.join(tmp_dir, "%s_s%02d_last.png" % (spec["name"], i - 1))
            subprocess.run(["ffmpeg", "-y", "-sseof", "-0.3", "-i", segf[i - 1].replace("\\", "/"), "-q:v", "2",
                            "-frames:v", "1", "-pix_fmt", "yuvj420p", "-strict", "unofficial", png.replace("\\", "/")],
                           check=True, capture_output=True)
            first = os.path.relpath(png, INPUT_ROOT).replace("\\", "/")
        wf = build_wf(prompt, spec.get("seed_base", 20261300) + i, "%s/%s" % (prefix, tag), W, H, frames, steps, sv, sa, first)
        r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
        pid = r.get("prompt_id")
        print("[%d/%d] %s pid=%s frames=%d 首帧=%s" % (i, len(prompts), tag, pid, frames, first), flush=True)
        if not wait_done(pid):
            print("  %s 失败" % tag); sys.exit(1)
        c = sorted([os.path.join(out_dir, f) for f in os.listdir(out_dir)
                    if f.startswith(tag) and f.endswith(".mp4") and "audio" not in f], key=os.path.getmtime)
        segf[i] = c[-1]; print("  ✓ %s" % os.path.basename(c[-1]), flush=True)
    ordered = []
    for i in sorted(segf):
        a_ = os.path.join(os.path.dirname(segf[i]), os.path.basename(segf[i]).replace(".mp4", "-audio.mp4"))
        ordered.append(a_ if os.path.exists(a_) else segf[i])
    lf = os.path.join(out_dir, "concat_list.txt")
    open(lf, "w", encoding="utf-8").write("".join("file '%s'\n" % p.replace(os.sep, "/") for p in ordered))
    out = os.path.join(out_dir, "%s_%dseg.mp4" % (spec.get("title", spec["name"]), len(ordered)))
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lf.replace("\\", "/"), "-c", "copy",
                    "-movflags", "+faststart", out.replace("\\", "/")], check=True, capture_output=True)
    print("✅ 成片:", out, "%.1fMB" % (os.path.getsize(out) / 1024 / 1024), flush=True)
    pr = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries",
                         "format=duration:stream=codec_type,codec_name,sample_rate,channels", "-of", "json",
                         out.replace("\\", "/")], capture_output=True, encoding="utf-8")
    print(pr.stdout, flush=True)
    dur = sum(f for _, f, _ in prompts) / 24.0
    for t in [x for x in (0.5, dur * 0.33, dur * 0.66, dur - 0.5)]:
        fr = os.path.join(out_dir, "frame_%.1fs.jpg" % t)
        subprocess.run(["ffmpeg", "-y", "-ss", "%.2f" % t, "-i", out.replace("\\", "/"), "-frames:v", "1", "-q:v", "3",
                        "-pix_fmt", "yuvj420p", "-strict", "unofficial", fr.replace("\\", "/")], capture_output=True)
    print("H3-GEN-DONE", flush=True)
    return out


def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
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
                print("  执行出错:", json.dumps([m for k, m in st.get("messages", []) if k == "execution_error"][:1],
                                              ensure_ascii=False)[:400], flush=True)
                return False
        el = int(time.time() - t0)
        if el % 120 < 20:
            print("   ⏱ %dm%02ds" % (el // 60, el % 60), flush=True)
        time.sleep(20)
    return False


def build_wf(prompt, seed, prefix, W, H, length, steps, sv, sa, first_frame=None, last_frame=None):
    n = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors", "type": "minimax"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
        "5": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["1", 0], "shift_video": sv, "shift_audio": sa}},
        "6": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {"clip": ["2", 0], "vae": ["3", 0], "prompt": prompt,
                                                                "width": W, "height": H, "length": length}},
        "7": {"class_type": "KSampler", "inputs": {"model": ["5", 0], "seed": seed, "steps": steps, "cfg": 1.0,
                                                   "sampler_name": "euler", "scheduler": "simple",
                                                   "positive": ["6", 0], "negative": ["6", 0],
                                                   "latent_image": ["6", 1], "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["7", 0], "vae": ["4", 0]}},
        "10": {"class_type": "SaveAudio", "inputs": {"audio": ["9", 0], "filename_prefix": prefix + "_aud"}},
        "11": {"class_type": "VHS_VideoCombine", "inputs": {"images": ["8", 0], "audio": ["9", 0], "frame_rate": 24.0,
                                                            "loop_count": 0, "filename_prefix": prefix,
                                                            "format": "video/h264-mp4", "pingpong": False, "save_output": True}},
    }
    if first_frame:
        n["12"] = {"class_type": "LoadImage", "inputs": {"image": first_frame}}
        n["6"]["inputs"]["first_frame"] = ["12", 0]
    if last_frame:
        n["13"] = {"class_type": "LoadImage", "inputs": {"image": last_frame}}
        n["6"]["inputs"]["last_frame"] = ["13", 0]
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--build", action="store_true", help="只生成提示词+归档+runner")
    ap.add_argument("--run", action="store_true", help="生成并直接排队跑")
    a = ap.parse_args()
    spec = json.load(open(a.spec, encoding="utf-8"))
    for k in ("style", "character", "outfit", "setting", "segments"):
        assert k in spec, "spec 缺字段: " + k
    prompts = build_prompts(spec)
    date = spec.get("date") or datetime.date.today().isoformat()
    rel = os.path.join(date, spec["name"]).replace("\\", "/")
    out_dir = os.path.join(COMFY, "output", date, spec["name"])
    tmp_dir = os.path.join(INPUT_ROOT, spec["name"] + "_frames")
    print("=== %s | %d 段 | %s | 总时长 %.2fs ===" % (spec.get("title", spec["name"]), len(prompts),
          "/".join(str(f) for _, f, _ in prompts), sum(f for _, f, _ in prompts) / 24.0))
    for i, f, p in prompts:
        print("  段%d %d帧 %.2fs | %d 字符" % (i, f, f / 24.0, len(p)))
    write_archive(spec, prompts, rel)
    write_runner(spec, prompts)
    if a.run:
        run_pipeline(spec, prompts, out_dir, rel, tmp_dir)


if __name__ == "__main__":
    main()
