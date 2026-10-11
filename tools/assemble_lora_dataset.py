# -*- coding: utf-8 -*-
"""将生成的候选图组装进 my_dataset 并自动打标。
规则(训练指南): 标注只描述非特征元素(服装/环境/光线/构图), 不描述长相; 触发词由 yaml 的 trigger_word 自动加入。
候选图重命名为顺序名, 同名 .txt 即 caption。
"""
import os, shutil, glob, re

SRC = r"D:\ai_projects\ComfyUI\output\2026-09-08\asian_lora_dataset"
DST = r"D:\ai_projects\ai-toolkit\my_dataset"

# name -> 简短场景标注(english, 无面部描述, 自动带触发词)
CAPTIONS = {
    "01_face_neutral_sun": "close-up portrait in soft neutral daylight from a window, straight dark hair, calm neutral expression, creamy blurred background",
    "02_face_45_smile": "close-up three-quarter portrait with studio softbox lighting, warm gentle smile, low ponytail with wispy bangs, shallow depth of field",
    "03_face_profile": "profile headshot in warm diffused afternoon sunlight, hair tucked behind ear, muted warm beige background",
    "04_face_wind_candid": "outdoor tight portrait in a park, breeze blowing hair, golden bokeh from autumn leaves, natural makeup",
    "05_face_morning_bare": "intimate morning portrait in bed, bare-face dewy skin, soft morning light, white cotton duvet, casual hair",
    "06_face_lowangle_film": "low-angle close-up against clear blue sky, crisp sunlight, 35mm film aesthetic, subtle grain",
    "07_face_candid_mood": "candid close-up laughing in a cozy coffee shop, hand touching chin, warm indoor lighting",
    "08_half_cafe_sweater": "sitting at a rustic wooden cafe table, beige cashmere knit sweater, holding a warm ceramic coffee mug, rainy window, cafe bokeh",
    "09_half_white_shirt": "standing against light grey studio backdrop, crisp white button-up shirt with rolled sleeves, navy trousers, soft studio dual-light",
    "10_half_bookstore": "leaning against wooden bookshelves in an old library, gold-rimmed glasses, dark green cardigan, open hardcover book, warm tungsten light",
    "11_half_street_casual": "waist-up urban street scene in Tokyo, black leather jacket over grey hoodie, tote bag, overcast daylight, glass skyscrapers blurred",
    "12_half_kitchen": "bright modern kitchen, oversized striped boyfriend shirt, reaching for a glass, morning sun, scandinavian interior",
    "13_half_gallery": "modern art gallery, sleeveless black turtleneck dress, hair in a chignon, architectural spotlighting",
    "14_half_hoodie_sport": "waist-up on a running track bench, athletic grey cropped hoodie, high ponytail, sports water bottle, crisp afternoon light",
    "15_half_sakura": "standing under blooming pink cherry blossom trees, pastel lavender trench coat, diffused pastel tones, petal bokeh",
    "16_half_rain_neon": "rainy city street at night, clear vinyl umbrella, magenta and cyan neon reflections on wet pavement, beige trench coat",
    "17_half_sofa_lounging": "curled up on a plush cream sofa, hugging a soft throw pillow, grey lounge wear, reading a tablet, warm floor lamp",
    "18_half_coast_breeze": "seaside railing at sunset, white linen sundress, sun hat in hand, ocean waves, golden hour light",
    "19_full_crosswalk": "full-body striding across a city crosswalk, wide-leg denim jeans, white sneakers, cropped bomber jacket, sunny afternoon",
    "20_full_loft": "full-body fashion lookbook in a sunlit loft, emerald green pleated midi skirt, fitted cream knit top, polished concrete floors",
    "21_full_picnic": "full-body sitting cross-legged on a red gingham picnic blanket in a park, floral cotton dress, picnic basket, dappled sunlight",
    "22_full_beach_sunset": "full-body walking barefoot along the wet shoreline at twilight, terracotta maxi dress, sandals in hand, purple twilight sky",
    "23_full_steps_editorial": "full-body sitting on wide outdoor stone steps of a museum, navy blazer, tailored shorts, black loafers, urban editorial",
    "24_atmo_golden_rim": "cinematic medium portrait half-away facing the setting sun, intense golden rim lighting, lens flare, deep shadows",
    "25_atmo_candle": "low-key portrait at a dark wooden table lit by candlelight, one side lit one side in shadow, cinematic noir, vintage grain",
}

def main():
    os.makedirs(DST, exist_ok=True)
    files = sorted(glob.glob(os.path.join(SRC, "*.png")))
    print("found", len(files), "generated images")
    placed = 0
    for f in files:
        stem = os.path.basename(f)
        # ComfyUI SaveImage 输出名: <prefix>_<counter>_.png, prefix 形如 01_face_neutral_sun_a
        m = re.match(r"^(.+)_([ab])_\d+_\.png$", stem)
        if m and m.group(1) in CAPTIONS:
            base = m.group(1) + "_" + m.group(2)  # 如 01_face_neutral_sun_a
            dst = os.path.join(DST, base + ".png")
            shutil.copy2(f, dst)
            with open(os.path.join(DST, base + ".txt"), "w", encoding="utf-8") as fh:
                fh.write("A photo of ohwx woman, " + CAPTIONS[m.group(1)])
            placed += 1
        else:
            print("SKIP unmatched:", stem)
    print("placed", placed, "pairs into", DST)

if __name__ == "__main__":
    main()