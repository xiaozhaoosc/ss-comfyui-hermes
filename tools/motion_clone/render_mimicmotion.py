#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""动作克隆 —— MimicMotion 出片提交器（参考角色图 + 驱动视频，姿态由节点内部 DWPose 提取）。

本脚本只负责「提交 + 汇报」，**不轮询、不等待**；提交后请自行用
`GET /history/<prompt_id>` 查询执行结果。

复用 tools/h3_fast_submit.py 的端口预检 / HTTP / 校验工具函数。

用法示例：
  # 干跑（只校验、不提交）
  python tools/motion_clone/render_mimicmotion.py --dry-run \
      --ref-image "input/xxx.png" --video "input/yyy.mp4" \
      --out-dir "output/2026-10-02/motion_clone_render/mimic"

  # 真提交
  python tools/motion_clone/render_mimicmotion.py \
      --ref-image ... --video ... --out-dir ...
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
    ROOT, "workflows", "mimicmotion", "mimic_motion_api.json")

# 工作流内的节点 ID（与 mimic_motion_api.json 一一对应）
NID_REF_IMAGE = "1"          # LoadImage：参考角色图
NID_DRIVING_VIDEO = "2"      # VHS_LoadVideo：驱动视频（frame_load_cap=帧数）
NID_REF_RESIZE = "3"         # ImageResizeKJ：参考图尺寸对齐（持 width/height）
NID_POSE_RESIZE = "4"        # ImageResizeKJ：姿态帧尺寸对齐
NID_GET_POSES = "5"          # MimicMotionGetPoses：DWPose 姿态提取
NID_MODEL = "6"             # DownloadAndLoadMimicMotionModel
NID_SAMPLER = "7"           # MimicMotionSampler（steps/seed）
NID_DECODE = "8"            # MimicMotionDecode
NID_VIDEO_COMBINE = "9"      # VHS_VideoCombine：出片

# 这些节点的 file/image 输入是「input 目录文件」下拉，ComfyUI 运行时用
# exists_annotated_filepath 校验（允许子目录相对路径），但 h3 的 validate_workflow
# 只做静态枚举比对，会误报子目录路径「不在合法枚举内」——dry-run 中过滤掉这类误报。
_FILE_INPUT_NODES = {NID_REF_IMAGE, NID_DRIVING_VIDEO}

# 实测基线尚缺，这里给出粗略估算：约 900 秒 / 16 帧，ETA 按帧长线性外推。
BASE_SECONDS_16 = 900.0
BASE_FRAMES_16 = 16

DEFAULT_MODEL = "MimicMotionMergedUnet_1-1-fp16.safetensors"
DEFAULT_PRECISION = "fp16"


def _fail(msg):
    """打印中文错误并以非零码退出。"""
    print("[失败] " + msg)
    sys.exit(1)


# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------
def resolve_project_name(args):
    """项目名：驱动视频文件名 stem。"""
    return os.path.splitext(os.path.basename(args.video))[0]


def resolve_out_dir(args, project_name):
    """--out-dir 缺失时默认 output/<今日>/motion_clone_render/<项目名>_mimicmotion/。"""
    if args.out_dir:
        return os.path.abspath(args.out_dir)
    today = date.today().strftime("%Y-%m-%d")
    return os.path.join(OUTPUT_ROOT, today, "motion_clone_render",
                        "%s_mimicmotion" % project_name)


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
    """过滤掉 input 文件/图片下拉针对子目录相对路径的静态枚举误报。"""
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


def dry_run_report(wf, args, out_dir, ref_rel, drv_rel, model, steps, seed,
                   filename_prefix):
    """打印注入后的关键参数与校验结论，返回进程退出码。"""
    print("\n=== dry-run 关键参数（不会 POST /prompt）===")
    print("  参考角色图      : %s" % ref_rel)
    print("  驱动视频        : %s" % drv_rel)
    print("  模型名          : %s（精度 %s）" % (model, DEFAULT_PRECISION))
    print("  length/width/height : %d / %d / %d" % (args.length, args.width, args.height))
    print("  steps/seed      : %d / %d" % (steps, seed))
    print("  frame_load_cap  : %d" % wf[NID_DRIVING_VIDEO]["inputs"]["frame_load_cap"])
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
        description="MimicMotion 动作克隆出片提交器（不轮询）")
    ap.add_argument("--ref-image", required=True, help="参考角色图（绝对路径）")
    ap.add_argument("--video", required=True, help="驱动视频（绝对路径）")
    ap.add_argument("--out-dir", default=None,
                    help="输出目录；默认 output/<今日>/motion_clone_render/<项目名>_mimicmotion/")
    ap.add_argument("--length", type=int, default=16, help="帧数（映射到 frame_load_cap）")
    ap.add_argument("--width", type=int, default=576, help="宽，建议 64 的整数倍")
    ap.add_argument("--height", type=int, default=1024, help="高，建议 64 的整数倍")
    ap.add_argument("--steps", type=int, default=None, help="采样步数（默认沿用工作流值）")
    ap.add_argument("--seed", type=int, default=None, help="随机种子（默认沿用工作流值）")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="MimicMotion 模型文件名")
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

    # 2. 校验输入文件存在且可读
    for label, path in (("参考角色图", args.ref_image), ("驱动视频", args.video)):
        if not os.path.isfile(path):
            _fail("%s 不存在：%s" % (label, path))
        if not os.access(path, os.R_OK):
            _fail("%s 不可读：%s" % (label, path))

    # 3. 加载工作流（深拷贝，绝不写回原文件）
    if not os.path.isfile(DEFAULT_WORKFLOW):
        _fail("工作流不存在：%s" % DEFAULT_WORKFLOW)
    with open(DEFAULT_WORKFLOW, "r", encoding="utf-8") as f:
        wf = json.loads(json.dumps(json.load(f)))

    # 4. 尺寸校验：ImageResizeKJ 允许任意正整数尺寸，但其 divisible_by=64，
    #    非 64 整数倍会被自动吸附，这里只给中文警告、不拦截。
    for nm, v in (("--width", args.width), ("--height", args.height)):
        if v <= 0:
            _fail("%s=%d 非法：宽高必须 >0。" % (nm, v))
        if v % 64 != 0:
            print("[警告] %s=%d 不是 64 的整数倍，ImageResizeKJ(divisible_by=64) 会自行吸附，"
                  "建议改用 64 的倍数（如 576/1024）。" % (nm, v))

    # 5. 帧长校验
    if args.length <= 0:
        _fail("--length=%d 非法：必须 >0。" % args.length)

    # 6. 项目名 / 输出目录 / 输入搬运
    project_name = resolve_project_name(args)
    out_dir = resolve_out_dir(args, project_name)
    os.makedirs(out_dir, exist_ok=True)

    in_dir_name = "motion_clone_mimic_%s" % datetime.now().strftime("%Y%m%d_%H%M%S")
    in_dir_abs = os.path.join(INPUT_ROOT, in_dir_name)
    os.makedirs(in_dir_abs, exist_ok=True)
    print("  输入搬运目录: %s" % in_dir_abs)

    _, ref_name = _unique_copy(os.path.abspath(args.ref_image), in_dir_abs)
    _, drv_name = _unique_copy(os.path.abspath(args.video), in_dir_abs)
    ref_rel = "%s/%s" % (in_dir_name, ref_name)
    drv_rel = "%s/%s" % (in_dir_name, drv_name)

    # 7. 参数注入（默认沿用工作流里的 steps/seed）
    steps = args.steps if args.steps is not None else wf[NID_SAMPLER]["inputs"]["steps"]
    seed = args.seed if args.seed is not None else wf[NID_SAMPLER]["inputs"]["seed"]

    wf[NID_REF_IMAGE]["inputs"]["image"] = ref_rel
    wf[NID_DRIVING_VIDEO]["inputs"]["video"] = drv_rel
    wf[NID_DRIVING_VIDEO]["inputs"]["frame_load_cap"] = args.length
    for nid in (NID_REF_RESIZE, NID_POSE_RESIZE):
        wf[nid]["inputs"]["width"] = args.width
        wf[nid]["inputs"]["height"] = args.height
    wf[NID_MODEL]["inputs"]["model"] = args.model
    wf[NID_SAMPLER]["inputs"]["steps"] = steps
    wf[NID_SAMPLER]["inputs"]["seed"] = seed

    # filename_prefix 必须让成片落在与 render_submit.json 相同的目录，
    # 否则「成片 + 提交记录」会被拆到两个目录，破坏输出契约。
    # 因此优先由 --out-dir 反推相对 output 根的路径；out_dir 不在 output 根下时
    # 退回按日期 + 项目名的默认拼法。
    _rel = os.path.relpath(out_dir, OUTPUT_ROOT)
    if not _rel.startswith("..") and not os.path.isabs(_rel):
        filename_prefix = "%s/mimicmotion" % _rel.replace(os.sep, "/")
    else:
        filename_prefix = "%s/motion_clone_render/%s_mimicmotion/mimicmotion" % (
            date.today().strftime("%Y-%m-%d"), project_name)
    wf[NID_VIDEO_COMBINE]["inputs"]["filename_prefix"] = filename_prefix

    # 8. dry-run
    if args.dry_run:
        return dry_run_report(wf, args, out_dir, ref_rel, drv_rel, args.model,
                              steps, seed, filename_prefix)

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

    eta_seconds = BASE_SECONDS_16 * args.length / float(BASE_FRAMES_16)
    eta_minutes = round(eta_seconds / 60.0, 1)

    print("  prompt_id       : %s" % pid)
    print("  pose_mode       : mimicmotion_internal（姿态由节点内部 DWPose 提取）")
    print("  length          : %d" % args.length)
    print("  预计完成时间    : 约 %.1f 分钟（粗略基线 %.1fs / %d 帧线性外推）"
          % (eta_minutes, BASE_SECONDS_16, BASE_FRAMES_16))
    print("  已入队，请稍后用 GET /history/%s 手动查询，本次不轮询。" % pid)

    record = {
        "prompt_id": pid,
        "pose_mode": "mimicmotion_internal",
        "length": args.length,
        "width": args.width,
        "height": args.height,
        "steps": steps,
        "seed": seed,
        "model": args.model,
        "ref_image": os.path.abspath(args.ref_image),
        "driving_video": os.path.abspath(args.video),
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