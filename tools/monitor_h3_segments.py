#!/usr/bin/env python3
"""监控「烽火边关」7个分段的生成进度，全部完成后退出"""
import json, urllib.request, time, sys, os

BASE_URL = "http://127.0.0.1:8188"
PIDS_FILE = sys.argv[1] if len(sys.argv) > 1 else "workflows/v1/h3_segment_pids.json"

def check_history(pid):
    try:
        h = json.loads(urllib.request.urlopen(f"{BASE_URL}/history/{pid}", timeout=10).read())
        if pid in h:
            st = h[pid].get("status", {})
            return st.get("completed", False), st.get("status_str", "?"), st.get("messages", [])
        return False, "pending", []
    except Exception as e:
        return False, f"err:{e}", []

def main():
    with open(PIDS_FILE, encoding="utf-8") as f:
        segs = json.load(f)
    total = len(segs)
    print(f"监控 {total} 个分段...", flush=True)
    done = {}
    start = time.time()
    last_report = 0
    while len(done) < total:
        for s in segs:
            pid = s["pid"]
            if pid in done:
                continue
            completed, status, msgs = check_history(pid)
            if completed:
                # 检查是否有错误（输出文件是否存在）
                has_err = any("error" in str(m).lower() for m in msgs) if msgs else False
                done[pid] = (s["name"], status, has_err)
                print(f"[完成] {s['name']}: {status} {'(有错误!)' if has_err else ''}", flush=True)
        # 每 3 分钟报一次进度
        if time.time() - last_report > 180:
            elapsed = int((time.time() - start) / 60)
            print(f"[进度] {len(done)}/{total} 完成，已用 {elapsed} 分钟", flush=True)
            last_report = time.time()
        if len(done) < total:
            time.sleep(45)

    elapsed = int((time.time() - start) / 60)
    print(f"\n=== 全部 {total} 个分段完成，总耗时 {elapsed} 分钟 ===", flush=True)
    errs = [(n, s) for pid, (n, s, e) in done.items() if e]
    if errs:
        print("有错误的分段:", errs, flush=True)
    else:
        print("全部成功，无错误", flush=True)

if __name__ == "__main__":
    os.chdir("D:/ai_projects/ComfyUI")
    main()
