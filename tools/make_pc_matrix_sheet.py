# -*- coding: utf-8 -*-
"""把多模型矩阵产物拼成对比图：全景图 + 中心微距图。

行 = 模型，列 = 场景。输出到 output/YYYY-MM-DD_wb/_eval/。
用法：python tools/make_pc_matrix_sheet.py
"""
import os, io, sys, glob, time

BASE = r"D:\ai_projects\ComfyUI"
OUT_ROOT = os.path.join(BASE, "output")
EVAL_DIR = os.path.join(OUT_ROOT, time.strftime("%Y-%m-%d") + "_wb", "_eval")

MODELS = [
    ("z_image_turbo", "Z-Image Turbo 8步"),
    ("flux_dev_fp8", "Flux.1 Dev FP8"),
    ("sdxl_realvis", "SDXL RealVisXL v4.0"),
    ("juggernaut", "SDXL Juggernaut v9"),
]
SCENES = ["s01_camisole_touch_hair", "s02_lying_on_sofa", "s03_hugging_knees",
          "s04_flushed_selfie", "s05_outdoor_knit_hat", "s06_indoor_standing",
          "s07_hand_on_chest", "s08_tousle_hair"]


def find_img(model_key, scene):
    pat = "pc_%s_%s_*.png" % (model_key, scene)
    for p in [os.path.join(OUT_ROOT, "*_wb", model_key, pat),
              os.path.join(OUT_ROOT, "prompt_compare", model_key, pat),
              os.path.join(OUT_ROOT, pat)]:
        hits = sorted(glob.glob(p))
        if hits:
            return hits[-1]
    return None


def font(sz):
    from PIL import ImageFont
    for n in ["msyh.ttc", "msyhbd.ttc", "simhei.ttf", "arial.ttf"]:
        try:
            return ImageFont.truetype(n, sz)
        except Exception:
            pass
    return ImageFont.load_default()


def build(kind="full"):
    from PIL import Image, ImageDraw
    TH, PAD, LBL, HDR = 300, 8, 190, 78
    cells, widths = [], []
    for mk, label in MODELS:
        row = []
        for sc in SCENES:
            p = find_img(mk, sc)
            row.append(p)
        cells.append(row)
        widths.append(None)

    # 单元宽度按第一张可用图的长宽比推算（统一为同一列宽，避免歪斜）
    tw = 240
    for row in cells:
        for p in row:
            if p:
                with Image.open(p) as im:
                    tw = int(im.width * TH / float(im.height))
                break
        else:
            continue
        break
    tw = max(150, min(tw, 300))

    cols, rows = len(SCENES), len(MODELS)
    W = LBL + cols * (tw + PAD) + PAD
    H = HDR + rows * (TH + PAD + 22) + PAD + 34
    sheet = Image.new("RGB", (W, H), (250, 250, 252))
    d = ImageDraw.Draw(sheet)

    title = ("四模型全景对比 — 同一组提示词（行=模型 / 列=场景）" if kind == "full"
             else "四模型中心微距 — 同一区域放大对比（行=模型 / 列=场景）")
    d.text((PAD + 4, 12), title, font=font(24), fill=(18, 18, 28))
    d.text((PAD + 4, 46), "Z-Image Turbo / Flux.1 Dev / SDXL RealVisXL / SDXL Juggernaut",
           font=font(15), fill=(110, 110, 125))
    for ci, s in enumerate(SCENES):
        d.text((LBL + ci * (tw + PAD) + PAD, HDR - 20), s.split("_")[0],
               font=font(14), fill=(90, 90, 105))

    y = HDR
    for ri, (mk, label) in enumerate(MODELS):
        d.text((PAD + 4, y + TH // 2 - 10), label, font=font(17), fill=(30, 30, 45))
        for ci, p in enumerate(cells[ri]):
            x = LBL + ci * (tw + PAD) + PAD
            if not p:
                d.rectangle([x, y, x + tw, y + TH], fill=(240, 240, 244), outline=(215, 215, 225))
                d.text((x + 8, y + TH // 2), "n/a", font=font(14), fill=(160, 160, 170))
                continue
            with Image.open(p) as im:
                im = im.convert("RGB")
                if kind == "crop":
                    w, h = im.size
                    cw, ch = int(w * 0.42), int(h * 0.42)
                    cx, cy = w // 2, int(h * 0.42)
                    im = im.crop((max(0, cx - cw // 2), max(0, cy - ch // 2),
                                  min(w, cx + cw // 2), min(h, cy + ch // 2)))
                nw = int(im.width * TH / float(im.height))
                sheet.paste(im.resize((nw, TH), Image.LANCZOS), (x, y))
            d.rectangle([x, y, x + tw, y + TH], outline=(215, 215, 225))
        y += TH + PAD + 22

    name = "compare_matrix_full.png" if kind == "full" else "compare_matrix_crop.png"
    out = os.path.join(EVAL_DIR, name)
    os.makedirs(EVAL_DIR, exist_ok=True)
    sheet.save(out, quality=93)
    return out, sheet.size


if __name__ == "__main__":
    res = []
    for k in ("full", "crop"):
        o, sz = build(k)
        res.append("%s  %s" % (o, sz))
        print("SAVED:", o, sz)
    with io.open(os.path.join(EVAL_DIR, "_sheets.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(res))
