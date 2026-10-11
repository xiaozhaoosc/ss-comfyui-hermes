"""
临时验证脚本：把 UI 工作流提交到本地 ComfyUI 执行并等待结果。
仅用于 V2-verify 验证，验证完成后可删除。
"""
import json
import time
import urllib.request
import urllib.error
import sys
from pathlib import Path

COMFY_URL = "http://127.0.0.1:8188"
WORKFLOW_FILE = Path(r"d:\ai_projects\ComfyUI\workflows\faceswap_video_reactor_260805_v2_verify.json")
EXPECTED_OUTPUT_DIR = Path(r"d:\ai_projects\ComfyUI\output")
EXPECTED_PREFIX = "faceswap_video_v2_verify"


def http_post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_get_json(url):
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def convert_ui_to_prompt(ui_workflow):
    """通过 /api/workflow 把 UI 格式转成 API prompt 格式。"""
    url = f"{COMFY_URL}/api/workflow"
    try:
        return http_post_json(url, ui_workflow)
    except urllib.error.HTTPError as e:
        # 某些 ComfyUI 版本不支持该端点，回退到 /prompt 直接吃 UI 格式
        print(f"[warn] /api/workflow HTTP {e.code}, 回退到直接提交 UI 格式")
        return ui_workflow


def submit_prompt(prompt_payload):
    """提交 prompt，返回 prompt_id。"""
    url = f"{COMFY_URL}/prompt"
    resp = http_post_json(url, prompt_payload)
    if "prompt_id" not in resp:
        raise RuntimeError(f"提交失败: {resp}")
    return resp["prompt_id"]


def wait_for_completion(prompt_id, timeout_sec=300):
    """轮询 /history 直到任务完成或超时。"""
    url = f"{COMFY_URL}/history/{prompt_id}"
    deadline = time.time() + timeout_sec
    last_status = None
    while time.time() < deadline:
        try:
            history = http_get_json(url)
            if prompt_id in history:
                entry = history[prompt_id]
                status = entry.get("status", {})
                completed = status.get("completed", False)
                status_str = status.get("status_str", "unknown")
                if status_str in ("error", "failed"):
                    return False, status, entry
                if completed or status_str == "success":
                    return True, status, entry
                # 仍在执行
                if status_str != last_status:
                    print(f"[info] 状态: {status_str}")
                    last_status = status_str
            else:
                print("[info] 排队中...")
        except Exception as e:
            print(f"[warn] 轮询异常: {e}")
        time.sleep(2)
    return False, {"status_str": "timeout", "messages": []}, {}


def check_output():
    """检查输出目录里是否有 v2_verify 前缀的新文件。"""
    files = sorted(EXPECTED_OUTPUT_DIR.glob(f"{EXPECTED_PREFIX}_*.mp4"))
    return files


def main():
    print(f"[1/5] 读取工作流: {WORKFLOW_FILE}")
    ui = json.loads(WORKFLOW_FILE.read_text(encoding="utf-8"))

    print("[2/5] 转换为 API prompt 格式...")
    prompt_payload = convert_ui_to_prompt(ui)
    # /api/workflow 返回 {prompt: ..., output: ...}, /prompt 接受 {prompt: ...}
    if isinstance(prompt_payload, dict) and "prompt" in prompt_payload:
        prompt_data = prompt_payload["prompt"]
    else:
        prompt_data = prompt_payload
    submission = {"prompt": prompt_data, "client_id": "v2_verify_agent"}

    print("[3/5] 提交到 ComfyUI 执行...")
    prompt_id = submit_prompt(submission)
    print(f"      prompt_id = {prompt_id}")

    print("[4/5] 等待执行完成（最多 5 分钟）...")
    ok, status, entry = wait_for_completion(prompt_id, timeout_sec=300)
    print(f"      结果: ok={ok}, status={status.get('status_str')}")

    # 打印执行消息
    messages = status.get("messages", [])
    if messages:
        print("      执行消息:")
        for m in messages:
            print(f"        - {m}")

    if not ok:
        # 尝试拉取节点错误
        for m in messages:
            if isinstance(m, list) and len(m) >= 2 and m[0] == "execution_error":
                print(f"[error] 节点执行错误: {m[1]}")
        sys.exit(1)

    print("[5/5] 检查输出文件...")
    out_files = check_output()
    if not out_files:
        print(f"[warn] 没在 {EXPECTED_OUTPUT_DIR} 找到 {EXPECTED_PREFIX}_*.mp4")
        sys.exit(2)
    print("      输出文件:")
    for f in out_files:
        size_kb = f.stat().st_size / 1024
        print(f"        - {f.name}  ({size_kb:.1f} KB)")
    print("\n[done] 验证通过，可在 ComfyUI 中加载工作流查看预览")


if __name__ == "__main__":
    main()
