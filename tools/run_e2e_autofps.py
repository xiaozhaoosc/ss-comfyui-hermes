"""端到端：从 UI 工作流文件 → API prompt → 提交执行 → 验证输出。"""
import json
import time
import sys
import urllib.request
from pathlib import Path

COMFY = "http://127.0.0.1:8188"
WORKFLOW_FILE = Path(r"d:\ai_projects\ComfyUI\workflows\faceswap_video_reactor_260805_v2_verify.json")
OUTPUT_DIR = Path(r"d:\ai_projects\ComfyUI\output")
PREFIX = "faceswap_video_v2_verify"

sys.path.insert(0, r"d:\ai_projects\ComfyUI\tools")
from ui_to_prompt import convert_ui_to_prompt


def http_post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_get_json(url):
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    print(f"[1/5] 读取 UI 工作流: {WORKFLOW_FILE.name}")
    ui = json.loads(WORKFLOW_FILE.read_text(encoding="utf-8"))

    print("[2/5] 转换为 API prompt...")
    prompt = convert_ui_to_prompt(ui)
    # 关键校验
    fr = prompt["11"]["inputs"]["frame_rate"]
    assert isinstance(fr, list) and fr == ["14", 5], f"frame_rate 未连到 VHS_VideoInfo: {fr}"
    print(f"      校验通过: frame_rate 连接到 {fr}")

    print("[3/5] 提交到 ComfyUI...")
    resp = http_post_json(COMFY + "/prompt", {"prompt": prompt, "client_id": "e2e_autofps"})
    pid = resp["prompt_id"]
    print(f"      prompt_id = {pid}")

    print("[4/5] 等待执行...")
    deadline = time.time() + 300
    last = None
    while time.time() < deadline:
        h = http_get_json(COMFY + "/history/" + pid)
        if pid in h:
            s = h[pid].get("status", {})
            st = s.get("status_str", "unknown")
            if st != last:
                print(f"      [{time.strftime('%H:%M:%S')}] {st}")
                last = st
            if st in ("success", "error"):
                print(f"      结果: {st}")
                if st == "error":
                    print(json.dumps(s, ensure_ascii=False, indent=2))
                    sys.exit(1)
                outs = h[pid].get("outputs", {})
                for nid, o in outs.items():
                    print(f"      节点 {nid}: {json.dumps(o, ensure_ascii=False)}")
                break
        time.sleep(3)
    else:
        print("超时")
        sys.exit(1)

    print("[5/5] 检查输出...")
    # 用修改时间过滤出新文件
    files = sorted(OUTPUT_DIR.glob(f"{PREFIX}_*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        print("      无输出文件")
        sys.exit(1)
    latest = files[0]
    size_kb = latest.stat().st_size / 1024
    mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(latest.stat().st_mtime))
    print(f"      最新输出: {latest.name} ({size_kb:.1f} KB, {mtime})")
    print("\n[done] 端到端验证通过")


if __name__ == "__main__":
    main()
