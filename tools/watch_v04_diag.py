#!/usr/bin/env python3
"""v04 诊断 watchdog：每 60s 检查 ComfyUI 进程存活 + v04 完成状态。
用法: python tools/watch_v04_diag.py <pid>
"""
import json, os, subprocess, sys, time, urllib.request

COMFY = "http://127.0.0.1:8188"
PID = sys.argv[1] if len(sys.argv) > 1 else ""

def comfy_alive():
    try:
        urllib.request.urlopen(f"{COMFY}/queue", timeout=5)
        return True
    except Exception:
        return False

def history(pid):
    try:
        h = json.loads(urllib.request.urlopen(f"{COMFY}/history/{pid}", timeout=5).read())
        if pid in h:
            st = h[pid].get("status", {})
            return st.get("completed", False), st.get("status_str", "?")
        return False, "pending"
    except Exception:
        return None, None

start = time.time()
last = 0
while True:
    alive = comfy_alive()
    if not alive:
        print(f"[{int(time.time()-start)}s] ❌ ComfyUI 无响应/已崩溃!", flush=True)
        break
    if PID:
        done, st = history(PID)
        if done is not None and done:
            print(f"[{int(time.time()-start)}s] ✅ v04 完成 status={st}", flush=True)
            break
        if done is None:
            print(f"[{int(time.time()-start)}s] ⚠️ history 查询异常", flush=True)
    if time.time() - last > 120:
        print(f"[{int(time.time()-start)}s] 存活中，v04 仍在跑（{st if PID else ''}）", flush=True)
        last = time.time()
    time.sleep(60)
