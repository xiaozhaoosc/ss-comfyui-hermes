#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""动作迁移 —— AnimateDiff + ControlNet(OpenPose) 出片提交器。

链路：SD1.5 底模 + AnimateDiff v3 运动模块 + OpenPose ControlNet，
用上一阶段产出的黑底彩色骨架视频（OpenPose 风格）作为控制信号，
让 SD1.5 按该骨架动作生成一段跳舞动画。

本脚本只负责「提交 + 汇报」，**不轮询、不等待**；提交后请自行用
`GET /history/<prompt_id>` 查询执行结果。

复用 tools/h3_fast_submit.py 的端口预检 / HTTP / 校验工具函数。

用法示例：
  # 干跑（只校验、不提交）
  python tools/motion_clone/render_animatediff.py --dry-run \
      --pose-video "output/2026-10-02/motion_clone/xinniang_seg3/pose.mp4" \
      --out-dir "output/2026-10-02/motion_clone_render/demo_animatediff"

  # 真提交
  python tools/motion_clone/render_animatediff.py \
      --pose-video ... --out-dir ...
"""

import argparse
import json
import os
import shutil
import sys
import uuid
from datetime import date, datetime

# 复用 tools/h3_fast_submit.py（先把 tools 目录插入 sys.path）
_TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from h3_fast_submit import (  # noqa: E402
    INPUT_ROOT,
    _post_json,
    check_single_instance,
    validate_workflow,
)

ROOT = r"D:\ai_projects\ComfyUI"
OUTPUT_ROOT = os.path.join(ROOT, "output")
DEFAULT_WORKFLOW = os.path.join(
    ROOT, "workflows", "animatediff", "animatediff_openpose_sd15_api.json")

# 工作流内的节点 ID（与 animatediff_openpose_sd15_api.json 一一对应）
NID_CKPT = "1"             # CheckpointLoaderSimple：SD1.5 底模
NID_POS = "2"              # CLIPTextEncode：正向提示词
NID_NEG = "3"              # CLIPTextEncode：负向提示词
NID_AD_MODEL = "4"         # ADE_LoadAnimateDiffModel：运动模块（model_name）
NID_CONTROLNET = "7"       # ControlNetLoader：OpenPose ControlNet
NID_LOAD_VIDEO = "8"       # VHS_LoadVideo：骨架视频（frame_load_cap=帧数）
NID_IMAGE_SCALE = "9"      # ImageScale：骨架帧尺寸对齐（持 width/height）
NID_LATENT = "11"          # EmptyLatentImage（持 width/height/batch_size）
NID_SAMPLER = "12"         # KSampler（steps/cfg/seed）
NID_VIDEO_COMBINE = "14"   # VHS_VideoCombine：出片

# VHS_LoadVideo 的 video 输入是「input 目录文件」下拉，ComfyUI 运行时用
# exists_annotated_filepath 校验（允许子目录相对路径），但 h3 的 validate_workflow
# 只做静态枚举比对，会误报子目录路径「不在合法枚举内」——dry-run 中过滤掉这类误报。
_FILE_INPUT_NODES = {NID_LOAD_VIDEO}

# 实测基线尚缺，这里给出粗略估算：约 12 秒 / 帧（SD1.5 + AnimateDiff + ControlNet）。
BASE_SECONDS_PER_FRAME = 12.0

DEFAULT_PROMPT = "a beautiful woman dancing, full body, cinematic lighting, highly detailed"
DEFAULT_NEGATIVE = "blurry, low quality, distorted, extra limbs, bad anatomy, watermark, text"
DEFAULT_MOTION_MODEL = "v3_sd15_mm.ckpt"
DEFAULT_CKPT = "v1-5-pruned-emaonly.safetensors"
DEFAULT_POSE_VIDEO = os.path.join(
    OUTPUT_ROOT, "2026-10-02", "motion_clone", "xinniang_seg3", "pose.mp4")


def _fail(msg):
    """打印中文错误并以非零码退出。"""
    print("[失败] " + msg)
    sys.exit(1)


# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------
def resolve_project_name(args):
    """项目名：骨架视频父目录名；父目录为空/异常时退回文件 stem。"""
    stem = os.path.splitext(os.path.basename(args.pose_video))[0]
    parent = os.path.basename(os.path.dirname(os.path.abspath(args.pose_video)))
    return parent or stem


def resolve_out_dir(args, project_name):
    """--out-dir 缺失时默认 output/<今日>/motion_clone_render/<项目名>_animatediff/。"""
    if args.out_dir:
        return os.path.abspath(args.out_dir)
    today = date.today().strftime("%Y-%m-%d")
    return os.path.join(OUTPUT_ROOT, today, "motion_clone_render",
                        "%s_animatediff" % project_name)


# ---------------------------------------------------------------------------
# 输入搬运
# ---------------------------------------------------------------------------
def _unique_copy(src, dst_dir):
    """把 src 复制进 dst_dir；若同名已存在则加序号，绝不覆盖。返回 (绝对路径, 文件名)。"""
    base = os.path.basename(src)
    stem, ext = os.path.splitext(base)
    dst = os.path.join(dst_dir, base)
    i = 1
    while os.path.exists(dst):
        dst = os.path.join(dst_dir, "%s_%d%s" % (stem, i, ext))
        i += 1
    shutil.copy2(src, dst)
    return dst, os.path.basename(dst)


# ---------------------------------------------------------------------------
# dry-run 辅助
# ---------------------------------------------------------------------------
def _filter_file_input_false_positives(errors):
    """过滤掉 input 文件下拉针对子目录相对路径的静态枚举误报。"""
    real, warned = [], []
    for e in errors:
        is_enum = "不在合法枚举内" in e
        hit = any(e.startswith("[%s]" % nid) for nid in _FILE_INPUT_NODES)
        if is_enum and hit:
            warned.append(e)
        else:
            real.append(e)
    return real, warned


def _print_validation(wf):
    """调用 h3 的 validate_workflow 并打印结论；返回真实错误列表。"""
    errors, lines = validate_workflow(wf)
    real, warned = _filter_file_input_false_positives(errors)
    for ln in lines:
        print(ln)
    for w in warned:
        print("  [忽略-子目录路径] " + w)
    return real


def dry_run_report(wf, args, out_dir, pose_rel, steps, cfg, seed, filename_prefix):
    """打印注入后的关键参数与校验结论，返回进程退出码。"""
    print("\n=== dry-run 关键参数（不会 POST /prompt）===")
    print("  骨架视频        : %s" % pose_rel)
    print("  SD1.5 底模      : %s" % args.ckpt)
    print("  运动模块        : %s" % args.motion_model)
    print("  ControlNet      : control_v11p_sd15_openpose.pth（strength=%.2f）"
          % wf["10"]["inputs"]["strength"])
    print("  length/width/height : %d / %d / %d" % (args.length, args.width, args.height))
    print("  steps/cfg/seed  : %d / %s / %d" % (steps, cfg, seed))
    print("  batch_size      : %d" % wf[NID_LATENT]["inputs"]["batch_size"])
    print("  frame_load_cap  : %d" % wf[NID_LOAD_VIDEO]["inputs"]["frame_load_cap"])
    print("  frame_rate      : %s" % wf[NID_VIDEO_COMBINE]["inputs"]["frame_rate"])
    print("  filename_prefix : %s" % filename_prefix)
    print("  out_dir         : %s" % out_dir)

    print("\n=== dry-run 逐节点校验 ===")
    real_errors = _print_validation(wf)
    if real_errors:
        print("\n[失败] 校验发现 %d 个问题:" % len(real_errors))
        for e in real_errors:
            print("  - " + e)
        return 1
    print("\n[通过] 全部校验通过（dry-run 结束，未提交）")
    return 0


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description="AnimateDiff + ControlNet(OpenPose) 动作迁移出片提交器（不轮询）")
    ap.add_argument("--pose-video", default=DEFAULT_POSE_VIDEO,
                    help="OpenPose 骨架视频（绝对路径；默认建议 %s）" % DEFAULT_POSE_VIDEO)
    ap.add_argument("--prompt", default=DEFAULT_PROMPT, help="正向提示词（英文）")
    ap.add_argument("--negative-prompt", default=DEFAULT_NEGATIVE, help="负向提示词")
    ap.add_argument("--out-dir", default=None,
                    help="输出目录；默认 output/<今日>/motion_clone_render/<项目名>_animatediff/")
    ap.add_argument("--length", type=int, default=16, help="帧数（建议 4 的倍数，16 最稳）")
    ap.add_argument("--width", type=int, default=512, help="宽，建议 64 的整数倍")
    ap.add_argument("--height", type=int, default=768, help="高，建议 64 的整数倍")
    ap.add_argument("--steps", type=int, default=20, help="采样步数")
    ap.add_argument("--cfg", type=float, default=7.5, help="CFG 缩放")
    ap.add_argument("--seed", type=int, default=42, help="随机种子")
    ap.add_argument("--motion-model", default=DEFAULT_MOTION_MODEL, help="AnimateDiff 运动模块文件名")
    ap.add_argument("--ckpt", default=DEFAULT_CKPT, help="SD1.5 底模文件名")
    ap.add_argument("--dry-run", action="store_true", help="只校验、不提交")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    # 1. 端口预检（复用 h3_fast_submit 的单实例检查）
    print("=== 预检 ===")
    ok, msg = check_single_instance()
    if not ok:
        _fail("ComfyUI 未就绪：%s" % msg)
    print("  [通过] 单实例: %s" % msg)

    # 2. 校验骨架视频存在且可读
    args.pose_video = os.path.abspath(args.pose_video)
    if not os.path.isfile(args.pose_video):
        _fail("骨架视频不存在：%s" % args.pose_video)
    if not os.access(args.pose_video, os.R_OK):
        _fail("骨架视频不可读：%s" % args.pose_video)

    # 3. 加载工作流（深拷贝，绝不写回原文件）
    if not os.path.isfile(DEFAULT_WORKFLOW):
        _fail("工作流不存在：%s" % DEFAULT_WORKFLOW)
    with open(DEFAULT_WORKFLOW, "r", encoding="utf-8") as f:
        wf = json.loads(json.dumps(json.load(f)))

    # 4. 尺寸校验：ImageScale/EmptyLatentImage 允许任意正整数，但 64 的倍数最稳，
    #    非 64 整数倍只给中文警告、不拦截。
    for nm, v in (("--width", args.width), ("--height", args.height)):
        if v <= 0:
            _fail("%s=%d 非法：宽高必须 >0。" % (nm, v))
        if v % 64 != 0:
            print("[警告] %s=%d 不是 64 的整数倍，建议改用 64 的倍数（如 512/768）。" % (nm, v))

    # 5. 帧长校验：AnimateDiff 的 context 对齐要求，建议 4 的倍数（16 最保险）。
    if args.length <= 0:
        _fail("--length=%d 非法：必须 >0。" % args.length)
    if args.length % 4 != 0:
        print("[警告] --length=%d 不是 4 的倍数，AnimateDiff 的 context 对齐可能不稳定，"
              "建议改用 4 的倍数（如 16）。" % args.length)

    # 6. 项目名 / 输出目录 / 输入搬运
    project_name = resolve_project_name(args)
    out_dir = resolve_out_dir(args, project_name)
    os.makedirs(out_dir, exist_ok=True)

    in_dir_name = "motion_clone_animdiff_%s" % datetime.now().strftime("%Y%m%d_%H%M%S")
    in_dir_abs = os.path.join(INPUT_ROOT, in_dir_name)
    os.makedirs(in_dir_abs, exist_ok=True)
    print("  输入搬运目录: %s" % in_dir_abs)

    _, pose_name = _unique_copy(args.pose_video, in_dir_abs)
    pose_rel = "%s/%s" % (in_dir_name, pose_name)

    # 7. 参数注入
    wf[NID_CKPT]["inputs"]["ckpt_name"] = args.ckpt
    wf[NID_POS]["inputs"]["text"] = args.prompt
    wf[NID_NEG]["inputs"]["text"] = args.negative_prompt
    wf[NID_AD_MODEL]["inputs"]["model_name"] = args.motion_model
    wf[NID_LOAD_VIDEO]["inputs"]["video"] = pose_rel
    wf[NID_LOAD_VIDEO]["inputs"]["frame_load_cap"] = args.length
    wf[NID_IMAGE_SCALE]["inputs"]["width"] = args.width
    wf[NID_IMAGE_SCALE]["inputs"]["height"] = args.height
    wf[NID_LATENT]["inputs"]["width"] = args.width
    wf[NID_LATENT]["inputs"]["height"] = args.height
    wf[NID_LATENT]["inputs"]["batch_size"] = args.length
    wf[NID_SAMPLER]["inputs"]["steps"] = args.steps
    wf[NID_SAMPLER]["inputs"]["cfg"] = args.cfg
    wf[NID_SAMPLER]["inputs"]["seed"] = args.seed

    # filename_prefix 必须让成片落在与 render_submit.json 相同的目录，
    # 否则「成片 + 提交记录」会被拆到两个目录，破坏输出契约。
    # 因此优先由 --out-dir 反推相对 output 根的路径；out_dir 不在 output 根下时
    # 退回按日期 + 项目名的默认拼法。
    _rel = os.path.relpath(out_dir, OUTPUT_ROOT)
    if not _rel.startswith("..") and not os.path.isabs(_rel):
        filename_prefix = "%s/animatediff" % _rel.replace(os.sep, "/")
    else:
        filename_prefix = "%s/motion_clone_render/%s_animatediff/animatediff" % (
            date.today().strftime("%Y-%m-%d"), project_name)
    wf[NID_VIDEO_COMBINE]["inputs"]["filename_prefix"] = filename_prefix

    # 8. dry-run
    if args.dry_run:
        return dry_run_report(wf, args, out_dir, pose_rel, args.steps, args.cfg,
                              args.seed, filename_prefix)

    # 9. 提交（不轮询、不等待）
    print("\n=== 提交 ===")
    payload = {"prompt": wf, "client_id": str(uuid.uuid4())}
    try:
        r = _post_json("/prompt", payload)
    except Exception as e:
        _fail("提交异常：%s" % e)
    pid = r.get("prompt_id")
    node_errors = r.get("node_errors") or {}
    if node_errors:
        print("[失败] node_errors 非空:")
        print(json.dumps(node_errors, ensure_ascii=False)[:2000])
        sys.exit(1)

    eta_seconds = BASE_SECONDS_PER_FRAME * args.length
    eta_minutes = round(eta_seconds / 60.0, 1)

    print("  prompt_id       : %s" % pid)
    print("  pipeline        : SD1.5 + AnimateDiff v3 + OpenPose ControlNet")
    print("  length          : %d" % args.length)
    print("  预计完成时间    : 约 %.1f 分钟（粗略基线 %.1fs / 帧线性外推）"
          % (eta_minutes, BASE_SECONDS_PER_FRAME))
    print("  已入队，请稍后用 GET /history/%s 手动查询，本次不轮询。" % pid)

    record = {
        "prompt_id": pid,
        "pipeline": "animatediff_openpose_sd15",
        "length": args.length,
        "width": args.width,
        "height": args.height,
        "steps": args.steps,
        "cfg": args.cfg,
        "seed": args.seed,
        "motion_model": args.motion_model,
        "ckpt": args.ckpt,
        "control_net": "control_v11p_sd15_openpose.pth",
        "pose_video": args.pose_video,
        "prompt": args.prompt,
        "negative_prompt": args.negative_prompt,
        "filename_prefix": filename_prefix,
        "submitted_at": datetime.now().isoformat(),
        "eta_minutes": eta_minutes,
        "out_dir": out_dir,
        "workflow_source": DEFAULT_WORKFLOW,
    }
    rec_path = os.path.join(out_dir, "render_submit.json")
    with open(rec_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    print("  提交记录已写入: %s" % rec_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())