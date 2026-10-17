#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""等待 ComfyUI 某个 prompt 执行完成，成功退出 0，error/超时退出非 0。

提交器只负责 POST /prompt（长任务不轮询），需要通知时用本脚本挂后台等待，
完成任务后由系统回调，避免主流程反复 sleep 轮询。

用法：
    python tools/wait_prompt.py <prompt_id> [--timeout 7200] [--interval 20]
"""

import argparse
import json
import sys
import time
import urllib.request

COMFY_URL = "http://127.0.0.1:8188"


def main():
    ap = argparse.ArgumentParser(description="等待 ComfyUI prompt 完成")
    ap.add_argument("prompt_id")
    ap.add_argument("--timeout", type=float, default=7200.0, help="最长等待秒数")
    ap.add_argument("--interval", type=float, default=20.0, help="轮询间隔秒数")
    ap.add_argument("--url", default=COMFY_URL)
    args = ap.parse_args()

    url = "%s/history/%s" % (args.url, args.prompt_id)
    deadline = time.time() + args.timeout
    last = None
    while time.time() < deadline:
        try:
            h = json.loads(urllib.request.urlopen(url, timeout=15).read().decode("utf-8"))
            if args.prompt_id in h:
                status = h[args.prompt_id].get("status", {})
                s = status.get("status_str", "unknown")
                if s != last:
                    print("[%s] 状态: %s" % (time.strftime("%H:%M:%S"), s), flush=True)
                    last = s
                if s in ("success", "error"):
                    for nid, out in (h[args.prompt_id].get("outputs") or {}).items():
                        print("  节点 %s: %s" % (nid, json.dumps(out, ensure_ascii=False)[:300]), flush=True)
                    if s == "error":
                        print(json.dumps(status.get("messages", []), ensure_ascii=False)[:1500], flush=True)
                    return 0 if s == "success" else 1
        except Exception as e:
            print("[%s] 轮询异常: %s" % (time.strftime("%H:%M:%S"), e), flush=True)
        time.sleep(args.interval)
    print("超时未完成")
    return 2


if __name__ == "__main__":
    sys.exit(main())
