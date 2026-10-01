# -*- coding: utf-8 -*-
"""Build comparison sheets. Usage: python _pc_sheet.py <mode>
 mode=sd15  -> 3 SD1.5 models
 mode=all   -> include flux
"""
import os, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_T = {}


def _run(models, scenes, outname, title):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("PIL MISSING - pip install pillow"); return None
    BASE = r"D:\ai_projects\ComfyUI"
    OUT = os.path.join(BASE, "output", "prompt_compare")
    SHEET = os.path.join(OUT, "sheets"); os.makedirs(SHEET, exist_ok=True)

    def find_img(model, scene):
        for p in [os.path.join(BASE, "output", "pc_%s_%s_*.png" % (model, scene)),
                  os.path.join(OUT, model, "pc_%s_%s_*.png" % (model, scene))]:
            hits = sorted(glob.glob(p))
            if hits: return hits[-1]
        return None

    def font(sz):
        for n in ["msyh.ttc", "msyhbd.ttc", "simhei.ttf", "arial.ttf"]:
            try: return ImageFont.truetype(n, sz)
            except Exception: pass
        return ImageFont.load_default()

    TH, PAD, HDR, LBL = 400, 8, 72, 200
    cells = [[find_img(m, s) for s in scenes] for m, _ in models]
    if not any(any(r) for r in cells):
        print("no images found for", outname); return None
    tw = 300
    for r in cells:
        for p in r:
            if p:
                with Image.open(p) as im: tw = int(im.width * TH / im.height)
                break
        else: continue
        break
    cols = len(scenes); rows = len(models)
    W = LBL + cols * (tw + PAD) + PAD
    H = HDR + rows * (TH + PAD + 20) + PAD + 30
    sh = Image.new("RGB", (W, H), (250, 250, 252)); d = ImageDraw.Draw(sh)
    d.text((PAD + 4, 12), title, font=font(25), fill=(18, 18, 28))
    d.text((PAD + 4, 46), "列 = 场景（对应用户提示词）    行 = 模型 / 采样器",
           font=font(15), fill=(110, 110, 125))
    for ci, s in enumerate(scenes):
        d.text((LBL + ci * (tw + PAD) + PAD, HDR - 18), s.split("_")[0],
               font=font(14), fill=(90, 90, 105))
    y = HDR
    for ri, (m, label) in enumerate(models):
        d.text((PAD + 4, y + TH // 2 - 12), label, font=font(18), fill=(30, 30, 45))
        for ci, p in enumerate(cells[ri]):
            x = LBL + ci * (tw + PAD) + PAD
            if p:
                with Image.open(p) as im:
                    im = im.convert("RGB")
                    nw = int(im.width * TH / im.height)
                    sh.paste(im.resize((nw, TH), Image.LANCZOS), (x, y))
                d.rectangle([x, y, x + tw, y + TH], outline=(215, 215, 225))
            else:
                d.rectangle([x, y, x + tw, y + TH], fill=(240, 240, 244),
                            outline=(215, 215, 225))
                d.text((x + 8, y + TH // 2), "n/a", font=font(14), fill=(160, 160, 170))
        y += TH + PAD + 20
    out = os.path.join(SHEET, outname)
    sh.save(out, quality=92)
    print("SAVED:", out, sh.size)
    return out


SCENES = ["s01_camisole_touch_hair", "s02_lying_on_sofa", "s03_hugging_knees",
          "s04_flushed_selfie", "s05_outdoor_knit_hat", "s06_indoor_standing",
          "s07_hand_on_chest", "s08_tousle_hair"]

SD15 = [("majicmix", "majicmixRealistic_v7  (SD1.5 写实)"),
        ("counterfeit", "Counterfeit-V3.0  (SD1.5 动漫)"),
        ("aom3", "AOM3A3_orangemixs  (SD1.5 动漫)")]
ALL = SD15 + [("flux_dev_fp8", "Flux.1-dev FP8  (流匹配)")]

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "sd15"
    if mode in ("sd15", "all"):
        _run(SD15, SCENES, "compare_sd15_models.png",
             "SD1.5 三模型对比 — 同一组提示词")
    if mode == "all":
        _run(ALL, SCENES, "compare_all_models.png",
             "ComfyUI 四模型对比 — 同一组提示词（SD1.5×3 + Flux Dev）")
