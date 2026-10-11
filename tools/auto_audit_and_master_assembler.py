#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""北宋杨家将 · 第 3 集自动化质检与母带总装守护系统

在后台监控 ComfyUI 渲染流水线：
1. 定期扫描 output/2026-10-09/yangjiajiang_ep03/ 目录下的全新视频
2. 调用 comfy_shot_quality_auditor.py 逐镜审计
3. 当 54 镜全部完成并 PASS 时，自动触发 yangjiajiang_ep03_master_engine.py 进行母带总装！
"""

import os
import sys
import time
import subprocess
import json
import urllib.request

ROOT = r"D:\ai_projects\ComfyUI"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.comfy_shot_quality_auditor import run_full_audit

def main_loop(max_wait_minutes=120):
    start_time = time.time()
    print("=" * 65)
    print("  【北宋杨家将】第 3 集全新纯净流水线自动化质检与总装守护")
    print("=" * 65)

    while True:
        elapsed_min = (time.time() - start_time) / 60.0
        if elapsed_min > max_wait_minutes:
            print("[!] 超出最大守护时长，退出守护循环。")
            break

        passed, missing, flagged = run_full_audit()
        print(f"\n[*] 守护心跳: 已通过 {passed}/54 镜 | 待生成 {missing} 镜 | 耗时 {elapsed_min:.1f}m")

        if passed == 54:
            print("\n" + "=" * 65)
            print("【全量质检 100% 达成】全部 54 镜纯净电影级视频已通过机器审计！")
            print("立即自动触发母带引擎进行 720P 声画大总成...")
            print("=" * 65)

            cmd = [
                "python", "tools/yangjiajiang_ep03_master_engine.py",
                "--assemble",
                "--source", "comfyui"
            ]
            res = subprocess.run(cmd)
            print(f"母带总装结束，返回值: {res.returncode}")
            break

        # 如果正在渲染中，休眠 30 秒
        time.sleep(30)

if __name__ == "__main__":
    main_loop()
