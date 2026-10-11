#!/usr/bin/env python3
"""雨夜古街女子 480p 5s - 金色亮片吊带裙+红灯笼+湿发."""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
import h3_xinniang_v1 as X
import uuid

X.REF_IMG = r"gemini_ken1/C02_BODY_FRONT.png"

RAIN_PROMPT = (
    "A beautiful young East Asian woman with the same face as the reference image, "
    "anime-inspired aesthetic but photorealistic, in an atmospheric rain-night ancient-"
    "street display. She wears a golden sequined spaghetti-strap mini dress with a deep V "
    "neckline, the tight fabric clinging to her curves, the metallic sequins catching and "
    "reflecting every wet light, side-hem cut short exposing her long legs. Nude sheer "
    "pantyhose and stiletto high heels. No other accessories, just the dress, the rain, "
    "and her. She is completely rain-soaked — long black curls of hair wet and clinging "
    "to the sides of her face, her neck, her shoulders, her back, the wet dress sticking "
    "to her body emphasising every curve. "
    "Her figure: ample full round plump breasts, firm uplifted bosom, deep cleavage "
    "visible at the V neckline, dramatically nipped-in hourglass waist, perky round "
    "peach-shaped ass under the tight dress, long slender perfectly straight legs, "
    "nine-head-tall proportions, visible collarbones, elegant swan neck. "
    "BEAT 1 (0-1s) SITTING ENJOYING RAIN: she sits on a wet stone step, both hands "
    "placed behind her on the step, head tilted back, eyes closed in pleasure, rain "
    "streaming down her face and neck and clavicle into her cleavage, golden sequins "
    "slicked wet. "
    "BEAT 2 (1-2s) RISING: she slowly rises to standing, opening her eyes, her gaze "
    "hazy dreamy seductive locked on the camera, wet strands of hair sticking to her "
    "cheeks, droplets running down her neck. "
    "BEAT 3 (2-3s) WALK + HAIR FLIP: she takes a step forward toward the camera, her "
    "right hand rising to brush aside the wet hair stuck on her face in a slow sensual "
    "motion, her waist gently twisting as she walks, hips swaying subtly, sequins "
    "shimmering with each move, one long leg crossing in front of the other. "
    "BEAT 4 (3-4s) WALL LEAN: she reaches a stone wall to one side, one hand flat "
    "against the wall bracing herself, the other hand lightly caressing her own chest "
    "above the fabric, body leaning back, spine arched, wet hair dripping, chest "
    "slightly heaving with breath, the camera capturing her full arched S-curve. "
    "BEAT 5 (4-5s) FINAL POWER POSE: she steps to face the camera fully, both hands "
    "on her hips, legs slightly apart in a confident stance, chest pushed forward, "
    "head lifted, a confident slightly teasing sultry smile on her lips, water "
    "droplets still clinging to her skin and sequins sparkling. "
    "Movement is slow sensual atmospheric — not a formal dance but a fluid sequence "
    "of seductive body poses, hair wet and swaying, sequins catching the lantern "
    "light, each beat transitioning smoothly. Camera angle: eye-level static framing, "
    "mid-to-full body, no camera movement. "
    "Night rain in an ancient Chinese old street background — wet cobblestones, "
    "traditional wooden buildings with upturned eaves, glowing red paper lanterns "
    "hanging along the street, reflections shimmering in the puddles, soft rain "
    "falling visibly through the lantern light, misty atmospheric haze, cinematic "
    "mood. Background music is a slow moody mysterious instrumental, atmospheric "
    "synth pads, no lyrics., anime-inspired aesthetic, photorealistic, ultra high "
    "detail, cinematic lighting, warm lantern glow against cool blue night rain, "
    "wet skin sheen, saturated colors, shallow depth of field, glossy porcelain "
    "wet skin, sequined dress sheen, hourglass figure, ample breasts, long straight "
    "legs, peach-shaped ass, seductive atmospheric poses, visible rain drops, wet "
    "hair clinging, no AI artifacts, no deformed hands, no extra limbs, clean composition"
)

OUT_DIR = r"D:\ai_projects\ComfyUI\output\rain_street_simple"
os.makedirs(OUT_DIR, exist_ok=True)

W, H, LENGTH = 544, 960, 124
t0 = time.time()
wf = X.build_segment(RAIN_PROMPT, None, 20260915, "rain_street_simple/s01", W, H, LENGTH, X.REF_IMG)
r = X.post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
pid = r.get("prompt_id")
print(f"提交 pid={pid}  ({W}×{H} × {LENGTH}帧 ≈5.17s, 28步)  雨夜古街")

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
