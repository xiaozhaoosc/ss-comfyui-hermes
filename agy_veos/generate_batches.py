import urllib.request
import json
import time
import shutil
import os

OUT_DATE = "2026-09-28"
ARTIFACT_DIR = r"C:\Users\kenzhao\.gemini\antigravity-ide\brain\eff45711-cf9b-45db-9603-8b64b900c0e7"
COMFY_OUT_DIR = rf"D:\ai_projects\ComfyUI\output\{OUT_DATE}"

os.makedirs(COMFY_OUT_DIR, exist_ok=True)

# 10 Outfits
OUTFITS = [
    {
        "id": "outfit_01_quiet_luxury_blazer",
        "title": "老钱风静奢廓形西装套裙",
        "pose": "pose_stretched_natural.png",
        "seed": 928401,
        "text": "Full body mirror selfie of a stunning Korean drama lead actress, fair luminous skin, silky dark hair. Wearing an oversized oatmeal grey tailored wool blazer over a black silk bandeau top, high-waisted pleated micro skirt, slender long legs, strappy kitten heels. Minimalist luxury dressing room, candid reflection photo, 8k resolution, cinematic soft lighting."
    },
    {
        "id": "outfit_02_silk_slip_dress",
        "title": "纯欲法式香槟真丝吊带裙",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928402,
        "text": "Full body mirror selfie of an elegant Korean young woman, glowing porcelain skin, wavy brunette hair. Wearing a champagne ivory silk satin slip camisole dress with a high side thigh slit, slender endless legs, nude pointed stilettos. Luxurious bedroom mirror reflection, warm golden daylight, quiet luxury aesthetic, 8k resolution."
    },
    {
        "id": "outfit_03_tennis_athleisure",
        "title": "复古网球老钱运动风",
        "pose": "pose_stretched_natural.png",
        "seed": 928403,
        "text": "Full body mirror selfie of a chic Korean young woman, radiant fair skin, high ponytail. Wearing a retro forest green and cream striped knit polo crop top, high-waisted white pleated tennis mini skirt, white crew socks, vintage designer sneakers, slender long legs. Bright modern apartment dressing mirror, clean sunlight, 8k resolution."
    },
    {
        "id": "outfit_04_retro_denim_flare",
        "title": "美式复古长腿喇叭牛仔裤",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928404,
        "text": "Full body mirror selfie of a tall slender Korean fashion influencer. Wearing a fitted square-neck white ribbed crop top, ultra-high-waisted floor-length flare denim jeans, legs looking impossibly long and lean, pointed-toe boots under hem. Sunlit minimalist corridor mirror, candid chic look, 8k resolution."
    },
    {
        "id": "outfit_05_chaebol_tweed",
        "title": "财阀千金小香风粗花呢套装",
        "pose": "pose_stretched_natural.png",
        "seed": 928405,
        "text": "Full body mirror selfie of a rich Korean drama chaebol heiress. Wearing a pastel cream textured tweed cropped collarless jacket, matching high-waisted A-line tweed mini skirt, bare slender legs, black pointed-toe Mary Jane kitten heels. Elegant boutique suite mirror, high-end refined aesthetic, 8k resolution."
    },
    {
        "id": "outfit_06_urban_cargo_chic",
        "title": "松弛感工装街头露腰风",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928406,
        "text": "Full body mirror selfie of a stylish Korean young woman. Wearing a black ribbed racerback halter crop top showing toned waistline, low-slung tailored wide-leg sand khaki cargo trousers, slender elongated silhouette, chunky designer sole sneakers. Industrial concrete studio mirror, edgy luxury fashion look, 8k resolution."
    },
    {
        "id": "outfit_07_boyfriend_white_shirt",
        "title": "经典男友风纯白府绸衬衫",
        "pose": "pose_stretched_natural.png",
        "seed": 928407,
        "text": "Full body mirror selfie of a Korean beauty, porcelain skin, tousled dark hair. Wearing an oversized crisp white poplin button-down shirt unbuttoned casually, tucked into vintage blue high-waisted denim cutoffs, bare slender legs, silver pendant necklace. Soft morning bedroom sunlight mirror reflection, effortless chic, 8k resolution."
    },
    {
        "id": "outfit_08_audrey_little_black_dress",
        "title": "赫本风一字肩紧身小黑裙",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928408,
        "text": "Full body mirror selfie of a glamorous Korean actress, delicate collarbones, elegant updo. Wearing a structured off-the-shoulder black crepe mini dress, cinched high waist, bare slender endless legs, black patent pointed-toe stilettos. Luxurious marble bathroom mirror, dramatic moody interior lighting, 8k resolution."
    },
    {
        "id": "outfit_09_autumn_trench_leather",
        "title": "早秋长款风衣配高腰皮短裤",
        "pose": "pose_stretched_natural.png",
        "seed": 928409,
        "text": "Full body mirror selfie of a fashionable Korean woman. Wearing a flowing honey beige double-breasted long trench coat worn open, fitted black crewneck top, high-waisted black tailored leather shorts, sheer dark tights, slender legs, sleek ankle boots. Modern boutique hotel hallway mirror, autumn editorial look, 8k resolution."
    },
    {
        "id": "outfit_10_cashmere_cozy_knit",
        "title": "软糯羊绒开衫温感针织短裤",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928410,
        "text": "Full body mirror selfie of a Korean young woman, sweet natural smile, loose bun. Wearing a slouchy oatmeal cashmere knit cardigan slightly off-shoulder, matching cream high-waisted knit lounge shorts, bare slender long legs, fluffy shearling slides. Cozy bright sunlit scandi bedroom mirror, soft aesthetic, 8k resolution."
    }
]

# 10 Scenes
SCENES = [
    {
        "id": "scene_01_penthouse_sunset",
        "title": "顶层豪宅全景落地窗夕阳",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928411,
        "text": "Full body mirror selfie of a Korean drama lead actress, slender long legs. Standing before an expansive floor-to-ceiling mirror in a luxury high-rise penthouse, panoramic backdrop of glowing orange sunset skyline and Han river, warm rim light on silky hair, wearing a powder blue silk shirt and white high-waisted shorts, 8k resolution."
    },
    {
        "id": "scene_02_luxury_boutique_vip",
        "title": "清潭洞奢侈品旗舰店VIP沙龙",
        "pose": "pose_stretched_natural.png",
        "seed": 928412,
        "text": "Full body mirror selfie of an elegant Korean heiress, slender legs. In a Cheongdam-dong haute couture boutique private VIP fitting room, champagne velvet walls, ornate gilded arched mirror, soft designer track lighting, wearing an azure silk blouse and khaki micro shorts, quiet luxury, 8k resolution."
    },
    {
        "id": "scene_03_modern_art_gallery",
        "title": "极简水泥现代艺术画廊长廊",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928413,
        "text": "Full body mirror selfie of a chic Korean art curator, long slender legs. In a minimalist contemporary art gallery, raw architectural concrete walls, tall mirror leaning on wall, geometric overhead skylight, modern white sculpture reflection, crisp cobalt linen shirt and tailored shorts, 8k resolution."
    },
    {
        "id": "scene_04_french_balcony_apartment",
        "title": "巴黎奥斯曼公寓复古落地镜",
        "pose": "pose_stretched_natural.png",
        "seed": 928414,
        "text": "Full body mirror selfie of a Korean beauty, endless slender legs. In a Parisian Haussmann apartment with herringbone parquet floors, ornate gold leaf standing mirror reflecting open French balcony doors and zinc rooftops, morning diffused light, crisp shirt and shorts, 8k resolution."
    },
    {
        "id": "scene_05_hotel_brass_elevator",
        "title": "五星级奢华酒店黄铜镜面电梯",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928415,
        "text": "Full body mirror selfie of a Korean socialite, ultra slender legs. Inside a luxury boutique hotel polished brass elevator, mirrored geometric art deco panels, warm golden spotlight, reflecting elegant marble inlays, wearing chic resort blue shirt and shorts, 8k resolution."
    },
    {
        "id": "scene_06_tropical_villa_poolside",
        "title": "海岛独栋别墅无边泳池畔",
        "pose": "pose_stretched_natural.png",
        "seed": 928416,
        "text": "Full body mirror selfie of a Korean model on vacation. Master suite of a tropical private cliffside villa, open sliding glass doors overlooking turquoise infinity pool and palm trees, golden hour shimmer, breeze blowing shirt, slender tan legs, 8k resolution."
    },
    {
        "id": "scene_07_seongsu_industrial_cafe",
        "title": "圣水洞工业风设计师概念空间",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928417,
        "text": "Full body mirror selfie of a trendy Korean girl. In a hip Seongsu-dong designer concept studio, exposed warm brick walls, matte black industrial steel beams, minimalist Monstera green shadows, vintage oversized mirror, stylish boyfriend blue shirt and shorts, 8k resolution."
    },
    {
        "id": "scene_08_spiral_staircase_foyer",
        "title": "极简独栋别墅旋转楼梯前厅",
        "pose": "pose_stretched_natural.png",
        "seed": 928418,
        "text": "Full body mirror selfie of a Korean actress, slender tall silhouette. In a modern luxury villa foyer, dramatic curved sculptural white spiral staircase ascending in background, polished light travertine reflection, bright airy natural illumination, 8k resolution."
    },
    {
        "id": "scene_09_luxury_yacht_stateroom",
        "title": "私人游艇海景主卧特大圆镜",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928419,
        "text": "Full body mirror selfie of a Korean beauty at sea. Inside a mega yacht master stateroom, rich polished teak wood walls, round porthole window showing glittering azure Mediterranean sea, golden sunbeams, breezy linen shirt, ultra long legs, 8k resolution."
    },
    {
        "id": "scene_10_grand_theater_backstage",
        "title": "大剧院后台复古好莱坞灯泡化妆间",
        "pose": "pose_stretched_natural.png",
        "seed": 928420,
        "text": "Full body mirror selfie of a Korean prima ballerina, slender graceful legs. In a grand opera house dressing room, large vanity mirror surrounded by warm round Hollywood globe bulbs, deep emerald velvet curtains, romantic cinematic atmosphere, 8k resolution."
    }
]

def build_prompt(item, subfolder_prefix):
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "flux1-dev-fp8.safetensors",
                "weight_dtype": "fp8_e4m3fn"
            }
        },
        "2": {
            "class_type": "DualCLIPLoader",
            "inputs": {
                "clip_name1": "t5xxl_fp8_e4m3fn.safetensors",
                "clip_name2": "clip_l.safetensors",
                "type": "flux"
            }
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "flux-vae-bf16.safetensors"
            }
        },
        "20": {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": "hinaFluxDevAsianMix_v12.safetensors",
                "strength_model": 0.85,
                "strength_clip": 0.85,
                "model": ["1", 0],
                "clip": ["2", 0]
            }
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": item["text"],
                "clip": ["20", 1]
            }
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "short legs, dwarf proportions, stubby legs, disproportionate body, extra limbs, bad hands, deformed feet, blurry, low quality, oversaturated",
                "clip": ["20", 1]
            }
        },
        "10": {
            "class_type": "FluxGuidance",
            "inputs": {
                "guidance": 3.5,
                "conditioning": ["4", 0]
            }
        },
        "11": {
            "class_type": "FluxGuidance",
            "inputs": {
                "guidance": 1.0,
                "conditioning": ["5", 0]
            }
        },
        "30": {
            "class_type": "ControlNetLoader",
            "inputs": {
                "control_net_name": "flux_controlnet_union_pro_2.0.safetensors"
            }
        },
        "31": {
            "class_type": "SetUnionControlNetType",
            "inputs": {
                "control_net": ["30", 0],
                "type": "openpose"
            }
        },
        "32": {
            "class_type": "LoadImage",
            "inputs": {
                "image": item["pose"]
            }
        },
        "33": {
            "class_type": "ControlNetApplyAdvanced",
            "inputs": {
                "positive": ["10", 0],
                "negative": ["11", 0],
                "control_net": ["31", 0],
                "image": ["32", 0],
                "strength": 0.78,
                "start_percent": 0.0,
                "end_percent": 0.85,
                "vae": ["3", 0]
            }
        },
        "6": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {
                "width": 768,
                "height": 1280,
                "batch_size": 1
            }
        },
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "seed": item["seed"],
                "steps": 20,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0,
                "model": ["20", 0],
                "positive": ["33", 0],
                "negative": ["33", 1],
                "latent_image": ["6", 0]
            }
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["7", 0],
                "vae": ["3", 0]
            }
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": f"{OUT_DATE}/{item['id']}",
                "images": ["8", 0]
            }
        }
    }

def run_batch(items, group_name):
    print(f"\n==========================================")
    print(f"Starting {group_name} ({len(items)} images)...")
    print(f"==========================================")
    
    results = []
    for idx, item in enumerate(items, 1):
        print(f"\n[{idx}/{len(items)}] Submitting {item['id']} ({item['title']})...")
        prompt = build_prompt(item, OUT_DATE)
        req = urllib.request.Request(
            'http://127.0.0.1:8188/prompt',
            data=json.dumps({'prompt': prompt}).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        res = urllib.request.urlopen(req)
        prompt_id = json.loads(res.read())['prompt_id']
        print(f"Queued prompt_id: {prompt_id}. Waiting for completion...")
        
        start_t = time.time()
        while True:
            time.sleep(3)
            try:
                h_req = urllib.request.urlopen(f'http://127.0.0.1:8188/history/{prompt_id}')
                history = json.loads(h_req.read())
                if prompt_id in history:
                    elapsed = time.time() - start_t
                    out = history[prompt_id].get('outputs', {})
                    saved_images = out.get('9', {}).get('images', [])
                    if saved_images:
                        fname = saved_images[0]['filename']
                        sub = saved_images[0].get('subfolder', '')
                        full_path = os.path.join(r"D:\ai_projects\ComfyUI\output", sub, fname)
                        artifact_dest = os.path.join(ARTIFACT_DIR, fname)
                        if os.path.exists(full_path):
                            shutil.copy2(full_path, artifact_dest)
                        print(f"-> SUCCESS in {elapsed:.1f}s: {fname}")
                        results.append({
                            "id": item["id"],
                            "title": item["title"],
                            "filename": fname,
                            "path": full_path,
                            "artifact": artifact_dest
                        })
                    else:
                        print(f"-> WARNING: Finished without output image?")
                    break
            except Exception as e:
                pass
    return results

if __name__ == "__main__":
    print("Beginning Generation for 10 Outfits + 10 Scenes...")
    outfit_res = run_batch(OUTFITS, "Group 1: 10 Outfits")
    scene_res = run_batch(SCENES, "Group 2: 10 Scenes")
    print("\nAll 20 images successfully generated!")
    with open(r"d:\ai_projects\ComfyUI\agy_veos\batch_results.json", "w", encoding="utf-8") as f:
        json.dump({"outfits": outfit_res, "scenes": scene_res}, f, ensure_ascii=False, indent=2)
    print("Saved batch_results.json")
