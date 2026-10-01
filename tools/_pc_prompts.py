# -*- coding: utf-8 -*-
"""Prompt library derived from the user's brief: young woman, long black hair,
white camisole, soft indoor light, fresh & natural. Adapted per-model."""

# ---- shared negative prompt (SD1.5 family) ----
SD_NEG = ("lowres, bad anatomy, bad hands, text, error, missing fingers, "
          "extra digit, fewer digits, cropped, worst quality, low quality, "
          "normal quality, jpeg artifacts, signature, watermark, username, "
          "blurry, extra limbs, deformed, ugly, disfigured, nsfw")

# ---- Flux: abliterated base needs explicit clothing/safety anchoring ----
FLUX_NEG = ("nude, naked, topless, bottomless, exposed breasts, nipples, "
            "explicit, nsfw, lingerie, underwear, bikini, revealing clothes, "
            "deformed, bad anatomy, extra limbs, watermark, text")

# Clothing + framing anchor prepended to every Flux prompt to keep the brief
FLUX_ANCHOR = ("A fully dressed young East Asian woman with long black hair, "
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


def sd_positive(scene, extra=SD_QUALITY):
    return extra + ", " + scene["sd"]
