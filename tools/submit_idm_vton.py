import json, urllib.request

with open("D:/ai_projects/ComfyUI/tools/idm_vton_faceswap_workflow.json") as f:
    workflow = json.load(f)

prompt = {}
for node_id, node in workflow.items():
    prompt[node_id] = {
        "class_type": node["class_type"],
        "inputs": node["inputs"]
    }

payload = json.dumps({"prompt": prompt}).encode()

req = urllib.request.Request(
    "http://127.0.0.1:8188/prompt",
    data=payload,
    headers={"Content-Type": "application/json"}
)
try:
    resp = urllib.request.urlopen(req, timeout=10)
    result = json.loads(resp.read())
    print(f"Prompt submitted! ID: {result.get('prompt_id', 'unknown')}")
    print(json.dumps(result, indent=2))
except Exception as e:
    print(f"Error: {e}")
    if hasattr(e, 'read'):
        print(e.read().decode())
