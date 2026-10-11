# -*- coding: utf-8 -*-
"""
generate_mirror_selfies.py
依次调用 ComfyUI 生成 9 张自拍/镜面自拍图像
"""
import os
import sys
import json
import time
import urllib.request
import urllib.error
import uuid

HOST = "http://127.0.0.1:8188"
WORKFLOW_TEMPLATE = os.path.join(os.path.dirname(__file__), "..", "workflows", "v3", "flux_mirror_selfie_api.json")

PROMPTS = [
    {
        "id": 1,
        "tag": "01_crop_shorts_heels_wooden_floor",
        "prompt": "A young woman taking a mirror selfie indoors, wearing a black crop top and black shorts, showing her slim waist and long legs, with black high heels. The room has a wooden floor and patterned wallpaper, creating a cozy and casual atmosphere, photorealistic, 8k, natural lighting, realistic skin texture, 35mm photograph.",
        "seed": 1001
    },
    {
        "id": 2,
        "tag": "02_crop_shorts_hand_face_bedroom",
        "prompt": "A young woman taking a mirror selfie in a bedroom, wearing a black crop top and black shorts, covering her face with one hand. Her long hair is down. The room has soft lighting and light-patterned walls, with clothes casually placed on the bed, giving a relaxed and youthful vibe, photorealistic, 8k, soft cinematic lighting, highly detailed.",
        "seed": 1002
    },
    {
        "id": 3,
        "tag": "03_black_shorts_purple_phone_cheek",
        "prompt": "A young woman taking a selfie indoors, wearing a black short-sleeve top and black shorts, revealing her waist, with thin-strapped high heels. She has long black hair, holding a purple phone in one hand and touching her cheek with the other. The background features a light-colored door and wall, with an overall warm tone, photorealistic, natural skin texture, 8k.",
        "seed": 1003
    },
    {
        "id": 4,
        "tag": "04_crouching_purple_phone_heeled_sandals",
        "prompt": "A young woman taking a selfie indoors, wearing a black short-sleeve top and black shorts, with black heeled sandals. She is crouching on one knee, holding a purple phone that covers half of her face, with one hand near her neck. The background features a patterned wall and wooden floor, photorealistic, highly detailed, 8k.",
        "seed": 1004
    },
    {
        "id": 5,
        "tag": "05_flare_pants_brown_shoes_desk_bed",
        "prompt": "A young woman taking a mirror selfie in a bedroom, wearing a black short-sleeve top and white flare pants, with brown shoes. She is standing in front of a mirror, holding a phone to take the photo. The background features a bed, a desk, and light brown curtains, presenting a minimalist and cozy daily outfit style, photorealistic, 8k, soft daylight.",
        "seed": 1005
    },
    {
        "id": 6,
        "tag": "06_flare_pants_brown_slippers_cover_face",
        "prompt": "A young woman taking a mirror selfie in a bedroom, wearing a black short-sleeve top and white flare pants, with brown slippers. She has long black hair and is covering her face with the phone. The background shows a bed and a table, with brown curtains, creating a warm and tidy atmosphere, photorealistic, 8k, natural indoor light.",
        "seed": 1006
    },
    {
        "id": 7,
        "tag": "07_ponytail_flare_pants_curtains_books",
        "prompt": "A young woman with a ponytail taking a mirror selfie indoors, wearing a black short-sleeve top and white flare pants, standing near light-colored curtains. The background features a desk with books and a bed, in a simple and soft-toned setting, capturing a daily fashion or life moment, photorealistic, 8k, clean aesthetic.",
        "seed": 1007
    },
    {
        "id": 8,
        "tag": "08_full_length_mirror_white_flare_pants_rug",
        "prompt": "A young woman taking a mirror selfie in a bedroom, wearing a black short-sleeve top and white high-waisted flare pants that reveal her waistline, with light-colored slippers. She stands in front of a full-length mirror, holding a phone to take the photo, her face blocked by the phone. The room has a bed with gray bedding, a white desk with items, and a woven texture rug on the floor, creating a warm and cozy feel, photorealistic, 8k.",
        "seed": 1008
    },
    {
        "id": 9,
        "tag": "09_relaxed_near_curtains_gray_bedding",
        "prompt": "A young woman taking a mirror selfie, wearing a black short-sleeve top and white flare pants, standing naturally and relaxed next to curtains. The room is simply furnished with a bed with gray bedding and a white desk against the wall with stationery on it. The photo has a fresh and natural style with soft, even light and harmonious colors, photorealistic, 8k.",
        "seed": 1009
    }
]

def load_template():
    with open(WORKFLOW_TEMPLATE, "r", encoding="utf-8") as f:
        return json.load(f)

def enqueue(workflow):
    client_id = str(uuid.uuid4())
    data = json.dumps({"prompt": workflow, "client_id": client_id}).encode("utf-8")
    req = urllib.request.Request(f"{HOST}/prompt", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))["prompt_id"]

def wait_for_completion(prompt_id, timeout=600):
    start = time.time()
    last_print = 0
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(f"{HOST}/history/{prompt_id}")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if prompt_id in data:
                    hist = data[prompt_id]
                    outputs = hist.get("outputs", {})
                    images = []
                    for node_id, out in outputs.items():
                        if "images" in out:
                            for img in out["images"]:
                                images.append(img.get("filename") or img.get("subfolder", "") + "/" + img.get("filename", ""))
                    return True, images, time.time() - start
        except Exception as e:
            pass

        now = time.time()
        if now - last_print > 10:
            print(f"  [Waiting] {now - start:.0f}s elapsed...", flush=True)
            last_print = now

        time.sleep(3)
    return False, [], time.time() - start

def main():
    print(f"Starting batch generation of {len(PROMPTS)} mirror selfie images via ComfyUI...")
    base_wf = load_template()
    results = []

    # Optional start/end slice from cli args
    start_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    end_idx = int(sys.argv[2]) if len(sys.argv) > 2 else len(PROMPTS)

    selected_prompts = PROMPTS[start_idx:end_idx]

    for item in selected_prompts:
        item_id = item["id"]
        tag = item["tag"]
        prompt_text = item["prompt"]
        seed = item["seed"]

        print(f"\n==================================================")
        print(f"[{item_id}/{len(PROMPTS)}] Task: {tag}")
        print(f"Prompt: {prompt_text[:80]}...")
        print(f"Seed: {seed}")
        print(f"==================================================")

        # Clone and customize workflow
        wf = json.loads(json.dumps(base_wf))
        wf["5"]["inputs"]["text"] = prompt_text
        wf["10"]["inputs"]["noise_seed"] = seed
        wf["14"]["inputs"]["filename_prefix"] = f"mirror_selfies/{tag}"

        t0 = time.time()
        try:
            pid = enqueue(wf)
            print(f"Queued with prompt_id: {pid}")
            success, images, dur = wait_for_completion(pid)
            if success:
                print(f"[SUCCESS] Finished in {dur:.1f}s! Images: {images}")
                results.append({"id": item_id, "tag": tag, "images": images, "duration": dur, "status": "success"})
            else:
                print(f"[FAILED] Timeout or error after {dur:.1f}s")
                results.append({"id": item_id, "tag": tag, "images": [], "duration": dur, "status": "timeout"})
        except Exception as e:
            print(f"[ERROR] Failed to queue or process task: {e}")
            results.append({"id": item_id, "tag": tag, "images": [], "duration": 0, "status": f"error: {e}"})

    print("\n\n================ Summary ================")
    for r in results:
        print(f"Item #{r['id']} ({r['tag']}): {r['status']} -> {r.get('images', [])} ({r.get('duration', 0):.1f}s)")

if __name__ == "__main__":
    main()
