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
        pat = "pc_%s_%s_*.png" % (model, scene)
        for p in [os.path.join(BASE, "output", pat),
                  os.path.join(OUT, model, pat),
                  # 规范产物目录 output/YYYY-MM-DD_wb/<model>/
                  os.path.join(BASE, "output", "*_wb", model, pat)]:
            hits = sorted(glob.glob(p))
            if hits: return hits[-1]
        return None

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
ALL = SD15 + [("flux_dev_fp8", "Flux.1-dev FP8  (流匹配)"),
              ("z_image_turbo", "Z-Image Turbo  (8步 蒸馏·默认档)")]

def font(sz):
    from PIL import ImageFont
    for n in ["msyh.ttc", "msyhbd.ttc", "simhei.ttf", "arial.ttf"]:
        try: return ImageFont.truetype(n, sz)
        except Exception: pass
    return ImageFont.load_default()


def build_sheet(images, labels, outname, title, cols=3, th=512):
    """把一组图片拼成带标签的网格资产表（用于角色 turnaround sheet）。

    images: 图片路径列表（允许 None 占位）；labels: 与 images 等长的标签；
    outname: 输出文件路径；title: 标题；cols: 每行列数；th: 单元目标高度(px)。
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("PIL MISSING - pip install pillow"); return None
    imgs = [(p if (p and os.path.exists(p)) else None) for p in images]
    n = len(imgs)
    if n == 0:
        print("no images for sheet", outname); return None
    rows = (n + cols - 1) // cols
    PAD, LBL_H, HDR = 10, 26, 64
    loaded = []
    for p in imgs:
        if p:
            with Image.open(p) as im:
                loaded.append(im.convert("RGB"))
        else:
            loaded.append(None)
    cell_w = 0
    for im in loaded:
        if im:
            cell_w = max(cell_w, int(im.width * th / im.height))
    if cell_w == 0:
        cell_w = 300
    W = PAD + cols * (cell_w + PAD)
    H = HDR + rows * (th + LBL_H + PAD) + PAD
    sh = Image.new("RGB", (W, H), (250, 250, 252))
    d = ImageDraw.Draw(sh)
    d.text((PAD, 14), title, font=font(24), fill=(18, 18, 28))
    idx, y = 0, HDR
    for _ in range(rows):
        x = PAD
        for _c in range(cols):
            if idx >= n:
                break
            im = loaded[idx]
            if im:
                w = int(im.width * th / im.height)
                sh.paste(im.resize((w, th), Image.LANCZOS), (x + (cell_w - w) // 2, y))
            else:
                d.rectangle([x, y, x + cell_w, y + th], fill=(240, 240, 244),
                            outline=(215, 215, 225))
                d.text((x + 8, y + th // 2), "n/a", font=font(14), fill=(160, 160, 170))
            lbl = labels[idx] if idx < len(labels) else ""
            d.text((x + 4, y + th + 4), lbl, font=font(15), fill=(60, 60, 75))
            x += cell_w + PAD
            idx += 1
        y += th + LBL_H + PAD
    sh.save(outname, quality=92)
    print("SAVED:", outname, sh.size)
    return outname


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "sd15"
    if mode in ("sd15", "all"):
        _run(SD15, SCENES, "compare_sd15_models.png",
             "SD1.5 三模型对比 — 同一组提示词")
    if mode == "all":
        _run(ALL, SCENES, "compare_all_models.png",
             "ComfyUI 五模型对比 — 同一组提示词（SD1.5×3 + Flux Dev + Z-Image Turbo）")
