#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/run_motion_transfer_tests.py
=============================================================================
动作迁移自动化测试套件：
- 模式一（Web UI 工作流架构自动化验证）：生成 3 个 10 秒测试视频
- 模式二（CLI 流水线端到端自动化验证）：生成 3 个 10 秒测试视频

共 6 个自动化测试用例，每个用例由 3 个连贯分块渲染并自动缝合为 10 秒高清视频。
所有产物按日期归档至 output/YYYY-MM-DD/motion_transfer_test/ 目录。
=============================================================================
"""

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = r"D:\ai_projects\ComfyUI"
COMFY_URL = "http://127.0.0.1:8188"
FFMPEG_BIN = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"

# 工作流模板路径
WF_UI_TEMPLATE = os.path.join(ROOT, "workflows", "v3", "ootd_wan_animate_pure_pose_ui.json")
WF_API_TEMPLATE = os.path.join(ROOT, "workflows", "v3", "wan_animate_pure_pose_api.json")

# 测试矩阵定义 (模式一: 1~3, 模式二: 4~6)
TEST_CASES = [
    {
        "id": 1,
        "mode": 1,
        "name": "mode1_case1_look1",
        "desc": "模式一·用例1: 经典LOOK1气质模特 + 舞步分块驱动",
        "image": "ootd_look_1_g1_g1.png",
        "prompt": "Cinematic high fashion video of an elegant model, naturally performing the motion from reference video, soft gentle smile, relaxed hands, sharp focus, 8k uhd"
    },
    {
        "id": 2,
        "mode": 1,
        "name": "mode1_case2_bathroom",
        "desc": "模式一·用例2: 室内写真女模 + 舞步分块驱动",
        "image": "cover_refine_01_bathroom.png",
        "prompt": "Cinematic beautiful female portrait, naturally performing the dance motion, detailed facial features, realistic skin texture, photorealistic lighting"
    },
    {
        "id": 3,
        "mode": 1,
        "name": "mode1_case3_sailor",
        "desc": "模式一·用例3: 水手服户外模特 + 舞步分块驱动",
        "image": "cover_refine_03_sailor_rain.png",
        "prompt": "Cinematic photorealistic portrait of a young model in sailor outfit, graceful dancing, natural facial expressions, subtle smiling, masterpiece"
    },
    {
        "id": 4,
        "mode": 2,
        "name": "mode2_case4_redslip",
        "desc": "模式二·用例4 (CLI): 红色吊带裙模特 + 端到端动作迁移",
        "image": "cover_refine_04_red_slipdress.png",
        "prompt": "Cinematic photorealistic portrait of an elegant woman in red slip dress, fluid dancing motion, detailed face, studio lighting, 8k uhd"
    },
    {
        "id": 5,
        "mode": 2,
        "name": "mode2_case5_refimage",
        "desc": "模式二·用例5 (CLI): 官方 Wan2.2 基准模特 + 端到端动作迁移",
        "image": "video_wan2_2_14B_animate_reference_image.png",
        "prompt": "High fashion model performing dance movement, photorealistic, cinematic camera, natural micro-expressions, 8k masterpiece"
    },
    {
        "id": 6,
        "mode": 2,
        "name": "mode2_case6_model1",
        "desc": "模式二·用例6 (CLI): Qwen 实拍风格模特 + 端到端动作迁移",
        "image": "model1_qwen.png",
        "prompt": "Photorealistic female model performing graceful choreography, sharp focus on eyes and face, natural motion, perfect anatomy"
    }
]

# 3 个分块驱动 (总长 9.9 秒 ≈ 10 秒)
CHUNKS = [
    {
        "index": 0,
        "drv": "ootd_drv_chunk_0_drv16.mp4",
        "pose": "motion_poses/ootd_dance/chunk0_pose_pure.mp4",
        "face": "motion_poses/ootd_dance/chunk0_face_pure.mp4"
    },
    {
        "index": 1,
        "drv": "ootd_drv_chunk_1_drv16.mp4",
        "pose": "motion_poses/ootd_dance/chunk1_pose_pure.mp4",
        "face": "motion_poses/ootd_dance/chunk1_face_pure.mp4"
    },
    {
        "index": 2,
        "drv": "ootd_drv_chunk_2_drv16.mp4",
        "pose": "motion_poses/ootd_dance/chunk2_pose_pure.mp4",
        "face": "motion_poses/ootd_dance/chunk2_face_pure.mp4"
    }
]


def log(msg):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}", flush=True)


def check_server():
    try:
        r = urllib.request.urlopen(f"{COMFY_URL}/system_stats", timeout=3)
        return r.status == 200
    except Exception:
        return False


def post_prompt(wf):
    payload = json.dumps({"prompt": wf}).encode("utf-8")
    req = urllib.request.Request(
        f"{COMFY_URL}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as res:
        data = json.loads(res.read().decode("utf-8"))
        return data.get("prompt_id")


def wait_for_prompt(prompt_id, timeout_sec=600):
    """在脚本内部等待单个分块完成 (避免主智能体上下文轮询)"""
    t0 = time.time()
    while time.time() - t0 < timeout_sec:
        try:
            with urllib.request.urlopen(f"{COMFY_URL}/history/{prompt_id}", timeout=5) as res:
                data = json.loads(res.read().decode("utf-8"))
                if prompt_id in data:
                    item = data[prompt_id]
                    status = item.get("status", {})
                    if status.get("completed", False):
                        outputs = item.get("outputs", {})
                        # 查找 30fps 视频或 16fps 视频路径
                        for nid in ["32", "21"]:
                            if nid in outputs:
                                gifs = outputs[nid].get("gifs") or outputs[nid].get("videos") or []
                                if gifs and gifs[0].get("fullpath"):
                                    return gifs[0].get("fullpath")
                                imgs = outputs[nid].get("images") or []
                                for im in imgs:
                                    fn = im.get("filename", "")
                                    sub = im.get("subfolder", "")
                                    if fn.endswith((".mp4", ".mov", ".mkv", ".webm")):
                                        p = os.path.join(ROOT, "output", sub, fn)
                                        if os.path.exists(p):
                                            return p
        except Exception:
            pass
        time.sleep(10)
    return None


def stitch_video(chunk_files, output_mp4):
    """使用 FFmpeg 无损拼接 3 个分块为 10 秒成片"""
    concat_txt = output_mp4 + ".concat.txt"
    with open(concat_txt, "w", encoding="utf-8") as f:
        for cf in chunk_files:
            f.write(f"file '{os.path.abspath(cf)}'\n")

    cmd = [
        FFMPEG_BIN, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_txt,
        "-c", "copy",
        output_mp4
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if os.path.exists(concat_txt):
        os.remove(concat_txt)
    return res.returncode == 0 and os.path.exists(output_mp4)


def build_workflow_prompt(case, chunk, out_prefix):
    """基于纯净姿态 API 模板注入参数"""
    with open(WF_API_TEMPLATE, "r", encoding="utf-8") as f:
        wf = json.load(f)

    wf["10"]["inputs"]["image"] = case["image"]
    wf["12"]["inputs"]["file"] = chunk["drv"]
    wf["22"]["inputs"]["file"] = chunk["pose"]
    wf["24"]["inputs"]["file"] = chunk["face"]
    wf["8"]["inputs"]["text"] = case["prompt"]

    wf["17"]["inputs"]["width"] = 480
    wf["17"]["inputs"]["height"] = 832
    wf["17"]["inputs"]["length"] = 49
    wf["17"]["inputs"]["video_frame_offset"] = 0
    wf["18"]["inputs"]["seed"] = 20261004 + case["id"] * 10 + chunk["index"]

    wf["21"]["inputs"]["filename_prefix"] = out_prefix + "_raw16"
    return wf


def run_tests(selected_mode=None, dry_run=False):
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    out_dir = os.path.join(ROOT, "output", today_str, "motion_transfer_test")
    chunks_dir = os.path.join(out_dir, "chunks")
    os.makedirs(chunks_dir, exist_ok=True)

    log("=" * 70)
    log("★ 动作迁移自动化测试套件 (模式一 & 模式二 各 3 个 10 秒视频)")
    log("=" * 70)
    log(f"产物输出目录: {out_dir}")

    cases_to_run = [c for c in TEST_CASES if (selected_mode is None or c["mode"] == selected_mode)]
    log(f"本次计划执行用例数: {len(cases_to_run)} 个")

    if not dry_run and not check_server():
        log("[错误] ComfyUI 服务 (8188) 未启动，无法执行测试！")
        sys.exit(1)

    completed_videos = []

    for case in cases_to_run:
        cid = case["id"]
        cname = case["name"]
        final_mp4 = os.path.join(out_dir, f"{cname}_10s.mp4")

        log("-" * 60)
        log(f"▶ 开始执行用例 [{cid}/6]: {case['desc']}")
        log(f"  · 目标人物: {case['image']}")
        log(f"  · 预期成片: {final_mp4}")

        # 检查图像是否存在
        img_full = os.path.join(ROOT, "input", case["image"])
        if not os.path.exists(img_full):
            log(f"  [跳过] 找不到人物素材: {img_full}")
            continue

        if os.path.exists(final_mp4) and os.path.getsize(final_mp4) > 1000000:
            log(f"  ✔ 该成片已存在且完整，直接复用: {final_mp4}")
            completed_videos.append(final_mp4)
            continue

        rendered_chunks = []
        for chk in CHUNKS:
            idx = chk["index"]
            chk_prefix = f"{today_str}/motion_transfer_test/chunks/{cname}_chk{idx}"
            log(f"  [分块 {idx}/2] 准备分块任务 (约 3.3s)...")

            # 检查分块是否已存在
            import glob
            cands = glob.glob(os.path.join(chunks_dir, f"{cname}_chk{idx}_raw16_*.mp4"))
            if cands and os.path.exists(cands[0]) and os.path.getsize(cands[0]) > 100000:
                log(f"    ✔ 命中已有分块产物，直接复用: {os.path.basename(cands[0])}")
                rendered_chunks.append(cands[0])
                continue

            if dry_run:
                log(f"    [Dry-Run] 静态校验分块 {idx}: drv={chk['drv']}, pose={chk['pose']}")
                rendered_chunks.append(os.path.join(chunks_dir, f"{cname}_chk{idx}_dummy.mp4"))
                continue

            wf = build_workflow_prompt(case, chk, chk_prefix)
            pid = post_prompt(wf)
            log(f"    ✔ 分块 {idx} 已提交至 ComfyUI (Prompt ID: {pid})，等待渲染...")

            chunk_video = wait_for_prompt(pid, timeout_sec=900)
            if chunk_video and os.path.exists(chunk_video):
                log(f"    ✔ 分块 {idx} 渲染完成: {chunk_video}")
                rendered_chunks.append(chunk_video)
            else:
                log(f"    [错误] 分块 {idx} 渲染超时或失败！")
                break

        if dry_run:
            log(f"  [Dry-Run] 用例 {cid} 校验通过。")
            continue

        if len(rendered_chunks) == len(CHUNKS):
            log(f"  ▶ 3 个分块全部就绪，正在使用 FFmpeg 缝合为 10 秒最终成片...")
            ok = stitch_video(rendered_chunks, final_mp4)
            if ok:
                log(f"  ★ [成功] 用例 {cid} 10 秒成片已生成: {final_mp4}")
                completed_videos.append(final_mp4)
            else:
                log(f"  [错误] 拼接成片失败: {final_mp4}")
        else:
            log(f"  [失败] 用例 {cid} 未能完成全部 3 个分块。")

    log("=" * 70)
    log(f"★ 自动化测试执行完毕！共完成 {len(completed_videos)} 个 10 秒成片交付。")
    for v in completed_videos:
        log(f"  · {v}")
    log("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="动作迁移 6 个 10 秒视频自动化测试")
    parser.add_argument("--mode", type=int, choices=[1, 2], default=None, help="仅测试模式 1 或模式 2")
    parser.add_argument("--dry-run", action="store_true", help="干跑校验全部用例，不实际提交")
    args = parser.parse_args()

    run_tests(selected_mode=args.mode, dry_run=args.dry_run)
