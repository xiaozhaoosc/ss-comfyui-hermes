#!/usr/bin/env python3
"""Monitor ComfyUI face swap progress every 60 seconds"""
import json, urllib.request, time, os, glob

COMFYUI_URL = "http://127.0.0.1:8188"
OUR_IDS = ["9183a510", "1d75dfe4", "0565fb67"]
OUTPUT_DIR = r"D:\ai_projects\ComfyUI\output"

start = time.time()
while True:
    elapsed = int(time.time() - start)
    try:
        # Queue status
        q = json.loads(urllib.request.urlopen(f"{COMFYUI_URL}/queue", timeout=5).read())
        running = len(q.get("queue_running", []))
        pending = len(q.get("queue_pending", []))
        
        # History
        h = json.loads(urllib.request.urlopen(f"{COMFYUI_URL}/history", timeout=5).read())
        completed = len(h)
        
        # Output files
        outputs = [f for f in os.listdir(OUTPUT_DIR) if "qdb" in f.lower() and f.endswith(".mp4")]
        
        print(f"[{elapsed}s] Queue: {running}R/{pending}P | History: {completed} | Output: {outputs}", flush=True)
        
        if completed >= 3 and running == 0:
            print("ALL DONE!", flush=True)
            # Print final output info
            for f in outputs:
                fp = os.path.join(OUTPUT_DIR, f)
                size = os.path.getsize(fp) / 1e6
                print(f"  {f}: {size:.1f}MB", flush=True)
            break
    except Exception as e:
        print(f"[{elapsed}s] Error: {e}", flush=True)
    
    time.sleep(60)
