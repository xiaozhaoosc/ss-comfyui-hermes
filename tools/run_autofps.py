"""提交自动帧率版工作流并等待完成。"""
import json
import time
import sys
import urllib.request
from pathlib import Path

COMFY = "http://127.0.0.1:8188"
PROMPT_FILE = Path(r"d:\ai_projects\ComfyUI\tools\v2_autofps_api_prompt.json")
OUTPUT_DIR = Path(r"d:\ai_projects\ComfyUI\output")
PREFIX = "faceswap_video_v2_autofps"


def main():
    prompt = json.loads(PROMPT_FILE.read_text(encoding="utf-8"))
    submission = {"prompt": prompt, "client_id": "v2_autofps_agent"}
    data = json.dumps(submission).encode("utf-8")
    req = urllib.request.Request(
        COMFY + "/prompt", data=data, headers={"Content-Type": "application/json"}
    )
    resp = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
    pid = resp["prompt_id"]
    print(f"prompt_id = {pid}")
    print(f"node_errors = {resp.get('node_errors', {})}")
    if "error" in resp:
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        sys.exit(1)

    deadline = time.time() + 600
    last = None
    while time.time() < deadline:
        try:
            h = json.loads(urllib.request.urlopen(COMFY + "/history/" + pid, timeout=30).read().decode("utf-8"))
            if pid in h:
                s = h[pid].get("status", {})
                st = s.get("status_str", "unknown")
                if st != last:
                    print(f"[{time.strftime('%H:%M:%S')}] {st} (completed={s.get('completed')})")
                    last = st
                if st in ("success", "error"):
                    print(f"\n执行结束: {st}")
                    outs = h[pid].get("outputs", {})
                    if outs:
                        for nid, o in outs.items():
                            print(f"节点 {nid}: {json.dumps(o, ensure_ascii=False)}")
                    break
            else:
                print(f"[{time.strftime('%H:%M:%S')}] 队列中...")
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] 异常: {e}")
        time.sleep(3)
    else:
        print("超时未完成")
        sys.exit(1)

    files = sorted(OUTPUT_DIR.glob(f"{PREFIX}_*.mp4"))
    print("\n输出文件:")
    for f in files:
        size_kb = f.stat().st_size / 1024
        print(f"  - {f.name}  ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
