#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Google Flow 首帧锁定器 (Start Frame Lock)

背景：实测发现路线 A 声称的「挂载 Start Frame 驱动 Image-to-Video」**从未真正生效**——
`tools/` 下没有任何给 Flow 上传首帧的代码，流水线只填了文本提示词，走的是纯
text-to-video。后果是画风完全漂移（首帧水墨剪纸 → 成片写实真人）、画面结构与
首帧无关，而这些失败任务照样各扣 10 积分且"成功结束"。

本模块补齐三件事：
1. **真实上传**：Add media menu → Upload → 拦截系统文件选择器 → 注入首帧图。
2. **挂载确认**：上传前后做 DOM 快照比对，确认素材真的进了提示词的
   ingredient 区（而不只是"点过按钮"）。
3. **出片校验**：成片首帧与提交图做感知哈希 + 直方图比对，漂移即判废。

安全约定
--------
* 上传与挂载确认**不消耗积分**，可放心重试。
* 只有 `Start generation` 才扣费，本模块**永不点击**它。
* 校验判废后**默认不自动重跑**（重跑 = 再扣 10 分），只报错并留证据，由人决定。

用法
----
    from flow_frame_lock import attach_start_frame, verify_frame_lock
    ok, detail = attach_start_frame(page, "output/.../shot_01_frame.png")
    passed, report = verify_frame_lock(ref_img, video_path)

命令行
------
    python tools/flow_frame_lock.py --attach output/2026-10-10/route_a/images/shot_01_frame.png
    python tools/flow_frame_lock.py --ref img.png --video clip.mp4
"""

import os
import sys
import time
import json
import argparse

import cv2
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 判废阈值（用**已确认漂移**的 shot_01 / shot_02 样本标定，见下方注释基线）
#
# 实测基线：
#   自比（同一张图）            hamming=0   hist=1.000  gray=1.000
#   漂移 shot01（图 vs 成片）   hamming=36  hist=-0.064 gray=-0.235
#   漂移 shot02（图 vs 成片）   hamming=28  hist=0.698  gray=0.231
#   同视频 0s vs 4s（大幅摇移） hamming=34  hist=0.716  gray=-0.026
#   同视频 0s vs 8s（缓推）     hamming=16  hist=0.912  gray=0.605
#
# 结论：**gray_corr 对镜头运动过于敏感**（大幅摇移时甚至为负，比真漂移样本还低），
# 若拿它当硬判据会误杀正常运镜。因此以 phash 汉明距离为主判据，
# gray_corr 只作辅助、阈值放宽。
THRESHOLDS = {
    "phash_hamming_max": 20,     # 主判据：超过即判画面结构不同
    "hist_corr_min": 0.30,       # 辅助：色调/明暗漂移
    "gray_corr_min": 0.15,       # 辅助（放宽）：构图漂移，仅极端时才触发
}


# ---------------------------------------------------------------------------
# 一、相似度度量（纯离线，不碰浏览器）
# ---------------------------------------------------------------------------
def phash(img, size=32, hash_size=8):
    """感知哈希：缩放→灰度→DCT→低频 8x8→中位数阈值→64bit。"""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, (size, size), interpolation=cv2.INTER_AREA)
    d = cv2.dct(np.float32(g))
    low = d[:hash_size, :hash_size].flatten()
    med = np.median(low)
    bits = (low > med).astype(np.uint8)
    return bits


def hamming(a, b):
    return int(np.count_nonzero(a != b))


def hist_correlation(a, b):
    """三通道直方图相关性，取值 [-1, 1]，越大越像。"""
    sims = []
    for ch in range(3):
        ha = cv2.calcHist([a], [ch], None, [64], [0, 256])
        hb = cv2.calcHist([b], [ch], None, [64], [0, 256])
        cv2.normalize(ha, ha); cv2.normalize(hb, hb)
        sims.append(float(cv2.compareHist(ha, hb, cv2.HISTCMP_CORREL)))
    return float(np.mean(sims))


def gray_correlation(a, b, size=128):
    """灰度结构相关性（去均值归一化互相关），对构图和明暗漂移都敏感。"""
    ga = cv2.resize(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), (size, size)).astype(np.float64)
    gb = cv2.resize(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY), (size, size)).astype(np.float64)
    ga -= ga.mean(); gb -= gb.mean()
    denom = (np.linalg.norm(ga) * np.linalg.norm(gb))
    if denom < 1e-9:
        return 0.0
    return float((ga * gb).sum() / denom)


def frame_similarity(img_a, img_b):
    """综合三项指标。返回 dict。"""
    ha, hb = phash(img_a), phash(img_b)
    return {
        "phash_hamming": hamming(ha, hb),
        "hist_corr": round(hist_correlation(img_a, img_b), 3),
        "gray_corr": round(gray_correlation(img_a, img_b), 3),
    }


def judge(sim):
    """按阈值判定是否通过。返回 (passed, 未通过原因列表)。"""
    reasons = []
    if sim["phash_hamming"] > THRESHOLDS["phash_hamming_max"]:
        reasons.append(f"画面结构漂移 (汉明距离 {sim['phash_hamming']} > {THRESHOLDS['phash_hamming_max']})")
    if sim["hist_corr"] < THRESHOLDS["hist_corr_min"]:
        reasons.append(f"色调明暗漂移 (直方图相关性 {sim['hist_corr']} < {THRESHOLDS['hist_corr_min']})")
    if sim["gray_corr"] < THRESHOLDS["gray_corr_min"]:
        reasons.append(f"构图漂移 (结构相关性 {sim['gray_corr']} < {THRESHOLDS['gray_corr_min']})")
    return (len(reasons) == 0), reasons


def verify_frame_lock(ref_img_path, video_path, frame_pos=0.0, sample_frames=3):
    """校验成片开头与提交首帧是否一致。

    sample_frames: 从 frame_pos 起连续取几帧做比对，取**最像的那帧**作为判据。
    这样做是因为 Veo 偶尔在第 0 帧给黑场/转场，只比单帧会误判；而挂载成功时
    开头若干帧都应接近提交图。

    返回 (passed, report_dict)。
    """
    ref = cv2.imread(ref_img_path)
    if ref is None:
        return False, {"error": f"参考图读取失败: {ref_img_path}"}
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return False, {"error": f"视频打开失败: {video_path}"}
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    start = max(0, min(total - 1, int(total * frame_pos)))

    samples = []
    for k in range(max(1, sample_frames)):
        cap.set(cv2.CAP_PROP_POS_FRAMES, min(total - 1, start + k))
        ok, frame = cap.read()
        if ok:
            samples.append((k, frame, frame_similarity(ref, frame)))
    cap.release()

    if not samples:
        return False, {"error": "视频抽帧失败"}

    # 取汉明距离最小的那帧作为判定依据
    best_k, _best_frame, best_sim = min(samples, key=lambda s: s[2]["phash_hamming"])
    passed, reasons = judge(best_sim)
    return passed, {
        "ref": ref_img_path,
        "video": video_path,
        "video_frames": total,
        "compare_frame": start + best_k,
        "metrics": best_sim,
        "all_samples": [{"offset": k, **s} for k, _f, s in samples],
        "thresholds": THRESHOLDS,
        "passed": passed,
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# 二、浏览器侧：上传 + 挂载确认
# ---------------------------------------------------------------------------
def _snapshot(page):
    """上传前后各取一次 DOM 快照，用于确认素材是否真的挂上。

    实测确认信号（不是靠 img 总数，那个会被页面其他区域干扰）：
    挂载成功后提示词框会多出
        .prompt-top-row.has-ingredient-bar
        └─ .prompt-ingredient-bar > .ingredient-bar-container
           └─ .chip-container > .chip-image-wrapper > img
    因此以 chip / ingredient-bar 的出现与增长为准。
    """
    try:
        return page.evaluate("""() => {
            const bars = document.querySelectorAll('.prompt-ingredient-bar,.ingredient-bar-container');
            const chips = document.querySelectorAll('.chip-container');
            const chipImgs = document.querySelectorAll('.chip-image-wrapper img,.chip-container img');
            return {
                ingredient_bar: bars.length,
                chips: chips.length,
                chip_imgs: chipImgs.length,
                chip_src: Array.from(chipImgs).map(i => (i.src||'').slice(0, 48)),
                img_count: document.querySelectorAll('img').length,
            };
        }""")
    except Exception as e:
        return {"error": repr(e)[:120]}


def clear_ingredients(page, max_clicks=8):
    """清空提示词框里已挂载的 ingredient，避免多镜头累积串味。

    实测：移除按钮不是 button，而是文本为 "cancel" 的 **mat-icon**
    （`.chip-container > mat-icon`），用 button 选择器会一个都点不掉。
    返回移除的 chip 数量。
    """
    removed = 0
    for _ in range(max_clicks):
        try:
            btn = page.locator(".chip-container mat-icon").first
            if btn.count() == 0:
                break
            btn.click(force=True, timeout=3000)
            page.wait_for_timeout(500)
            removed += 1
        except Exception:
            break
    return removed


def _open_ingredients_panel(page):
    page.locator("button[aria-label='Add ingredients to the prompt box']").first.click(
        force=True, timeout=8000)
    page.wait_for_timeout(1600)


def _close_panel(page):
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    page.wait_for_timeout(600)


def _find_item(page, fname):
    return page.locator(f"div.cdk-overlay-container button:has-text('{fname}')").first


def _upload_via_media_menu(page, image_path, timeout_ms):
    """备用上传路径：Add media menu → Upload。已验证能把文件送进项目媒体库。"""
    page.locator("button[aria-label='Add media menu']").first.click(force=True, timeout=8000)
    page.wait_for_timeout(900)
    up = page.locator(
        "[role='menuitem']:has-text('Upload'), button:has-text('Upload')").first
    if up.count() == 0:
        return False
    with page.expect_file_chooser(timeout=timeout_ms) as fc_info:
        up.click(force=True, timeout=8000)
    fc_info.value.set_files(image_path)
    # 上传后服务端还要转码入库，点选得太早会选中一个还没就绪的条目（实测踩过）
    page.wait_for_timeout(6000)
    _close_panel(page)
    return True


def attach_start_frame(page, image_path, timeout_ms=30000, settle_sec=3.0, debug_dir=None):
    """上传首帧到 Flow 并挂进提示词框，随后确认真的挂上了。

    真实交互链路（实测得出，与「点一下上传就完事」的想当然不同）：
        button[aria-label='Add ingredients to the prompt box']  打开素材面板
        → 面板里若没有该素材：点 'Upload media'，拦截系统文件选择器注入文件
        → 在面板中**点选**该素材（只上传不选中是不会挂上去的）
        → 点 'Add to prompt'
    只做上传这一步，素材只会躺在项目媒体库里，Veo 根本看不到它——
    这正是此前首帧"挂了等于没挂"的原因。

    返回 (ok: bool, detail: dict)。**不点击生成，不消耗积分。**
    """
    if not os.path.exists(image_path):
        return False, {"error": f"首帧文件不存在: {image_path}"}

    fname = os.path.basename(image_path)
    detail = {"image": image_path, "file": fname}
    detail["before"] = _snapshot(page)

    try:
        # 1. 打开 ingredients 面板
        _open_ingredients_panel(page)

        # 2. 面板里没有该素材就先上传（面板内的 Upload media 有时不出现，
        #    因此回退到已验证可用的 Add media menu → Upload 路径）
        item = _find_item(page, fname)
        if item.count() == 0:
            _close_panel(page)
            if not _upload_via_media_menu(page, image_path, timeout_ms):
                return False, {**detail, "error": "未找到 Upload 入口"}
            detail["uploaded"] = True
            _open_ingredients_panel(page)
            item = _find_item(page, fname)
        else:
            detail["uploaded"] = False

        if item.count() == 0:
            return False, {**detail, "error": "上传后仍在面板中找不到该素材"}

        # 3. 点选挂载。素材刚上传时可能尚未就绪，故带重试
        base = detail["before"]
        attached_now = False
        for attempt in range(1, 4):
            item = _find_item(page, fname)
            if item.count() == 0:
                _close_panel(page)
                page.wait_for_timeout(1800)
                _open_ingredients_panel(page)
                continue
            item.click(force=True, timeout=6000)
            page.wait_for_timeout(1200)
            detail["selected"] = True

            mid = _snapshot(page)
            attached_now = (mid.get("chips", 0) > base.get("chips", 0)
                            or mid.get("ingredient_bar", 0) > base.get("ingredient_bar", 0))
            if attached_now:
                break

            # 兜底：面板若有 Add to prompt，再点一次
            add = page.locator(
                "div.cdk-overlay-container button:has-text('Add to prompt')").first
            if add.count() > 0:
                try:
                    add.click(force=True, timeout=5000)
                    page.wait_for_timeout(1500)
                    detail["add_clicked"] = True
                except Exception:
                    pass
                mid = _snapshot(page)
                attached_now = (mid.get("chips", 0) > base.get("chips", 0)
                                or mid.get("ingredient_bar", 0) > base.get("ingredient_bar", 0))
                if attached_now:
                    break
            detail["attempts"] = attempt
            _close_panel(page)
            page.wait_for_timeout(1500)
            _open_ingredients_panel(page)
    except Exception as e:
        detail["error"] = repr(e)[:200]
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        return False, detail
    finally:
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass

    page.wait_for_timeout(1200)
    detail["after"] = _snapshot(page)

    if debug_dir:
        os.makedirs(debug_dir, exist_ok=True)
        try:
            page.screenshot(path=os.path.join(debug_dir, "frame_attached.png"))
        except Exception:
            pass

    b_, a_ = detail["before"], detail["after"]
    bar_added = a_.get("ingredient_bar", 0) > b_.get("ingredient_bar", 0)
    chip_added = a_.get("chips", 0) > b_.get("chips", 0)
    img_added = a_.get("chip_imgs", 0) > b_.get("chip_imgs", 0)
    detail["attached"] = bool(bar_added or chip_added or img_added)
    detail["signal"] = {"bar_added": bar_added, "chip_added": chip_added, "chip_img_added": img_added}
    return detail["attached"], detail


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Google Flow 首帧锁定器")
    ap.add_argument("--attach", help="上传并挂载首帧到 Flow（不消耗积分）")
    ap.add_argument("--clear-first", action="store_true", help="挂载前先清空已挂的 ingredient")
    ap.add_argument("--ref", help="参考首帧图，配合 --video 做离线校验")
    ap.add_argument("--video", help="成片视频路径")
    ap.add_argument("--pos", type=float, default=0.0, help="取视频该比例的帧，默认 0（首帧）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.ref and args.video:
        passed, rep = verify_frame_lock(args.ref, args.video, args.pos)
        if args.json:
            print(json.dumps(rep, ensure_ascii=False, indent=2))
        else:
            print(f"参考图: {rep.get('ref')}")
            print(f"成片  : {rep.get('video')}  (比对第 {rep.get('compare_frame')} 帧)")
            m = rep.get("metrics", {})
            print(f"  汉明距离={m.get('phash_hamming')}  直方图相关={m.get('hist_corr')}  结构相关={m.get('gray_corr')}")
            print(f"  判定: {'PASS 首帧已锁定' if passed else 'FAIL 首帧漂移'}")
            for r in rep.get("reasons", []):
                print(f"    - {r}")
        sys.exit(0 if passed else 2)

    if args.attach:
        for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
            os.environ.pop(k, None)
        os.environ["NO_PROXY"] = "*"
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            ctx = b.contexts[0]
            page = next((pg for pg in ctx.pages if "flow.google.com" in pg.url), None)
            if page is None:
                print("未找到 Flow 页面"); sys.exit(1)
            page.bring_to_front(); page.wait_for_timeout(1500)
            if args.clear_first:
                n = clear_ingredients(page)
                print(f"已清空 {n} 个已挂载 ingredient")
                page.wait_for_timeout(800)
            ok, detail = attach_start_frame(page, args.attach, debug_dir="output/_frame_lock_debug")
            print(json.dumps(detail, ensure_ascii=False, indent=2))
            print("挂载成功" if ok else "挂载失败")
            b.close()
        sys.exit(0)

    ap.print_help()


if __name__ == "__main__":
    main()
