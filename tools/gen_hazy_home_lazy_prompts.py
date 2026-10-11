#!/usr/bin/env python3
"""生成「慵懒居家长裙」系列英文写真提示词 100 条

主题固定要素：
  - 若隐若现 / 朦胧感 (sheer/veiled/hazy/soft-focus)
  - 全身构图 (full-body)
  - 冷白皮 (cool porcelain/cool fair skin)
  - 大长腿长裙 (long legs / flowing long maxi dress)
  - 居家场景 (home interior)
  - 慵懒感 (languid/lazy/relaxed mood)

输出: D:\\obsidian\\obsidian\\ComfyUI\\50写真批次prompts\\en\\hazy_home_lazy_100_en.json
"""
import json, itertools, random, os

random.seed(20260831)

def A(x):  # article helper
    return ("an " if x[0].lower() in "aeiou" else "a ") + x

LENSES = [
    "85mm portrait lens with shallow depth of field",
    "85mm portrait lens with soft focus",
    "105mm portrait lens with shallow depth of field",
    "50mm prime lens with soft ambient rendering",
    "70-200mm telephoto lens at 105mm with shallow depth of field",
]
COMP = [
    "rule of thirds composition",
    "centered composition with warm negative space",
    "relaxed editorial composition",
    "natural snug composition along window light",
]
RATIOS = [
    "2:3 ratio",
    "3:4 ratio",
    "2:3 ratio",
    "3:4 ratio",
    "4:5 ratio",
]

FACE_TYPES = [
    "an East Asian girl with big lively deer eyes, full lips, and an oxygen-like gentle vibe",
    "a fresh-faced East Asian adult woman with peach blossom eyes and a soft smooth jawline",
    "a cool-toned East Asian adult beauty with slightly upturned fox eyes and refined features",
    "an elegant East Asian adult woman with doe eyes and a relaxed soft gaze",
    "a youthful East Asian adult woman with bright eyes, natural brows, and a gentle calm expression",
    "a soft-featured East Asian adult woman with warm eyes and a lazy delicate look",
]
SKIN = [
    "cool porcelain skin with a subtle natural sheen",
    "fair cool-toned skin with delicate translucent brightness",
    "cool fair skin showing natural fine pores and realistic texture",
    "cool ivory skin with soft diffuse cheek reflection and restrained T-zone highlight",
]

DRESSES = [
    "a light gray ribbed knit maxi dress with a gently swaying hem",
    "a soft mauve modal long dress with wide relaxed sleeves",
    "an ivory waffle-knit long dress draping loosely from the shoulders",
    "a sage green fine-knit maxi dress with a side slit revealing one long leg",
    "a blush pink silk-blend cami maxi dress with a weightless skirt",
    "a slate blue long T-shirt dress hanging softly to the ankles",
    "a cream gauze-layered long dress that softly containers the body line",
    "a pale lilac textured knit maxi dress gathered loosely at the waist",
    "a muted terracotta ribbed maxi dress with elegant drape over the long legs",
    "a clean white cotton Terry maxi dress with flowing side panels",
]
DETAILS = [
    "a thin sheer chiffon wrap rising and falling with the skirt, faintly exposing the leg silhouette",
    "an unbuttoned long sheer gauze shirt layered over the dress, catching light at the edges",
    "a soft translucent tulle scarf slipped down to the elbows",
    "a delicate camisole line showing where the thin knit clings softly",
    "a blurred curtain between camera and subject, turning the long dress into a half-seen shape",
    "the fine knit fabric semi-transparent where window light passes through it from behind",
    "a lightweight linen cardigan hanging half off one shoulder",
    "loose wide sleeves that obscure the hands and add to the lazy mood",
    "the dress fabric lifting slightly as she moves, hazy lines of the long legs beneath",
]

SCENES = [
    "a quiet minimalist bedroom with ivory walls and unmade white linen bedding",
    "a sunlit living room with a low beige sofa and soft folding screens",
    "a warm minimalist apartment with a round rattan chair near a large fogged window",
    "a peaceful reading corner with a floor cushion, scattered books, and a half-drawn sheer curtain",
    "a simple modern bedroom with morning light, an off-white rug, and muted plaster walls",
    "a cozy window alcove with a padded bench and pale linen curtains",
    "a minimalist tatami room with a low wooden table and a cream floor cushion",
    "a relaxed home studio with a soft daybed, drifted fabric panels, and diffused daylight",
]
SUBSCENES = [
    "standing by the window", "sitting cross-legged on a floor cushion",
    "leaning lazily against a padded armrest", "reclining gently on a soft daybed",
    "sitting sideways on a deep wicker chair", "standing relaxed beside a tall bookshelf",
]

GAZES = [
    "with her gaze turned slightly away from the camera, expression calm and unfocused",
    "half-closing her eyes as the light warms her face",
    "looking at the camera with a slow relaxed gaze and a hint of softness",
    "looking out through the sheer curtain, her profile softened by the haze",
    "with heavy relaxed eyelids, looking slightly downward",
    "with a faint sleepy gaze and lips gently parted",
]

LIGHTS = [
    "Soft window light enters from one side, falling on her cheek, collarbone, and the flowing skirt, with the sheer fabric edges producing a gentle haze and soft highlight bloom",
    "Warm morning light comes through a white curtain, falling on her shoulder, arm, and the long folds of the dress, creating soft shadows and subtle glow around the sheer edges",
    "Diffused natural light fills the room from a large soft window, wrapping her long form in low contrast, with highlights on her cheek and the fine knit texture",
    "Gentle overcast daylight glows through a fogged window, cooling the room slightly and leaving a delicate rim light on her loose hair and along the fabric edges",
    "Late afternoon window light touches the side of her face and the top of her head, scattering faintly through gauze curtains and creating a soft dreamy flare",
]

SKINS = [
    "natural satin-finish foundation with a natural semi-matte base, restrained narrow highlight on the T-zone, soft diffuse cheek reflection and no oily sheen",
    "soft real skin texture with natural fine pores, faint downy hairs, and calm cool-toned shine only on the high points of the face",
]

NEG = ("No plastic skin, no continuous oily film across the face, no glossy wax effect, no over-smoothing, "
       "no over-retouch, no HDR, no cheap filters, no green-screen feel, no harsh backlight blowouts, no extra limbs, "
       "no finger deformities, no deformed facial features")

def build(i, rnd):
    lens = rnd.choice(LENSES); comp = rnd.choice(COMP); ratio = rnd.choice(RATIOS)
    face = rnd.choice(FACE_TYPES); skin = rnd.choice(SKIN)
    dress = rnd.choice(DRESSES); detail = rnd.choice(DETAILS)
    scene = rnd.choice(SCENES); sub = rnd.choice(SUBSCENES)
    gaze = rnd.choice(GAZES); light = rnd.choice(LIGHTS); skin_fin = rnd.choice(SKINS)
    neg = NEG

    core = (
        f"{ratio}, wide shot, 35mm lens, camera at a distance with breathing room around subject, {face}, "
        f"20-24 years old, {skin}, {skin_fin}"
    )
    body = (
        f"head-to-toe full body visible with space above head and below feet, long legs fully shown under a flowing maxi dress, {dress}, {detail}"
    )
    env = f"{scene}, {sub}, {gaze}"
    light = f"{light}."

    positive = (
        f"{core}\n"
        f"{ body }\n"
        f"{ env }\n"
        f"{ light }"
    )
    return {"id": i, "positive": positive, "negative": neg}


# 生成 100 条，控制多样性：轮转 5 组不同 seed 组合
out = []
rnd = random.Random(20260831)
seen = set()
i = 1
while len(out) < 100:
    # 随机抽组合，过滤过短重复
    key = (rnd.random(), tuple(sorted(rnd.choices(range(60), k=3))))
    if key in seen:
        continue
    seen.add(key)
    p = build(i, rnd)
    # 简单去重：完全相同的 positive 跳过
    if len([o for o in out if o['positive'] == p['positive']]) > 0:
        continue
    out.append(p)
    i += 1

OUT = r"D:\obsidian\obsidian\ComfyUI\50写真批次prompts\en\hazy_home_lazy_100_en.json"
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f"✅ {len(out)} 条已生成 → {OUT}")
print(f"平均长度: {sum(len(o['positive']) for o in out)//len(out)} chars")
# 打印前 2 条样例
for o in out[:2]:
    print("\n=== 样例 P%d ===" % o['id'])
    print(o['positive'])
    print("\nNegative:", o['negative'][:120])
