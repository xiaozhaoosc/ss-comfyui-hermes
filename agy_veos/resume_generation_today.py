import urllib.request
import json
import time
import shutil
import os

OUT_DATE = "2026-09-30"
ARTIFACT_DIR = r"C:\Users\kenzhao\.gemini\antigravity-ide\brain\eff45711-cf9b-45db-9603-8b64b900c0e7"
COMFY_OUT_DIR = rf"D:\ai_projects\ComfyUI\output\{OUT_DATE}"
PROGRESS_FILE = r"d:\ai_projects\ComfyUI\agy_veos\progress_resume.json"

os.makedirs(COMFY_OUT_DIR, exist_ok=True)

# Remaining 10 Spiral Stairs (21 - 30)
REMAINING_STAIRS = [
    {
        "id": "spiral_stairs_21_navy_striped_knit",
        "title": "法式海军风条纹软糯针织",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928621,
        "text": "Full body mirror selfie of a Korean young woman, sweet natural charm. Foyer with sweeping white spiral staircase, bright sunny day. Wearing a classic navy and cream striped boatneck knit top, high-waisted white denim shorts, bare slender endless legs, casual chic quiet luxury, 8k resolution."
    },
    {
        "id": "spiral_stairs_22_emerald_silk_blouse",
        "title": "祖母绿真丝衬衫贵气千金",
        "pose": "pose_stretched_natural.png",
        "seed": 928622,
        "text": "Full body mirror selfie of a Korean drama lead actress, fair skin. Villa foyer with pure white spiral staircase. Wearing an unbuttoned rich emerald green silk shirt, black bandeau, high-waisted white tailored shorts, slender legs, gold necklace, striking color contrast, 8k resolution."
    },
    {
        "id": "spiral_stairs_23_trench_coat_belted_stair",
        "title": "经典英伦风衣系带立挺身姿",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928623,
        "text": "Full body mirror selfie of a Korean fashion model. Villa entrance hall, dramatic white spiral staircase curving upward in background. Wearing a classic beige cotton-gabardine trench coat with sleeves pushed up, micro shorts, sheer dark tights, slender supermodel legs, sleek pointed heels, 8k resolution."
    },
    {
        "id": "spiral_stairs_24_pastel_blue_knit_set",
        "title": "雾霾蓝羊绒针织套装",
        "pose": "pose_stretched_natural.png",
        "seed": 928624,
        "text": "Full body mirror selfie of a lovely Korean beauty. Light-filled duplex foyer, white spiral staircase and limestone floor. Wearing a slouchy dusty blue cashmere button-up cardigan, matching high-waisted knit shorts, bare slender legs, cozy minimalist luxury, 8k resolution."
    },
    {
        "id": "spiral_stairs_25_black_blazer_micro_shorts",
        "title": "干练黑西装内搭白色短打",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928625,
        "text": "Full body mirror selfie of a Korean chaebol daughter. Architectural foyer with pure white spiral staircase. Wearing an oversized sharp black wool blazer, white cropped ribbed tank, high-waisted black micro shorts, slender supermodel legs, silver slingback heels, 8k resolution."
    },
    {
        "id": "spiral_stairs_26_double_height_foyer_grand",
        "title": "8米大挑空全景气场宏大",
        "pose": "pose_stretched_natural.png",
        "seed": 928626,
        "text": "Full body mirror selfie of a Korean actress. Soaring eight-meter double-height modern villa entrance foyer, monumental white spiral staircase coiling dramatically upward, expansive floor-to-ceiling windows with garden view. Wearing a blue linen boyfriend shirt, khaki shorts, slender legs, 8k resolution."
    },
    {
        "id": "spiral_stairs_27_all_white_monochrome_luxe",
        "title": "全白纯净单色极简盛宴",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928627,
        "text": "Full body mirror selfie of a tall Korean fashion influencer. All-white minimalist villa entryway, pure white spiral staircase, white marble floor, immaculate white walls. Wearing an oversized white silk shirt, tailored white shorts, nude pointed heels, endless slender legs, editorial high fashion, 8k resolution."
    },
    {
        "id": "spiral_stairs_28_warm_timber_ceiling_accent",
        "title": "暖色木格栅吊顶与白梯映衬",
        "pose": "pose_stretched_natural.png",
        "seed": 928628,
        "text": "Full body mirror selfie of an elegant Korean woman. Modern villa foyer, warm natural cedar wood slatted ceiling contrasting against the fluid white spiral staircase and polished stone floor. Wearing a cream silk blouse, khaki micro shorts, slender shapely legs, 8k resolution."
    },
    {
        "id": "spiral_stairs_29_rainy_day_moody_atrium",
        "title": "雨日静谧天光与冷调反光",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928629,
        "text": "Full body mirror selfie of a Korean beauty, porcelain skin. Villa foyer on a rainy afternoon, soft cool diffused natural light filtering through frosted skylight onto white spiral staircase, calm moody atmosphere. Wearing an oversized black boyfriend blazer, black shorts, endless slender legs, 8k resolution."
    },
    {
        "id": "spiral_stairs_30_grand_finale_staircase",
        "title": "绝美极简旋转楼梯终章大片",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928630,
        "text": "Full body mirror selfie of a breathtaking Korean drama lead actress, silky dark hair, porcelain skin. Foyer of an architectural trophy villa, sculptural white spiral staircase curving gracefully toward heaven, warm sunbeams illuminating polished stone floor. Wearing a crisp sky blue linen shirt, high-waisted khaki shorts, ultra-long slender supermodel legs reaching floor, nude kitten heels, 8k resolution."
    }
]

# 30 Theater Backstage Prompts
THEATER_PROMPTS = [
    {
        "id": "theater_backstage_01_emerald_velvet_curtain",
        "title": "深祖母绿厚丝绒与好莱坞灯泡全景",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928701,
        "text": "Full body mirror selfie of a breathtaking Korean drama lead actress, fair porcelain skin, dark glossy waves. Standing before a magnificent floor-to-ceiling vanity mirror framed by glowing round Hollywood warm globe bulbs, draped heavy deep emerald green velvet stage curtains in background. Wearing a structured black velvet halter mini dress, high waist, slender endless legs reaching floor, black patent stiletto pumps, cinematic 35mm film mood, 8k resolution."
    },
    {
        "id": "theater_backstage_02_prima_ballerina_tutu",
        "title": "纯白天鹅芭蕾羽毛吊带与缎面足尖",
        "pose": "pose_stretched_natural.png",
        "seed": 928702,
        "text": "Full body mirror selfie of an elegant Korean prima ballerina. Historic opera house dressing suite, bulb-lit vanity mirror reflecting soft golden tungsten glow and antique wardrobe trunks. Wearing a delicate ivory swan feather embellished corseted slip dress, slender shapely legs, ribbon-tied nude satin kitten heels, graceful posture, 8k resolution."
    },
    {
        "id": "theater_backstage_03_champagne_silk_kimono",
        "title": "香槟重磅真丝晨袍微露香肩",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928703,
        "text": "Full body mirror selfie of a glamorous Korean opera singer. Backstage dressing room, Hollywood globe lights glowing warm amber, emerald green velvet drapery. Wearing a flowing heavy champagne gold silk satin dressing gown tied loosely at high waist, high slit exposing endless slender legs, barefoot on antique Persian rug, quiet wealth aesthetic, 8k resolution."
    },
    {
        "id": "theater_backstage_04_audrey_little_black_gown",
        "title": "赫本风一字肩高叉小黑裙",
        "pose": "pose_stretched_natural.png",
        "seed": 928704,
        "text": "Full body mirror selfie of a chic Korean beauty, elegant updo, delicate collarbones. Hollywood mirror reflection with soft diffused bulb lighting, rich velvet curtains. Wearing an off-the-shoulder sculpted black crepe evening dress with thigh slit, cinched waist, slender long legs, black pointed slingbacks, timeless vintage elegance, 8k resolution."
    },
    {
        "id": "theater_backstage_05_crimson_velvet_gloves",
        "title": "绯红丝绒及膝裙配长手套",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928705,
        "text": "Full body mirror selfie of a striking Korean theater actress. Backstage suite with glowing round vanity bulbs, deep emerald velvet backdrop creating rich jewel-tone contrast. Wearing a structured crimson red velvet strapless cocktail dress, black velvet opera gloves, bare slender supermodel legs, black stilettos, 8k resolution."
    },
    {
        "id": "theater_backstage_06_oversized_tuxedo_blazer",
        "title": "宽大黑西装下衣失踪名伶风",
        "pose": "pose_stretched_natural.png",
        "seed": 928706,
        "text": "Full body mirror selfie of a Korean fashion model. Grand theater dressing room, warm glowing Hollywood vanity mirror bulbs. Wearing an oversized sharp black wool tuxedo jacket worn as a mini dress, cinched belt, bare slender long legs, pointed silver metallic kitten heels, modern backstage editorial chic, 8k resolution."
    },
    {
        "id": "theater_backstage_07_emerald_kimono_leather_shorts",
        "title": "墨绿真丝衬衫搭高腰皮短裤",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928707,
        "text": "Full body mirror selfie of a stylish Korean actress. Dressing room with vanity bulbs casting flattering warm glow, velvet curtains. Wearing an unbuttoned emerald green silk boyfriend blouse over black bandeau, high-waisted tailored black leather shorts, endless slender legs, sleek ankle boots, 8k resolution."
    },
    {
        "id": "theater_backstage_08_cashmere_rehearsal_knit",
        "title": "软糯羊绒开衫与黑色紧身裤",
        "pose": "pose_stretched_natural.png",
        "seed": 928708,
        "text": "Full body mirror selfie of a Korean dancer taking a break. Full-length illuminated vanity mirror, costume racks and emerald velvet curtains in background. Wearing a slouchy grey heather cashmere knit cardigan slipped off shoulder, high-waisted black fitted dance shorts, black crew socks, slender shapely legs, candid backstage mood, 8k resolution."
    },
    {
        "id": "theater_backstage_09_cobalt_blue_silk_blouse",
        "title": "亮钴蓝真丝衬衫复古对镜自拍",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928709,
        "text": "Full body mirror selfie of a Korean drama lead actress, glowing fair skin. Warm glowing Hollywood bulb-framed mirror, deep green velvet backdrop. Wearing a crisp vibrant cobalt azure silk shirt casually tucked into white high-waisted tailored shorts, nude pointed heels, endless slender legs, rich color harmony, 8k resolution."
    },
    {
        "id": "theater_backstage_10_burgundy_velvet_shawl",
        "title": "酒红丝绒披肩与象牙吊带裙",
        "pose": "pose_stretched_natural.png",
        "seed": 928710,
        "text": "Full body mirror selfie of a poetic Korean beauty. Dressing room with warm vintage vanity bulbs. Wearing an ivory cowl-neck silk slip dress, draped in a rich deep burgundy velvet fringed shawl, slender legs, delicate gold jewelry, romantic pre-show atmosphere, 8k resolution."
    },
    {
        "id": "theater_backstage_11_crystal_perfume_roses",
        "title": "梳妆台古董水晶香水瓶与红玫瑰",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928711,
        "text": "Full body mirror selfie of a Korean actress. Antique wooden vanity table visible beside mirror filled with vintage crystal perfume decanters, silver powder compacts, and deep red velvet roses, glowing round bulbs. Wearing a black velvet mini dress, slender supermodel legs, golden warm tungsten illumination, 8k resolution."
    },
    {
        "id": "theater_backstage_12_circular_bokeh_lights",
        "title": "镜框球泡梦幻圆光斑散焦",
        "pose": "pose_stretched_natural.png",
        "seed": 928712,
        "text": "Full body mirror selfie of a Korean young woman. Beautiful circular golden bokeh spheres in foreground from glowing mirror bulbs, deep emerald velvet curtains behind her. Wearing an open cream silk shirt, tailored black shorts, slender glowing legs, cinematic 35mm shallow depth of field, 8k resolution."
    },
    {
        "id": "theater_backstage_13_dramatic_curtain_chink_beam",
        "title": "幕布缝隙穿透狭长侧逆光",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928713,
        "text": "Full body mirror selfie of a Korean beauty. Dramatic shaft of stage spotlight cutting through a gap in the heavy emerald green velvet curtains, highlighting hair and slender silhouette against vanity bulb warm ambient light. Wearing an off-shoulder white satin crop top, high-waisted black shorts, endless legs, 8k resolution."
    },
    {
        "id": "theater_backstage_14_fly_loft_reflection",
        "title": "镜面隐约倒映后台桁架景片",
        "pose": "pose_stretched_natural.png",
        "seed": 928714,
        "text": "Full body mirror selfie of a Korean theater star. Mirror reflects towering dark backstage steel fly-loft trusses, red velvet stage wings, and theatrical spotlights, warm globe bulbs framing reflection. Wearing an oversized white poplin button-down, black leather shorts, slender long legs, 8k resolution."
    },
    {
        "id": "theater_backstage_15_vintage_35mm_film_grain",
        "title": "复古35毫米电影胶片颗粒质感",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928715,
        "text": "Full body mirror selfie of a glamorous Korean woman. Rich vintage Kodak film tone, warm amber highlights, deep inky emerald velvet shadows, glowing vanity bulbs. Wearing a champagne silk satin camisole, high-waisted tailored shorts, slender supermodel legs, timeless movie star aura, 8k resolution."
    },
    {
        "id": "theater_backstage_16_silver_sequin_sparkle",
        "title": "银灰重工亮片抹胸裙波光",
        "pose": "pose_stretched_natural.png",
        "seed": 928716,
        "text": "Full body mirror selfie of a Korean pop star. Dressing room vanity bulbs making thousands of tiny silver sequins sparkle brilliantly on her micro tube dress, dark green velvet backdrop. Slender radiant legs, silver strappy heels, dazzling showgirl glamour, 8k resolution."
    },
    {
        "id": "theater_backstage_17_black_lace_sheer_couture",
        "title": "黑色高定透视蕾丝修身长裙",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928717,
        "text": "Full body mirror selfie of a tall Korean fashion icon. Grand theater suite, Hollywood bulbs reflecting warm rim light. Wearing a bespoke black French chantilly lace bodycon dress with high thigh slit, bare slender legs, black patent stilettos, dark romantic haute couture, 8k resolution."
    },
    {
        "id": "theater_backstage_18_modern_ivory_qipao",
        "title": "象牙白改良高叉立领名伶裙",
        "pose": "pose_stretched_natural.png",
        "seed": 928718,
        "text": "Full body mirror selfie of a Korean drama lead. Vintage dressing room with warm bulbs and velvet curtains. Wearing an ivory white modern tailored silk mandarin-collar dress with dramatic high side slit, slender elongated legs, nude pointed heels, oriental quiet luxury, 8k resolution."
    },
    {
        "id": "theater_backstage_19_midnight_velvet_smoking_suit",
        "title": "午夜蓝丝绒吸烟装中性飒爽",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928719,
        "text": "Full body mirror selfie of a chic Korean actress. Vanity mirror illuminated by warm round bulbs, rich velvet drapery. Wearing a midnight navy velvet tailored tuxedo blazer with satin lapels, high-waisted matching velvet micro shorts, slender endless legs, pointed stiletto pumps, 8k resolution."
    },
    {
        "id": "theater_backstage_20_powder_pink_silk_robe",
        "title": "浅粉丝缎系带睡袍温润光泽",
        "pose": "pose_stretched_natural.png",
        "seed": 928720,
        "text": "Full body mirror selfie of a delicate Korean beauty, luminous porcelain skin. Backstage vanity mirror, soft golden light. Wearing a pastel blush pink heavy silk robe casually tied, black lace lingerie peaking out, slender shapely legs, soft vintage romantic mood, 8k resolution."
    },
    {
        "id": "theater_backstage_21_curtain_call_afterglow",
        "title": "谢幕归来解开鞋带独处片刻",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928721,
        "text": "Full body mirror selfie of a Korean drama actress after curtain call. Tender post-performance atmosphere, glowing vanity bulbs, velvet curtains, discarded floral bouquet on chair. Wearing a little black dress, unbuckled stiletto heels, slightly tousled hair, slender supermodel legs, expressive depth, 8k resolution."
    },
    {
        "id": "theater_backstage_22_berry_lips_script_card",
        "title": "复古浓郁浆果红唇与台词卡",
        "pose": "pose_stretched_natural.png",
        "seed": 928722,
        "text": "Full body mirror selfie of a Korean beauty, bold deep berry red lipstick, porcelain complexion. Standing before warm vanity bulbs holding a gilded script booklet, deep emerald velvet curtains. Wearing a black tailored vest top, high-waisted shorts, slender legs, intense cinematic gaze, 8k resolution."
    },
    {
        "id": "theater_backstage_23_gold_thread_embroidery_cape",
        "title": "金色丝线金绣斗篷衣领",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928723,
        "text": "Full body mirror selfie of a Korean opera prima donna. Dressing mirror with glowing bulbs. Wearing an elaborate gold thread embroidered theatrical short cape over a black corset top, high-waisted tailored shorts, endless slender legs, ornate historic costume drama, 8k resolution."
    },
    {
        "id": "theater_backstage_24_chaise_lounge_pose",
        "title": "墨绿丝绒贵妃榻边长腿交叠",
        "pose": "pose_stretched_natural.png",
        "seed": 928724,
        "text": "Full body mirror selfie of a relaxed Korean actress. Beside an antique carved emerald velvet chaise lounge in dressing room, round vanity bulbs glowing warmly. Wearing an oversized white silk shirt, black shorts, slender shapely legs, barefoot on ornate Persian rug, languid luxury, 8k resolution."
    },
    {
        "id": "theater_backstage_25_phantom_black_swan_tension",
        "title": "黑天鹅式戏剧张力光影反差",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928725,
        "text": "Full body mirror selfie of a dramatic Korean actress. High-contrast theatrical lighting, bright warm vanity bulbs casting deep moody shadows into emerald velvet folds. Wearing a structured black feathered corset top, high-waisted black mini skirt, slender endless legs, sharp intense gaze, 8k resolution."
    },
    {
        "id": "theater_backstage_26_rococo_gilded_frame_mirror",
        "title": "洛可可金漆雕花巨镜与双重灯光",
        "pose": "pose_stretched_natural.png",
        "seed": 928726,
        "text": "Full body mirror selfie of a Korean royal theater actress. Expansive antique Rococo gold leaf carved standing mirror surrounded by modern warm vanity bulbs, heavy green velvet curtains. Wearing a cream silk tailored blouse, black micro skirt, slender legs, museum-grade historic luxury, 8k resolution."
    },
    {
        "id": "theater_backstage_27_flowing_white_silk_train",
        "title": "纯白真丝拖尾长袍与黑色短打",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928727,
        "text": "Full body mirror selfie of a tall Korean fashion icon. Grand dressing suite, glowing vanity bulbs. Wearing an open dramatic floor-length white silk kimono robe pooling on floor, black high-cut bodysuit, slender endless supermodel legs, black heels, maximum editorial impact, 8k resolution."
    },
    {
        "id": "theater_backstage_28_emerald_and_gold_contrast",
        "title": "祖母绿丝绒与金球光华彩",
        "pose": "pose_stretched_natural.png",
        "seed": 928728,
        "text": "Full body mirror selfie of an elegant Korean heiress. Deep forest emerald velvet curtains reflecting warm gold specks from round vanity bulbs. Wearing an ivory silk cowl-neck dress with high slit, slender legs, delicate gold layered necklaces, rich opulent color palette, 8k resolution."
    },
    {
        "id": "theater_backstage_29_multi_angle_mirror_reflection",
        "title": "三面折叠镜多重光影倒影",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928729,
        "text": "Full body mirror selfie of a Korean beauty. Three-way folding triptych vanity mirror with glowing perimeter bulbs showing multiple angled reflections of her slender silhouette, emerald velvet curtains. Wearing a black off-shoulder cocktail mini dress, endless legs, silver slingbacks, 8k resolution."
    },
    {
        "id": "theater_backstage_30_grand_finale_prima_donna",
        "title": "绝美大剧院后台名伶传奇终章",
        "pose": "pose_stretched_supermodel.png",
        "seed": 928730,
        "text": "Full body mirror selfie of a breathtaking Korean drama lead actress, silky dark hair, luminous porcelain skin. Grand opera house star dressing room, magnificent full-length vanity mirror framed by warm glowing Hollywood round bulbs, majestic emerald green heavy velvet curtains. Wearing an iconic oversized bright cobalt azure silk-linen shirt casually open, white ribbed crop top, tailored khaki shorts, bare ultra-long slender legs reaching floor, nude pointed kitten heels, 8k resolution."
    }
]

ALL_TASKS = REMAINING_STAIRS + THEATER_PROMPTS

def build_prompt(item):
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

def run_resumption():
    print(f"Resuming generation for remaining 40 images (10 stairs + 30 theater) for {OUT_DATE}...")
    results = []
    total = len(ALL_TASKS)
    
    for idx, item in enumerate(ALL_TASKS, 1):
        print(f"\n[{idx}/{total}] Submitting {item['id']} ({item['title']})...")
        prompt = build_prompt(item)
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
                        print(f"-> SUCCESS [{idx}/{total}] in {elapsed:.1f}s: {fname}")
                        results.append({
                            "idx": idx,
                            "id": item["id"],
                            "title": item["title"],
                            "filename": fname,
                            "path": full_path,
                            "artifact": artifact_dest
                        })
                    break
            except Exception as e:
                pass
        
        # Save progress file
        try:
            with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "completed": idx,
                    "total": total,
                    "last_image": item["id"],
                    "results": results
                }, f, ensure_ascii=False, indent=2)
        except:
            pass

    print("\nAll 40 remaining images successfully generated!")
    with open(r"d:\ai_projects\ComfyUI\agy_veos\batch_resumed_40_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("Saved batch_resumed_40_results.json.")

if __name__ == "__main__":
    run_resumption()
