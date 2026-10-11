#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""H3 fl2v 端到端流水线：参考人物图 + 分镜脚本 -> 关键帧 -> 分段视频 -> 成片

流程:
  1) 关键帧阶段: 用 Qwen-Image-2.1（保身份编辑）为每段首/尾帧各生成一张关键帧 PNG，
     并拷贝到 input/ 下稳定 ASCII 名 fl2v_<project>_k{j}.png，供后续 LoadImage 使用。
  2) 分段阶段: 用 H3 fl2v 工作流（首帧+尾帧+运动提示词）生成 N 段 ≈3.04s(73 帧) 736x1088 视频，
     每段带原生音频；逐段做抽帧亮度验收。
  3) 拼接阶段: 把 N 段硬切（默认 cut，无交叉叠影、保留原生音频）合并成整片。

分镜脚本契约 story.json:
{
  "project": "demo_project",
  "final_keyframe_desc": "英文：全片最后一帧的构图/动作/表情/场景描述",
  "segments": [
    {"keyframe_desc": "英文：本段起始关键帧的描述",
     "motion_prompt": "英文：从本段首帧到尾帧的运动描述（含声音/配乐）"},
    ...
  ]
}

链式规则: N = len(segments)。生成关键帧 K(0)..K(N):
  K(i) = segments[i].keyframe_desc  (i = 0..N-1)
  K(N) = final_keyframe_desc
第 i 段（1-based, i=1..N）: first_frame=K(i-1), last_frame=K(i),
                           prompt=segments[i-1].motion_prompt。

所有输出落在 output/<date>/<project>/ 下；--prefix 默认 "<YYYY-MM-DD>/<project>/fl2v"。

用法:
  # 干跑（预检 + 逐节点校验两个工作流，不提交）
  python tools/h3_fl2v_pipeline.py --dry-run \
      --ref-image "Gemini_Generated_Image_8tttsy8tttsy8ttt (1).jpg" \
      --story "output/2026-10-02/h3_fl2v_verify/story.json"

  # 全流程
  python tools/h3_fl2v_pipeline.py \
      --ref-image "ref.jpg" --story "output/2026-10-02/proj/story.json"

  # 复用已生成关键帧，只跑分段+拼接
  python tools/h3_fl2v_pipeline.py --skip-keyframes --ref-image "ref.jpg" --story story.json

  # 只重拼已有分段（改 --transition 免重跑生成）
  python tools/h3_fl2v_pipeline.py --merge-only --story story.json

复用 tools/h3_fast_submit.py（HTTP/注入/校验/等待/验收/预检）与
tools/h3_fast_segmented.py（拼接/探测/discover_segments）。
"""
import argparse
import json
import os
import re
import shutil
import sys
import time
import uuid
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import h3_fast_submit as base          # noqa: E402
import h3_fast_segmented as seg        # noqa: E402
from qwen_keyframe_submit import precheck as qwen_precheck  # noqa: E402

ROOT = base.ROOT
INPUT_ROOT = base.INPUT_ROOT
OUTPUT_ROOT = base.OUTPUT_ROOT
DEFAULT_KEYFRAME_WORKFLOW = os.path.join(
    ROOT, "workflows", "v5", "qwen_image_2_1_keyframe_api.json")
DEFAULT_FL2V_WORKFLOW = os.path.join(
    ROOT, "workflows", "v5", "h3_fast_fl2v_9x16_api.json")
DEFAULT_REF_IMAGE = "Gemini_Generated_Image_8tttsy8tttsy8ttt (1).jpg"


# ----------------------------- 工具 -----------------------------

def _ascii_slug(s):
    """把项目名归一为稳定 ASCII 标识（用于 input 文件名），避免中文/空格。"""
    s = re.sub(r"[^0-9A-Za-z_-]+", "_", str(s)).strip("_")
    return s or "project"


def load_story(path):
    """读取并校验分镜脚本，返回 dict。"""
    with open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("story.json 顶层必须是对象")
    if not data.get("project"):
        raise ValueError("story.json 缺少 project 字段")
    segs = data.get("segments")
    if not isinstance(segs, list) or not segs:
        raise ValueError("story.json 的 segments 必须是非空数组")
    for idx, s in enumerate(segs):
        if not isinstance(s, dict) or not s.get("keyframe_desc") or not s.get("motion_prompt"):
            raise ValueError(f"segments[{idx}] 需同时含 keyframe_desc 与 motion_prompt")
    if not data.get("final_keyframe_desc"):
        raise ValueError("story.json 缺少 final_keyframe_desc 字段")
    return data


def build_keyframe_descs(story, n):
    """按链式规则返回 K(0)..K(n)，长度为 n+1。"""
    segs = story["segments"]
    if n > len(segs):
        raise ValueError(f"--segments={n} 超过 story 提供的 {len(segs)} 段，无法推导关键帧描述")
    descs = [segs[i]["keyframe_desc"] for i in range(n)]
    descs.append(story["final_keyframe_desc"])
    return descs


def keyframe_input_name(slug, j):
    return f"fl2v_{slug}_k{j}.png"


def build_keyframe_wf(template, ref, prompt, seed, out_prefix):
    return base.inject_placeholders(template, {
        "image": ref, "prompt": prompt, "seed": seed, "output": out_prefix})


def build_fl2v_wf(template, first, last, prompt, width, height, length, seed, filename_prefix):
    return base.inject_placeholders(template, {
        "first_frame": first, "last_frame": last, "prompt": prompt,
        "width": width, "height": height, "length": length,
        "seed": seed, "filename_prefix": filename_prefix})


def submit(wf):
    """POST /prompt，返回 prompt_id；node_errors 非空时抛错。"""
    r = base._post_json("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
    if r.get("node_errors"):
        raise RuntimeError("node_errors: " + json.dumps(r["node_errors"], ensure_ascii=False)[:800])
    pid = r.get("prompt_id")
    if not pid:
        raise RuntimeError(f"提交未返回 prompt_id: {json.dumps(r, ensure_ascii=False)[:400]}")
    return pid


# ----------------------------- 预检 -----------------------------

def run_prechecks(fl2v_wf, keyframe_workflow, skip_keyframes):
    """项目预检：单实例 / SLA 依赖 / 内存(仅告警) / fp16 视频 VAE / Qwen 关键帧预检。

    返回 True 表示硬检查全部通过（内存偏低不拦截）。
    """
    print("\n=== 预检 ===")
    failed = False
    ok, msg = base.check_single_instance()
    print(f"  [{'通过' if ok else '失败'}] 单实例: {msg}")
    failed = failed or not ok

    ok, msg = base.check_sla_deps()
    print(f"  [{'通过' if ok else '失败'}] SLA 依赖: {msg}")
    failed = failed or not ok

    okm, msgm = base.check_memory(8.0)
    print(f"  [{'通过' if okm else '警告'}] 可用内存: {msgm}"
          + ("" if okm else "（偏低，仅告警，不拦截）"))

    ok, msg = base.check_video_vae(fl2v_wf)
    print(f"  [{'通过' if ok else '失败'}] fl2v 视频 VAE fp16: {msg}")
    failed = failed or not ok

    if skip_keyframes:
        print("  [跳过] Qwen 关键帧预检（--skip-keyframes）")
    else:
        kok, klines = qwen_precheck(keyframe_workflow)
        for ln in klines:
            print("  " + ln)
        failed = failed or not kok

    if failed:
        print("\n[失败] 预检未通过，终止（未提交）。")
        return False
    print("[通过] 预检全部通过。")
    return True


# ----------------------------- 各阶段 -----------------------------

def stage_keyframes(template, ref, descs, slug, prefix, seed, no_wait):
    """生成 K(0)..K(N) 关键帧并拷入 input/，返回 input 相对名列表。"""
    n = len(descs) - 1
    print(f"\n=== 关键帧阶段（{len(descs)} 张，Qwen-Image-2.1 保身份）===")
    names = []
    for j, desc in enumerate(descs):
        name = keyframe_input_name(slug, j)
        out_prefix = f"{prefix}/kf/k{j}"
        wf = build_keyframe_wf(template, ref, desc, seed + j, out_prefix)
        pid = submit(wf)
        print(f"[关键帧 {j}/{n}] 已提交 pid={pid} out={out_prefix} seed={seed + j}", flush=True)
        if no_wait:
            names.append(name)
            continue
        rec = base.wait_done(pid)
        if not rec:
            raise RuntimeError(f"关键帧 {j} 执行失败/超时")
        files = base.find_output_files(rec)
        if not files:
            raise RuntimeError(f"关键帧 {j} 未定位到输出 PNG")
        png = files[-1]
        dst = os.path.join(INPUT_ROOT, name)
        shutil.copy2(png, dst)
        names.append(name)
        print(f"[关键帧 {j}/{n}] 完成 {os.path.basename(png)} -> input/{name}", flush=True)
    return names


def stage_segments(template, kf_names, motion_prompts, prefix, args):
    """生成 N 段视频并逐段验收，返回成片文件路径列表。"""
    n = len(motion_prompts)
    print(f"\n=== 分段阶段（{n} 段 × {args.seg_len} 帧 @ {args.width}×{args.height}）===")
    seg_files = []
    for i in range(1, n + 1):
        t0 = time.time()
        wf = build_fl2v_wf(
            template, kf_names[i - 1], kf_names[i], motion_prompts[i - 1],
            args.width, args.height, args.seg_len, args.seed + i, f"{prefix}/s{i}")
        pid = submit(wf)
        print(f"[段{i}/{n}] 已提交 pid={pid} first={kf_names[i - 1]} last={kf_names[i]}", flush=True)
        if args.no_wait:
            continue
        rec = base.wait_done(pid)
        if not rec:
            raise RuntimeError(f"段{i} 执行失败/超时")
        files = base.find_output_files(rec)
        if not files:
            raise RuntimeError(f"段{i} 未定位到输出 MP4")
        mp4 = files[-1]
        seg_files.append(mp4)
        dur = base.exec_seconds(rec.get("status", {})) or 0.0
        print(f"[段{i}/{n}] 完成 {os.path.basename(mp4)}  执行 {dur:.0f}s  本段 {time.time() - t0:.0f}s",
              flush=True)
        okb = base.acceptance(mp4, args.seg_len, 24.0)
        if okb is False:
            raise RuntimeError(f"段{i} 抽帧亮度验收未通过")
    return seg_files


def stage_merge(seg_files, prefix, args):
    """拼接成片，打印总时长与是否含音轨。"""
    if not seg_files:
        raise RuntimeError("没有可拼接的分段文件")
    out_path = os.path.join(OUTPUT_ROOT, prefix + "_merged.mp4")
    print(f"\n=== 拼接阶段（mode={args.transition}, xfade={args.xfade}s, {len(seg_files)} 段）===")
    ok, err = seg.merge_segments(seg_files, out_path, args.xfade, mode=args.transition)
    if not ok:
        raise RuntimeError("拼接失败:\n" + err)
    total = seg.probe_duration(out_path)
    print(f"[完成] 成片: {out_path}")
    print(f"       总时长 {total:.2f}s  含音轨={seg.has_audio(out_path)}")
    return out_path


# ----------------------------- main -----------------------------

def main():
    ap = argparse.ArgumentParser(
        description="H3 fl2v 端到端流水线（参考人物图 + 分镜 -> 关键帧 -> 分段视频 -> 成片）")
    ap.add_argument("--ref-image", default=DEFAULT_REF_IMAGE,
                    help="input 目录下的参考人物图相对路径")
    ap.add_argument("--story", help="分镜脚本 story.json 路径")
    ap.add_argument("--segments", type=int, default=None,
                    help="覆盖 N（默认取 story.segments 长度；不得大于 story 提供的段数）")
    ap.add_argument("--seg-len", type=int, default=73, help="每段帧数（17k+5，73≈3.04s）")
    ap.add_argument("--width", type=int, default=736)
    ap.add_argument("--height", type=int, default=1088)
    ap.add_argument("--seed", type=int, default=20261002)
    ap.add_argument("--prefix", default=None,
                    help='输出前缀（默认 "<YYYY-MM-DD>/<project>/fl2v"）')
    ap.add_argument("--transition", choices=["cut", "crossfade"], default="cut",
                    help="cut=硬切(无叠影，推荐)；crossfade=xfade 交叉溶解(有鬼影风险)")
    ap.add_argument("--xfade", type=float, default=0.3, help="crossfade 时长（秒）")
    ap.add_argument("--dry-run", action="store_true", help="只预检+校验，不提交")
    ap.add_argument("--no-wait", action="store_true", help="只提交不等待")
    ap.add_argument("--skip-keyframes", action="store_true",
                    help="跳过关键帧生成，复用 input/ 下已存在的 fl2v_<project>_k*.png")
    ap.add_argument("--merge-only", action="store_true",
                    help="跳过生成，直接拼接 {prefix}/s*_*.mp4")
    ap.add_argument("--keyframe-workflow", default=DEFAULT_KEYFRAME_WORKFLOW)
    ap.add_argument("--fl2v-workflow", default=DEFAULT_FL2V_WORKFLOW)
    args = ap.parse_args()

    # --- 读取分镜（--prefix 由 project 推导时需要） ---
    story = None
    if args.story:
        if not os.path.exists(args.story):
            print(f"[失败] 分镜脚本不存在: {args.story}")
            return 1
        try:
            story = load_story(args.story)
        except Exception as e:
            print(f"[失败] 解析分镜脚本失败: {e}")
            return 1

    # --- 解析 prefix ---
    if args.prefix:
        prefix = args.prefix
    elif story:
        prefix = f"{date.today().isoformat()}/{_ascii_slug(story['project'])}/fl2v"
    else:
        print("[失败] 未提供 --prefix 时必须提供 --story（用于推导默认 prefix）")
        return 1
    slug = _ascii_slug(story["project"]) if story else _ascii_slug(prefix.split("/")[-1])
    print(f"[配置] prefix={prefix!r}")

    # --- 只重拼 ---
    if args.merge_only:
        seg_files = seg.discover_segments(prefix)
        if not seg_files:
            print(f"[失败] 未找到分段: {os.path.join(OUTPUT_ROOT, prefix)}\\s*_*.mp4")
            return 1
        print(f"[重拼] 分段 {len(seg_files)} 个：")
        for p in seg_files:
            print(f"  - {os.path.basename(p)}  {seg.probe_duration(p):.3f}s  audio={seg.has_audio(p)}")
        try:
            stage_merge(seg_files, prefix, args)
        except Exception as e:
            print(f"[失败] {e}")
            return 1
        return 0

    if not story:
        print("[失败] 全流程必须提供 --story")
        return 1

    # --- N 与关键帧描述 ---
    n = args.segments if args.segments is not None else len(story["segments"])
    if n <= 0:
        print(f"[失败] N={n} 非法")
        return 1
    try:
        descs = build_keyframe_descs(story, n)
    except Exception as e:
        print(f"[失败] {e}")
        return 1
    motion_prompts = [s["motion_prompt"] for s in story["segments"][:n]]

    # --- 帧长对齐 ---
    raw_len = args.seg_len
    args.seg_len = base.align_length(raw_len)
    if args.seg_len != raw_len:
        print(f"[对齐] seg-len {raw_len} -> {args.seg_len}（向上取整到 17k+5）")
    for nm, v in (("width", args.width), ("height", args.height)):
        if v % 32 != 0:
            print(f"[警告] {nm}={v} 不是 32 的倍数，模型会自行吸附，建议改 32 倍数")

    # --- 读取工作流模板 ---
    for path in (args.fl2v_workflow, args.keyframe_workflow):
        if not os.path.exists(path):
            print(f"[失败] 工作流不存在: {path}")
            return 1
    with open(args.fl2v_workflow, "r", encoding="utf-8") as f:
        fl2v_template = json.load(f)
    with open(args.keyframe_workflow, "r", encoding="utf-8") as f:
        kf_template = json.load(f)

    # 用于 dry-run/预检的示例注入（首段）
    kf_names = [keyframe_input_name(slug, j) for j in range(n + 1)]

    # --- dry-run ---
    if args.dry_run:
        # LoadImage.image 会按 input 目录枚举校验，未生成的 KF 用参考图占位以通过校验
        dry_frames = []
        for label, nm in (("首帧", kf_names[0]), ("尾帧", kf_names[1])):
            if os.path.exists(os.path.join(INPUT_ROOT, nm)):
                dry_frames.append(nm)
            else:
                print(f"[提示] dry-run：{label}（{nm}）尚未生成，"
                      f"暂以参考图 {args.ref_image!r} 通过校验")
                dry_frames.append(args.ref_image)
        dry_first, dry_last = dry_frames
        if not os.path.exists(os.path.join(INPUT_ROOT, args.ref_image)):
            print(f"[警告] input 目录下未找到参考人物图: {args.ref_image}")

        fl2v_wf = build_fl2v_wf(
            fl2v_template, dry_first, dry_last, motion_prompts[0],
            args.width, args.height, args.seg_len, args.seed + 1, f"{prefix}/s1")
        kf_wf = build_keyframe_wf(
            kf_template, args.ref_image, descs[0], args.seed, f"{prefix}/kf/k0")

        if not run_prechecks(fl2v_wf, args.keyframe_workflow, args.skip_keyframes):
            return 1

        print("\n=== dry-run 逐节点校验（不会 POST /prompt）===")
        print(f"[关键帧工作流] {os.path.basename(args.keyframe_workflow)}"
              f"  image={args.ref_image!r} prompt[:60]={descs[0][:60]!r}")
        errors1, lines1 = base.validate_workflow(kf_wf)
        for ln in lines1:
            print(ln)
        print(f"\n[分段工作流] {os.path.basename(args.fl2v_workflow)}"
              f"  N={n} first={dry_first!r} last={dry_last!r} "
              f"prompt[:60]={motion_prompts[0][:60]!r}")
        errors2, lines2 = base.validate_workflow(fl2v_wf)
        for ln in lines2:
            print(ln)

        errors = errors1 + errors2
        if errors:
            print(f"\n[失败] 校验发现 {len(errors)} 个问题:")
            for e in errors:
                print("  - " + e)
            return 1
        print("\n[通过] 两个工作流全部校验通过（dry-run 结束，未提交）")
        return 0

    # --- 预检（真跑前） ---
    sample_wf = build_fl2v_wf(
        fl2v_template, kf_names[0], kf_names[1], motion_prompts[0],
        args.width, args.height, args.seg_len, args.seed + 1, f"{prefix}/s1")
    if not run_prechecks(sample_wf, args.keyframe_workflow, args.skip_keyframes):
        return 1

    t_all = time.time()
    try:
        # --- 关键帧阶段 ---
        if args.skip_keyframes:
            print("\n=== 关键帧阶段（--skip-keyframes，复用 input/ 已有文件）===")
            for nm in kf_names:
                p = os.path.join(INPUT_ROOT, nm)
                if not os.path.exists(p):
                    print(f"[失败] 缺少关键帧 input/{nm}，无法复用；请先跑一次关键帧阶段。")
                    return 1
                print(f"  - 复用 input/{nm}")
        else:
            stage_keyframes(kf_template, args.ref_image, descs, slug, prefix, args.seed, args.no_wait)
            if args.no_wait:
                print("\n[提示] --no-wait：已提交关键帧作业，未等待。"
                      "关键帧落盘并拷贝到 input/ 后，"
                      "可运行 --skip-keyframes 进入分段阶段。")
                return 0

        # --- 分段阶段 ---
        seg_files = stage_segments(fl2v_template, kf_names, motion_prompts, prefix, args)
        if args.no_wait:
            print("\n[提示] --no-wait：已提交全部分段作业，未等待。"
                  "完成后可运行 --merge-only 拼接成片。")
            return 0

        # --- 拼接阶段 ---
        stage_merge(seg_files, prefix, args)
    except Exception as e:
        print(f"\n[失败] {e}")
        return 1

    print(f"\n[完成] 全流程结束，作业总耗时 {(time.time() - t_all) / 60:.1f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
