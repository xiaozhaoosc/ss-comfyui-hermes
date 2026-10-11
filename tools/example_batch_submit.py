#!/usr/bin/env python3
"""示例：如何使用 ComfyUI SQLite 外部队列进行批量分镜任务管理与断点续跑

本脚本演示标准工作流:
  1. 生成或加载多个分镜 API Prompt 任务
  2. 先行落库到 SQLite (状态为 pending，防止意外关机丢数据)
  3. 批量提交完毕后，启动调度器自动执行或交由后台 resume 处理
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.comfy_sqlite_queue import enqueue_task, resume_queue, print_status


def demo_batch_submission():
    batch_name = "ep01_part2_demo"
    print(f"[*] 开始批量落库分镜任务 (Batch: {batch_name})...")

    # 模拟 3 个分镜的 Prompt 数据
    shots = [
        {"shot_id": "shot_01", "prompt_text": "A futuristic cyberpunk street, neon lights, 4k", "seed": 1001},
        {"shot_id": "shot_02", "prompt_text": "Close-up portrait of female warrior, cinematic lighting", "seed": 1002},
        {"shot_id": "shot_03", "prompt_text": "Wide angle drone shot over high tech metropolis", "seed": 1003},
    ]

    for shot in shots:
        # 构建 ComfyUI API Prompt (此处为简化示意节点图)
        api_prompt = {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": shot["seed"],
                    "steps": 20,
                    "cfg": 7.0,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                }
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": shot["prompt_text"]}
            }
        }

        # 核心：落库入队 (即使系统下一秒断电，任务也已安全保存在 user/task_queue.db)
        task_id = enqueue_task(
            prompt_dict=api_prompt,
            batch_name=batch_name,
            extra_meta={"shot_id": shot["shot_id"], "seed": shot["seed"]}
        )
        print(f"  [+] 已登记分镜 {shot['shot_id']} -> Task ID: {task_id}")

    print("\n[*] 批量落库完毕，当前队列状态:")
    print_status()

    print("[*] 提示: 运行以下命令即可随时启动或断点恢复该批次任务:")
    print(f"    cmd /c python tools/comfy_sqlite_queue.py resume --batch {batch_name}\n")


if __name__ == "__main__":
    demo_batch_submission()
