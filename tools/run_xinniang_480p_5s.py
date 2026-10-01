#!/usr/bin/env python3
"""古风新娘Cosplay 480p 5s - 用 C01 人脸参考 (与用户的描述匹配)"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
import h3_xinniang_v1 as X
import uuid

# 新娘造型 = 不用 PADDED, 直接用 C01 脸部特写(配 BASE_PROMT 的 catwalk pose 描述会自动出全身)
# 或 C02 (全身但无 padding)——用 C02 保证全身入镜
X.REF_IMG = r"gemini_ken1/C02_BODY_FRONT.png"

XINNIANG_PROMPT = (
    "A beautiful young East Asian woman with the same face as the reference image, "
    "in luxurious traditional Chinese bridal cosplay with a bold seductive touch. "
    "She wears a red strapless corset with intricate golden flower brocade on the chest "
    "and a deep low sweetheart neckline that boldly exposes her full round pale bosom — "
    "as she executes wild exaggerated dance moves, her ample soft cleavage keeps "
    "half-spilling out of the fabric unintentionally, creamy full curves bouncing "
    "dramatically with every athletic twist and leap. Matching red short skirt with "
    "tassel decorations flying wildly in all directions, flesh-toned thigh-high "
    "stockings with black straps on her outer thighs, magnificent red phoenix crown "
    "headdress with white flowers and beaded strings swinging violently side to side. "
    "Long glossy black hair whipping in wide full circles through the air like a dark "
    "whip, completely airborne during spins. "
    "Her legs are exceptionally long slender and shapely — rounded well-proportioned "
    "thighs tapering down to elegant calves, porcelain-white luminous skin, elongated "
    "leg line visually lengthened by high heels, legs making up more than half her "
    "total height, model-like proportions. Upper body remains unchanged from reference. "
    "EXAGGERATED DRAMATIC MOVEMENT — golf swing dance at maximum amplitude: she "
    "performs a wildly exaggerated golf swing dance with FULL-BODY ROTATION — torso "
    "twisting 90 degrees sharply left then right in a full athletic golf backswing "
    "rotation, both arms raised high overhead in a dramatic full backswing pose then "
    "sweeping down forcefully in a wide arcing follow-through that spins her entire "
    "body around 180 degrees, hips snapping sharply with each rotation, her long "
    "shapely legs leaping slightly off the ground with each spin, the red skirt flaring "
    "UP violently in huge swirling circles fully exposing her long rounded "
    "porcelain-white legs, long black hair fanning out in a wide horizontal halo "
    "during every spin. Movement is HUGE ATHLETIC EXAGGERATED — not subtle swaying but "
    "full-body dynamic rotation like a professional dancer mid-leap. "
    "Confident playful grin, eyes sparkling with wild energy, head whipping side to "
    "side with each rotation, micro-expressions shifting rapidly from fierce "
    "concentration to delighted laughter. Motion blur on arms skirt hem and hair tips "
    "from sheer speed. Camera angle slightly low to emphasize her long leg line. "
    "Dreamy luxurious traditional Chinese wedding chamber with warm golden light. "
    "Background music is a light cheerful Japanese female pop song, very fast strong "
    "driving beat, high-energy bouncy., real photography, ultra high detail, cinematic "
    "lighting, soft warm light, saturated colors, shallow depth of field, glossy "
    "porcelain skin, long slender shapely legs, upper body unchanged, strong dynamic "
    "motion blur on hair skirt and arms, frozen mid-spin action shot, no AI artifacts, "
    "no deformed hands, no extra limbs, clean composition"
)

OUT_DIR = r"D:\ai_projects\ComfyUI\output\xinniang_cosplay_simple"
os.makedirs(OUT_DIR, exist_ok=True)

W, H, LENGTH = 544, 960, 124
t0 = time.time()
wf = X.build_segment(XINNIANG_PROMPT, None, 20260911, "xinniang_cosplay_simple/s07_golf_longlegs", W, H, LENGTH, X.REF_IMG)
r = X.post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
pid = r.get("prompt_id")
print(f"提交 pid={pid}  ({W}×{H} × {LENGTH}帧 ≈5.17s, 28步)")

gen_t0 = time.time()
ok = X.wait_done(pid, timeout=3600, poll=15)
gen_elapsed = time.time() - gen_t0
if not ok:
    print("生成失败"); sys.exit(1)

cand = sorted([os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
               if f.startswith("s07_golf_longlegs") and f.endswith(".mp4")])
out = cand[-1]
print(f"\n✅ {out}")
print(f"   生成耗时: {gen_elapsed:.0f}s ({gen_elapsed/60:.1f} min)")
print(f"   大小: {os.path.getsize(out)/1024/1024:.2f}MB")
