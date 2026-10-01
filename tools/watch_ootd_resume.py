#!/usr/bin/env python3
"""OOTD v05-v08 监控：完成检测 + ComfyUI 存活检测（崩溃立即报警）。
用法: python tools/watch_ootd_resume.py workflows/v1/ootd_v1_resume_pids.json
"""
import json, os, sys, time, urllib.request

COMFY = "http://127.0.0.1:8188"
PIDS_FILE = sys.argv[1] if len(sys.argv) > 1 else "workflows/v1/ootd_v1_resume_pids.json"

def alive():
    try:
        urllib.request.urlopen(f"{COMFY}/queue", timeout=5)
        return True
    except Exception:
        return False

def check(pid):
    try:
        h = json.loads(urllib.request.urlopen(f"{COMFY}/history/{pid}", timeout=5).read())
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("completed"):
                return "done", st.get("status_str", "?")
            if st.get("status_str") == "error":
                return "error", st.get("status_str")
        return "pending", ""
    except Exception:
        return "unknown", ""

def main():
    with open(PIDS_FILE, encoding="utf-8") as f:
        segs = json.load(f)
    total = len(segs)
    print(f"监控 {total} 个视频 (v05-v08)...", flush=True)
    done = {}
    start = time.time()
    last = 0
    crashed = 0
    while len(done) < total:
        if not alive():
            crashed += 1
            print(f"[{int((time.time()-start)/60)}min] ❌ ComfyUI 崩溃/无响应！已完成 {len(done)}/{total}", flush=True)
            break
        for s in segs:
            pid = s["pid"]
            if pid in done:
                continue
            st, detail = check(pid)
            if st in ("done", "error"):
                done[pid] = (s["name"], st, detail)
                print(f"[完成] {s['name']} ({st})", flush=True)
        if time.time() - last > 180:
            print(f"[进度] {len(done)}/{total} 完成，已用 {int((time.time()-start)/60)} 分钟", flush=True)
            last = time.time()
        if len(done) < total:
            time.sleep(45)
    elapsed = int((time.time() - start) / 60)
    if len(done) == total:
        errs = [(n, st, d) for n, st, d in done.values() if st == "error"]
        print(f"\n=== 全部 {total} 完成，耗时 {elapsed} 分钟 ===", flush=True)
        if errs:
            print("有错误:", errs, flush=True)
        else:
            print("全部成功 ✅", flush=True)
    else:
        print(f"\n=== 中断：仅 {len(done)}/{total} 完成（耗时 {elapsed} 分钟）===", flush=True)
        remaining = [s["name"] for s in segs if s["pid"] not in done]
        print("未完成:", remaining, flush=True)

if __name__ == "__main__":
    os.chdir("D:/ai_projects/ComfyUI")
    main()
