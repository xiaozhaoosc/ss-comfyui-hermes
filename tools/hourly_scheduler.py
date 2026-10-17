# -*- coding: utf-8 -*-
"""Continuous Local Scheduler for Hourly Character and Garment Asset Generation.

Runs continuously in the background:
- Generates a new Asian female character asset every hour (e.g. at minute :00).
- Generates a new standalone garment asset every hour (e.g. at minute :30).
"""
import os
import sys
import time
import datetime
from pathlib import Path

# Fix Windows console UTF-8 encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from hourly_character_task import generate_random_characters
from hourly_garment_task import generate_random_garments


def log(msg):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}", flush=True)


def main():
    log("=" * 65)
    log("🚀 启动本地 AIGC 资产常驻自动化调度器 (安全防风控模式)")
    log("  - 角色任务: 每小时 :00, :30 随机生成 1 位亚洲女性角色资产 (9视角独立高清大图)")
    log("  - 服装任务: 每小时 :15, :45 随机生成 1 款独立服装资产")
    log("  - 视角规格: 9大独立 9:16 高清大图逐一渲染 (向 Google Flow 连续请求 9 次，杜绝切片)")
    log("  - 安全防护: 严格保持 10~12 分钟静默冷却期，防封号与 Cookie 失效")
    log("  - 产物去向: 自动入库 character_library/、garment_library/ 并同步 Web 资产管理中心")
    log("=" * 65)

    last_char_min = -1
    last_garment_min = -1
    is_running_task = False

    while True:
        try:
            now = datetime.datetime.now()
            minute = now.minute

            # Run character generation at :00, :30 of each hour
            if minute in [0, 30] and minute != last_char_min:
                if is_running_task:
                    log(f"[!] 检测到前序任务尚未结束，安全跳过本次角色生成 ({minute:02d}分)")
                else:
                    log(f">>> 触发定时任务 ({minute:02d}分): 随机生成 1 位亚洲女性角色资产 (全套9个独立视角)...")
                    is_running_task = True
                    try:
                        generate_random_characters(count=1)
                        last_char_min = minute
                        log(f"[✓] 角色任务完成（9张独立高清原图入库），进入安全静默冷却期 ☕")
                    except Exception as e:
                        log(f"[!] 角色生成报错: {e}")
                    finally:
                        is_running_task = False

            # Run garment generation at :15, :45 of each hour
            if minute in [15, 45] and minute != last_garment_min:
                if is_running_task:
                    log(f"[!] 检测到前序任务尚未结束，安全跳过本次服装生成 ({minute:02d}分)")
                else:
                    log(f">>> 触发定时任务 ({minute:02d}分): 随机生成 1 款独立服装资产...")
                    is_running_task = True
                    try:
                        generate_random_garments(count=1)
                        last_garment_min = minute
                        log(f"[✓] 服装任务完成，进入 11~14 分钟安全静默冷却期 ☕")
                    except Exception as e:
                        log(f"[!] 服装生成报错: {e}")
                    finally:
                        is_running_task = False

            time.sleep(20)
        except KeyboardInterrupt:
            log("调度器收到退出指令，正常停止。")
            break
        except Exception as e:
            log(f"[!] 调度异常: {e}")
            time.sleep(30)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AIGC Continuous Asset Scheduler (9 Standalone HD Views)")
    parser.parse_args()
    main()
