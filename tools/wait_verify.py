"""等待 ComfyUI prompt 执行完成并检查输出。"""
import json
import time
import urllib.request
from pathlib import Path

COMFY_URL = "http://127.0.0.1:8188"
PROMPT_ID = "3e16339b-3b04-4744-9e3d-307288023f87"
OUTPUT_DIR = Path(r"d:\ai_projects\ComfyUI\output")
PREFIX = "faceswap_video_v2_verify"


def http_get_json(url):
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    url = f"{COMFY_URL}/history/{PROMPT_ID}"
    deadline = time.time() + 180  # 最多等 3 分钟
    last_status = None
    while time.time() < deadline:
        try:
            history = http_get_json(url)
            if PROMPT_ID in history:
                entry = history[PROMPT_ID]
                status = entry.get("status", {})
                status_str = status.get("status_str", "unknown")
                completed = status.get("completed", False)
                if status_str != last_status:
                    print(f"[{time.strftime('%H:%M:%S')}] 状态: {status_str} (completed={completed})")
                    last_status = status_str
                if status_str in ("success", "error"):
                    print(f"\n执行完成: {status_str}")
                    print(f"详细状态: {json.dumps(status, ensure_ascii=False, indent=2)}")
                    # 打印 outputs
                    outputs = entry.get("outputs", {})
                    if outputs:
                        print(f"\n节点输出:")
                        for node_id, out in outputs.items():
                            print(f"  节点 {node_id}: {json.dumps(out, ensure_ascii=False)}")
                    break
            else:
                print(f"[{time.strftime('%H:%M:%S')}] 还在队列中...")
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] 轮询异常: {e}")
        time.sleep(2)
    else:
        print("超时未完成")

    # 检查输出文件
    print("\n检查输出目录...")
    files = sorted(OUTPUT_DIR.glob(f"{PREFIX}_*.mp4"))
    if files:
        print("输出文件:")
        for f in files:
            size_kb = f.stat().st_size / 1024
            mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(f.stat().st_mtime))
            print(f"  - {f.name}  ({size_kb:.1f} KB, 修改时间 {mtime})")
    else:
        print(f"未找到 {PREFIX}_*.mp4")


if __name__ == "__main__":
    main()
