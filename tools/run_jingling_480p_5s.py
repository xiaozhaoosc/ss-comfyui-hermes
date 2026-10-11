#!/usr/bin/env python3
"""华丽精灵造型 480p 5s 快速验证 — 复用 h3_xinniang_v1 管线，覆盖精灵提示词+PADDED参考图."""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
import h3_xinniang_v1 as X
import uuid
import json

# 覆盖参考图与输出
X.REF_IMG = r"gemini_ken1/C02_PADDED.png"
ELF_PROMPT = (
    "A beautiful young East Asian woman with the same face and figure as the reference image, "
    "gorgeous elfin warrior look blending classical oriental fantasy. Long straight glossy black "
    "hair flowing and swaying naturally with her movement. She wears a golden strapless bodice "
    "with an emerald-green gemstone pendant inlaid at the chest, metallic pauldron armor on "
    "her shoulders, golden arm rings, yellow tassel ornaments at her wrists, and a flowing "
    "red long dress with exquisite floral embroidery. Red lips, bright confident eyes, charming "
    "playful smile. She tilts her body slightly, hands gently and rhythmically moving in front "
    "of her chest to the beat, head swaying subtly to the music, confident flirtatious "
    "micro-expressions. Dreamy magical palace background with soft golden-pink glow. "
    "Background music is an upbeat EDM dance track sung by a bright female voice, fast strong "
    "rhythm., real photography, ultra high detail, cinematic lighting, saturated colors, "
    "shallow depth of field, high-class fantasy fashion showcase, glossy skin, no AI artifacts, "
    "no deformed hands, no extra limbs, clean composition"
)
OUT_DIR = r"D:\ai_projects\ComfyUI\output\jingling_simple"
os.makedirs(OUT_DIR, exist_ok=True)

# 480p 9:16, 5s ⇒ 124 帧 (H3 最小合法格点 17k+5)
W, H, LENGTH = 544, 960, 124

t0 = time.time()
wf = X.build_segment(ELF_PROMPT, None, 20260905, "jingling_simple/s01", W, H, LENGTH, X.REF_IMG)
r = X.post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
pid = r.get("prompt_id")
print(f"提交成功 pid={pid}  ({W}×{H} × {LENGTH}帧 ≈ {LENGTH/24:.2f}s, 28步)")
submit_t = time.time() - t0
print(f"提交耗时: {submit_t:.1f}s")

gen_t0 = time.time()
ok = X.wait_done(pid, timeout=3600, poll=15)
gen_elapsed = time.time() - gen_t0

if not ok:
    print("生成失败"); sys.exit(1)

cand = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
               if f.startswith("s01") and f.endswith(".mp4")])
if not cand:
    print("未找到输出 mp4"); sys.exit(1)
out = cand[-1]
print(f"\n✅ 生成完成: {out}")
print(f"   生成耗时: {gen_elapsed:.0f}s ({gen_elapsed/60:.1f} min)")
print(f"   文件大小: {os.path.getsize(out)/1024/1024:.2f} MB")

# 探测信息
probe = X.probe_streams(out)
if probe.get("streams"):
    s = probe["streams"][0]
    print(f"   {s.get('width')}×{s.get('height')} {s.get('codec_name')} {s.get('r_frame_rate')}")
print(f"   时长: {X.probe_duration(out):.2f}s")
