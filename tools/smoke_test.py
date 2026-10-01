# ComfyUI 冒烟测试: 提交工作流并轮询结果
# 用法: python tools/smoke_test.py <workflow.json> [timeout_sec=300]
import json
import sys
import time
import urllib.request
import urllib.error

SERVER = "http://127.0.0.1:8188"


def submit(wf_path):
    wf = json.load(open(wf_path, encoding="utf-8"))
    payload = json.dumps({"prompt": wf["prompt"], "client_id": wf["client_id"]}).encode("utf-8")
    req = urllib.request.Request(f"{SERVER}/prompt", data=payload, headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode("utf-8"))
        return data.get("prompt_id"), None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return None, f"HTTP {e.code}: {body}"
    except Exception as e:
        return None, str(e)


def poll(prompt_id, timeout=300):
    start = time.time()
    last_status = None
    while time.time() - start < timeout:
        try:
            resp = urllib.request.urlopen(f"{SERVER}/history/{prompt_id}", timeout=10)
            data = json.loads(resp.read().decode("utf-8"))
            if prompt_id in data:
                outputs = data[prompt_id].get("outputs", {})
                status = data[prompt_id].get("status", {})
                if status.get("completed"):
                    return "success", outputs
                if status.get("status_str") == "error":
                    return "error", status
                return "unknown", outputs
        except Exception:
            pass
        # check queue
        try:
            resp = urllib.request.urlopen(f"{SERVER}/queue", timeout=5)
            q = json.loads(resp.read().decode("utf-8"))
            running = q.get("queue_running", [])
            pending = q.get("queue_pending", [])
            if not running and not pending:
                # nothing in queue, check history again
                resp = urllib.request.urlopen(f"{SERVER}/history/{prompt_id}", timeout=10)
                data = json.loads(resp.read().decode("utf-8"))
                if prompt_id in data:
                    outputs = data[prompt_id].get("outputs", {})
                    status = data[prompt_id].get("status", {})
                    if status.get("completed"):
                        return "success", outputs
                    return "finished_no_status", outputs
                return "lost", {}
        except Exception:
            pass
        time.sleep(3)
    return "timeout", {}


def main():
    wf_path = sys.argv[1]
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    name = wf_path.split("\\")[-1]
    print(f"[submit] {name} (timeout {timeout}s)")

    # validate input images exist
    wf = json.load(open(wf_path, encoding="utf-8"))
    for nid, node in wf["prompt"].items():
        if not isinstance(node, dict):
            continue
        if node.get("class_type") == "LoadImage":
            img = node["inputs"].get("image", "")
            print(f"  LoadImage[{nid}]: {img}")

    prompt_id, err = submit(wf_path)
    if err:
        print(f"[FAIL] {name}: {err}")
        sys.exit(1)

    print(f"  prompt_id: {prompt_id}")
    print(f"  polling...", end="", flush=True)

    result, outputs = poll(prompt_id, timeout=timeout)
    print(f" {result}")

    if result == "success":
        for nid, out in outputs.items():
            if "images" in out:
                for img in out["images"]:
                    print(f"  [output] {img.get('subfolder','')}/{img.get('filename','')} ({img.get('type','')})")
            if "gifs" in out:
                for g in out["gifs"]:
                    print(f"  [output] {g.get('subfolder','')}/{g.get('filename','')} ({g.get('format','')})")
        print(f"[OK] {name}")
    else:
        print(f"[FAIL] {name}: {result}")
        if outputs:
            print(f"  details: {json.dumps(outputs, indent=2)[:500]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
