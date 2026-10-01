#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""restore_qa —— 纯离线的高清修复数值体检工具。

完全不依赖 GPU / ComfyUI 在线服务 / ComfyUI API，只吃两个图片文件：
源图（修复前）与修复输出图，用数值方法客观判断"到底有没有真修复"。

主要指标：
  ① 尺寸与倍率        —— 源图/输出的边长倍率与像素倍率
  ② 源图块状度        —— 8px(或 --pitch) JPEG 压缩块在源图里的强度
  ③ 输出周期性格子     —— 把源图压缩块网格映射到输出尺寸后，检测成片里是否残留
  ④ 锐度对比          —— 输出 vs "源图 LANCZOS 放大到同尺寸"基线（1:1 同尺寸比）
  ⑤ 细节密度          —— 高频能量占比（FFT top octave）
  ⑥ 保真度            —— 输出缩回源图尺寸后与源图的 RMSE
  ⑦ 判定行            —— 综合 ③④⑥ 给出"是否真修复"的结论

用法：
  python tools/restore_qa.py --source <源图> --output <修复输出图>
  python tools/restore_qa.py --source in.png --output out.png --pitch 8
  python tools/restore_qa.py --source in.png --output out.png --json metrics.json

模块级函数 blockiness_ratio(img, pitch=8) 也被 tools/qwen_v4_submit.py 复用：
参数 img 既可以是文件路径，也可以是 numpy 灰度数组；返回 (col_ratio, row_ratio)。
该函数无任何副作用（import 时不打印、不读文件、不 argparse）。
"""
import argparse
import json
import sys

import numpy as np
from PIL import Image

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# ---------------------------------------------------------------- 底层工具

def to_gray_float(img):
    """把 路径 / numpy 数组 统一成 float32 灰度二维数组。无副作用。"""
    if isinstance(img, np.ndarray):
        g = np.asarray(img)
        if g.ndim == 3:
            g = g[..., :3].astype(np.float32).mean(axis=2)
        else:
            g = g.astype(np.float32)
        return g
    with Image.open(img) as im:
        return np.asarray(im.convert("L"), dtype=np.float32)


def _axis_profile(gray, axis):
    """沿 axis 求相邻差分绝对值，对另一轴取均值，得到一维剖面。

    axis=0 -> 沿宽度方向(x)差分，返回长度 w-1 的剖面（列剖面）
    axis=1 -> 沿高度方向(y)差分，返回长度 h-1 的剖面（行剖面）
    剖面索引 i 代表"像素 i 与 i+1 之间的边界"。
    """
    if axis == 0:
        d = np.abs(np.diff(gray, axis=1))       # (h, w-1)
        return d.mean(axis=0)
    d = np.abs(np.diff(gray, axis=0))           # (h-1, w)
    return d.mean(axis=1)


def _blockiness_1d(v, pitch):
    """给定一维剖面，返回 (格线均值, 非格线均值, 比值)。"""
    idx = np.arange(len(v))
    grid = (idx % pitch) == (pitch - 1)         # 格线 = 块边界
    g_mean = float(v[grid].mean())
    n_mean = float(v[~grid].mean())
    ratio = g_mean / n_mean if n_mean > 1e-12 else float("inf")
    return g_mean, n_mean, ratio


def blockiness_ratio(img, pitch=8):
    """源图块状度：返回 (col_ratio, row_ratio)。

    img 可为文件路径或 numpy 灰度数组。无副作用，供其它脚本 import 复用。
    col = 沿宽度(x)方向；row = 沿高度(y)方向。
    """
    gray = to_gray_float(img)
    _, _, col = _blockiness_1d(_axis_profile(gray, 0), pitch)
    _, _, row = _blockiness_1d(_axis_profile(gray, 1), pitch)
    return col, row


# ---------------------------------------------------------------- ③ 周期性

def _prep_profile(v):
    """周期检测前的剖面预处理：sqrt 方差稳定化。

    剖面是"相邻差分绝对值"，恒正且高度右偏；先开方压缩动态范围，
    能让格线峰更干净、同时保持全正，比值才是有意义的衬度。
    刻意**不**用"减去 31 点滑动平均"：剖面相减会变成有符号值，
    分母 mean(~mask) 趋零，实测比值被放大到 3.9e5 量级而失效。
    """
    return np.sqrt(np.maximum(v, 0.0))


def _periodicity_1d(v, P0):
    """在等效周期 P0 附近扫描，找最像格子的周期/相位及其衬度。

    返回 dict: peak(峰值比), P, ph, worst(最差相位比), contrast(峰值比/最差相位比)
    """
    vd = _prep_profile(v)
    idx = np.arange(len(vd))
    denom = max(len(vd), 1)
    best = None
    worst = None
    P = 0.8 * P0
    while P <= 1.2 * P0 + 1e-9:
        for ph in np.arange(0.0, P, 1.0):
            mask = np.abs(((idx - ph) % P)) < 1.0
            n_in = int(mask.sum())
            n_out = denom - n_in
            if n_in < 2 or n_out < 2:
                continue
            mean_in = vd[mask].mean()
            mean_out = vd[~mask].mean()
            if mean_out <= 1e-12:
                continue
            ratio = float(mean_in / mean_out)
            if best is None or ratio > best[0]:
                best = (ratio, float(P), float(ph))
            if worst is None or ratio < worst:
                worst = ratio
        P += 0.1
    if best is None:
        return None
    return {"peak": best[0], "P": best[1], "ph": best[2],
            "worst": float(worst),
            "contrast": best[0] / worst if worst > 1e-12 else float("inf")}


# ---------------------------------------------------------------- ④ 锐度

def _sharpness(gray):
    """mean(|4邻域拉普拉斯|) / max(mean(gray),1e-6)。"""
    lap = (4.0 * gray[1:-1, 1:-1]
           - gray[:-2, 1:-1] - gray[2:, 1:-1]
           - gray[1:-1, :-2] - gray[1:-1, 2:])
    return float(np.abs(lap).mean() / max(float(gray.mean()), 1e-6))


# ---------------------------------------------------------------- ⑤ 细节密度

def _detail_density(gray):
    """高频能量占比 top_octave = sum(power[r>0.5]) / sum(power[r>0.05])。"""
    h, w = gray.shape
    power = np.abs(np.fft.rfft2(gray)) ** 2
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.rfftfreq(w)[None, :]
    r = np.sqrt(fy ** 2 + fx ** 2) / 0.5     # 归一化半径，1 约为单轴奈奎斯特
    num = float(power[r > 0.5].sum())
    den = float(power[r > 0.05].sum())
    return num / den if den > 1e-12 else 0.0


# ---------------------------------------------------------------- ⑥ 保真

def _rgb_array(path, size=None):
    with Image.open(path) as im:
        im = im.convert("RGB")
        if size is not None and im.size != size:
            im = im.resize(size, Image.LANCZOS)
        return np.asarray(im, dtype=np.float64)


def _gray_at(path, size=None):
    """把图片转成 float32 灰度；若给定 size 则先在 RGB 域做 LANCZOS 缩放再转灰度。"""
    with Image.open(path) as im:
        im = im.convert("RGB")
        if size is not None and im.size != size:
            im = im.resize(size, Image.LANCZOS)
        return np.asarray(im.convert("L"), dtype=np.float32)


def _rmse(a, b):
    d = a - b
    return float(np.sqrt((d ** 2).mean()))


# ---------------------------------------------------------------- 判定

def _grade_block(peak, P, P0, detected):
    if not detected:
        return "不适用（未检出格子）"
    if peak < 1.25:
        return "✔"
    if peak < 1.45:
        return "△"
    return "✘"


def _grade_sharp(ratio):
    if ratio >= 1.5:
        return "✔"
    if ratio >= 1.2:
        return "△"
    return "✘"


def _grade_fidelity(rmse):
    if rmse <= 12.0:
        return "✔"
    if rmse <= 20.0:
        return "△"
    return "✘"


# ---------------------------------------------------------------- 主流程

def run(source, output, pitch, json_path):
    im_src = Image.open(source)
    im_out = Image.open(output)
    w0, h0 = im_src.size
    w1, h1 = im_out.size
    im_src.close()
    im_out.close()

    gray_src = to_gray_float(source)
    gray_out = _gray_at(output)

    metrics = {}

    # ① 尺寸与倍率
    rw = w1 / w0
    rh = h1 / h0
    rpix = (w1 * h1) / (w0 * h0)
    metrics["sizes"] = {"source": [w0, h0], "output": [w1, h1],
                        "ratio_w": rw, "ratio_h": rh, "ratio_pixels": rpix}
    print("① 尺寸与倍率")
    print(f"   源图 {w0}x{h0}  →  输出 {w1}x{h1}")
    print(f"   边长倍率  宽 {rw:.2f}x   高 {rh:.2f}x")
    print(f"   像素倍率  {rpix:.2f}x")

    # ② 源图块状度
    vx = _axis_profile(gray_src, 0)
    vy = _axis_profile(gray_src, 1)
    col_g, col_n, col_ratio = _blockiness_1d(vx, pitch)
    row_g, row_n, row_ratio = _blockiness_1d(vy, pitch)
    metrics["source_blockiness"] = {"pitch": pitch,
                                    "col_ratio": col_ratio, "row_ratio": row_ratio,
                                    "col_grid_mean": col_g, "col_nongrid_mean": col_n,
                                    "row_grid_mean": row_g, "row_nongrid_mean": row_n}
    print()
    print(f"② 源图 {pitch}px 块状度")
    print(f"   col  格线均值 {col_g:.4f}  非格线均值 {col_n:.4f}  比值 {col_ratio:.3f}")
    print(f"   row  格线均值 {row_g:.4f}  非格线均值 {row_n:.4f}  比值 {row_ratio:.3f}")

    # ③ 输出周期性格子（剖面取自输出灰度）
    ovx = _axis_profile(gray_out, 0)
    ovy = _axis_profile(gray_out, 1)
    P0w = pitch * rw
    P0h = pitch * rh
    per_col = _periodicity_1d(ovx, P0w)
    per_row = _periodicity_1d(ovy, P0h)
    metrics["periodicity"] = {"P0_w": P0w, "P0_h": P0h,
                              "col": per_col, "row": per_row}
    print()
    print("③ 输出周期性格子检测")

    def _print_per(name, per, P0):
        if per is None:
            print(f"   {name}  未检出（剖面过短）")
            return
        print(f"   {name}  峰值比 {per['peak']:.3f}  等效周期 P {per['P']:.1f}px  "
              f"相位 ph {per['ph']:.1f}  最差相位比 {per['worst']:.3f}  "
              f"衬度 {per['contrast']:.3f}")

    _print_per("col", per_col, P0w)
    _print_per("row", per_row, P0h)

    # 取最显著（峰值比最大）的轴做判定
    cands = [c for c in (per_col, per_row) if c is not None]
    if cands:
        lead = max(cands, key=lambda c: c["peak"])
        P0_lead = P0w if lead is per_col else P0h
        detected = 0.85 * P0_lead <= lead["P"] <= 1.15 * P0_lead
    else:
        lead = None
        P0_lead = P0w
        detected = False

    # ④ 锐度 1:1 同尺寸
    # 基线 = 源图用 LANCZOS 放大到输出尺寸；注意先在 RGB 域放大再转灰度，
    # 这样才与参考值一致（先转灰度再放大偏低约 4%）。
    base_gray = _gray_at(source, (w1, h1))
    sharp_out = _sharpness(gray_out)
    sharp_base = _sharpness(base_gray)
    sharp_ratio = sharp_out / sharp_base if sharp_base > 1e-12 else float("inf")
    metrics["sharpness"] = {"output": sharp_out, "baseline": sharp_base, "ratio": sharp_ratio}
    print()
    print("④ 锐度对比（1:1 同尺寸）")
    print(f"   输出 {sharp_out:.5f}   基线(源图 LANCZOS 放大) {sharp_base:.5f}   "
          f"比值 {sharp_ratio:.2f}x")

    # ⑤ 细节密度
    det_out = _detail_density(gray_out)
    det_base = _detail_density(base_gray)
    det_ratio = det_out / det_base if det_base > 1e-12 else float("inf")
    metrics["detail_density"] = {"output": det_out, "baseline": det_base, "ratio": det_ratio}
    print()
    print("⑤ 细节密度（高频能量占比）")
    print(f"   输出 {det_out:.5f}   基线 {det_base:.5f}   比值 {det_ratio:.2f}x")

    # ⑥ 保真度
    src_rgb = _rgb_array(source)
    out_back = _rgb_array(output, size=(w0, h0))
    rmse = _rmse(out_back, src_rgb)
    metrics["fidelity"] = {"rmse": rmse, "rmse_norm": rmse / 255.0}
    print()
    print("⑥ 保真度（输出缩回源图尺寸 vs 源图）")
    print(f"   RMSE {rmse:.2f}   (RMSE/255 = {rmse / 255.0:.4f})")

    # ⑦ 判定
    if lead is None:
        g_block = "不适用（未检出格子）"
        peak_val = float("nan")
        P_val = float("nan")
    else:
        g_block = _grade_block(lead["peak"], lead["P"], P0_lead, detected)
        peak_val = lead["peak"]
        P_val = lead["P"]
    g_sharp = _grade_sharp(sharp_ratio)
    g_faith = _grade_fidelity(rmse)

    metrics["verdict"] = {"block": g_block, "sharp": g_sharp, "fidelity": g_faith,
                          "peak_ratio": peak_val, "period": P_val,
                          "period_ok": detected}

    ok_block = g_block in ("✔", "△", "不适用（未检出格子）")
    real = ok_block and g_sharp == "✔" and g_faith != "✘"

    print()
    print("⑦ 判定")
    peak_txt = "n/a" if lead is None else f"{peak_val:.2f}"
    print(f"   块状 {g_block}({peak_txt})   锐度 {g_sharp}({sharp_ratio:.2f}x)   "
          f"保真 {g_faith}(RMSE {rmse:.1f})")
    verdict_word = "真修复" if real else "未真修复"
    print(f"判定：{verdict_word} → 块状 {g_block}({peak_txt}) "
          f"锐度 {g_sharp}({sharp_ratio:.2f}x) 保真 {g_faith}(RMSE {rmse:.1f})")

    if not detected:
        human = "未在输出里检出源图压缩块对应的周期格子，源图压缩块可能本就微弱。"
    elif g_block == "✔":
        human = "修复确实生效，且未留下压缩块格子。"
    elif g_block == "△":
        human = "修复生效，但压缩块格子仍有轻微残留。"
    else:
        human = "锐度提升但压缩块格子仍在，说明链路只是把压缩块放大了。"
    print(f"结论：{human}")

    if json_path:
        def _clean(o):
            if isinstance(o, dict):
                return {k: _clean(v) for k, v in o.items()}
            if isinstance(o, list):
                return [_clean(v) for v in o]
            if isinstance(o, float) and (np.isnan(o) or np.isinf(o)):
                return None
            return o
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(_clean(metrics), f, ensure_ascii=False, indent=2)
        print(f"（指标已写入 {json_path}）")

    return metrics


def main(argv=None):
    ap = argparse.ArgumentParser(description="高清修复离线数值体检工具（不依赖 GPU/ComfyUI）")
    ap.add_argument("--source", required=True, help="源图（修复前）")
    ap.add_argument("--output", required=True, help="修复输出图")
    ap.add_argument("--pitch", type=int, default=8, help="源图压缩块网格间距，默认 8")
    ap.add_argument("--json", dest="json_path", default=None, help="把指标写成 JSON 的路径")
    args = ap.parse_args(argv)

    if args.pitch <= 0:
        raise SystemExit("✗ --pitch 必须为正整数")
    run(args.source, args.output, args.pitch, args.json_path)


if __name__ == "__main__":
    main()