#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OOTD 图文 -> 视频全链路编排（series.json 驱动）

把「Flux 图文批量生成（ootd_series_submit.py）」与「H3 4 步快线 I2V 直驱」编排成
一条命令：每张系列图各出一段 736x1088 / 73 帧（≈3.04s）带原生音频的短视频，
逐段抽帧亮度验收，硬切合并成片，并输出汇总报告 + 首帧比例适配判读。

阶段划分（--stage）：
  images  仅图文：子进程调用 tools/ootd_study/ootd_series_submit.py（--resume 断点续跑）
  video   仅视频：发现 output/<date>/<project>/img/ 下系列图 -> 逐图 I2V -> 合并
  all     图文 + 视频（默认）

视频阶段默认 H3 I2V 直驱（--mode i2v）；--mode reactor 复用
run_ootd_faceswap_bg_v4.build_workflow_v4()（ReActor 换脸 + 背景置换，实拍驱动）。

归档规则：
  图   output/<date>/<project>/img/<shot_id>_*.png
  段   output/<date>/<project>/s<i>_*.mp4
  成片 output/<date>/<project>/<project>_merged.mp4
  报告 output/<date>/<project>/pipeline_report.json

用法:
  # 全链路（图文已存在则复用）
  python tools/ootd_study/ootd_pipeline.py --stage all \
      --series tools/ootd_study/series/ootd_blue_shirt.json

  # 只补图文（--resume 跳过已完成 shot）
  python tools/ootd_study/ootd_pipeline.py --stage images

  # 只跑视频（复用已有图文）+ 干跑校验（预检 + 逐节点，不提交）
  python tools/ootd_study/ootd_pipeline.py --stage video --dry-run

  # 视频最小冒烟（只处理前 1 张图）并做首帧比例适配判读
  python tools/ootd_study/ootd_pipeline.py --stage video --limit 1 --first-frame-check

  # 复用已生成分段，仅重拼成片
  python tools/ootd_study/ootd_pipeline.py --stage video --merge-only

  # ReActor 实拍驱动分支（540x960 / 25fps / 60 帧快速档）
  python tools/ootd_study/ootd_pipeline.py --mode reactor \
      --source-video ootd_target.mp4 --face characters/v3/C01_FACE_FRONT.png \
      --bg bg_paris_terrace.jpg --frames 60

复用 tools/h3_fast_submit.py（注入/校验/排队等待/验收/预检）、
tools/h3_fast_segmented.py（merge_segments/probe_duration/has_audio/discover_segments）与
tools/ootd_study/run_ootd_faceswap_bg_v4.py（build_workflow_v4）。
仅依赖标准库 + 上述模块 + venv 内已装的 av/numpy。
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import date as _date

# --- sys.path: 同时含 tools/ 与 tools/ootd_study/ ---
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS_DIR = os.path.dirname(_THIS_DIR)
for _p in (_TOOLS_DIR, _THIS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import h3_fast_submit as base          # noqa: E402
import h3_fast_segmented as seg        # noqa: E402

# ROOT = 上三级目录（tools/ootd_study/ootd_pipeline.py -> ComfyUI），带 input/ 兜底
_ROOT = os.path.dirname(_TOOLS_DIR)
if not os.path.isdir(os.path.join(_ROOT, "input")):
    _ROOT = base.ROOT
ROOT = _ROOT
INPUT_ROOT = os.path.join(ROOT, "input")
OUTPUT_ROOT = os.path.join(ROOT, "output")

DEFAULT_SERIES = os.path.join(_THIS_DIR, "series", "ootd_blue_shirt.json")
DEFAULT_I2V_WORKFLOW = os.path.join(ROOT, "workflows", "v5", "h3_fast_i2v_9x16_api.json")
IMG_SUBMIT = os.path.join(_THIS_DIR, "ootd_series_submit.py")

# 缺省运动提示词（shot 未提供 motion_prompt 时使用）
DEFAULT_MOTION = (
    "she breathes softly with subtle natural movement, gentle weight shift, "
    "the outfit fabric sways lightly, calm gaze into the mirror, steady camera, "
    "photorealistic daily OOTD mood"
)


# ----------------------------- 工具 -----------------------------

def _ascii_slug(s):
    """把项目名归一为稳定 ASCII 标识（用于 input 文件名），避免中文/空格。"""
    s = re.sub(r"[^0-9A-Za-z_-]+", "_", str(s)).strip("_")
    return s or "project"


def load_series(path):
    if not os.path.exists(path):
        raise ValueError(f"系列配置不存在: {path}")
    with open(path, "r", encoding="utf-8-sig") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"系列配置 JSON 解析失败: {e}")
    if not isinstance(data, dict):
        raise ValueError("系列配置根节点必须是 JSON 对象")
    if not data.get("project"):
        raise ValueError("系列配置缺少 project")
    if not isinstance(data.get("shots"), list) or not data["shots"]:
        raise ValueError("系列配置 shots 缺失或为空")
    return data


def discover_images(series, img_dir, limit=0):
    """按 shots 顺序匹配 output/<date>/<project>/img/^{shot_id}_*.png（取最新一张）。

    返回 [{shot_id, shot, png}]；未匹配到的 shot 跳过并告警。limit>0 时只取前 N 张。
    """
    found = []
    missing = []
    for shot in series["shots"]:
        sid = shot.get("id")
        if not sid:
            continue
        cands = glob.glob(os.path.join(img_dir, f"{sid}_*.png"))
        cands = [p for p in cands if os.path.exists(p)]
        if not cands:
            missing.append(sid)
            continue
        png = max(cands, key=os.path.getmtime)
        found.append({"shot_id": sid, "shot": shot, "png": png})
    if missing:
        print(f"[警告] 以下 shot 未在 img/ 中找到对应 PNG，已跳过: {', '.join(missing)}")
    if limit and limit > 0:
        found = found[:limit]
    return found


def copy_to_input(slug, shot_id, png):
    """把图拷贝到 input/ 稳定 ASCII 名，返回相对名。"""
    name = f"ootd_{slug}_{shot_id}.png"
    dst = os.path.join(INPUT_ROOT, name)
    shutil.copy2(png, dst)
    return name


def build_i2v_wf(template, first_frame, prompt, width, height, length, seed, filename_prefix):
    return base.inject_placeholders(template, {
        "first_frame": first_frame, "prompt": prompt,
        "width": width, "height": height, "length": length,
        "seed": seed, "filename_prefix": filename_prefix})


def submit(wf):
    """POST /prompt，返回 prompt_id；node_errors 非空时抛错。"""
    r = base._post_json("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
    if r.get("node_errors"):
        raise RuntimeError("node_errors: "
                           + json.dumps(r["node_errors"], ensure_ascii=False)[:1200])
    pid = r.get("prompt_id")
    if not pid:
        raise RuntimeError("提交未返回 prompt_id: "
                           + json.dumps(r, ensure_ascii=False)[:400])
    return pid


def find_existing_segment(seg_dir, i):
    cands = glob.glob(os.path.join(seg_dir, f"s{i}_*.mp4"))
    cands = [p for p in cands if os.path.exists(p)]
    return max(cands, key=os.path.getmtime) if cands else None


# ----------------------------- 预检 -----------------------------

def run_prechecks(wf):
    """单实例 / SLA 依赖 / fp16 视频 VAE 为硬检查；可用内存仅告警。"""
    print("\n=== 预检 ===")
    failed = False
    checks = [
        ("单实例", base.check_single_instance, False),
        ("SLA 依赖", base.check_sla_deps, False),
        ("可用内存", lambda: base.check_memory(8.0), True),
        ("视频 VAE fp16", lambda: base.check_video_vae(wf), False),
    ]
    for name, fn, soft in checks:
        try:
            ok, msg = fn()
        except Exception as e:
            ok, msg = False, f"检查异常: {e}"
        if ok:
            print(f"  [通过] {name}: {msg}")
        elif soft:
            print(f"  [警告] {name}: {msg}（仅告警，不拦截）")
        else:
            print(f"  [失败] {name}: {msg}")
            failed = True
    if failed:
        print("\n[失败] 预检未通过，终止（未提交）。")
        return False
    print("[通过] 预检全部通过。")
    return True


# ----------------------------- 首帧比例适配判读 -----------------------------

def _load_rgb(path):
    import av
    with av.open(path) as c:
        for f in c.decode(video=0):
            return f.to_ndarray(format="rgb24")
    return None


def _resize_nn(img, w, h):
    import numpy as np
    sh, sw = img.shape[:2]
    ys = (np.arange(h) * sh / h).astype(np.int64).clip(0, sh - 1)
    xs = (np.arange(w) * sw / w).astype(np.int64).clip(0, sw - 1)
    return img[ys][:, xs]


def _cover_crop(img, w, h):
    """保持比例缩放至覆盖目标尺寸后居中裁剪。"""
    import numpy as np
    sh, sw = img.shape[:2]
    scale = max(w / float(sw), h / float(sh))
    nw, nh = max(w, int(round(sw * scale))), max(h, int(round(sh * scale)))
    r = _resize_nn(img, nw, nh)
    y0 = (nh - h) // 2
    x0 = (nw - w) // 2
    return r[y0:y0 + h, x0:x0 + w]


def _grid_diff(a, b, gw=32, gh=48):
    """降采样到 gw×gh 后求平均绝对像素差（抗噪，用于形态比较）。"""
    import numpy as np
    A = _resize_nn(a, gw, gh).astype(np.float32)
    B = _resize_nn(b, gw, gh).astype(np.float32)
    return float(np.abs(A - B).mean())


def analyze_aspect(src_png, mp4, keep_dir=None):
    """抽 mp4 首帧，与源图做映射策略比对，判读 H3 首帧比例适配行为。

    返回 dict（含 verdict）；keep_dir 非空时把抽出的首帧 PNG 保留在该目录便于人工查看。
    """
    result = {"source_png": src_png, "mp4": mp4}
    ff = base.resolve_ffmpeg()
    if not ff:
        result["verdict"] = "未找到 ffmpeg，无法抽帧判读"
        return result
    tmp = keep_dir or tempfile.mkdtemp(prefix="ootd_ff_check_")
    os.makedirs(tmp, exist_ok=True)
    out_png = os.path.join(tmp, "first_frame.png")
    r = subprocess.run([ff, "-y", "-ss", "0", "-i", mp4, "-frames:v", "1", out_png],
                       capture_output=True)
    if r.returncode != 0 or not os.path.exists(out_png):
        result["verdict"] = "首帧抽帧失败"
        return result
    result["first_frame_png"] = out_png

    bright = base.mean_brightness(out_png)
    result["first_frame_brightness"] = None if bright is None else round(float(bright), 3)

    try:
        import numpy as np  # noqa: F401
        src = _load_rgb(src_png)
        out = _load_rgb(out_png)
    except Exception as e:
        result["verdict"] = f"图像解码失败: {e}"
        return result
    if src is None or out is None:
        result["verdict"] = "源图/首帧解码为空"
        return result

    sh, sw = src.shape[:2]
    oh, ow = out.shape[:2]
    src_asp = sw / float(sh)
    out_asp = ow / float(oh)
    d_stretch = _grid_diff(_resize_nn(src, ow, oh), out)
    d_cover = _grid_diff(_cover_crop(src, ow, oh), out)

    result["source_size"] = f"{sw}x{sh}"
    result["source_aspect"] = round(src_asp, 4)
    result["output_size"] = f"{ow}x{oh}"
    result["output_aspect"] = round(out_asp, 4)
    result["aspect_delta_pct"] = round((out_asp / src_asp - 1.0) * 100, 2)
    result["diff_stretch"] = round(d_stretch, 3)
    result["diff_cover_crop"] = round(d_cover, 3)

    if bright is not None and bright < 3.0:
        result["closer_to"] = "n/a"
        result["verdict"] = f"异常：首帧平均亮度 {bright:.2f} < 3.0，疑似黑屏"
        result["abnormal"] = True
        return result

    if d_stretch + 1.0 < d_cover:
        closer = "stretch"
    elif d_cover + 1.0 < d_stretch:
        closer = "cover_crop"
    else:
        closer = "ambiguous"
    result["closer_to"] = closer
    result["abnormal"] = False
    if closer == "stretch":
        result["verdict"] = (f"首帧更接近「直接拉伸」映射（Δ拉伸={d_stretch:.2f} < Δ裁剪={d_cover:.2f}）；"
                             f"源 {sw}x{sh}({src_asp:.3f}) -> 输出 {ow}x{oh}({out_asp:.3f})，"
                             f"横向比例差 {result['aspect_delta_pct']}%")
    elif closer == "cover_crop":
        result["verdict"] = (f"首帧更接近「缩放+居中裁剪」映射（Δ裁剪={d_cover:.2f} < Δ拉伸={d_stretch:.2f}）；"
                             f"源 {sw}x{sh}({src_asp:.3f}) -> 输出 {ow}x{oh}({out_asp:.3f})")
    else:
        result["verdict"] = (f"拉伸与裁剪两种映射差异接近（Δ拉伸={d_stretch:.2f}，"
                             f"Δ裁剪={d_cover:.2f}），无法明确判定；比例差 {result['aspect_delta_pct']}%")
    return result


# ----------------------------- images 阶段 -----------------------------

def stage_images(args, date):
    """子进程调用 ootd_series_submit.py；--resume 断点续跑。返回 (rc, seconds)。"""
    print(f"\n=== images 阶段（ootd_series_submit.py，date={date}）===")
    t0 = time.time()
    cmd = [sys.executable, IMG_SUBMIT, "--series", args.series, "--date", date, "--resume"]
    if args.dry_run:
        cmd.append("--dry-run")
    print("  " + " ".join(f'"{c}"' if " " in c else c for c in cmd), flush=True)
    rc = subprocess.run(cmd).returncode
    secs = time.time() - t0
    if rc != 0:
        print(f"[失败] 图文阶段退出码 {rc}")
        return rc, secs
    # 校验产物
    img_dir = os.path.join(OUTPUT_ROOT, date, args._project)
    pngs = glob.glob(os.path.join(img_dir, "img", "*.png"))
    if not pngs:
        print(f"[失败] 图文阶段完成但未找到 PNG: {os.path.join(img_dir, 'img')}")
        return 1, secs
    print(f"[通过] 图文阶段完成，img/ 现有 {len(pngs)} 张 PNG")
    return 0, secs


# ----------------------------- video 阶段（I2V） -----------------------------

def stage_video(args, series, date, project, slug, report):
    """发现图 -> 拷贝 input -> 逐段 I2V -> 逐段验收 -> 合并收口。

    返回退出码。report 就地更新。
    """
    lang = base.align_length(args.seg_len)
    if lang != args.seg_len:
        print(f"[对齐] seg-len {args.seg_len} -> {lang}（向上取整到 17k+5）")
    args.seg_len = lang
    for nm, v in (("width", args.width), ("height", args.height)):
        if v % 32 != 0:
            print(f"[警告] {nm}={v} 不是 32 的倍数，模型会自行吸附，建议改 32 倍数")

    seg_dir = os.path.join(OUTPUT_ROOT, date, project)
    img_dir = os.path.join(seg_dir, "img")
    if not os.path.exists(args.i2v_workflow):
        print(f"[失败] I2V 工作流不存在: {args.i2v_workflow}")
        return 1
    with open(args.i2v_workflow, "r", encoding="utf-8") as f:
        template = json.load(f)

    # --- merge-only：跳过生成，直接重拼 ---
    if args.merge_only:
        files = seg.discover_segments(f"{date}/{project}")
        if not files:
            print(f"[失败] 未找到分段: {os.path.join(seg_dir, 's*_*.mp4')}")
            return 1
        print(f"\n=== merge-only 重拼（{len(files)} 段）===")
        segs = []
        for i, p in enumerate(files, start=1):
            dur = seg.probe_duration(p)
            print(f"  - {os.path.basename(p)}  {dur:.3f}s  audio={seg.has_audio(p)}")
            print(f"[段{i}/{len(files)}] 验收（抽首/中/尾帧算亮度）:")
            okb = base.acceptance(p, args.seg_len, 24.0)
            segs.append({"index": i, "path": p, "duration": round(dur, 3),
                         "reused": True, "accepted": okb, "pid": None, "seconds": None})
        report["segments"] = segs
        for it in discover_images(series, img_dir, args.limit):
            report["images"].append({"shot_id": it["shot_id"], "png": it["png"],
                                     "input_name": f"ootd_{slug}_{it['shot_id']}.png"})
        return _do_merge(files, args, date, project, report)

    # --- 发现图 ---
    images = discover_images(series, img_dir, args.limit)
    if not images:
        print(f"[失败] 未发现可用系列图: {os.path.join(img_dir, '<shot_id>_*.png')}")
        return 1
    print(f"\n=== 发现系列图 {len(images)} 张"
          + (f"（--limit {args.limit}）" if args.limit else "") + " ===")
    for it in images:
        print(f"  - {it['shot_id']}: {os.path.basename(it['png'])}")

    # --- 拷贝到 input/ 稳定 ASCII 名 ---
    for it in images:
        it["input_name"] = copy_to_input(slug, it["shot_id"], it["png"])
        print(f"  [拷贝] {os.path.basename(it['png'])} -> input/{it['input_name']}")

    # --- dry-run：逐张注入 + 预检 + 逐节点校验 ---
    if args.dry_run:
        sample = build_i2v_wf(
            template, images[0]["input_name"],
            images[0]["shot"].get("motion_prompt") or DEFAULT_MOTION,
            args.width, args.height, args.seg_len, args.seed + 1,
            f"{date}/{project}/s1")
        if not run_prechecks(sample):
            return 1
        print("\n=== dry-run 逐节点校验（不会 POST /prompt）===")
        errors_all = []
        for i, it in enumerate(images, start=1):
            prompt = it["shot"].get("motion_prompt") or DEFAULT_MOTION
            wf = build_i2v_wf(template, it["input_name"], prompt,
                              args.width, args.height, args.seg_len, args.seed + i,
                              f"{date}/{project}/s{i}")
            print(f"\n[段{i}] first_frame={it['input_name']!r} "
                  f"seed={args.seed + i} prompt[:60]={prompt[:60]!r}")
            errors, lines = base.validate_workflow(wf)
            for ln in lines:
                print(ln)
            if errors:
                errors_all.extend(errors)
                print(f"[段{i}] 校验失败（{len(errors)} 项）:")
                for e in errors:
                    print("  - " + e)
            else:
                print(f"[段{i}] 校验 OK（{len(wf)} 节点）")
        if errors_all:
            print(f"\n[失败] 校验发现 {len(errors_all)} 个问题（dry-run 结束，未提交）")
            return 1
        print(f"\n[通过] {len(images)} 段全部校验通过（dry-run 结束，未提交）")
        return 0

    # --- 真跑：预检一次 ---
    sample = build_i2v_wf(
        template, images[0]["input_name"],
        images[0]["shot"].get("motion_prompt") or DEFAULT_MOTION,
        args.width, args.height, args.seg_len, args.seed + 1,
        f"{date}/{project}/s1")
    if not run_prechecks(sample):
        return 1

    # --- 逐段生成 ---
    n = len(images)
    print(f"\n=== 分段阶段（{n} 段 × {args.seg_len} 帧 @ {args.width}×{args.height}）===")
    seg_files = []
    submitted = []
    for i, it in enumerate(images, start=1):
        t0 = time.time()
        prompt = it["shot"].get("motion_prompt") or DEFAULT_MOTION
        existing = find_existing_segment(seg_dir, i)
        if existing and not args.force:
            mp4 = existing
            dur = seg.probe_duration(mp4)
            print(f"[段{i}/{n}] [复用] {os.path.basename(mp4)}  {dur:.3f}s", flush=True)
            okb = base.acceptance(mp4, args.seg_len, 24.0)
            seg_files.append(mp4)
            report["segments"].append({"index": i, "path": mp4, "duration": round(dur, 3),
                                       "reused": True, "accepted": okb, "pid": None,
                                       "seconds": round(time.time() - t0, 1)})
            if okb is False:
                print(f"[失败] 复用段{i} 抽帧验收未通过，中止（保留现场，可用 --merge-only 重拼）")
                return 1
            continue

        wf = build_i2v_wf(template, it["input_name"], prompt,
                          args.width, args.height, args.seg_len, args.seed + i,
                          f"{date}/{project}/s{i}")
        try:
            pid = submit(wf)
        except Exception as e:
            print(f"[失败] 段{i} 提交异常: {e}")
            return 1
        print(f"[段{i}/{n}] 已提交 pid={pid} first={it['input_name']}", flush=True)
        submitted.append(pid)

        if args.no_wait:
            report["segments"].append({"index": i, "path": None, "duration": None,
                                       "reused": False, "accepted": None, "pid": pid,
                                       "seconds": None})
            continue

        rec = base.wait_done(pid)
        if not rec:
            print(f"[失败] 段{i} 执行失败/超时，中止（保留现场，可用 --merge-only 重拼）")
            return 1
        files = base.find_output_files(rec)
        if not files:
            print(f"[失败] 段{i} 未定位到输出 MP4，中止")
            return 1
        mp4 = files[-1]
        dur = base.exec_seconds(rec.get("status", {})) or 0.0
        seg_files.append(mp4)
        print(f"[段{i}/{n}] 完成 {os.path.basename(mp4)}  执行 {dur:.0f}s  "
              f"本段 {time.time() - t0:.0f}s", flush=True)
        print(f"[段{i}/{n}] 验收（抽首/中/尾帧算亮度）:")
        okb = base.acceptance(mp4, args.seg_len, 24.0)
        seg_dur = seg.probe_duration(mp4)
        report["segments"].append({"index": i, "path": mp4, "duration": round(seg_dur, 3),
                                   "reused": False, "accepted": okb, "pid": pid,
                                   "seconds": round(time.time() - t0, 1)})
        if okb is False:
            print(f"[失败] 段{i} 抽帧亮度验收未通过，中止（保留现场，可用 --merge-only 重拼）")
            return 1

    # --- no-wait：不合并 ---
    if args.no_wait:
        print(f"\n[提示] --no-wait：已提交 {len(submitted)} 段（未等待、未合并）。")
        print(f"       预计分段数 {n}；完成后可运行 --stage video --merge-only 重拼。")
        report["merged"] = None
        _write_report(date, project, report)
        return 0

    # --- 合并 ---
    return _do_merge(seg_files, args, date, project, report)


def _do_merge(seg_files, args, date, project, report):
    if not seg_files:
        print("[失败] 没有可拼接的分段文件")
        return 1
    out_path = os.path.join(OUTPUT_ROOT, date, project, f"{project}_merged.mp4")
    n = len(seg_files)
    t0 = time.time()
    print(f"\n=== 合并阶段（mode={args.transition}, xfade={args.xfade}s, {n} 段）===")
    # 各段来自不同首帧图，接缝无需帧级回退对齐 -> align=off 保证时长精确 = N×seg_len/24
    ok, err = seg.merge_segments(seg_files, out_path, args.xfade,
                                 mode=args.transition, align="off")
    if not ok:
        print("[失败] 合并失败:\n" + err)
        return 1
    total = seg.probe_duration(out_path)
    has_a = seg.has_audio(out_path)
    expected = n * args.seg_len / 24.0
    dur_ok = abs(total - expected) <= 0.5
    report["merged"] = {"path": out_path, "duration": round(total, 3),
                        "has_audio": has_a, "expected_duration": round(expected, 3),
                        "duration_ok": dur_ok, "seconds": round(time.time() - t0, 1)}
    print(f"[完成] 成片: {out_path}")
    print(f"       总时长 {total:.3f}s（期望 ≈{expected:.3f}s = {n}×{args.seg_len}/24，"
          f"容差±0.5s）-> {'通过' if dur_ok else '未通过'}")
    print(f"       含音轨 = {has_a}")

    # --- 首帧比例适配判读（可选） ---
    if getattr(args, "first_frame_check", False):
        print("\n=== 首帧比例适配判读 ===")
        imgs = report.get("images") or []
        src = imgs[0]["png"] if imgs else None
        if src and os.path.exists(src):
            res = analyze_aspect(src, seg_files[0], keep_dir=None)
            report["first_frame_aspect"] = res
            print(f"  源图 {res.get('source_size')} (aspect {res.get('source_aspect')}) -> "
                  f"输出 {res.get('output_size')} (aspect {res.get('output_aspect')})")
            print(f"  首帧亮度 = {res.get('first_frame_brightness')}")
            print(f"  Δ拉伸={res.get('diff_stretch')}  Δ裁剪={res.get('diff_cover_crop')} "
                  f"-> closer_to={res.get('closer_to')}")
            print(f"  抽帧 PNG: {res.get('first_frame_png')}")
            print(f"  判读: {res.get('verdict')}")
        else:
            print("  [警告] 未找到源图，跳过首帧判读")

    _write_report(date, project, report)
    return 0


# ----------------------------- reactor 分支 -----------------------------

def stage_reactor(args, date, project):
    """复用 run_ootd_faceswap_bg_v4.build_workflow_v4（540×960/25fps/frames 帧快速档）。"""
    print(f"\n=== reactor 分支（ReActor 换脸 + 背景置换 v4，date={date}）===")
    try:
        import run_ootd_faceswap_bg_v4 as rv4
    except Exception as e:
        print(f"[失败] 导入 run_ootd_faceswap_bg_v4 失败: {e}")
        return 1

    wf = rv4.build_workflow_v4(
        video=args.source_video,
        bg_image=args.bg,
        char_image=args.face,
        width=540, height=960, fps=25.0,
        frame_load_cap=args.frames,
        codeformer_weight=0.95,
        bg_blur=10,
        prefix="ootd_swap_bg_v4",
    )
    for nm, p in (("源视频", args.source_video), ("背景", args.bg), ("人脸", args.face)):
        full = os.path.join(INPUT_ROOT, p)
        print(f"  {nm}: input/{p}（存在={os.path.exists(full)}）")
    print(f"  档位: 540x960 / 25fps / frames={args.frames} / YOLOv5l + CodeFormer 0.95 / bg_blur=10")

    if args.dry_run:
        print("\n=== dry-run 逐节点校验（不会 POST /prompt）===")
        errors, lines = base.validate_workflow(wf)
        for ln in lines:
            print(ln)
        if errors:
            print(f"\n[失败] 校验发现 {len(errors)} 个问题:")
            for e in errors:
                print("  - " + e)
            return 1
        print("\n[通过] reactor 工作流校验通过（dry-run 结束，未提交）")
        return 0

    print("\n=== 提交 ===")
    try:
        pid = submit(wf)
    except Exception as e:
        print(f"[失败] 提交异常: {e}")
        return 1
    print(f"  已提交 pid={pid}")
    if args.no_wait:
        print("  --no-wait：不等待，退出。")
        return 0
    rec = base.wait_done(pid)
    if not rec:
        print("[失败] 未正常完成")
        return 1
    files = base.find_output_files(rec)
    mp4s = [p for p in files if p.lower().endswith(".mp4")]
    if not mp4s:
        print(f"[失败] 未定位到输出 MP4（outputs={files}）")
        return 1
    mp4 = mp4s[-1]
    print(f"[完成] 归档: {mp4}")
    print(f"       时长 {seg.probe_duration(mp4):.3f}s  含音轨={seg.has_audio(mp4)}")
    base.acceptance(mp4, args.frames, 25.0)
    return 0


# ----------------------------- 报告 -----------------------------

def _write_report(date, project, report):
    report["date"] = date
    report["project"] = project
    report["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    path = os.path.join(OUTPUT_ROOT, date, project, "pipeline_report.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n[报告] {path}")
    return path


# ----------------------------- main -----------------------------

def main():
    ap = argparse.ArgumentParser(
        description="OOTD 图文 -> 视频全链路编排（series.json 驱动；I2V 直驱 / ReActor 分支）")
    ap.add_argument("--stage", choices=["images", "video", "all"], default="all")
    ap.add_argument("--series", default=DEFAULT_SERIES, help="系列配置 series.json 路径")
    ap.add_argument("--project", default=None, help="项目名（默认取 series.project）")
    ap.add_argument("--date", default=None, help="归档日期 YYYY-MM-DD（默认今天）")
    ap.add_argument("--mode", choices=["i2v", "reactor"], default="i2v")
    ap.add_argument("--skip-images", action="store_true", help="跳过图文阶段（复用已有图）")
    ap.add_argument("--merge-only", action="store_true",
                    help="跳过生成，直接重拼 output/<date>/<project>/s*_*.mp4")
    ap.add_argument("--dry-run", action="store_true", help="只预检+逐节点校验，不提交")
    ap.add_argument("--no-wait", action="store_true", help="提交后不等待、不合并")
    ap.add_argument("--force", action="store_true",
                    help="强制重跑已存在的同名分段 s<i>（默认复用并跳过）")
    # I2V 参数
    ap.add_argument("--width", type=int, default=736)
    ap.add_argument("--height", type=int, default=1088)
    ap.add_argument("--seg-len", type=int, default=73, help="每段帧数（17k+5，73≈3.04s）")
    ap.add_argument("--seed", type=int, default=20261002)
    ap.add_argument("--transition", choices=["cut", "crossfade"], default="cut")
    ap.add_argument("--xfade", type=float, default=0.3)
    ap.add_argument("--i2v-workflow", default=DEFAULT_I2V_WORKFLOW)
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 张图（0=全部，最小冒烟用）")
    ap.add_argument("--first-frame-check", action="store_true",
                    help="生成后做首帧比例适配判读（抽首帧 + 源图映射比对）")
    # reactor 参数
    ap.add_argument("--source-video", default="ootd_target.mp4")
    ap.add_argument("--face", default="characters/v3/C01_FACE_FRONT.png")
    ap.add_argument("--bg", default="bg_paris_terrace.jpg")
    ap.add_argument("--frames", type=int, default=60)
    args = ap.parse_args()

    date = args.date or _date.today().isoformat()

    # --- 加载系列 ---
    try:
        series = load_series(args.series)
    except ValueError as e:
        print(f"[失败] {e}")
        return 1
    project = args.project or series["project"]
    args._project = project
    slug = _ascii_slug(project)
    print(f"[系列] {project}（slug={slug}） date={date} stage={args.stage} mode={args.mode}")

    t_all = time.time()
    report = {
        "mode": args.mode,
        "stages": {},
        "images": [],
        "segments": [],
        "merged": None,
        "params": {
            "width": args.width, "height": args.height, "seg_len": args.seg_len,
            "seed": args.seed, "transition": args.transition, "xfade": args.xfade,
            "limit": args.limit,
            "i2v_workflow": os.path.basename(args.i2v_workflow),
        },
    }

    # --- merge-only 短路（不跑图文） ---
    if args.merge_only and args.mode == "i2v":
        return stage_video(args, series, date, project, slug, report)

    # --- images 阶段 ---
    need_images = args.stage in ("images", "all") and not args.skip_images
    if need_images:
        rc, secs = stage_images(args, date)
        report["stages"]["images"] = round(secs, 1)
        if rc != 0:
            return rc
    elif args.skip_images:
        print("[跳过] images 阶段（--skip-images）")
    if args.stage == "images":
        _write_report(date, project, report)
        return 0

    # --- reactor 分支 ---
    if args.mode == "reactor":
        rc = stage_reactor(args, date, project)
        report["stages"]["video"] = round(time.time() - t_all, 1)
        _write_report(date, project, report)
        return rc

    # --- video 阶段（I2V） ---
    # 记录系列图（供报告）
    img_dir = os.path.join(OUTPUT_ROOT, date, project, "img")
    for it in discover_images(series, img_dir, args.limit):
        report["images"].append({"shot_id": it["shot_id"],
                                 "png": it["png"],
                                 "input_name": f"ootd_{slug}_{it['shot_id']}.png"})
    t_v = time.time()
    rc = stage_video(args, series, date, project, slug, report)
    report["stages"]["video"] = round(time.time() - t_v, 1)

    if rc == 0:
        print(f"\n[完成] 全流程结束，作业总耗时 {(time.time() - t_all) / 60:.1f} min")
    return rc


if __name__ == "__main__":
    sys.exit(main())