#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OOTD 无手机全链路极速重渲端到端流水线（按需 9 块剪枝版）。

项目：ootd_multilook_nophone
输出目录：output/2026-10-03/ootd_multilook_nophone/
核心策略：
1. 剪辑级按需剪枝：仅渲染 12.033s BGM 拍点成片所需的 9 个分块（从 25 块缩至 9 块，纯渲染 ~1.8h）
2. 驱动分块复用：导出 4 个 49 帧驱动分块，无用分块以 dummy 对齐，零位移保证全局时间线一致
3. RIFE 补帧增强：5 套版本逐套执行 16fps -> 30fps (1080x1920)
4. 静态角标与主画面直通：跳过 BiRefNet 冗余抠像，静态参考图队列卡片贴入，生成成片
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import time

import cv2
import numpy as np

ROOT = r"D:\ai_projects\ComfyUI"
for _p in (os.path.join(ROOT, "tools"), os.path.join(ROOT, "tools", "ootd_study")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import h3_fast_submit as base        # noqa: E402
import h3_fast_segmented as seg      # noqa: E402
import ootd_multilook as ml          # noqa: E402
import multilook_compose as mc       # noqa: E402

DATE = "2026-10-03"
PROJECT = "ootd_multilook_nophone"
OUT = os.path.join(ROOT, "output", DATE, PROJECT)
VER = os.path.join(OUT, "versions")
SWAP_DIR = os.path.join(OUT, "swap_nophone")
DRIVING = os.path.join(ROOT, "input", "ootd_target_clean.mp4")
DRV16 = os.path.join(OUT, "drv16.mp4")
PLATE = os.path.join(ROOT, "output", "2026-10-02", "ootd_multilook_poc", "plate_clean.png")
LOGF = os.path.join(OUT, "chain_nophone_fast.log")
PROGRESS_FILE = os.path.join(OUT, "render_progress.json")
PIDS_FILE = os.path.join(OUT, "prequeue_pids.json")
REPORT_FILE = os.path.join(OUT, "multilook_report.json")
WORKFLOW_PATH = ml.WORKFLOW
SIZE = (480, 832)
CHUNK_LEN = 49
FPS = 16.0
SEED_BASE = 20261003

# 9 块渲染计划：(look_index, look_id, chunk_index)
# 对应成片时间线切点：[2.926, 5.329, 7.732, 10.135], 总长 12.033s
RENDER_PLAN = [
    (1, "g1", 0),  # 0.00s ~ 2.93s 主画面 (Chunk 0)
    (2, "g2", 0),  # 2.93s ~ 5.33s 主画面 (跨 Chunk 0 尾与 Chunk 1 前)
    (2, "g2", 1),
    (3, "g3", 1),  # 5.33s ~ 7.73s 主画面 (跨 Chunk 1 尾与 Chunk 2 前)
    (3, "g3", 2),
    (4, "g4", 2),  # 7.73s ~ 10.14s 主画面 (跨 Chunk 2 尾与 Chunk 3 前)
    (4, "g4", 3),
    (5, "g5", 2),  # 10.14s ~ 12.03s 主画面 (跨 Chunk 2 与 Chunk 3)
    (5, "g5", 3),
]


def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOGF), exist_ok=True)
        with open(LOGF, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def setup_workspace():
    """初始化今日输出目录与素材配置。"""
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(VER, exist_ok=True)
    os.makedirs(SWAP_DIR, exist_ok=True)

    # 拷贝 5 张去手机参考图
    src_swap = os.path.join(ROOT, "output", "2026-10-02", "ootd_multilook_full", "swap_nophone")
    looks = []
    for k in range(1, 6):
        src_png = os.path.join(src_swap, f"g{k}_00001_.png")
        dst_png = os.path.join(SWAP_DIR, f"g{k}_00001_.png")
        if not os.path.exists(dst_png) and os.path.exists(src_png):
            shutil.copy2(src_png, dst_png)
        if not os.path.exists(dst_png):
            raise RuntimeError(f"缺少去手机参考图: {dst_png}")
        input_name = ml.copy_to_input(dst_png, f"{PROJECT}_look{k}.png")
        looks.append({"id": f"g{k}", "key": f"g{k}", "index": k,
                      "path": dst_png, "input_name": input_name})

    looks_json = os.path.join(OUT, "looks_5_nophone.json")
    with open(looks_json, "w", encoding="utf-8") as f:
        json.dump([{"id": x["id"], "image": x["path"]} for x in looks],
                  f, ensure_ascii=False, indent=2)

    log(f"[setup] 参考图已就绪: {len(looks)} 张 -> {looks_json}")
    return looks


def prepare_driving_chunks():
    """规范化驱动视频并切出 4 个驱动分块 + 1 个 dummy 对齐块。"""
    if not os.path.exists(DRIVING):
        raise RuntimeError(f"驱动视频不存在: {DRIVING}")

    # 规范化为 16fps（clean 版已有遮罩，mask_rects 为空）
    if not os.path.exists(DRV16):
        log(f"[driving] 规范化驱动视频 16fps: {DRIVING} -> {DRV16}")
        ok, err = ml.normalize_driving(DRIVING, DRV16, fps=FPS, mask_rects=None)
        if not ok:
            raise RuntimeError(f"驱动规范化失败: {err}")
    total = ml.probe_nb_frames(DRV16)
    log(f"[driving] 驱动视频已就绪: {total} 帧 @ {FPS}fps")

    chunks = ml.plan_chunks(total, CHUNK_LEN)
    chunk_in_names = []
    for i in range(4):  # 仅需前 4 块 (0..3)，覆盖 0~12.25s
        start, raw, length = chunks[i]
        name = f"{PROJECT}_drv_chunk{i}.mp4"
        dst = os.path.join(base.INPUT_ROOT, name)
        if not os.path.exists(dst):
            log(f"[driving] 导出分块 chunk{i}: start={start} raw={raw} length={length} -> {name}")
            ok, err = ml.export_chunk(DRV16, start, raw, length, dst, fps=FPS)
            if not ok:
                raise RuntimeError(f"分块导出失败 chunk{i}: {err}")
        chunk_in_names.append(name)

    # 创建一个 dummy 块（49 帧全黑视频），用于无缝填充未渲染的分块
    dummy_path = os.path.join(VER, "dummy_chunk.mp4")
    if not os.path.exists(dummy_path):
        ff = base.resolve_ffmpeg()
        cmd = [ff, "-y", "-f", "lavfi", "-i",
               f"color=c=black:s={SIZE[0]}x{SIZE[1]}:d={CHUNK_LEN / FPS}:r={FPS}",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart", dummy_path]
        subprocess.run(cmd, capture_output=True, check=True)
        log(f"[driving] 生成时间线占位 dummy 块: {dummy_path}")

    return chunks[:4], chunk_in_names, dummy_path


def render_9_chunks(looks, chunk_in_names, chunks):
    """预检并提交 9 个核心渲染块，等待完成。"""
    with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
        tpl = json.load(f)

    look_map = {x["id"]: x for x in looks}
    prog = {"completed": [], "chunks": {}}
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                prog = json.load(f)
        except Exception:
            pass

    log(f"\n=== 开始 9 块按需渲染流水线（总任务数: {len(RENDER_PLAN)}）===")

    for k, look_id, i in RENDER_PLAN:
        key = f"{k}_{i}"
        expected_len = chunks[i][2]
        out_name = f"{k}_{i}_00001_.mp4"
        final_mp4 = os.path.join(VER, out_name)

        # 检查是否已完成
        if os.path.exists(final_mp4) and os.path.getsize(final_mp4) > 10000:
            log(f"[render][look {look_id} chunk{i}] 已存在产物，跳过: {out_name}")
            if key not in prog["completed"]:
                prog["completed"].append(key)
            continue

        it = look_map[look_id]
        seed = SEED_BASE + k * 1000 + i
        prefix = f"{DATE}/{PROJECT}/versions/{key}"

        wf = base.inject_placeholders(tpl, {
            "reference_image": it["input_name"],
            "driving_video": chunk_in_names[i],
            "width": SIZE[0],
            "height": SIZE[1],
            "length": expected_len,
            "frame_offset": 0,
            "seed": seed,
            "output": prefix,
        })

        errors, _ = ml.validate_nodes(wf)
        if errors:
            raise RuntimeError(f"工作流校验失败 ({key}): {errors}")

        t0 = time.time()
        log(f"[render][look {look_id} chunk{i}] 提交 ComfyUI 队列 (seed={seed}, length={expected_len})...")
        pid = ml.submit(wf)
        log(f"[render][look {look_id} chunk{i}] 已入队 pid={pid}，等待渲染完成...")

        rec = base.wait_done(pid)
        if not rec:
            raise RuntimeError(f"渲染任务失败或超时: {key} (pid={pid})")

        elapsed = round(time.time() - t0, 1)
        # 验证产物
        if not os.path.exists(final_mp4):
            # 尝试在输出目录匹配
            cands = glob.glob(os.path.join(VER, f"{k}_{i}_*.mp4"))
            if cands:
                final_mp4 = max(cands, key=os.path.getmtime)
            else:
                raise RuntimeError(f"未找到渲染产物: {final_mp4}")

        log(f"[render][look {look_id} chunk{i}] 完成! 耗时={elapsed}s -> {os.path.basename(final_mp4)}")
        prog["completed"].append(key)
        prog["chunks"][key] = {"pid": pid, "output": final_mp4, "seconds": elapsed}
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(prog, f, ensure_ascii=False, indent=2)

    log("[render] 9 块核心 Wan Animate 渲染全部顺利完成!")


def assemble_and_enhance_versions(chunks, dummy_path):
    """将分块按时间线对齐拼接为 5 套完整 full16，并提交 RIFE 补帧增强。"""
    log("\n=== 组装 5 套全局时间线版本并进行 RIFE 补帧 ===")
    v_enhanced = {}
    total_4chunks = sum(c[2] for c in chunks)
    exps = [c[2] for c in chunks]

    # 每个 Look 的真实渲染块集合
    active_chunks = {
        1: [0],
        2: [0, 1],
        3: [1, 2],
        4: [2, 3],
        5: [2, 3],
    }

    for k in range(1, 6):
        v16 = os.path.join(VER, f"v{k}_full16.mp4")
        e30_pattern = os.path.join(VER, f"v{k}_30_*.mp4")
        cands_e30 = glob.glob(e30_pattern)
        if cands_e30 and os.path.exists(cands_e30[0]) and os.path.getsize(cands_e30[0]) > 10000:
            log(f"[enhance][v{k}] 已存在 30fps 增强产物，跳过: {os.path.basename(cands_e30[0])}")
            v_enhanced[f"g{k}"] = cands_e30[0]
            continue

        # 组织 4 个块的输入文件（渲染块用真块，未渲染用 dummy_path）
        chunk_files = []
        for i in range(4):
            real_file = os.path.join(VER, f"{k}_{i}_00001_.mp4")
            if i in active_chunks[k] and os.path.exists(real_file):
                chunk_files.append(real_file)
            else:
                chunk_files.append(dummy_path)

        log(f"[assemble][v{k}] 拼接 full16 (有效分块: {active_chunks[k]})...")
        ok, err, cinfo = ml.concat_full16(chunk_files, v16, DRV16, exps, total_4chunks, fps=FPS)
        if not ok:
            raise RuntimeError(f"v{k} 拼接失败: {err}")
        log(f"[assemble][v{k}] full16 完成: {v16}")

        # 提交 RIFE 补帧增强 (16fps -> 30fps, 1080x1920)
        log(f"[enhance][v{k}] 提交 RIFE 补帧超分 (16->30fps, 1080x1920)...")
        prefix = f"{DATE}/{PROJECT}/versions/v{k}_30"
        ok_e, _, _ = ml.enhance_version(
            v16, prefix, [1080, 1920], 30.0, os.path.join(OUT, "enhance")
        )
        if not ok_e:
            raise RuntimeError(f"v{k} RIFE 补帧失败")

        cands = glob.glob(os.path.join(VER, f"v{k}_30_*.mp4"))
        if not cands:
            raise RuntimeError(f"未找到增强产物: v{k}_30_*.mp4")
        e30 = max(cands, key=os.path.getmtime)
        log(f"[enhance][v{k}] 补帧增强完成! -> {os.path.basename(e30)}")
        v_enhanced[f"g{k}"] = e30

    return v_enhanced


def prepare_matte_bypass(v_enhanced):
    """短路 BiRefNet 抠像：准备全白蒙版，实现 100% 直通合成。"""
    matte_dir = os.path.join(OUT, "matte")
    os.makedirs(matte_dir, exist_ok=True)
    # 为每个版本生成 1 张 540x960 全白 PNG 作为软 mask 缓存
    for vid, mp4 in v_enhanced.items():
        d = os.path.join(matte_dir, vid)
        os.makedirs(d, exist_ok=True)
        nb_frames = ml.probe_nb_frames(mp4)
        have = len(glob.glob(os.path.join(d, "*.png")))
        if have < nb_frames:
            log(f"[matte-bypass][{vid}] 预制直通蒙版 (全白 alpha, 共 {nb_frames} 帧)...")
            white_mask = np.full((960, 540), 255, dtype=np.uint8)
            # 批量写入序列以命中 multilook_compose 的 _matte_complete 复用检查
            for fi in range(1, nb_frames + 1):
                cv2.imwrite(os.path.join(d, f"{fi:06d}.png"), white_mask)
            log(f"[matte-bypass][{vid}] 直通蒙版就绪 (已跳过 BiRefNet，节省 25 分钟)")


def compose_final_collage(looks, v_enhanced):
    """调用合成器生成最终的卡点成片。"""
    out_path = os.path.join(OUT, f"{PROJECT}_collage.mp4")
    log(f"\n=== 开始最终成片合成: {out_path} ===")

    versions_cfg = [{"id": vid, "video": p} for vid, p in sorted(v_enhanced.items())]
    look_images = [x["path"] for x in looks]

    cfg = {
        "project": PROJECT,
        "date": DATE,
        "driving": DRIVING,
        "out_dir": OUT,
        "out_path": out_path,
        "plate": PLATE if os.path.exists(PLATE) else None,
        "versions": versions_cfg,
        "looks": look_images,
        "tiles_mode": "ref",        # 静态参考图卡片
        "no_main_dash": True,       # 主人物去虚线
        "bgm_auto": True,           # 自动匹配 Calling_Through_The_Screen 拍点
        "cuts": [2.926, 5.329, 7.732, 10.135],
        "fps": 30,
        "size": [1080, 1920],
        "single_person": False,     # 直通模式无需单人物过滤
    }

    t0 = time.time()
    res = mc.run_compose(cfg)
    elapsed = round(time.time() - t0, 1)

    if not os.path.exists(out_path):
        raise RuntimeError(f"合成成片文件未生成: {out_path}")

    dur = seg.probe_duration(out_path)
    fps_val = seg.probe_fps(out_path)
    frames = ml.probe_nb_frames(out_path)
    size_mb = os.path.getsize(out_path) / 1e6
    has_a = seg.has_audio(out_path)

    log(f"\n=======================================================")
    log(f"★ 极速重渲全流程顺利达成! ★")
    log(f"成片路径: {out_path}")
    log(f"规格指标: {dur:.2f}s | {fps_val:.1f}fps | {frames}帧 | {size_mb:.1f}MB | 音轨={has_a}")
    log(f"合成耗时: {elapsed}s")
    log(f"=======================================================")
    return out_path


def main():
    log(f"=== OOTD 无手机全链路重渲流水线启动 (项目: {PROJECT}) ===")
    t_start = time.time()

    looks = setup_workspace()
    chunks, chunk_in_names, dummy_path = prepare_driving_chunks()
    render_9_chunks(looks, chunk_in_names, chunks)
    v_enhanced = assemble_and_enhance_versions(chunks, dummy_path)
    prepare_matte_bypass(v_enhanced)
    out_collage = compose_final_collage(looks, v_enhanced)

    total_time = round((time.time() - t_start) / 60, 1)
    log(f"[ALL DONE] 全部端到端流程执行完毕，总耗时 {total_time} 分钟。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
