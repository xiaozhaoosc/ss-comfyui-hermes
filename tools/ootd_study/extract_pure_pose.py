#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_pure_pose.py
=============================================================================
纯净单人骨骼/面部视频提取工具（彻底根除 Wan2.2 多手/畸变肢体）

功能：
1. 输入任意舞蹈/动作视频（mp4），自动调整分辨率至 480x832 (9:16)
2. 逐帧运行 DWPose 关键点检测
3. 动态计算人体 BBox 包围盒面积，过滤掉角落贴纸、路人与背景小人，仅锁定主舞者
4. 分流导出两路标准 H.264 视频存入 ComfyUI/input/ 目录：
   - <前缀>_pose_pure.mp4  (身体+双手骨骼，输入 WanAnimate pose_video)
   - <前缀>_face_pure.mp4  (面部表情点，输入 WanAnimate face_video)

用法：
  python tools/ootd_study/extract_pure_pose.py --video input/your_dance.mp4
  python tools/ootd_study/extract_pure_pose.py --video input/ootd_target.mp4 --prefix ootd_chunk0 --frames 49
=============================================================================
"""

import argparse
import os
import sys
import subprocess
import cv2
import numpy as np
import torch
from PIL import Image

ROOT = r"D:\ai_projects\ComfyUI"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from custom_nodes.comfyui_controlnet_aux.node_wrappers.dwpose import DWPose_Preprocessor
from custom_nodes.comfyui_controlnet_aux.src.custom_controlnet_aux.dwpose import decode_json_as_poses, draw_poses

FFMPEG_BIN = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"


def get_person_area(p):
    kpts = p.get("pose_keypoints_2d", [])
    valid_x = [kpts[i] for i in range(0, len(kpts), 3) if kpts[i+2] > 0]
    valid_y = [kpts[i+1] for i in range(0, len(kpts), 3) if kpts[i+2] > 0]
    if not valid_x or not valid_y:
        return 0
    return (max(valid_x) - min(valid_x)) * (max(valid_y) - min(valid_y))


def extract_pure_poses(video_path, output_dir=None, dance=None, prefix=None, max_frames=None, width=480, height=832, fps=16.0):
    if output_dir is None:
        if dance:
            output_dir = os.path.join(ROOT, "input", "motion_poses", dance)
        else:
            output_dir = os.path.join(ROOT, "input")
    os.makedirs(output_dir, exist_ok=True)

    if prefix is None:
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        prefix = base_name

    pose_out = os.path.join(output_dir, f"{prefix}_pose_pure.mp4")
    face_out = os.path.join(output_dir, f"{prefix}_face_pure.mp4")
    temp_pose = os.path.join(output_dir, f"_temp_{prefix}_pose.mp4")
    temp_face = os.path.join(output_dir, f"_temp_{prefix}_face.mp4")

    print(f"[1/3] 初始化 DWPose 检测器 (YOLOX-L + DWPose-384)...")
    pre = DWPose_Preprocessor()

    cap = cv2.VideoCapture(video_path)
    total_src_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frames_to_process = min(total_src_frames, max_frames) if max_frames else total_src_frames

    vw_pose = cv2.VideoWriter(temp_pose, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    vw_face = cv2.VideoWriter(temp_face, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))

    print(f"[2/3] 提取纯净单人姿态: {video_path} -> {frames_to_process} 帧 ({width}x{height} @ {fps}fps)...")
    for fi in range(frames_to_process):
        ret, frame = cap.read()
        if not ret:
            break

        pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).resize((width, height), Image.Resampling.LANCZOS)
        img_t = torch.from_numpy(np.array(pil).astype(np.float32) / 255.0).unsqueeze(0)

        # 单次前向同时检测 body, hand, face
        ret_pose = pre.estimate_pose(
            image=img_t,
            detect_hand="enable",
            detect_body="enable",
            detect_face="enable",
            resolution=512,
            bbox_detector="yolox_l.onnx",
            pose_estimator="dw-ll_ucoco_384_bs5.torchscript.pt",
            scale_stick_for_xinsr_cn="disable"
        )

        openpose_json = ret_pose["result"][1][0]
        people = openpose_json["people"]
        areas = [get_person_area(p) for p in people]
        main_idx = int(np.argmax(areas)) if areas else 0

        # 仅保留主舞者，剥离角标小人与背景杂人
        filtered_json = {
            "people": [people[main_idx]] if people else [],
            "canvas_height": openpose_json["canvas_height"],
            "canvas_width": openpose_json["canvas_width"]
        }

        poses, animals, H, W = decode_json_as_poses(filtered_json)

        # 纯肢体+双手（无脸部）
        canvas_pose = draw_poses(poses, height, width, draw_body=True, draw_hand=True, draw_face=False)
        # 纯面部表情（无肢体手部）
        canvas_face = draw_poses(poses, height, width, draw_body=False, draw_hand=False, draw_face=True)

        vw_pose.write(cv2.cvtColor(canvas_pose, cv2.COLOR_RGB2BGR))
        vw_face.write(cv2.cvtColor(canvas_face, cv2.COLOR_RGB2BGR))

        if (fi + 1) % 15 == 0 or fi == frames_to_process - 1:
            print(f"   已处理 {fi+1}/{frames_to_process} 帧...")

    cap.release()
    vw_pose.release()
    vw_face.release()

    print(f"[3/3] 编码为标准 H.264 视频...")
    for tmp_f, fin_f in [(temp_pose, pose_out), (temp_face, face_out)]:
        subprocess.run([
            FFMPEG_BIN, "-y",
            "-i", tmp_f,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            fin_f
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        if os.path.exists(tmp_f):
            os.remove(tmp_f)

    print(f"\n★ 纯净姿态骨骼提取完成！可以直接在 ComfyUI LoadVideo 节点中选择：")
    print(f"  · 肢体骨骼: {pose_out}")
    print(f"  · 面部表情: {face_out}")
    return pose_out, face_out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="提取纯净单人肢体与面部骨骼视频")
    parser.add_argument("--video", required=True, help="输入的源视频路径")
    parser.add_argument("--dance", default=None, help="舞蹈名称分类 (如 ootd_dance, street_dance，自动输出至 input/motion_poses/<dance>/)")
    parser.add_argument("--prefix", default=None, help="输出文件前缀 (默认为源视频名)")
    parser.add_argument("--frames", type=int, default=49, help="处理帧数 (默认49帧)")
    parser.add_argument("--width", type=int, default=480, help="目标宽度 (默认480)")
    parser.add_argument("--height", type=int, default=832, help="目标高度 (默认832)")
    parser.add_argument("--fps", type=float, default=16.0, help="目标帧率 (默认16.0)")
    args = parser.parse_args()

    extract_pure_poses(
        video_path=args.video,
        dance=args.dance,
        prefix=args.prefix,
        max_frames=args.frames,
        width=args.width,
        height=args.height,
        fps=args.fps
    )
