# -*- coding: utf-8 -*-
"""多模型出图质量评测：同一组场景提示词 × 多个底模，逐张算指标 → 跨模型归一化 → 综合打分。

维度（每张图独立计算，再在同一场景的模型间归一化到 0-10）：
  sharpness    拉普拉斯方差             越高越好
  micro_detail 高频能量占比             越高越好（细节）
  skin         皮肤区纹理/塑料感        接近理想区间越好
  face         人脸检出 + 人脸区清晰度   越高越好
  color        色彩自然度               由饱和度贴合理想值程度得出
  exposure     曝光正常度               过曝/欠曝像素越少越好
  clean        画面干净度               块效应/伪影越少越好

⚠️ 尺度公平性：四个模型输出分辨率不同（512×768 / 768² / 1024²）。
   所有纹理类指标都在**统一缩放到短边 768 之后**再算，避免高分辨率白捡分。

用法：python tools/eval_pc_models.py [--res 768]
"""
import os, io, sys, glob, json, time
import numpy as np
import cv2

BASE = r"D:\ai_projects\ComfyUI"
OUT_ROOT = os.path.join(BASE, "output")
EVAL_DIR = os.path.join(OUT_ROOT, time.strftime("%Y-%m-%d") + "_wb", "_eval")

# model_key 同时也是产物子目录名 / 文件名前缀（pc_<model_key>_<scene>）
PRESETS = {
    "models4": [
        ("z_image_turbo", "Z-Image Turbo (8步)"),
        ("flux_dev_fp8", "Flux.1 Dev FP8 (20步)"),
        ("sdxl_realvis", "SDXL RealVisXL v4.0 (30步)"),
        ("juggernaut", "SDXL Juggernaut v9 (30步)"),
    ],
    # Z-Image 皮肤纹理补偿 A/B（同 seed 基线，仅换补偿手段）
    "lora_ab": [
        ("zimg_base", "Z-Image 基线"),
        ("zimg_skinlora", "Z-Image + 皮肤纹理 LoRA"),
        ("zimg_realism", "Z-Image + 写实 LoRA"),
        ("zimg_boost", "Z-Image + 提示词强化"),
    ],
    "withqwen": [
        ("z_image_turbo", "Z-Image Turbo (8步)"),
        ("qwen_image_21", "Qwen-Image 2.1 GGUF (25步)"),
    ],
}
PRESETS["all"] = PRESETS["models4"] + [("qwen_image_21", "Qwen-Image 2.1 GGUF (25步)")]

MODELS = PRESETS["models4"]

SCENES = ["s01_camisole_touch_hair", "s02_lying_on_sofa", "s03_hugging_knees",
          "s04_flushed_selfie", "s05_outdoor_knit_hat", "s06_indoor_standing",
          "s07_hand_on_chest", "s08_tousle_hair"]

WEIGHTS = {
    "sharpness": 0.18,     # 全图锐度
    "micro_detail": 0.12,  # 细节丰富度
    "skin": 0.15,          # 皮肤区纹理密度（抗塑料感）
    "face": 0.18,          # 人脸区清晰度（人像场景最关键）
    "framing": 0.10,       # 构图贴合度（上身肖像的脸部占比）
    "color": 0.12,         # 色彩自然度
    "exposure": 0.10,      # 曝光正常度
    "clean": 0.05,         # 画面干净度（实测各模型差异 <3%，区分度低故降权）
}

# 理想值（用于"越接近越好"型指标）
IDEAL_SAT = 0.30            # HSV 饱和度理想中心
IDEAL_FACE_AREA = (0.06, 0.15)  # "上身肖像"应有的脸部面积占比区间
                              # （实测区间外说明模型没按提示词拉近构图）

TARGET_SHORT = 768        # 统一缩放的短边

DET_PATH = r"C:\Users\kenzhao\.insightface\models\buffalo_l\det_10g.onnx"
_det = None


def get_det():
    """直连 RetinaFace，禁用 FaceAnalysis.get()（逐帧调用会 native 崩溃）。"""
    global _det
    if _det is not None:
        return _det
    try:
        from insightface.model_zoo import get_model
        m = get_model(DET_PATH)
        m.prepare(ctx_id=-1, input_size=(640, 640))
        _det = m
    except Exception as e:
        print("  [face] detector unavailable: %s" % str(e)[:120])
        _det = False
    return _det


def find_img(model_key, scene):
    pat = "pc_%s_%s_*.png" % (model_key, scene)
    for p in [os.path.join(OUT_ROOT, "*_wb", model_key, pat),
              os.path.join(OUT_ROOT, "*_wb", "lora_ab", model_key, pat),
              os.path.join(OUT_ROOT, "prompt_compare", model_key, pat),
              os.path.join(OUT_ROOT, pat)]:
        hits = sorted(glob.glob(p))
        if hits:
            return hits[-1]
    return None


def resize_short(img, short=TARGET_SHORT):
    h, w = img.shape[:2]
    s = short / float(min(h, w))
    return cv2.resize(img, (max(1, int(round(w * s))), max(1, int(round(h * s)))),
                      interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)


def high_freq_ratio(gray):
    """高频能量占总能量的比例（DoG）。"""
    lo = cv2.GaussianBlur(gray, (0, 0), 2.0)
    hf = gray - lo
    num = float(np.mean(hf * hf))
    den = float(np.mean(gray * gray)) + 1e-8
    return num / den


def blockiness(gray):
    """8px 网格边界梯度 / 内部梯度。越高说明块效应越明显。"""
    g = gray.astype(np.float32)
    dv = np.abs(np.diff(g, axis=0))
    dh = np.abs(np.diff(g, axis=1))
    ev = dv[7::8].mean() if dv.shape[0] > 8 else 0.0
    eh = dh[:, 7::8].mean() if dh.shape[1] > 8 else 0.0
    iv = np.delete(dv, np.s_[7::8], axis=0).mean() if dv.shape[0] > 8 else 1.0
    ih = np.delete(dh, np.s_[7::8], axis=1).mean() if dh.shape[1] > 8 else 1.0
    edge = (ev + eh) / 2.0
    inner = (iv + ih) / 2.0 + 1e-6
    return edge / inner


def framing_score(area):
    """脸部面积占比落在「上身肖像」理想区间内得满分，偏离越多扣越多。"""
    if area is None:
        return None
    lo, hi = IDEAL_FACE_AREA
    if lo <= area <= hi:
        return 1.0
    if area < lo:
        return max(0.0, area / lo)
    return max(0.0, 1.0 - (area - hi) / hi)


def color_score(img_bgr):
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1].astype(np.float32) / 255.0
    s = float(sat.mean())
    return max(0.0, 1.0 - abs(s - IDEAL_SAT) / IDEAL_SAT), s


def exposure_score(gray):
    hi = float((gray > 0.98).mean())
    lo = float((gray < 0.02).mean())
    return max(0.0, 1.0 - (hi + lo) * 12.0), hi, lo


def face_metrics(img_bgr, gray):
    """返回 (检出数, 最大人脸占比, 人脸区清晰度, 人脸区高频占比)"""
    det = get_det()
    if not det:
        return None
    try:
        bboxes, kps = det.detect(img_bgr)
    except Exception:
        return None
    if bboxes is None or len(bboxes) == 0:
        return 0, 0.0, 0.0, 0.0
    H, W = gray.shape[:2]
    best = None
    for b in bboxes:
        x1, y1, x2, y2, sc = [float(v) for v in b[:5]]
        area = max(0.0, (x2 - x1)) * max(0.0, (y2 - y1)) / float(H * W)
        if best is None or area > best[0]:
            best = (area, x1, y1, x2, y2)
    area, x1, y1, x2, y2 = best
    # 取人脸中心 60% 作为皮肤区（避开边缘背景）
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    bw, bh = (x2 - x1) * 0.6, (y2 - y1) * 0.6
    ax1, ay1 = int(max(0, cx - bw / 2)), int(max(0, cy - bh / 2))
    ax2, ay2 = int(min(W, cx + bw / 2)), int(min(H, cy + bh / 2))
    if ax2 - ax1 < 8 or ay2 - ay1 < 8:
        return len(bboxes), area, 0.0, 0.0
    crop = gray[ay1:ay2, ax1:ax2]
    # ⚠️ cv2.Laplacian 不支持 float32 → CV_64F 的组合，必须先转 uint8
    crop_u8 = (np.clip(crop, 0.0, 1.0) * 255).astype(np.uint8)
    return (len(bboxes), area,
            float(cv2.Laplacian(crop_u8, cv2.CV_64F).var()),
            high_freq_ratio(crop))


def measure(path):
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        return None
    h0, w0 = img.shape[:2]
    img = resize_short(img)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0

    lap = float(cv2.Laplacian((gray * 255).astype(np.uint8), cv2.CV_64F).var())
    hf = high_freq_ratio(gray)
    blk = blockiness(gray)
    cs, sat = color_score(img)
    es, hi, lo = exposure_score(gray)

    fm = face_metrics(img, gray)
    if fm is None:
        n_face, face_area, face_lap, skin_hf = None, None, None, None
    else:
        n_face, face_area, face_lap, skin_hf = fm

    return {
        "path": path, "orig_w": w0, "orig_h": h0,
        "brightness": float(gray.mean()),
        "contrast": float(gray.std()),
        "lap_var": lap,
        "hf_ratio": hf,
        "saturation": sat,
        "clip_high": hi, "clip_low": lo,
        "blockiness": blk,
        "n_face": n_face, "face_area": face_area,
        "face_lap": face_lap, "skin_hf": skin_hf,
        "color_score": cs, "exposure_score": es,
    }


def norm_scene(values, mode="max"):
    """在同一场景的模型之间归一化到 0-10。"""
    vals = [v for v in values if v is not None]
    if not vals:
        return [5.0] * len(values)
    lo, hi = min(vals), max(vals)
    out = []
    for v in values:
        if v is None:
            out.append(5.0)
        elif hi - lo < 1e-12:
            out.append(7.0)
        else:
            out.append(10.0 * (v - lo) / (hi - lo))
    return out


def main():
    global MODELS
    preset_name = "models4"
    if "--preset" in sys.argv:
        i = sys.argv.index("--preset")
        if i + 1 < len(sys.argv):
            name = sys.argv[i + 1]
            if name not in PRESETS:
                print("!! 未知 preset %r，可选：%s" % (name, " / ".join(PRESETS)))
                return
            preset_name = name
            MODELS = PRESETS[name]
            print(">> preset = %s（%d 个模型）" % (name, len(MODELS)))

    os.makedirs(EVAL_DIR, exist_ok=True)
    rows = []
    missing = []
    t0 = time.time()

    for scene in SCENES:
        for mk, label in MODELS:
            p = find_img(mk, scene)
            if not p:
                missing.append("%s / %s" % (mk, scene))
                continue
            m = measure(p)
            if m is None:
                missing.append("%s / %s (unreadable)" % (mk, scene))
                continue
            m.update({"model": mk, "model_label": label, "scene": scene})
            rows.append(m)
            print("  measured %-16s %s  lap=%.0f hf=%.4f" % (
                mk, scene, m["lap_var"], m["hf_ratio"]), flush=True)

    if not rows:
        print("!! 没有可测的图，先跑 tools/_pc_run_matrix.py")
        return

    # ---- 场景内归一化 → 维度分 ----
    for scene in SCENES:
        grp = [r for r in rows if r["scene"] == scene]
        if not grp:
            continue
        sharp = norm_scene([r["lap_var"] for r in grp])
        detail = norm_scene([r["hf_ratio"] for r in grp])
        # 皮肤：皮肤区高频密度越高 = 毛孔/纹理越丰富，越低 = 越像磨皮涂抹
        skin = norm_scene([r["skin_hf"] if r["skin_hf"] else None for r in grp])
        # 人脸：针对人脸区的清晰度（检出数已全部为 1，不参与区分）
        face = norm_scene([np.log1p(r["face_lap"]) if r["face_lap"] else None for r in grp])
        framing = norm_scene([framing_score(r["face_area"]) for r in grp])
        color = norm_scene([r["color_score"] for r in grp])
        expos = norm_scene([r["exposure_score"] for r in grp])
        clean = norm_scene([-r["blockiness"] for r in grp])
        for i, r in enumerate(grp):
            r["score_sharpness"] = round(sharp[i], 2)
            r["score_micro_detail"] = round(detail[i], 2)
            r["score_skin"] = round(skin[i], 2)
            r["score_face"] = round(face[i], 2)
            r["score_framing"] = round(framing[i], 2)
            r["score_color"] = round(color[i], 2)
            r["score_exposure"] = round(expos[i], 2)
            r["score_clean"] = round(clean[i], 2)
            r["score_total"] = round(sum(
                r["score_" + k] * w for k, w in WEIGHTS.items()), 2)

    # ---- 汇总 ----
    summary = {}
    for mk, label in MODELS:
        sub = [r for r in rows if r["model"] == mk]
        if not sub:
            continue
        dims = {}
        for k in WEIGHTS:
            vals = [r["score_" + k] for r in sub]
            dims[k] = round(float(np.mean(vals)), 2)
        tot = round(float(np.mean([r["score_total"] for r in sub])), 2)
        summary[mk] = {
            "label": label, "n": len(sub), "dims": dims, "total": tot,
            "mean_lap_var": round(float(np.mean([r["lap_var"] for r in sub])), 1),
            "mean_hf_ratio": round(float(np.mean([r["hf_ratio"] for r in sub])), 4),
            "mean_saturation": round(float(np.mean([r["saturation"] for r in sub])), 3),
            "mean_blockiness": round(float(np.mean([r["blockiness"] for r in sub])), 3),
            "mean_face_area": (round(float(np.mean([r["face_area"] for r in sub
                                                    if r["face_area"] is not None])), 4)
                               if any(r["face_area"] is not None for r in sub) else None),
        }

    # ---- 落盘 ----
    import csv
    csv_path = os.path.join(EVAL_DIR, "metrics_%s.csv" % preset_name)
    cols = ["model", "model_label", "scene", "orig_w", "orig_h", "brightness", "contrast",
            "lap_var", "hf_ratio", "saturation", "clip_high", "clip_low", "blockiness",
            "n_face", "face_area", "face_lap", "skin_hf",
            "score_sharpness", "score_micro_detail", "score_skin", "score_face",
            "score_framing", "score_color", "score_exposure", "score_clean",
            "score_total", "path"]
    with io.open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda x: (x["model"], x["scene"])):
            w.writerow(r)

    json_path = os.path.join(EVAL_DIR, "summary_%s.json" % preset_name)
    with io.open(json_path, "w", encoding="utf-8") as f:
        json.dump({"weights": WEIGHTS, "models": summary, "missing": missing,
                   "target_short": TARGET_SHORT, "scenes": SCENES}, f,
                  ensure_ascii=False, indent=2)

    # ---- 报告 ----
    lines = []
    lines.append("# 多模型出图质量评测（同一组提示词）")
    lines.append("")
    lines.append("评测时间：%s ｜ 图像数：%d ｜ 纹理指标统一缩放短边至 %d" % (
        time.strftime("%Y-%m-%d %H:%M"), len(rows), TARGET_SHORT))
    lines.append("")
    dims_cn = {"sharpness": "清晰度", "micro_detail": "细节丰富度", "skin": "皮肤质感",
               "face": "人脸质量", "framing": "构图贴合", "color": "色彩自然",
               "exposure": "曝光", "clean": "画面干净"}
    hdr = "| 模型 | " + " | ".join("%s(%.2f)" % (dims_cn[k], WEIGHTS[k]) for k in WEIGHTS) + " | **综合** |"
    lines.append(hdr)
    lines.append("|" + "---|" * (len(WEIGHTS) + 2))
    ordered = sorted(summary.items(), key=lambda kv: -kv[1]["total"])
    for i, (mk, s) in enumerate(ordered):
        rank = ["🥇", "🥈", "🥉", "4️⃣"][i] if i < 4 else ""
        cells = " | ".join("%.2f" % s["dims"][k] for k in WEIGHTS)
        lines.append("| %s %s | %s | **%.2f** |" % (rank, s["label"], cells, s["total"]))
    lines.append("")
    lines.append("## 单项冠军")
    for k in WEIGHTS:
        best = max(summary.items(), key=lambda kv: kv[1]["dims"][k])
        lines.append("- **%s**：%s（%.2f）" % (dims_cn[k], best[1]["label"], best[1]["dims"][k]))
    lines.append("")
    lines.append("## 原始指标均值")
    lines.append("| 模型 | 拉普拉斯方差 | 高频占比 | 饱和度 | 块效应 | 人脸面积占比 |")
    lines.append("|---|---|---|---|---|---|")
    for mk, s in ordered:
        lines.append("| %s | %.1f | %.4f | %.3f | %.3f | %s |" % (
            s["label"], s["mean_lap_var"], s["mean_hf_ratio"], s["mean_saturation"],
            s["mean_blockiness"], ("%.4f" % s["mean_face_area"]) if s["mean_face_area"] is not None else "n/a"))
    if missing:
        lines.append("")
        lines.append("## 缺失")
        for m in missing:
            lines.append("- %s" % m)
    lines.append("")
    lines.append("耗时 %.1f 分钟" % ((time.time() - t0) / 60.0))

    md_path = os.path.join(EVAL_DIR, "评测报告_%s.md" % preset_name)
    with io.open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("")
    print("\n".join(lines))
    print("")
    print("CSV : %s" % csv_path)
    print("JSON: %s" % json_path)
    print("MD  : %s" % md_path)


if __name__ == "__main__":
    main()
