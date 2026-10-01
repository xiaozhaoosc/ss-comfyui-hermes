#!/usr/bin/env python3
"""
《我的女友是丧尸》v2 批量视频生成脚本
修复: 分辨率翻倍(1280x768→实际640x384), 帧率12fps, 帧数81
"""

import json
import requests
import time
import os
import random
import shutil

COMFYUI_URL = "http://127.0.0.1:8188"
OUTPUT_DIR = r"D:\ai_projects\ComfyUI\output\zombie_girlfriend"
V2_DIR = os.path.join(OUTPUT_DIR, "v2")
TTS_DIR = os.path.join(V2_DIR, "tts")
SCENES_DIR = os.path.join(V2_DIR, "scenes")
FINAL_DIR = os.path.join(V2_DIR, "final")

for d in [V2_DIR, TTS_DIR, SCENES_DIR, FINAL_DIR]:
    os.makedirs(d, exist_ok=True)

# v2: 更详细的角色描述确保一致性
CHARACTER_DESC = "beautiful young East Asian woman zombie, age 20, long straight black hair to waist, very pale white skin, dark circles under eyes, wearing torn dirty pink dress, subtle dark veins on neck, gentle soft expression, slightly vacant eyes"

STYLE_DESC = "cinematic movie still, anamorphic lens, shallow depth of field, film grain, color grading, professional cinematography, 4K quality"

NEGATIVE = "low quality, blurry, distorted, ugly, deformed, extra limbs, bad anatomy, watermark, text, logo, nsfw"

SCENE_PROMPTS = {
    # 第一集：相遇篇
    1: {"title": "丧尸来袭", "prompt": f"{STYLE_DESC}, terrifying zombie horde shambles through destroyed city street at dusk, broken cars shattered glass debris everywhere, dark ominous atmosphere orange sunset light, horror movie style dramatic lighting"},
    2: {"title": "躲藏求生", "prompt": f"{STYLE_DESC}, young East Asian man age 25 with short black hair wearing worn jacket hiding behind overturned bus, holding breath peeking through broken window with wide fearful eyes, zombies wandering background, tense suspenseful dim lighting"},
    3: {"title": "初次相遇", "prompt": f"{STYLE_DESC}, in abandoned supermarket, young East Asian man and {CHARACTER_DESC}, soft beam of light from broken skylight, romantic tension bittersweet moment, warm soft lighting"},
    4: {"title": "决定同行", "prompt": f"{STYLE_DESC}, zombie girl {CHARACTER_DESC} extending hand to young man, movements slightly stiff but gentle, he hesitates then reaches out, close-up of hands almost touching, soft backlight creating silhouette, emotional hopeful moment"},
    5: {"title": "保护时刻", "prompt": f"{STYLE_DESC}, zombie girl {CHARACTER_DESC} stepping in front of young man protectively, spreading arms wide growling at aggressive zombies, dramatic lighting heroic pose showing loyalty, post-apocalyptic urban setting"},

    # 第二集：相处篇
    6: {"title": "一起逛街", "prompt": f"{STYLE_DESC}, zombie girl {CHARACTER_DESC} and human boyfriend walking hand-in-hand through abandoned shopping mall, she wears cute found hat, sweet romantic atmosphere soft natural light from skylights"},
    7: {"title": "学习使用手机", "prompt": f"{STYLE_DESC}, in cozy corner of abandoned building, zombie girl {CHARACTER_DESC} trying to use smartphone clumsily, young man teaches her patiently, warm domestic scene soft candlelight intimate moment"},
    8: {"title": "分享食物", "prompt": f"{STYLE_DESC}, young man offering can of food to zombie girlfriend {CHARACTER_DESC}, she looks curiously tries to eat but struggles, he helps her gently, intimate moment warm candlelight"},
    9: {"title": "夜晚守候", "prompt": f"{STYLE_DESC}, zombie girl {CHARACTER_DESC} sitting by window at night watching over sleeping boyfriend, moonlight illuminates pale face, peaceful romantic atmosphere beautiful moonlight composition"},
    10: {"title": "温馨时刻", "prompt": f"{STYLE_DESC}, couple sitting together by campfire in safe hideout, she rests head on his shoulder looking at stars through broken roof, cozy intimate moment warm firelight mixed with cool moonlight"},

    # 第三集：危机篇
    11: {"title": "丧尸围攻", "prompt": f"{STYLE_DESC}, massive horde of aggressive zombies surrounding safe house clawing at doors and windows, dark threatening atmosphere dramatic shadows, intense action scene horror movie style"},
    12: {"title": "保护反击", "prompt": f"{STYLE_DESC}, zombie girlfriend {CHARACTER_DESC} standing at doorway facing horde alone letting out powerful scream, protects boyfriend with own body, heroic dramatic lighting powerful pose"},
    13: {"title": "受伤时刻", "prompt": f"{STYLE_DESC}, during escape young man scratched by zombie, zombie girl {CHARACTER_DESC} panics with tears bandaging his wound with torn dress, emotional close-up dramatic lighting"},
    14: {"title": "病毒危机", "prompt": f"{STYLE_DESC}, young man falling ill from infection tossing with fever, zombie girl {CHARACTER_DESC} stays by his side wiping forehead with cool cloth, tender emotional scene soft lighting"},
    15: {"title": "找到解药", "prompt": f"{STYLE_DESC}, in abandoned hospital zombie girl {CHARACTER_DESC} finding vial of medicine holding it up to light with hope in eyes, dramatic backlight creates halo effect, moment of hope"},

    # 第四集：重生篇
    16: {"title": "解药生效", "prompt": f"{STYLE_DESC}, young man opening eyes to see zombie girlfriend {CHARACTER_DESC} watching over with tears of joy, soft morning light through broken windows, emotional reunion warm lighting"},
    17: {"title": "互相依偎", "prompt": f"{STYLE_DESC}, couple sitting together holding each other close after ordeal, she leans into him he wraps arms around her, intimate tender moment soft focus beautiful composition"},
    18: {"title": "许下承诺", "prompt": f"{STYLE_DESC}, under cherry blossom tree in abandoned park young man kneeling with ring, zombie girl {CHARACTER_DESC} covers mouth in surprise tears streaming, romantic beautiful scene petals falling"},
    19: {"title": "夕阳婚礼", "prompt": f"{STYLE_DESC}, couple exchanging vows in abandoned church at sunset, golden light through stained glass windows, she wears makeshift wedding dress, beautiful romantic ceremony warm sunset colors"},
    20: {"title": "新世界希望", "prompt": f"{STYLE_DESC}, couple standing together on rooftop at dawn looking over city, sun rises casting golden light over ruins, they hold hands, hopeful beautiful composition epic scale"},
}

# TTS台词（徐州方言风格）
SCENE_LINES = {
    1: {"speaker": "male", "text": "我地个娘来！这丧尸咋嫩多！快跑快跑！"},
    2: {"speaker": "male", "text": "嘘...别出声...千万别出声...老天爷保佑..."},
    3: {"speaker": "male", "text": "恁...恁别过来啊！俺...俺身上没肉！诶？恁咋不动了？"},
    4: {"speaker": "female", "text": "(疑惑地歪头)...手...手..."},
    5: {"speaker": "female", "text": "(低吼保护)...不...不准...碰他！"},
    6: {"speaker": "male", "text": "哈哈，恁看这帽子中不中？戴恁头上真好看！"},
    7: {"speaker": "male", "text": "这个叫手机，恁这样按...诶对了对了！恁学嘞还不赖来！"},
    8: {"speaker": "male", "text": "饿了吧？来，尝尝这个...诶恁慢点吃，没人跟恁抢！"},
    9: {"speaker": "female", "text": "(轻声)...守...守护你..."},
    10: {"speaker": "male", "text": "恁看那星星，跟恁眼睛一样亮...咱俩这样也怪好嘞。"},
    11: {"speaker": "male", "text": "不好！门要顶不住了！恁快从后门跑！"},
    12: {"speaker": "female", "text": "(怒吼)...不准！碰！他！"},
    13: {"speaker": "male", "text": "没事儿没事儿...就蹭破点皮...恁别哭啊..."},
    14: {"speaker": "female", "text": "(焦急)...不...不要...离开..."},
    15: {"speaker": "female", "text": "(惊喜)...药！找到了！"},
    16: {"speaker": "male", "text": "恁...恁是...我的丧尸女孩？天呐...我好了？"},
    17: {"speaker": "female", "text": "(温柔)...在...一直...在..."},
    18: {"speaker": "male", "text": "俺知道俺配不上恁...但是俺想跟恁过一辈子！恁愿意不？"},
    19: {"speaker": "male", "text": "不管世界变成啥样，俺都要跟恁在一起。这是俺对恁嘞承诺。"},
    20: {"speaker": "male", "text": "看，太阳出来了。新的一天开始了。咱们嘞故事，才刚开始。"},
}

# 分集配置
EPISODES = {
    1: {"title": "第一集_相遇篇", "scenes": [1,2,3,4,5]},
    2: {"title": "第二集_相处篇", "scenes": [6,7,8,9,10]},
    3: {"title": "第三集_危机篇", "scenes": [11,12,13,14,15]},
    4: {"title": "第四集_重生篇", "scenes": [16,17,18,19,20]},
}


def create_api_workflow(prompt, seed=None, width=1280, height=768, length=81, steps=25):
    """v2 工作流：分辨率翻倍, 帧数增加"""
    if seed is None:
        seed = random.randint(1, 2**32)

    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "wan2.1-t2v-1.3b\\diffusion_pytorch_model.safetensors",
                "weight_dtype": "default"
            }
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "umt5xxl_encoder.safetensors",
                "type": "wan"
            }
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "Wan2.1_VAE.pth"
            }
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": prompt,
                "clip": ["2", 0]
            }
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": NEGATIVE,
                "clip": ["2", 0]
            }
        },
        "6": {
            "class_type": "Wan22ImageToVideoLatent",
            "inputs": {
                "vae": ["3", 0],
                "width": width,
                "height": height,
                "length": length,
                "batch_size": 1
            }
        },
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["4", 0],
                "negative": ["5", 0],
                "latent_image": ["6", 0],
                "seed": seed,
                "control_after_generate": "fixed",
                "steps": steps,
                "cfg": 6.5,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1
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
                "images": ["8", 0],
                "filename_prefix": "zombie_v2"
            }
        },
        "10": {
            "class_type": "SaveAnimatedWEBP",
            "inputs": {
                "images": ["8", 0],
                "filename_prefix": "zombie_v2_video",
                "fps": 12,
                "lossless": False,
                "quality": 90,
                "method": "default"
            }
        }
    }


def queue_prompt(workflow):
    p = {"prompt": workflow}
    data = json.dumps(p).encode('utf-8')
    req = requests.post(f"{COMFYUI_URL}/prompt", data=data)
    return json.loads(req.text)


def get_history(prompt_id):
    req = requests.get(f"{COMFYUI_URL}/history/{prompt_id}")
    return json.loads(req.text)


def wait_for_completion(prompt_id, timeout=600):
    start_time = time.time()
    while time.time() - start_time < timeout:
        history = get_history(prompt_id)
        if prompt_id in history:
            outputs = history[prompt_id].get('outputs', {})
            if outputs:
                return outputs
        time.sleep(3)
    return None


def download_video(outputs, scene_num):
    """下载生成的WEBP视频"""
    for node_id, node_output in outputs.items():
        if 'gifs' in node_output:
            for gif in node_output['gifs']:
                filename = gif['filename']
                subfolder = gif.get('subfolder', '')
                url = f"{COMFYUI_URL}/view?filename={filename}&subfolder={subfolder}&type=output"
                r = requests.get(url)
                if r.status_code == 200:
                    dest = os.path.join(SCENES_DIR, f"scene_{scene_num:02d}.webp")
                    with open(dest, 'wb') as f:
                        f.write(r.content)
                    return dest
    return None


def generate_all_scenes():
    """生成所有20个场景视频"""
    print("=" * 60)
    print("《我的女友是丧尸》v2 - 批量视频生成")
    print("=" * 60)
    print(f"分辨率: 1280x768 (实际输出640x384)")
    print(f"帧数: 81 (~6.75秒@12fps)")
    print(f"采样步数: 25")
    print(f"输出目录: {V2_DIR}")
    print()

    results = {}
    for scene_num, scene_info in SCENE_PROMPTS.items():
        prompt = scene_info["prompt"]
        title = scene_info["title"]
        print(f"[{scene_num:02d}/20] 生成: {title}...")

        workflow = create_api_workflow(prompt)
        try:
            response = queue_prompt(workflow)
            if 'prompt_id' not in response:
                print(f"  ❌ 提交失败: {response}")
                results[scene_num] = False
                continue

            prompt_id = response['prompt_id']
            print(f"  已提交: {prompt_id}")

            outputs = wait_for_completion(prompt_id, timeout=600)
            if outputs:
                path = download_video(outputs, scene_num)
                if path:
                    print(f"  ✅ 完成: {path}")
                    results[scene_num] = True
                else:
                    print(f"  ❌ 下载失败")
                    results[scene_num] = False
            else:
                print(f"  ❌ 超时")
                results[scene_num] = False

        except Exception as e:
            print(f"  ❌ 错误: {e}")
            results[scene_num] = False

    success = sum(1 for v in results.values() if v)
    print(f"\n生成完成: {success}/20")
    return results


if __name__ == "__main__":
    generate_all_scenes()
