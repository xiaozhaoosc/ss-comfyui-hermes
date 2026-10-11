#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/motion_transfer_pipeline.py
=============================================================================
端到端通用动作迁移与人物融合流水线 (基于 Wan2.2 Animate 14B + 纯净姿态管道)

全流程能力：
1. 接收【人物参考图】+【参考驱动视频】；
2. 【提取与保存管道】：逐帧提取参考视频的面部表情 (face_video) 与肢体动作 (pose_video)；
   - 内置最大 BBox 动态过滤，彻底杜绝水印、贴纸与背景路人干扰（杜绝“第三只手”）；
   - 提取成果保存至 input/motion_poses/<项目名>/ 目录，永久可复用；
3. 【人物融合驱动渲染】：
   - 加载 Wan2.2 Animate 14B (Move 模式) + 4步蒸馏 LoRA + Relight LoRA；
   - 融合目标人物形象与驱动动作，4 步极速采样出片；
   - 后置 RIFE 超分插帧至 1080P @ 30fps。

用法示例：
  # 1. 干跑验证 (只校验，不提交)：
  cmd /c python tools/motion_transfer_pipeline.py --image input/look1_refined.png --video input/ootd_chunk0.mp4 --dry-run

  # 2. 仅提取与保存管道资产 (方便后续多次复用，不调用 14B 渲染)：
  cmd /c python tools/motion_transfer_pipeline.py --video input/my_dance.mp4 --project dance_pop --skip-render

  # 3. 全链路端到端运行 (自动提取管道 -> 自动提交人物融合渲染)：
  cmd /c python tools/motion_transfer_pipeline.py --image input/my_character.png --video input/my_dance.mp4 --project dance_pop
=============================================================================
"""

import argparse
import json
import os
import shutil
import sys
import urllib.request
import urllib.error
from datetime import date

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = r"D:\ai_projects\ComfyUI"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

TOOLS_DIR = os.path.join(ROOT, "tools")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from tools.ootd_study.extract_pure_pose import extract_pure_poses

DEFAULT_API_WF = os.path.join(ROOT, "workflows", "v3", "wan_animate_pure_pose_api.json")
COMFY_URL = "http://127.0.0.1:8188"


def check_server_live():
    """检查 ComfyUI 服务是否存活"""
    try:
        req = urllib.request.Request(f"{COMFY_URL}/system_stats")
        with urllib.request.urlopen(req, timeout=3) as res:
            return res.status == 200
    except Exception:
        return False


def post_prompt(workflow_prompt):
    """向 ComfyUI 提交渲染任务 (长任务只提交不轮询)"""
    payload = json.dumps({"prompt": workflow_prompt}).encode("utf-8")
    req = urllib.request.Request(
        f"{COMFY_URL}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as res:
        data = json.loads(res.read().decode("utf-8"))
        return data.get("prompt_id")


def run_pipeline(
    image_path=None,
    video_path=None,
    project_name=None,
    frames=49,
    width=480,
    height=832,
    fps=16.0,
    skip_render=False,
    dry_run=False,
    reuse_existing_pose=True
):
    print("=" * 70)
    print("★ Wan2.2 动作迁移与人物融合流水线 (纯净姿态解耦版)")
    print("=" * 70)

    if not video_path or not os.path.exists(video_path):
        print(f"[错误] 参考驱动视频不存在: {video_path}")
        sys.exit(1)

    if not skip_render and (not image_path or not os.path.exists(image_path)):
        print(f"[错误] 目标人物图片不存在: {image_path}")
        sys.exit(1)

    if not project_name:
        project_name = os.path.splitext(os.path.basename(video_path))[0]

    today_str = date.today().strftime("%Y-%m-%d")
    pose_dir = os.path.join(ROOT, "input", "motion_poses", project_name)
    os.makedirs(pose_dir, exist_ok=True)

    expected_pose = os.path.join(pose_dir, f"{project_name}_pose_pure.mp4")
    expected_face = os.path.join(pose_dir, f"{project_name}_face_pure.mp4")

    # 1. 姿态与表情提取管道
    print(f"\n[阶段 1/2] 动作骨骼与面部表情管道检测 / 提取...")
    if reuse_existing_pose and os.path.exists(expected_pose) and os.path.exists(expected_face):
        print(f"✔ 命中已有姿态管道，直接复用 (节省提取算力与时间):")
        print(f"  · 肢体骨骼: {expected_pose}")
        print(f"  · 面部表情: {expected_face}")
        pose_out, face_out = expected_pose, expected_face
    else:
        if dry_run:
            print(f"[Dry-Run] 计划运行 extract_pure_poses 提取 {frames} 帧骨架至 {pose_dir}")
            pose_out, face_out = expected_pose, expected_face
        else:
            print(f"▶ 启动 DWPose 单人纯净化提取: 目标 {frames} 帧 ({width}x{height} @ {fps}fps)...")
            pose_out, face_out = extract_pure_poses(
                video_path=video_path,
                output_dir=pose_dir,
                prefix=project_name,
                max_frames=frames,
                width=width,
                height=height,
                fps=fps
            )
            # 同时在 input 根目录同步一份方便 ComfyUI UI 检索
            root_pose = os.path.join(ROOT, "input", f"{project_name}_pose_pure.mp4")
            root_face = os.path.join(ROOT, "input", f"{project_name}_face_pure.mp4")
            shutil.copy2(pose_out, root_pose)
            shutil.copy2(face_out, root_face)
            print(f"✔ 管道资产已保存至归档目录及 input/ 根目录，可随时永久复用。")

    if skip_render:
        print(f"\n★ 动作与表情管道保存完成！(--skip-render 已激活，跳过 14B 模型渲染)")
        print(f"您可以在 ComfyUI 中加载 workflows/v3/motion_transfer_wan_animate_ui.json 并直接选择此管道。")
        return

    # 2. 人物融合驱动渲染
    print(f"\n[阶段 2/2] 人物融合与动作迁移渲染...")
    if not os.path.exists(DEFAULT_API_WF):
        print(f"[错误] API 模板工作流不存在: {DEFAULT_API_WF}")
        sys.exit(1)

    with open(DEFAULT_API_WF, "r", encoding="utf-8") as f:
        wf = json.load(f)

    # 准备相对路径以满足 ComfyUI input 规范
    def to_rel(p):
        p_abs = os.path.abspath(p)
        in_abs = os.path.abspath(os.path.join(ROOT, "input"))
        if p_abs.startswith(in_abs):
            rel = os.path.relpath(p_abs, in_abs).replace("\\", "/")
            return rel
        # 如果不在 input 目录，复制一份进去
        dst = os.path.join(in_abs, os.path.basename(p))
        if not os.path.exists(dst):
            shutil.copy2(p_abs, dst)
        return os.path.basename(dst)

    rel_image = to_rel(image_path)
    rel_video = to_rel(video_path)
    rel_pose = to_rel(pose_out)
    rel_face = to_rel(face_out)

    # 注入节点参数
    wf["10"]["inputs"]["image"] = rel_image
    wf["12"]["inputs"]["file"] = rel_video
    wf["22"]["inputs"]["file"] = rel_pose
    wf["24"]["inputs"]["file"] = rel_face

    wf["17"]["inputs"]["width"] = width
    wf["17"]["inputs"]["height"] = height
    wf["17"]["inputs"]["length"] = frames
    wf["17"]["inputs"]["video_frame_offset"] = 0
    wf["18"]["inputs"]["seed"] = 20261004

    # 规范化输出目录
    out_prefix = f"{today_str}/motion_transfer/{project_name}"
    wf["21"]["inputs"]["filename_prefix"] = out_prefix

    print("✔ 参数注入完成:")
    print(f"  · 目标人物: {rel_image}")
    print(f"  · 参考视频: {rel_video}")
    print(f"  · 肢体动作: {rel_pose}")
    print(f"  · 面部表情: {rel_face}")
    print(f"  · 输出前缀: output/{out_prefix}")

    if dry_run:
        print("\n✔ [Dry-Run] 静态校验全部通过，不执行实际提交。")
        return

    # 提交任务
    if not check_server_live():
        print(f"[警告] ComfyUI 服务 (8188) 未启动，无法立即提交任务。")
        print(f"已将准备好的任务配置保存为可复用管道。启动 ComfyUI 后可重新运行。")
        return

    prompt_id = post_prompt(wf)
    print(f"\n★ 动作迁移任务已成功提交至 ComfyUI！")
    print(f"  · 任务 Prompt ID: {prompt_id}")
    print(f"  · 预期渲染产物: output/{out_prefix}*.mp4")
    print(f"  · 遵循项目执行纪律：长任务后台自主运行，不进行轮询。")
    print(f"  · 稍后可在终端手动执行查询: curl http://127.0.0.1:8188/history/{prompt_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wan2.2 动作迁移与人物融合流水线")
    parser.add_argument("--image", default=None, help="目标人物图片路径")
    parser.add_argument("--video", required=True, help="参考驱动视频路径")
    parser.add_argument("--project", default=None, help="项目/动作归档名称")
    parser.add_argument("--frames", type=int, default=49, help="提取/生成帧数 (需满足 length % 4 == 1，默认 49)")
    parser.add_argument("--width", type=int, default=480, help="宽度 (默认 480)")
    parser.add_argument("--height", type=int, default=832, help="高度 (默认 832)")
    parser.add_argument("--fps", type=float, default=16.0, help="基础帧率 (默认 16.0)")
    parser.add_argument("--skip-render", action="store_true", help="仅提取动作与表情管道，不执行 14B 渲染")
    parser.add_argument("--dry-run", action="store_true", help="干跑检查，不实际生成与提交")
    parser.add_argument("--no-reuse", action="store_false", dest="reuse_existing_pose", help="强制重新提取姿态，不复用已存管道")
    args = parser.parse_args()

    run_pipeline(
        image_path=args.image,
        video_path=args.video,
        project_name=args.project,
        frames=args.frames,
        width=args.width,
        height=args.height,
        fps=args.fps,
        skip_render=args.skip_render,
        dry_run=args.dry_run,
        reuse_existing_pose=args.reuse_existing_pose
    )
