#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""动作克隆 —— Wan2.2 Animate 14B 出片提交器（新角色图 + 参考舞蹈视频 + 英文提示词）。

两种姿态控制模式：
  internal（默认）：沿用工作流内置的 DWPreprocessor（节点 15/16）从驱动视频现算骨架；
  ours            ：用上一阶段 keypoints.json 重绘两路控制视频（pose=身体+双手 / face=仅脸），
                    替换工作流里节点 15/16 的输出，让骨架流水线真正参与渲染。

本脚本只负责「提交 + 汇报」，**不轮询、不等待**；提交后请自行用
`GET /history/<prompt_id>` 查询执行结果。

复用 tools/h3_fast_submit.py 的端口预检 / HTTP / 校验工具函数。

用法示例：
  # 干跑（只校验、不提交）
  python tools/motion_clone/render_wan_animate.py --dry-run --pose-mode internal \
      --ref-image "input/xxx.png" --video "input/yyy.mp4" \
      --project-dir "output/2026-10-02/motion_clone/xinniang_seg3"

  # 真提交
  python tools/motion_clone/render_wan_animate.py \
      --ref-image ... --video ... --project-dir ... --out-dir ...
"""

import argparse
import json
import os
import shutil
import sys
import uuid
from datetime import date, datetime

import cv2
import numpy as np

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
    ROOT, "workflows", "wan22_animate", "wan22_animate_14b_move_api.json")
DWPOSE_SRC = os.path.join(
    ROOT, "custom_nodes", "comfyui_controlnet_aux", "src")

# 实测基线：49 帧约 2444.6 秒；ETA 按帧长线性外推
BASE_SECONDS_49 = 2444.6
BASE_FRAMES_49 = 49

# 关键点数量约定（与 keypoints.json 的 counts 一致）
N_BODY, N_HAND, N_FACE = 18, 21, 70

# 这些节点的 file/image 输入是「input 目录文件」下拉，ComfyUI 运行时用
# exists_annotated_filepath 校验（允许子目录相对路径），但 h3 的 validate_workflow
# 只做静态枚举比对，会误报子目录路径「不在合法枚举内」——dry-run 中过滤掉这类误报。
_FILE_INPUT_NODES = {"10", "12", "900", "902"}


def _fail(msg):
    """打印中文错误并以非零码退出。"""
    print("[失败] " + msg)
    sys.exit(1)


# ---------------------------------------------------------------------------
# 路径 / 提示词
# ---------------------------------------------------------------------------
def resolve_project_name(args):
    """项目名：优先取 --project-dir 的 basename，否则取驱动视频文件名 stem。"""
    if args.project_dir:
        name = os.path.basename(os.path.normpath(args.project_dir))
        if name:
            return name
    return os.path.splitext(os.path.basename(args.video))[0]


def resolve_out_dir(args, project_name):
    """--out-dir 缺失时默认 output/<今日>/motion_clone_render/<项目名>/。"""
    if args.out_dir:
        return os.path.abspath(args.out_dir)
    today = date.today().strftime("%Y-%m-%d")
    return os.path.join(OUTPUT_ROOT, today, "motion_clone_render", project_name)


def read_prompt(args):
    """提示词：--prompt 优先，否则读 <project-dir>/prompt.txt。"""
    if args.prompt:
        return args.prompt
    if args.project_dir:
        p = os.path.join(args.project_dir, "prompt.txt")
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8-sig") as f:
                text = f.read().strip()
            if text:
                return text
            _fail("prompt.txt 内容为空：%s" % p)
        _fail("未提供 --prompt，且 %s 不存在。" % p)
    _fail("未提供 --prompt，且未提供 --project-dir（无法定位 prompt.txt）。")


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
# ours 模式：用 keypoints.json 重绘两路控制视频
# ---------------------------------------------------------------------------
def _prepare_dwpose_import():
    """import controlnet_aux 之前设置环境变量并注入源码路径。"""
    os.environ.setdefault("NPU_DEVICE_COUNT", "0")
    os.environ.setdefault("MMCV_WITH_OPS", "0")
    if DWPOSE_SRC not in sys.path:
        sys.path.insert(0, DWPOSE_SRC)


def _to_kps(pts, n, Keypoint):
    """把 [[x,y,conf], ...] 转成 [Keypoint 或 None]；[0,0,0]（缺失）转成 None。"""
    out = [None] * n
    if not pts:
        return out
    for i in range(min(n, len(pts))):
        p = pts[i]
        if p is None:
            continue
        x, y, c = float(p[0]), float(p[1]), float(p[2])
        if x == 0.0 and y == 0.0 and c == 0.0:
            continue  # 缺失关键点
        out[i] = Keypoint(x, y, c, i)
    return out


def _fit_cover(img, W, H):
    """与工作流 ImageScale(crop='center') 等价的 cover 缩放：先缩放到覆盖，再中心裁剪。"""
    h, w = img.shape[:2]
    scale = max(W / float(w), H / float(h))
    nw = max(W, int(round(w * scale)))
    nh = max(H, int(round(h * scale)))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
    x0 = (nw - W) // 2
    y0 = (nh - H) // 2
    return resized[y0:y0 + H, x0:x0 + W]


def _render_pose_rgb(src_w, src_h, body, lh, rh, dw_util, Keypoint):
    """pose 路：身体 + 双手（不画脸），黑底。坐标为源分辨率，不在此缩放。"""
    canvas = np.zeros((src_h, src_w, 3), dtype=np.uint8)
    canvas = dw_util.draw_bodypose(canvas, _to_kps(body, N_BODY, Keypoint))
    canvas = dw_util.draw_handpose(canvas, _to_kps(lh, N_HAND, Keypoint))
    canvas = dw_util.draw_handpose(canvas, _to_kps(rh, N_HAND, Keypoint))
    return canvas


def _render_face_rgb(src_w, src_h, face, dw_util, Keypoint):
    """face 路：只画脸（不画身体、不画手），黑底。"""
    canvas = np.zeros((src_h, src_w, 3), dtype=np.uint8)
    canvas = dw_util.draw_facepose(canvas, _to_kps(face, N_FACE, Keypoint))
    return canvas


def _probe_video(path):
    """解码统计视频的 (帧数, 宽, 高)，用于 dry-run 断言。"""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return 0, 0, 0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    n = 0
    while True:
        ok, _ = cap.read()
        if not ok:
            break
        n += 1
    cap.release()
    return n, w, h


def build_control_videos(kp_path, project, out_dir, width, height, length, frame_offset):
    """按 keypoints.json 重绘 pose / face 两路控制视频，返回 (pose_path, face_path, fps)。"""
    if not os.path.isfile(kp_path):
        _fail("keypoints.json 不存在：%s" % kp_path)
    with open(kp_path, "r", encoding="utf-8") as f:
        kp = json.load(f)

    frames = kp.get("frames") or []
    need = length + frame_offset
    if len(frames) < need:
        _fail("keypoints.json 帧数不足：需要 %d 帧（length=%d + frame_offset=%d），"
              "实际只有 %d 帧。请减小 --length/--frame-offset 或换用更长的关键点文件。"
              % (need, length, frame_offset, len(frames)))

    src_w = int(kp.get("width") or 0)
    src_h = int(kp.get("height") or 0)
    if src_w <= 0 or src_h <= 0:
        _fail("keypoints.json 缺少有效的 width/height（当前 %dx%d）。" % (src_w, src_h))
    fps = float(kp.get("fps") or 0.0) or 24.0

    _prepare_dwpose_import()
    from custom_controlnet_aux.dwpose import util as dw_util  # noqa: E402
    from custom_controlnet_aux.dwpose.types import Keypoint  # noqa: E402

    control_dir = os.path.join(out_dir, "control")
    os.makedirs(control_dir, exist_ok=True)
    pose_path = os.path.join(control_dir, "pose_%s.mp4" % project)
    face_path = os.path.join(control_dir, "face_%s.mp4" % project)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw_pose = cv2.VideoWriter(pose_path, fourcc, fps, (width, height))
    vw_face = cv2.VideoWriter(face_path, fourcc, fps, (width, height))
    if not vw_pose.isOpened() or not vw_face.isOpened():
        _fail("VideoWriter 打开失败（mp4v），无法写出控制视频。")

    print("[ours] 重绘控制视频：源 %dx%d，fps=%.3f，窗口 [%d, %d)"
          % (src_w, src_h, fps, frame_offset, frame_offset + length))
    for fi in range(frame_offset, frame_offset + length):
        fr = frames[fi]
        people = fr.get("people") or []
        person = people[0] if people else {}
        body = person.get("body")
        lh = person.get("left_hand")
        rh = person.get("right_hand")
        face = person.get("face")

        pose_rgb = _render_pose_rgb(src_w, src_h, body, lh, rh, dw_util, Keypoint)
        face_rgb = _render_face_rgb(src_w, src_h, face, dw_util, Keypoint)
        # cover 缩放到目标尺寸，再 RGB->BGR 写盘
        pose_bgr = cv2.cvtColor(_fit_cover(pose_rgb, width, height), cv2.COLOR_RGB2BGR)
        face_bgr = cv2.cvtColor(_fit_cover(face_rgb, width, height), cv2.COLOR_RGB2BGR)
        vw_pose.write(pose_bgr)
        vw_face.write(face_bgr)
        if (fi - frame_offset + 1) % 20 == 0:
            print("  [ours] 已重绘 %d / %d 帧 ..." % (fi - frame_offset + 1, length))

    vw_pose.release()
    vw_face.release()
    return pose_path, face_path, fps


# ---------------------------------------------------------------------------
# 工作流改写（ours 模式支路）
# ---------------------------------------------------------------------------
def add_control_branch(wf, load_id, gvc_id, video_rel_path):
    """新增一条「加载控制视频 -> 取帧」支路，返回取帧节点的 images 输出引用。

    说明：任务描述里 900/902 为「视频加载节点」、901/903 为 GetVideoComponents。
    这里使用 ComfyUI 内置 LoadVideo（输出 VIDEO）而非 VHS_LoadVideoPath，原因是：
    VHS_LoadVideoPath 的输出类型是 IMAGE，而 GetVideoComponents 需要 VIDEO 输入，
    两者类型不兼容（会被 /prompt 以 return_type_mismatch 拒绝）。LoadVideo 与基础
    工作流节点 12 一致，能合法接上 GetVideoComponents。控制视频已按 length 精确写出，
    因此无需 frame_load_cap。
    """
    wf[load_id] = {
        "class_type": "LoadVideo",
        "_meta": {"title": "Load Video (%s control)" % load_id},
        "inputs": {"file": video_rel_path},
    }
    wf[gvc_id] = {
        "class_type": "GetVideoComponents",
        "_meta": {"title": "Get Video Components (%s control)" % gvc_id},
        "inputs": {"video": [load_id, 0]},
    }
    return [gvc_id, 0]


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


def dry_run_report(wf, args, project_name, out_dir, prompt, ref_image, driving_video,
                   filename_prefix, control=None):
    """打印注入后的关键参数与校验结论，返回进程退出码。"""
    print("\n=== dry-run 关键参数（不会 POST /prompt）===")
    print("  pose_mode       : %s" % args.pose_mode)
    print("  正向提示词      : %s" % prompt)
    neg = (wf.get("9", {}).get("inputs", {}) or {}).get("text", "")
    print("  负向提示词[:60] : %r" % neg[:60])
    print("  参考角色图      : %s" % ref_image)
    print("  驱动视频        : %s" % driving_video)
    print("  length/width/height : %d / %d / %d" % (args.length, args.width, args.height))
    print("  steps/seed      : %d / %d" % (args.steps, args.seed))
    print("  frame_offset    : %d" % args.frame_offset)
    print("  filename_prefix : %s" % filename_prefix)
    print("  out_dir         : %s" % out_dir)
    if args.pose_mode == "ours" and control:
        print("  控制视频(pose)  : %s" % control["pose_path"])
        print("  控制视频(face)  : %s" % control["face_path"])
        print("  两路帧数/尺寸   : %s -> %d帧 %dx%d ; %s -> %d帧 %dx%d"
              % (control["pose_path"], control["pose_n"], control["pose_w"], control["pose_h"],
                 control["face_path"], control["face_n"], control["face_w"], control["face_h"]))

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
        description="Wan2.2 Animate 14B 动作克隆出片提交器（不轮询）")
    ap.add_argument("--ref-image", required=True, help="新角色图（绝对路径）")
    ap.add_argument("--video", required=True, help="参考驱动视频（绝对路径）")
    ap.add_argument("--project-dir", default=None,
                    help="上一阶段产物目录（读其 prompt.txt；ours 模式读 keypoints.json）")
    ap.add_argument("--prompt", default=None, help="英文正向提示词（优先级高于 prompt.txt）")
    ap.add_argument("--out-dir", default=None,
                    help="输出目录；默认 output/<今日>/motion_clone_render/<项目名>/")
    ap.add_argument("--length", type=int, default=49, help="帧数，必须满足 length %% 4 == 1")
    ap.add_argument("--width", type=int, default=512, help="宽，必须为 16 的整数倍")
    ap.add_argument("--height", type=int, default=512, help="高，必须为 16 的整数倍")
    ap.add_argument("--steps", type=int, default=4, help="采样步数")
    ap.add_argument("--seed", type=int, default=20261002, help="随机种子（默认沿用工作流值）")
    ap.add_argument("--pose-mode", choices=["internal", "ours"], default="internal",
                    help="internal=内置 DWPreprocessor；ours=用 keypoints.json 重绘控制视频")
    ap.add_argument("--frame-offset", type=int, default=0, help="起始帧偏移")
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

    # 4. 提示词
    prompt = read_prompt(args)

    # 5. 尺寸校验（WanAnimateToVideo 要求 16 的整数倍）
    for nm, v in (("--width", args.width), ("--height", args.height)):
        if v <= 0 or v % 16 != 0:
            _fail("%s=%d 非法：WanAnimateToVideo 要求宽高为 16 的整数倍且 >0（如 512/544/960）。"
                  % (nm, v))

    # 6. 帧长校验（Wan 时序压缩要求 length % 4 == 1）
    if args.length % 4 != 1 or args.length < 1:
        _fail("--length=%d 非法：必须满足 length %% 4 == 1（可用值如 9/17/25/33/41/49）。"
              % args.length)

    # 7. 项目名 / 输出目录 / 输入搬运
    project_name = resolve_project_name(args)
    out_dir = resolve_out_dir(args, project_name)
    os.makedirs(out_dir, exist_ok=True)

    in_dir_name = "motion_clone_render_%s" % datetime.now().strftime("%Y%m%d_%H%M%S")
    in_dir_abs = os.path.join(INPUT_ROOT, in_dir_name)
    os.makedirs(in_dir_abs, exist_ok=True)
    print("  输入搬运目录: %s" % in_dir_abs)

    _, ref_name = _unique_copy(os.path.abspath(args.ref_image), in_dir_abs)
    _, drv_name = _unique_copy(os.path.abspath(args.video), in_dir_abs)
    ref_rel = "%s/%s" % (in_dir_name, ref_name)
    drv_rel = "%s/%s" % (in_dir_name, drv_name)

    # 8. 注入提示词 / 输入 / 采样参数
    wf["8"]["inputs"]["text"] = prompt
    wf["10"]["inputs"]["image"] = ref_rel
    wf["12"]["inputs"]["file"] = drv_rel
    wf["17"]["inputs"]["length"] = args.length
    wf["17"]["inputs"]["width"] = args.width
    wf["17"]["inputs"]["height"] = args.height
    wf["18"]["inputs"]["steps"] = args.steps
    wf["18"]["inputs"]["seed"] = args.seed

    suffix = "wan_ours" if args.pose_mode == "ours" else "wan_internal"
    # filename_prefix 必须让成片落在与 render_submit.json 相同的目录，
    # 否则「成片 + 提交记录 + control/」会被拆到两个目录，破坏输出契约。
    # 因此优先由 --out-dir 反推相对 output 根的路径；out_dir 不在 output 根下时
    # 退回按日期 + 项目名的默认拼法。
    _rel = os.path.relpath(out_dir, OUTPUT_ROOT)
    if not _rel.startswith("..") and not os.path.isabs(_rel):
        filename_prefix = "%s/%s" % (_rel.replace(os.sep, "/"), suffix)
    else:
        filename_prefix = "%s/motion_clone_render/%s/%s" % (
            date.today().strftime("%Y-%m-%d"), project_name, suffix)

    control_info = None
    if args.pose_mode == "ours":
        # 9. ours：重绘两路控制视频并改写工作流
        kp_path = os.path.join(args.project_dir, "keypoints.json") if args.project_dir else ""
        pose_abs, face_abs, _fps = build_control_videos(
            kp_path, project_name, out_dir, args.width, args.height,
            args.length, args.frame_offset)

        # 副本复制到本轮的 input 目录
        _, pose_name = _unique_copy(pose_abs, in_dir_abs)
        _, face_name = _unique_copy(face_abs, in_dir_abs)
        pose_rel = "%s/%s" % (in_dir_name, pose_name)
        face_rel = "%s/%s" % (in_dir_name, face_name)

        # 新增两段支路，并把 17 的控制输入指向它们
        wf["17"]["inputs"]["pose_video"] = add_control_branch(wf, "900", "901", pose_rel)
        wf["17"]["inputs"]["face_video"] = add_control_branch(wf, "902", "903", face_rel)
        # 控制视频已按 frame_offset 切好，这里不再二次偏移
        wf["17"]["inputs"]["video_frame_offset"] = 0

        pose_n, pose_w, pose_h = _probe_video(pose_abs)
        face_n, face_w, face_h = _probe_video(face_abs)
        control_info = {
            "pose_path": pose_abs, "pose_n": pose_n, "pose_w": pose_w, "pose_h": pose_h,
            "face_path": face_abs, "face_n": face_n, "face_w": face_w, "face_h": face_h,
        }
    else:
        # internal：--frame-offset 映射到 WanAnimateToVideo.video_frame_offset
        wf["17"]["inputs"]["video_frame_offset"] = args.frame_offset

    wf["21"]["inputs"]["filename_prefix"] = filename_prefix

    # 10. dry-run
    if args.dry_run:
        if args.pose_mode == "ours":
            assert wf["17"]["inputs"]["pose_video"][0] == "901", "pose_video 未指向 901"
            assert wf["17"]["inputs"]["face_video"][0] == "903", "face_video 未指向 903"
            if control_info["pose_n"] != args.length or control_info["face_n"] != args.length:
                _fail("控制视频帧数断言失败：pose=%d face=%d，期望 %d"
                      % (control_info["pose_n"], control_info["face_n"], args.length))
            for tag in ("pose", "face"):
                if (control_info["%s_w" % tag], control_info["%s_h" % tag]) != (args.width, args.height):
                    _fail("控制视频尺寸断言失败：%s=%dx%d，期望 %dx%d"
                          % (tag, control_info["%s_w" % tag], control_info["%s_h" % tag],
                             args.width, args.height))
            print("[断言通过] pose_video->%s, face_video->%s；两路帧数==%d；尺寸==%dx%d"
                  % (wf["17"]["inputs"]["pose_video"][0], wf["17"]["inputs"]["face_video"][0],
                     args.length, args.width, args.height))
        return dry_run_report(wf, args, project_name, out_dir, prompt,
                              args.ref_image, args.video, filename_prefix, control_info)

    # 11. 提交（不轮询、不等待）
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

    eta_seconds = BASE_SECONDS_49 * args.length / float(BASE_FRAMES_49)
    eta_minutes = round(eta_seconds / 60.0, 1)

    print("  prompt_id       : %s" % pid)
    print("  pose_mode       : %s" % args.pose_mode)
    print("  length          : %d" % args.length)
    print("  预计完成时间    : 约 %.1f 分钟（基线 %.1fs / %d 帧线性外推）"
          % (eta_minutes, BASE_SECONDS_49, BASE_FRAMES_49))
    print("  已入队，请稍后用 GET /history/%s 手动查询，本次不轮询。" % pid)

    record = {
        "prompt_id": pid,
        "pose_mode": args.pose_mode,
        "length": args.length,
        "width": args.width,
        "height": args.height,
        "steps": args.steps,
        "seed": args.seed,
        "submitted_at": datetime.now().isoformat(),
        "eta_minutes": eta_minutes,
        "positive_prompt": prompt,
        "ref_image": os.path.abspath(args.ref_image),
        "driving_video": os.path.abspath(args.video),
        "filename_prefix": filename_prefix,
        "out_dir": out_dir,
        "workflow_source": DEFAULT_WORKFLOW,
    }
    if control_info:
        record["control_pose_video"] = control_info["pose_path"]
        record["control_face_video"] = control_info["face_path"]

    rec_path = os.path.join(out_dir, "render_submit.json")
    with open(rec_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    print("  提交记录已写入: %s" % rec_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())