"""WanAnimate 批处理进度检查：统计已完成/队列中/失败，并核对产物文件是否存在。

用法：python tools/wan_batch_status.py [--prefix 2026-10-11_wb/wanC]
"""
import argparse, json, os, re, urllib.request, glob

ROOT = r"d:\ai_projects\ComfyUI"
SERVER = "http://127.0.0.1:8188"


def opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="2026-10-11_wb/wanC")
    a = ap.parse_args()

    out_dir = os.path.join(ROOT, "output", os.path.dirname(a.prefix))
    base = os.path.basename(a.prefix)

    q = json.loads(opener().open(SERVER + "/queue", timeout=20).read().decode())
    run, pend = q.get("queue_running", []), q.get("queue_pending", [])
    mine_run = [e for e in run if "WanAnimateToVideo" in [v.get("class_type") for v in e[2].values()]]
    mine_pend = [e for e in pend if "WanAnimateToVideo" in [v.get("class_type") for v in e[2].values()]]

    print("=== ComfyUI 队列 ===")
    print("  总 running=%d pending=%d ｜ 我的 WanAnimate: running=%d pending=%d"
          % (len(run), len(pend), len(mine_run), len(mine_pend)))
    tot_chunks = sum(sum(1 for v in e[2].values() if v.get("class_type") == "WanAnimateToVideo")
                     for e in mine_run + mine_pend)
    print("  我的剩余 chunks: %d" % tot_chunks)
    if mine_run:
        n = mine_run[0][2]
        print("  正在渲染:", n.get("12", {}).get("inputs", {}).get("file"))

    # 已完成：扫 history
    try:
        h = json.loads(opener().open(SERVER + "/history?max_items=200", timeout=30).read().decode())
    except Exception:
        h = {}
    done = []
    for pid, v in h.items():
        for o in v.get("outputs", {}).values():
            for k in ("videos", "gifs", "images"):
                for f in o.get(k, []):
                    fn = f.get("filename", "")
                    if base in fn or base in (f.get("subfolder") or ""):
                        done.append(fn)
        if v.get("status", {}).get("status_str") == "error":
            pass

    files = sorted(glob.glob(os.path.join(out_dir, base + "*.mp4")))
    # 只统计本轮渲染目录下的
    files = [f for f in files if os.path.dirname(os.path.abspath(f)) == os.path.abspath(out_dir)]

    print()
    print("=== 产物 ===")
    print("  目录: %s" % out_dir)
    print("  已落盘 mp4: %d" % len(files))
    for f in files:
        sz = os.path.getsize(f) / 1024
        print("    %.0f KB  %s" % (sz, os.path.basename(f)))

    total = len(files) + len(mine_run) + len(mine_pend)
    print()
    print("=== 进度 === 已出 %d / 约 %d 条" % (len(files), total))


if __name__ == "__main__":
    main()
