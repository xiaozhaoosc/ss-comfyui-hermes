import json
import urllib.request
import urllib.parse
import time
import sys

COMFYUI_URL = "http://127.0.0.1:8188"

# Load the workflow
with open("D:/ai_projects/ComfyUI/tools/idm_vton_faceswap_workflow.json") as f:
    workflow = json.load(f)

# Update the garment image and description
workflow["2"]["inputs"]["image"] = "garment.jpg"
workflow["7"]["inputs"]["garment_description"] = "a white t-shirt"

# Queue the workflow
payload = json.dumps({"prompt": workflow}).encode('utf-8')
req = urllib.request.Request(
    f"{COMFYUI_URL}/prompt",
    data=payload,
    headers={"Content-Type": "application/json"}
)

try:
    resp = urllib.request.urlopen(req)
    result = json.loads(resp.read())
    prompt_id = result.get("prompt_id")
    print(f"Workflow queued. Prompt ID: {prompt_id}")
    
    # Poll for completion
    while True:
        time.sleep(5)
        try:
            history_resp = urllib.request.urlopen(f"{COMFYUI_URL}/history/{prompt_id}")
            history = json.loads(history_resp.read())
            if prompt_id in history:
                status = history[prompt_id].get("status", {})
                if status.get("completed", False) or status.get("status_str") == "success":
                    print("Workflow completed successfully!")
                    outputs = history[prompt_id].get("outputs", {})
                    for node_id, output in outputs.items():
                        if "images" in output:
                            for img in output["images"]:
                                print(f"Output image: {img.get('filename')} (subfolder: {img.get('subfolder', '')})")
                    break
                elif status.get("status_str") == "error":
                    print(f"Workflow failed with error: {status}")
                    messages = history[prompt_id].get("messages", [])
                    for msg in messages:
                        print(f"  Message: {msg}")
                    break
            print("Still processing...")
        except Exception as e:
            print(f"Poll error: {e}")
except Exception as e:
    print(f"Error: {e}")
