# -*- coding: utf-8 -*-
"""Prompt library derived from the user's brief: young woman, long black hair,
white camisole, soft indoor light, fresh & natural. Adapted per-model."""

# ---- shared negative prompt (SD1.5 family) ----
SD_NEG = ("lowres, bad anatomy, bad hands, text, error, missing fingers, "
          "extra digit, fewer digits, cropped, worst quality, low quality, "
          "normal quality, jpeg artifacts, signature, watermark, username, "
          "blurry, extra limbs, deformed, ugly, disfigured, nsfw, "
          "2girls, multiple girls, two people, twin, duplicate, cloned person, extra person")

# ---- Flux: abliterated base needs explicit clothing/safety anchoring ----
FLUX_NEG = ("nude, naked, topless, bottomless, exposed breasts, nipples, "
            "explicit, nsfw, lingerie, underwear, bikini, revealing clothes, "
            "deformed, bad anatomy, extra limbs, watermark, text")

# Clothing + framing anchor prepended to every Flux prompt to keep the brief
FLUX_ANCHOR = ("A fully dressed young East Asian woman with long black hair, "
               "wearing a white spaghetti-strap camisole top, modest everyday clothing, "
               "upper body portrait. ")

# ---- Z-Image Turbo: distilled, cfg=1.0 -> negative is INEFFECTIVE.
# Clothing/framing must therefore be carried entirely by the positive anchor.
ZIMAGE_NEG = ("lowres, bad anatomy, bad hands, extra limbs, deformed, "
              "watermark, text, jpeg artifacts, blurry")

ZIMAGE_ANCHOR = ("A fully dressed young East Asian woman with long black hair, "
                 "wearing a white spaghetti-strap camisole top, modest everyday clothing, "
                 "upper body portrait. ")

# ---- SD1.5 / SDXL style supplementary quality tags (positive) ----
SD_QUALITY = ("masterpiece, best quality, ultra detailed, photorealistic, "
              "8k uhd, dslr, soft lighting, film grain, sharp focus")

# Each scene: id, English SD prompt, Chinese note
SCENES = [
    {
        "id": "s01_camisole_touch_hair",
        "note": "白色吊带，手轻触耳边发丝，浅色虚化背景",
        "sd": ("1girl, solo, young woman, long black hair, flowing hair, "
               "white spaghetti strap top, camisole, bare shoulders, collarbone, "
               "hand touching hair near ear, looking at viewer, gentle smile, "
               "bright indoor, softly blurred background, soft light, "
               "fresh and serene atmosphere"),
        "flux": ("A close-up portrait of a young woman with long, black, flowing hair. "
                 "She is wearing a simple white spaghetti strap top, revealing her shoulders "
                 "and collarbone. Her right hand is gently touching her hair near her ear. "
                 "The background is softly blurred, creating a fresh and serene atmosphere."),
    },
    {
        "id": "s02_lying_on_sofa",
        "note": "侧卧浅色沙发，手托头，温柔微笑",
        "sd": ("1girl, solo, young woman, long black hair, white camisole, "
               "lying on side, on sofa, propping head with hand, gentle smile, "
               "looking at viewer, tender expression, cozy indoor, soft natural light, "
               "simple cozy room"),
        "flux": ("A young woman with long black hair, wearing a white spaghetti strap top, "
                 "lying on her side on a light-colored sofa. She is propping up her head with "
                 "her hands, smiling gently at the camera with a tender and tranquil expression. "
                 "The background is a simple and cozy indoor setting with soft, natural light."),
    },
    {
        "id": "s03_hugging_knees",
        "note": "抱膝托腮，甜美微笑，明亮室内",
        "sd": ("1girl, solo, young woman, long black hair, smooth hair, white camisole, "
               "hugging knees, chin resting on knees, sitting, sweet smile, looking at viewer, "
               "bright indoor, minimalist, fresh natural youthful, soft bright colors"),
        "flux": ("An upper-body close-up of a young woman with smooth, black long hair, "
                 "sitting in a bright indoor setting. She is wearing a minimalist white camisole, "
                 "hugging her knees with her chin resting on them, smiling sweetly at the camera. "
                 "The overall style is fresh, natural, and youthful, with a soft and bright color palette."),
    },
    {
        "id": "s04_flushed_selfie",
        "note": "特写自拍，脸颊微红，手托下巴",
        "sd": ("1girl, solo, young woman, long black hair, white camisole, close-up selfie, "
               "slightly flushed cheeks, chin resting on hand, tender gaze, serene expression, "
               "bright indoor, light-colored sofa, soft natural light, delicate skin"),
        "flux": ("A close-up selfie of a young woman with long black hair, wearing a simple "
                 "white spaghetti strap top. Her cheeks are slightly flushed, and she is gently "
                 "resting her chin on her hand, gazing tenderly at the camera with a serene "
                 "expression. The background is a bright indoor environment with a light-colored "
                 "sofa, bathed in soft, natural light that highlights her delicate skin."),
    },
    {
        "id": "s05_outdoor_knit_hat",
        "note": "户外蓝天地野，灰针织帽+浅灰短卫衣+黑高腰裙",
        "sd": ("1girl, solo, young woman, long hair down, covering face with one hand, "
               "gray knitted hat, yellow logo, light gray long-sleeve crop top hoodie, "
               "black high-waisted skirt, outdoor, blue sky, white clouds, open field, "
               "distant hills, fresh bright relaxed, blue and earth tones"),
        "flux": ("A young woman in an outdoor setting with a blue sky and white clouds. "
                 "She is wearing a gray knitted hat with a yellow logo, a light gray long-sleeve "
                 "crop top hoodie, and a black high-waisted skirt. She has long hair down and is "
                 "covering part of her face with one hand. The background features an open field "
                 "with distant hills. The overall atmosphere is fresh, bright, and relaxed, with "
                 "a color palette dominated by blue and earth tones."),
    },
    {
        "id": "s06_indoor_standing",
        "note": "室内站立，白吊带，优雅姿态，沙发背景",
        "sd": ("1girl, solo, young woman, long hair down, white camisole, standing, "
               "elegant posture, simply furnished room, sofa, furniture, soft light, "
               "warm tranquil atmosphere, fresh natural style"),
        "flux": ("A young woman with long hair is standing indoors, wearing a white camisole. "
                 "She has long hair down and an elegant posture. The background is a simply "
                 "furnished room with a sofa and other furniture. The light is soft, creating "
                 "a warm and tranquil atmosphere. The overall style is fresh and natural."),
    },
    {
        "id": "s07_hand_on_chest",
        "note": "手轻搭身前，米棕色调，窗外柔光",
        "sd": ("1girl, solo, young woman, long black hair, white camisole, "
               "hand gently on chest, cozy sunlit indoor, beige and brown tones, "
               "sofa, vases, picture frames, soft-focus background, bright harmonious cheerful"),
        "flux": ("A young woman with long black hair, wearing a white spaghetti strap top, "
                 "her hand gently placed on her chest. She is in a cozy, sunlit indoor setting "
                 "with a beige and brown tone, featuring a sofa, vases, and picture frames in the "
                 "soft-focused background. The overall atmosphere is bright, harmonious, and cheerful."),
    },
    {
        "id": "s08_tousle_hair",
        "note": "双手拨弄头发，明亮极简室内",
        "sd": ("1girl, solo, young woman, long black hair, white camisole, "
               "both hands tousling hair, minimalist bright indoor, sofa, decorative items, "
               "fresh natural feeling, soft light"),
        "flux": ("A young woman with long black hair, wearing a white spaghetti strap top, "
                 "using both hands to gently tousle her hair. The background is a minimalist, "
                 "bright indoor space with a sofa and decorative items, creating a fresh and "
                 "natural feeling."),
    },
]


# ---- 柔美金姿系列（2026-10-16 新增，见 prompt_assets/03）：自带着装锚点，3 个生图后端共用 ----
SCENES += [
    {
        "id": "rm01_morning_camisole",
        "note": "晨光窗前 · 白吊带 · 手抚锁骨",
        "anchor": ("An attractive young East Asian woman in a thin white ribbed spaghetti-strap "
                   "camisole that leaves her shoulders and collarbone bare, with soft grey lounge "
                   "trousers, upper body portrait. "),
        "sd": ("1girl, solo, young woman, long dark wavy hair, white ribbed spaghetti strap top, "
               "bare shoulders, collarbone, fingertips on collarbone, head tilted, half-closed eyes, "
               "sitting by window, sheer curtain, warm backlight, rim light, soft cinematic light"),
        "flux": ("A soft morning scene, an attractive young East Asian woman with long dark wavy hair "
                 "sitting by a bright window, wearing a thin white ribbed spaghetti-strap top; her "
                 "fingertips rest lightly on her collarbone, head tilted slightly, eyes half-lowered, "
                 "lips softly parted; sheer curtain diffusing warm backlight, gentle rim light on her "
                 "shoulder and neck, soft cinematic light, delicate skin texture, natural film grain, "
                 "photorealistic, high detail."),
    },
    {
        "id": "rm02_sofa_recline",
        "note": "沙发侧卧 · 回眸浅笑",
        "anchor": ("An attractive young East Asian woman in a fitted cream knit long-sleeve dress "
                   "that follows the curves of her body, barefoot, full body. "),
        "sd": ("1girl, solo, long dark hair, cream fitted knit dress, bare feet, lying on side, "
               "on sofa, propping head with hand, looking back over shoulder, half smile, "
               "cozy living room, warm afternoon sunlight, soft cinematic light, full body"),
        "flux": ("An attractive young East Asian woman with long dark hair lying on her side on a light "
                 "beige linen sofa, propping her head with one hand; she wears a fitted cream knit "
                 "long-sleeve dress, one knee softly bent; she looks back over her shoulder with a "
                 "warm, quietly confident half-smile; late-afternoon sunlight falls in long bands "
                 "across the sofa, cozy minimal living room, soft cinematic light, delicate skin "
                 "texture, natural film grain, photorealistic, full body."),
    },
    {
        "id": "rm03_mirror_satin",
        "note": "镜前束腰 · 真丝长裙 · 优雅转身",
        "anchor": ("An attractive young East Asian woman in a floor-length champagne satin slip dress "
                   "with a low draped cowl neck and a bare back, hair pinned up, full body. "),
        "sd": ("1girl, solo, hair pinned up, champagne satin floor length slip dress, cowl neck, "
               "hand on waist, lifting hem, graceful turn, looking back over shoulder, standing at "
               "floor mirror, warm minimal bedroom, lamp light, full body"),
        "flux": ("An elegant young East Asian woman standing in front of a tall floor mirror in a warm "
                 "minimalist bedroom, wearing a floor-length champagne satin slip dress with a soft "
                 "draped cowl neck; one hand rests on her own waistline, the other lifts the hem a few "
                 "centimetres to step; her body turns in a graceful three-quarter twist, chin over her "
                 "shoulder toward the mirror; warm lamp light, gentle fabric sheen, elegant posture, "
                 "soft cinematic light, delicate skin texture, natural film grain, photorealistic, "
                 "full body."),
    },
    {
        "id": "rm04_backlit_linen",
        "note": "落地窗逆光 · 长裙轻扬 · 剪影轮廓",
        "anchor": ("An attractive young East Asian woman in a flowing off-white linen maxi dress with "
                   "a slim sleeveless bodice that leaves her shoulders bare, full body. "),
        "sd": ("1girl, solo, loose long hair, off-white linen maxi dress, sleeveless fitted bodice, "
               "dress lifting in breeze, backlit, rim light, floor to ceiling window, bright airy "
               "interior, profile silhouette, full body"),
        "flux": ("A striking backlit full-body scene: an attractive young East Asian woman with loose "
                 "long hair stands at a floor-to-ceiling window in a flowing off-white linen maxi "
                 "dress; a soft breeze lifts the hem and the fabric folds, her profile and the curve "
                 "of her waist read clearly against the bright light; strong rim light rims her hair "
                 "and shoulders, large bright interior with airy haze, elegant and serene, soft "
                 "cinematic light, delicate skin texture, natural film grain, photorealistic, full body."),
    },
    {
        "id": "rm05_bed_stretch",
        "note": "床榻抱枕 · 慵懒舒展 · 柔光",
        "anchor": ("An attractive young East Asian woman in a soft oversized cotton shirt unbuttoned "
                   "at the collar over light shorts, barefoot, full body. "),
        "sd": ("1girl, solo, oversized cotton shirt unbuttoned at collar, light shorts, barefoot, hugging plush "
               "cushion, kneeling on bed, relaxed stretch, eyes closed, content smile, white bed, "
               "lace curtain, morning light, intimate, full body"),
        "flux": ("An attractive young East Asian woman kneeling and settling back on a crisp white bed, "
                 "hugging a large plush cushion against her chest with both arms, wearing an oversized "
                 "soft cotton shirt buttoned up and light shorts; her back arches gently in a relaxed "
                 "stretch, head resting on the cushion, eyes softly closed with a contented smile; "
                 "morning light through lace curtains falls in a soft pattern across the linen, "
                 "intimate and serene, soft cinematic light, delicate skin texture, natural film "
                 "grain, photorealistic, full body."),
    },
    {
        "id": "rm06_bathrobe_damp",
        "note": "浴后 · 湿发 · 浴袍半拢（备用）",
        "anchor": ("An attractive young East Asian woman in a white terry bathrobe loosely tied at the "
                   "waist, bare shoulders, damp hair, upper body portrait. "),
        "sd": ("1girl, solo, damp dark hair, flushed cheeks, white terry bathrobe loosely tied, "
               "bare shoulders, lifting wet hair strand, warm bathroom, steam haze, condensation "
               "mirror, soft cinematic light, upper body portrait"),
        "flux": ("An attractive young East Asian woman just out of a shower, damp dark hair clinging in "
                 "soft strands to her temples, cheeks lightly flushed; she is wrapped in a thick white "
                 "terry bathrobe tied firmly at the waist, holding the collar closed with one hand, the "
                 "other hand lifting a strand of wet hair away from her cheek; a warm-lit bathroom with "
                 "soft steam haze and a mirror with a little condensation, soft cinematic light, "
                 "delicate skin texture, natural film grain, photorealistic, upper body portrait."),
    },
]


def _anchor(scene, default):
    """场景自带 anchor 时用它（柔美金姿系列各自需要贴身的着装锚点），否则用默认档。"""
    return scene.get("anchor") or default


def sd_positive(scene, extra=SD_QUALITY):
    return extra + ", " + scene["sd"]


def zimage_positive(scene, extra=None):
    """Z-Image Turbo takes natural-language prose. cfg=1.0 means the negative
    prompt has no effect, so the clothing anchor MUST be in the positive."""
    return _anchor(scene, ZIMAGE_ANCHOR) + scene["flux"]


def flux_positive(scene):
    return _anchor(scene, FLUX_ANCHOR) + scene["flux"]
