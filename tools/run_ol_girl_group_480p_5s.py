#!/usr/bin/env python3
"""OL女团舞 480p 5s - 用 C01 面部参考 + 白色半透明衬衫+黑包臀短裙+双马尾 + 欢快女团舞(OK手势+V字)"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
import h3_xinniang_v1 as X
import uuid

X.REF_IMG = r"gemini_ken1/C01_FACE_FRONT.png"   # 半身特写，OL 是半身/中景更合适

OL_PROMPT = (
    "A beautiful young East Asian woman with the same face as the reference image, "
    "in a清纯 cute office-lady (OL) girl-group dance look. She wears a white semi-sheer "
    "long-sleeve blouse with a dark blue bow tie at the collar, the thin translucent "
    "fabric barely containing her ample full round breasts — a plump generous firm "
    "uplifted bosom, proudly prominent full curves pushing against the fabric, deep "
    "cleavage visible at the open collar, voluptuous and brimming. A black tight "
    "high-waist hip-hugging mini skirt wrapping her perky round peach-shaped ass, "
    "her lower body slender long tall and straight — long thin shapely legs in sheer "
    "black silk stockings (or fishnet/tight leggings option), leg line elongated and "
    "perfectly straight, black high heels further lengthening her calves. "
    "Her figure is the perfect S-curve hourglass: nine-head-tall proportions, "
    "a dramatically nipped-in hourglass waist highlighting her full bust above and "
    "peach-shaped ass below, visible collarbones, elegant swan neck, "
    "straight-angle ballerina shoulders, subtle mermaid-line abs and toned oblique "
    "lines at her slender waist, curved front-and-back silhouette. "
    "Her long black hair is tied in two cute high pigtails (twin tails) bouncing with "
    "every move. Delicate makeup, glossy red lips, sparkling playful eyes, a sweet "
    "bright smile throughout. "
    "BEAT 1 (0-1s) OPENING: she stands facing the camera, both hands crossed in front "
    "of her chest then opening gracefully outward, head swaying side to side with a "
    "sweet smile, pigtails bouncing, full breasts gently bouncing with each sway. "
    "BEAT 2 (1-3s) OK SIGN GROOVE: she alternates both hands making cute OK hand signs, "
    "bouncing them up and down rhythmically in front of her chest, body swaying "
    "rhythmically left and right to the music, hips gently twisting in her tight "
    "skirt, peach ass swaying, pigtails swinging wildly, full breasts bouncing with "
    "each hip beat, skirt hem bouncing high on her long stockinged thighs. "
    "BEAT 3 (3-4s) V-SIGN FINALE: both hands swiftly raise up high above her head, "
    "index and middle fingers spread in classic V-sign pose, elbows slightly bent, "
    "her chest pushed forward proudly with the raised arms, big bright smile directly "
    "at the camera, eyes sparkling, one long stockinged leg slightly bent with hip "
    "cocked out, hourglass silhouette on full display. "
    "BEAT 4 (4-5s) WINK & TONGUE OUT: hands come back down crossing in front of her "
    "chest again, she winks one eye at the camera and playfully sticks out her tongue, "
    "head tilted cute, pigtails settling, cleavage heaving slightly with a breathy "
    "laugh. "
    "Movement is energetic youthful rhythmic K-pop girl-group style — clear distinct "
    "phases, cute bouncy energy, rhythmic hip sways, pigtails flying with every head "
    "shake, full breasts bouncing gently with every beat. Camera angle slightly low "
    "at waist level to emphasize her long straight stockinged legs and hourglass "
    "figure. "
    "Bright modern minimalist white and pastel-pink bedroom/office background with "
    "soft window light. Background music is an upbeat electronic dance track with a "
    "strong 'ho ho lady' vocal sample hook, fast strong driving beat, cheerful K-pop "
    "girl-group energy., real photography, ultra high detail, cinematic lighting, soft "
    "bright daylight, saturated pastel colors, shallow depth of field, glossy skin, "
    "twin-tail pigtails, sweet girl-group dance, hourglass figure, ample full breasts, "
    "long straight legs in black stockings, peach-shaped ass, visible collarbones, "
    "swan neck, no AI artifacts, no deformed hands, no extra limbs, clean composition"
)

OUT_DIR = r"D:\ai_projects\ComfyUI\output\ol_girl_group_simple"
os.makedirs(OUT_DIR, exist_ok=True)

W, H, LENGTH = 544, 960, 124
t0 = time.time()
wf = X.build_segment(OL_PROMPT, None, 20260913, "ol_girl_group_simple/s02_hourglass", W, H, LENGTH, X.REF_IMG)
r = X.post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
pid = r.get("prompt_id")
print(f"提交 pid={pid}  ({W}×{H} × {LENGTH}帧 ≈5.17s, 28步)  OL女团舞")

gen_t0 = time.time()
ok = X.wait_done(pid, timeout=3600, poll=15)
gen_elapsed = time.time() - gen_t0
if not ok:
    print("生成失败"); sys.exit(1)

cand = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
               if f.startswith("s02_hourglass") and f.endswith(".mp4")])
out = cand[-1]
print(f"\n✅ {out}")
print(f"   生成耗时: {gen_elapsed:.0f}s ({gen_elapsed/60:.1f} min)")
print(f"   大小: {os.path.getsize(out)/1024/1024:.2f}MB")
