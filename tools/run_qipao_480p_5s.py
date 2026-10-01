#!/usr/bin/env python3
"""旗袍舞动 480p 5s - 白色挂脖改良旗袍+黑丝+夜景酒吧."""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
import h3_xinniang_v1 as X
import uuid

X.REF_IMG = r"gemini_ken1/C02_BODY_FRONT.png"   # 全身照供旗袍全身构图

QIPAO_PROMPT = (
    "A beautiful young East Asian woman with the same face as the reference image, "
    "anime-inspired aesthetic but photorealistic, in a seductive qipao dance. "
    "She wears a white halter-neck modern cheongsam with a high neckline and delicate "
    "pink floral prints across the fabric, side slit running high up the thigh "
    "exposing her long legs, the form-fitting silk clinging to her curves. She pairs "
    "it with sheer black silk stockings and black high heels. "
    "Her figure: ample full round breasts pushing up the halter neckline, plump firm "
    "uplifted bosom with deep cleavage, dramatically nipped-in hourglass waist, "
    "perky round peach-shaped ass under the tight qipao, long slender perfectly "
    "straight legs, nine-head-tall proportions, visible collarbones, elegant swan neck, "
    "straight-angle shoulders, subtle mermaid-line abs. S-curve silhouette front and back. "
    "Long glossy jet-black straight hair flowing down past her waist, whipping and "
    "dancing with every body sway. Delicate sparkling earrings catching the light. "
    "BEAT 1 (0-1s) OPENING POSE: she stands with both hands on her hips, body tilted "
    "slightly back, looking at the camera with dreamy languid slightly hazy eyes, a "
    "cool aloof almost arrogant expression, long black hair cascading over one shoulder. "
    "BEAT 2 (1-2s) HAND CARESSES FACE: her right hand rises gracefully to gently caress "
    "her own cheek and jawline, while her left hand waves rhythmically in front of her "
    "chest in soft undulating motions, fingers curling delicately, hair swaying. "
    "BEAT 3 (2-4s) HIP + WAIST SWAY: her hips and waist begin wide elastic side-to-side "
    "twists in rhythm with the beat, smooth and fluid with a springy quality, her tight "
    "qipao riding up slightly with each sway exposing more of her black-stockinged "
    "thighs, her breasts bouncing gently with each hip rotation, hair fanning side to side. "
    "BEAT 4 (4-5s) HEAD + EXPRESSION: her head sways playfully following the body "
    "rhythm, long hair flying, her expression shifting from cold seductive to relaxed "
    "to a playful pouty flirty smile at the very end, a soft teasing smirk on her lips. "
    "Movement is fluid languid seductive — elastic waist sways,弹性 rhythmic hip twists, "
    "hair dancing with every sway, breasts and skirt responding to every motion. "
    "Camera angle eye-level with slight low-tilt emphasizing leg line, static framing "
    "on her mid-to-full body. "
    "Night bar background with warm ambient neon lights in pink gold and deep blue, "
    "bokeh lights flickering softly behind her, blurred bottles on a bar counter, "
    "intimate seductive nightclub atmosphere. Background music is an energetic EDM "
    "dance track with a fast strong driving beat and clear drum hits, perfect for "
    "rhythmic sensual dancing., anime-inspired aesthetic, photorealistic, ultra high "
    "detail, cinematic lighting, warm neon glow, saturated colors, shallow depth of "
    "field, glossy porcelain skin, qipao silk sheen, hourglass figure, ample breasts, "
    "long straight legs in black stockings, peach-shaped ass, seductive dance, "
    "no AI artifacts, no deformed hands, no extra limbs, clean composition"
)

OUT_DIR = r"D:\ai_projects\ComfyUI\output\qipao_dance_simple"
os.makedirs(OUT_DIR, exist_ok=True)

W, H, LENGTH = 544, 960, 124
t0 = time.time()
wf = X.build_segment(QIPAO_PROMPT, None, 20260914, "qipao_dance_simple/s01", W, H, LENGTH, X.REF_IMG)
r = X.post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
pid = r.get("prompt_id")
print(f"提交 pid={pid}  ({W}×{H} × {LENGTH}帧 ≈5.17s, 28步)  旗袍舞动")

gen_t0 = time.time()
ok = X.wait_done(pid, timeout=3600, poll=15)
gen_elapsed = time.time() - gen_t0
if not ok:
    print("生成失败"); sys.exit(1)

cand = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
               if f.startswith("s01") and f.endswith(".mp4")])
out = cand[-1]
print(f"\n✅ {out}")
print(f"   生成耗时: {gen_elapsed:.0f}s ({gen_elapsed/60:.1f} min)")
print(f"   大小: {os.path.getsize(out)/1024/1024:.2f}MB")
