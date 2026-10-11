# -*- coding: utf-8 -*-
"""FLUX 虚拟训练集批量出图：25 组提示词 x2 = 50 张候选训练图
底模 fp8 + hina AsianMix LoRA(0.75) 锚定面容一致性; euler/simple 24步; guidance 3.5; 1024x1024。
输出: output/2026-09-08/asian_lora_dataset/
"""
import json, os, sys, time, urllib.request, uuid

HOST = "http://127.0.0.1:8188"
STEPS = 24
GUIDANCE = 3.5
W, H = 1024, 1024
LORA = "hinaFluxDevAsianMix_v12.safetensors"
LORA_STRENGTH = 0.75

# 命令行参数: 可选指定 unet 模型文件 + 节点类型 + 输出子目录(用于多模型对比)
def parse_args():
    unet = sys.argv[1] if len(sys.argv) > 1 else "flux1-dev-fp8.safetensors"
    node = sys.argv[2] if len(sys.argv) > 2 else "UNETLoader"
    sub = sys.argv[3] if len(sys.argv) > 3 else "asian_lora_dataset"
    return unet, node, sub

UNET, UNET_NODE, SUB = parse_args()
PREFIX = f"2026-09-08/{SUB}"

PROMPTS = [
    ("01_face_neutral_sun",
     "A close-up beauty portrait of a gorgeous 21-year-old East Asian young woman, natural double eyelids, gentle almond-shaped dark brown eyes, soft high bridge nose, delicate jawline, healthy radiant skin with subtle natural texture. Soft neutral daylight illuminating her face from a nearby window, gentle catchlights in her eyes, neutral calm expression, straight dark hair falling softly around her shoulders. Shot on 85mm f/1.8 lens, sharp focus on eyes, soft creamy background blur. photorealistic, high detail, DSLR, skin pores."),
    ("02_face_45_smile",
     "A close-up three-quarter angle portrait of a gorgeous 21-year-old East Asian young woman, looking towards the camera with a gentle warm smile. Natural skin pores, soft cheek flush, parted glossy lips showing slightly visible teeth. Hair styled in a loose low ponytail with wispy bangs framing her face. Studio softbox lighting creating a flattering rim light along her jawline. 105mm macro lens, shallow depth of field. photorealistic, high detail."),
    ("03_face_profile",
     "A refined profile shot of a gorgeous 21-year-old East Asian woman looking to the side, showcasing her elegant jawline and delicate nose bridge. Soft hair strands tucked behind her ear, subtle stud earring. Warm diffused afternoon sunlight glancing across her cheek, highlighting the natural peach fuzz and porcelain skin texture. Minimalist aesthetic, muted warm beige background. photorealistic."),
    ("04_face_wind_candid",
     "An outdoor tight portrait of a gorgeous 21-year-old East Asian woman in a park, breeze gently blowing strands of hair across her cheek. She looks softly into the lens with thoughtful dark brown eyes. Dappled sunlight filtering through autumn leaves, creating soft golden bokeh circles in the background. Natural authentic skin without heavy makeup. photorealistic."),
    ("05_face_morning_bare",
     "A close-up intimate portrait of a gorgeous 21-year-old East Asian young woman in soft morning light, sitting in bed. Bare-face aesthetic, fresh dewy skin, sleepy gentle gaze, relaxed expression. Messy casual dark hair, cozy white cotton duvet visible near the bottom of frame. High dynamic range, soft organic tones. photorealistic."),
    ("06_face_lowangle_film",
     "A low-angle close-up portrait of a gorgeous 21-year-old East Asian woman tilting her head slightly back against a clear blue sky. Direct crisp sunlight carving gentle shadows beneath her chin, natural skin tone, slight wind in her hair. 35mm film photograph aesthetic, subtle grain, vivid natural colors. photorealistic."),
    ("07_face_candid_mood",
     "A close-up portrait capturing a candid moment of a gorgeous 21-year-old East Asian woman laughing softly with hand lightly touching her chin. Genuine eye smile, expressive crinkles at the outer eyes, joyful aura. Soft diffused indoor coffee shop lighting, warm cozy ambience. photorealistic."),
    ("08_half_cafe_sweater",
     "A medium shot of a gorgeous 21-year-old East Asian young woman sitting at a rustic wooden cafe table, wearing an oversized beige cashmere knit sweater. Holding a warm ceramic coffee mug with both hands, steam rising gently. She gazes out the rain-streaked window with a relaxed expression. Ambient warm indoor cafe lights in the background, cinematic bokeh, 50mm f/1.4 lens. photorealistic."),
    ("09_half_white_shirt",
     "A half-body portrait of a gorgeous 21-year-old East Asian woman standing against a clean light grey studio backdrop. She is wearing a relaxed crisp white button-up shirt with rolled-up sleeves. Modern minimalist elegance, confident poised posture, hands tucked in navy trousers pockets. Soft studio dual-light setup. photorealistic."),
    ("10_half_bookstore",
     "A medium portrait of a gorgeous 21-year-old East Asian woman leaning against wooden bookshelves in an old library. Wearing thin gold-rimmed glasses and a dark green cardigan over a white tee. Holding an open vintage hardcover book, eyes cast downward in calm concentration. Warm tungsten lighting from brass library lamps. photorealistic."),
    ("11_half_street_casual",
     "A waist-up street style photo of a gorgeous 21-year-old East Asian woman walking along a modern city sidewalk in Tokyo. Wearing a tailored black leather jacket over a grey hoodie, carrying a minimalist tote bag. Daytime overcast diffuse lighting, modern glass skyscrapers softly blurred in the background, candid motion feel. photorealistic."),
    ("12_half_kitchen",
     "A half-body lifestyle photograph of a gorgeous 21-year-old East Asian woman in a bright modern kitchen, wearing an oversized striped boyfriend shirt. She is reaching for a glass in the upper cabinet, turning her head back toward the camera with a playful smile. Morning sun streaming through the window, clean scandinavian interior design. photorealistic."),
    ("13_half_gallery",
     "A medium shot of a gorgeous 21-year-old East Asian woman standing in a spacious modern art gallery, viewing a large minimalist canvas. She is wearing a sleek sleeveless black turtleneck dress, hair pinned up into an effortless chignon. Architectural spotlighting creating soft chiaroscuro contrast. photorealistic."),
    ("14_half_hoodie_sport",
     "A waist-up portrait of a gorgeous 21-year-old East Asian woman in an athletic grey cropped hoodie, athletic high ponytail. She is resting on a running track bench, drinking from a sports water bottle, glowing slightly with healthy post-workout vitality. Crisp afternoon outdoor light. photorealistic."),
    ("15_half_sakura",
     "A medium shot of a gorgeous 21-year-old East Asian woman standing under blooming pink cherry blossom trees. Wearing a pastel lavender trench coat, one hand gently reaching towards a blossom. Soft diffused pastel tones, dreamy spring atmosphere, petal bokeh in the foreground and background. photorealistic."),
    ("16_half_rain_neon",
     "A medium portrait of a gorgeous 21-year-old East Asian woman holding a clear vinyl umbrella on a rainy city street at night. Neon signs from nearby shops reflect colorful magenta and cyan hues on the wet pavement and umbrella. She wears a beige trench coat, looking forward with reflective, glowing eyes. photorealistic."),
    ("17_half_sofa_lounging",
     "A half-body shot of a gorgeous 21-year-old East Asian woman curled up on a plush cream-colored sofa, hugging a soft throw pillow. Wearing cozy grey lounge wear, barefoot. Reading a tablet, soft warm floor lamp glowing beside the couch, peaceful evening indoor mood. photorealistic."),
    ("18_half_coast_breeze",
     "A waist-up portrait of a gorgeous 21-year-old East Asian woman standing by the seaside railing at sunset. Wearing a lightweight white linen sundress, sun hat held in hand. Ocean waves splashing in the background, warm golden hour sun bathing her face and shoulders with radiant warm tones. photorealistic."),
    ("19_full_crosswalk",
     "A full-body street photography shot of a gorgeous 21-year-old East Asian woman striding across a city pedestrian crosswalk. Wearing wide-leg high-waisted denim jeans, white sneakers, and a cropped bomber jacket. Dynamic walking pose, hair flowing slightly behind her, full figure in frame from head to toe, sunny afternoon urban scene. photorealistic."),
    ("20_full_loft",
     "A full-body fashion lookbook photograph of a gorgeous 21-year-old East Asian woman standing gracefully in a sunlit loft apartment with polished concrete floors. Wearing an emerald green pleated midi skirt and a fitted cream knit top. Relaxed standing posture, natural body proportions, floor-to-ceiling glass windows behind her. photorealistic."),
    ("21_full_picnic",
     "A full-body candid shot of a gorgeous 21-year-old East Asian woman sitting cross-legged on a red gingham picnic blanket in a lush green park. Wearing a floral cotton summer dress. Surrounded by a picnic basket and fruit, leaning forward slightly with a joyful laugh. Sunlight dappled across the lawn, wide angle perspective. photorealistic."),
    ("22_full_beach_sunset",
     "A full-body long shot of a gorgeous 21-year-old East Asian woman walking barefoot along the wet shoreline at twilight. Holding her sandals in one hand, wearing a flowing terracotta maxi dress that catches the ocean breeze. Wet sand reflecting the orange and purple twilight sky, peaceful cinematic composition. photorealistic."),
    ("23_full_steps_editorial",
     "A full-body architectural portrait of a gorgeous 21-year-old East Asian woman sitting casually on wide outdoor stone steps of a contemporary museum. Wearing a navy blue tailored blazer over tailored shorts and black loafers. Stylish urban editorial pose, geometric leading lines in the stone architecture. photorealistic."),
    ("24_atmo_golden_rim",
     "A cinematic medium portrait of a gorgeous 21-year-old East Asian woman turned half-away from the camera, facing the setting sun. Intense warm golden rim lighting outlining her silhouette, hair glowing like spun gold. Rich lens flare curving across the frame, evocative romantic tone, deep filmic shadows. photorealistic."),
    ("25_atmo_candle",
     "A low-key intimate portrait of a gorgeous 21-year-old East Asian woman sitting at a dark wooden dinner table lit solely by candlelight. Warm flickering amber light illuminating one side of her delicate face, leaving the other side in deep soft shadow. High contrast, cinematic noir aesthetic, soft vintage grain. photorealistic."),
]

def unet_inputs(name, node):
    if node == "UNETLoader":
        return {"unet_name": name, "weight_dtype": "default"}
    return {"unet_name": name}

def wf(prompt, seed, fn_prefix):
    return {
        "2": {"class_type": UNET_NODE, "inputs": unet_inputs(UNET, UNET_NODE)},
        "4": {"class_type": "DualCLIPLoader", "inputs": {
            "clip_name1": "t5xxl_fp8_e4m3fn.safetensors",
            "clip_name2": "clip_l.safetensors", "type": "flux"}},
        "3": {"class_type": "LoraLoader", "inputs": {
            "model": ["2", 0], "clip": ["4", 0], "lora_name": LORA,
            "strength_model": LORA_STRENGTH, "strength_clip": LORA_STRENGTH}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["3", 1]}},
        "F": {"class_type": "FluxGuidance", "inputs": {"conditioning": ["6", 0], "guidance": GUIDANCE}},
        "22": {"class_type": "BasicGuider", "inputs": {"model": ["2", 0], "conditioning": ["F", 0]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["10", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": fn_prefix, "images": ["8", 0]}},
        "10": {"class_type": "VAELoader", "inputs": {"vae_name": "flux-vae-bf16.safetensors"}},
        "13": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["25", 0], "guider": ["22", 0], "sampler": ["16", 0],
            "sigmas": ["17", 0], "latent_image": ["27", 0]}},
        "16": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "17": {"class_type": "BasicScheduler", "inputs": {
            "scheduler": "simple", "steps": STEPS, "denoise": 1.0, "model": ["2", 0]}},
        "25": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "27": {"class_type": "EmptySD3LatentImage", "inputs": {
            "width": W, "height": H, "batch_size": 1}},
    }

def submit(w, client_id):
    data = json.dumps({"prompt": w, "client_id": client_id}).encode()
    req = urllib.request.Request(HOST + "/prompt", data=data, headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=20).read())

def main():
    client_id = str(uuid.uuid4())
    jobs = []
    for idx, (name, prompt) in enumerate(PROMPTS):
        for variant in ("a", "b"):
            seed = 1000 + idx * 10 + (0 if variant == "a" else 1)
            fn = f"{PREFIX}/{name}_{variant}"
            r = submit(wf(prompt, seed, fn), client_id)
            pid = r["prompt_id"]
            jobs.append((name, variant, pid))
            print(f"queued {name}_{variant} -> {pid}", flush=True)
            time.sleep(0.35)
    print(f"\nsubmitted {len(jobs)} jobs", flush=True)

    # 收集所有历史里的保存文件名
    done = {pid: False for _, _, pid in jobs}
    failed = {}
    while not all(done.values()):
        try:
            hist = json.loads(urllib.request.urlopen(HOST + "/history", timeout=10).read())
        except Exception as e:
            print("history fetch err:", e, flush=True)
            time.sleep(5); continue
        for pid in list(done):
            if done[pid]:
                continue
            if pid in hist:
                done[pid] = True
                h = hist[pid]
                status = h.get("status", {})
                saved = []
                for nid, node in h.get("outputs", {}).items():
                    for img in node.get("images", []):
                        saved.append(img.get("filename"))
                if status.get("completed") and saved:
                    print(f"OK {pid} files={saved}", flush=True)
                else:
                    failed[pid] = (status.get("status_str"), saved)
                    print(f"FAIL/EMPTY {pid} status={status}", flush=True)
        time.sleep(5)
    print("\n=== DONE ===", flush=True)
    print("total:", len(jobs), "failed:", len(failed), flush=True)

if __name__ == "__main__":
    main()