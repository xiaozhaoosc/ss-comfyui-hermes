import urllib.request
import json
import glob
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def check_status():
    # 1. ComfyUI 本地状态
    try:
        res = json.loads(urllib.request.urlopen('http://127.0.0.1:8188/queue').read())
        running = len(res.get('queue_running', []))
        pending = len(res.get('queue_pending', []))
    except Exception as e:
        running, pending = "N/A", "N/A"

    local_shots = glob.glob('output/2026-10-09/yangjiajiang_ep03/yang_ep03_shot*.mp4')
    muse_shots = glob.glob('output/2026-10-09/yangjiajiang_ep03/muse_videos/muse_shot*.mp4')

    print("=" * 60)
    print("【双轨流水线实时生产看板】")
    print("=" * 60)
    print(f"[方案 1 · 本地 ComfyUI]")
    print(f"  - 队列状态: 正在渲染 {running} 镜 | 等待排队 {pending} 镜")
    print(f"  - 本地已出片: {len(local_shots)} / 54 镜 (完成率: {len(local_shots)/54*100:.1f}%)")
    print(f"\n[方案 2 · 云端 Muse.ai]")
    print(f"  - 云端已出片: {len(muse_shots)} / 54 镜 (完成率: {len(muse_shots)/54*100:.1f}%)")
    print(f"  - 最新落盘: {[os.path.basename(f) for f in sorted(muse_shots)[-5:]]}")
    print("=" * 60)

if __name__ == "__main__":
    check_status()
