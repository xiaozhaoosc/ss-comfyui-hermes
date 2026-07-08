#!/usr/bin/env python3
"""
《我的女友是丧尸》v4 - 第1-2集
CogView/Flux 参考图 + Wan img2vid
"""

import os
import subprocess
import shutil
import tempfile
import random
import json
import requests
import time

# ============================================================
# 配置
# ============================================================
COMFYUI_URL = "http://127.0.0.1:8188"
V4_DIR = r"D:\ai_projects\ComfyUI\output\zombie_girlfriend\v4"
EP_DIR = {
    1: os.path.join(V4_DIR, "EP01_相遇篇"),
    2: os.path.join(V4_DIR, "EP02_相处篇"),
}

# 创建目录结构
for ep, d in EP_DIR.items():
    for sub in ["ref_images", "scenes", "tts", "final"]:
        os.makedirs(os.path.join(d, sub), exist_ok=True)

# 技术参数
REF_W = 1024        # 参考图宽度
REF_H = 576         # 参考图高度 (16:9)
VID_W = 1280        # 请求视频宽度 (实际输出640)
VID_H = 720         # 请求视频高度 (实际输出360)
LENGTH = 81         # 帧数
FPS = 12            # 帧率
STEPS = 25          # 采样步数
TARGET_W = 640      # 实际输出
TARGET_H = 360

FONT = "C\\:/Windows/Fonts/msyh.ttc"
FONT_SIZE = 18

# ============================================================
# 角色描述（用于参考图生成和视频prompt）
# ============================================================
GIRL_DESC = (
    "beautiful young East Asian woman zombie, age 20, "
    "long straight black hair reaching waist, extremely pale white skin, "
    "dark sunken eyes with black smudged eye makeup, "
    "dark red blood streaks trailing from eyes down cheeks, "
    "faint blue glowing bioluminescent lines on neck and arms, "
    "wearing torn dirty pale pink dress with decayed lace details"
)

GIRL_REF = (
    f"full body portrait of {GIRL_DESC}, "
    "standing in abandoned building interior, "
    "dim atmospheric lighting with blue glow accents, "
    "cinematic horror-romance aesthetic, ultra detailed, 8K"
)

BOY_DESC = (
    "young East Asian man, age 25, short black hair, "
    "worn dark brown military-style jacket over gray t-shirt, "
    "tired but kind eyes, slight stubble"
)

# ============================================================
# 第1集《相遇篇》场景数据
# ============================================================
EP1_SCENES = {
    1: {
        "title": "丧尸来袭",
        "ref_prompt": (
            f"POV first-person perspective from inside a wrecked bus, "
            f"looking through cracked windshield at zombie horde in destroyed city street, "
            f"orange sunset sky, broken cars and debris everywhere, "
            f"horrifying atmosphere, cinematic lighting, ultra detailed, 8K"
        ),
        "vid_prompt": (
            "POV first person view from inside wrecked bus, "
            "camera shaking slightly, "
            "zombie horde approaching through broken windshield, "
            "orange sunset light, dust particles, tense atmosphere"
        ),
        "speaker": "male",
        "text": "我地个娘来！前面那是啥？丧尸！咋嫩多！快跑快跑！别回头！往那边巷子里钻！"
    },
    2: {
        "title": "躲藏求生",
        "ref_prompt": (
            f"young Asian man {BOY_DESC} hiding inside dark overturned bus, "
            f"peeking through broken window with terrified expression, "
            f"hand covering mouth, zombies visible outside in background, "
            f"dim blue moonlight, tense suspenseful atmosphere, cinematic, 8K"
        ),
        "vid_prompt": (
            "inside dark overturned bus, young man hiding, "
            "peeking through broken window, terrified expression, "
            "hand over mouth, zombies visible outside, "
            "dim moonlight, tense atmosphere, slight camera shake"
        ),
        "speaker": "male",
        "text": "嘘...别出声...千万别出声...那丧尸就在外面晃悠...老天爷保佑，千万别让它们发现咱...再等等...再等等..."
    },
    3: {
        "title": "初次相遇",
        "ref_prompt": (
            f"young Asian man {BOY_DESC} and zombie girl {GIRL_DESC} "
            f"face to face inside abandoned supermarket aisle, "
            f"beam of light from broken ceiling, "
            f"she stares at him with confused gentle expression, "
            f"he looks terrified but curious, romantic tension, cinematic, 8K"
        ),
        "vid_prompt": (
            "abandoned supermarket interior, young man and zombie girl face to face, "
            "beam of dusty light from broken ceiling, "
            "she tilts head confused, he backs away then stops, "
            "romantic tension, soft atmospheric lighting"
        ),
        "speaker": "male",
        "text": "恁...恁别过来啊！俺...俺身上没肉！诶？恁咋不动了？恁跟别的丧尸不一样？恁...恁能听懂俺说话？"
    },
    4: {
        "title": "决定同行",
        "ref_prompt": (
            f"close-up of zombie girl {GIRL_DESC} reaching out her pale hand "
            f"toward camera (POV of young man), "
            f"blue glowing veins visible on her wrist, "
            f"soft backlight creating silhouette, emotional moment, cinematic, 8K"
        ),
        "vid_prompt": (
            "close-up POV, zombie girl reaching her pale hand toward camera, "
            "blue glowing veins on her wrist, "
            "she moves slowly, hesitantly, "
            "soft backlight, emotional intimate moment"
        ),
        "speaker": "female",
        "text": "手...我的手...以前...以前是温暖的吗？我想不起来了...但是，我想牵你的手...可以吗？"
    },
    5: {
        "title": "保护时刻",
        "ref_prompt": (
            f"zombie girl {GIRL_DESC} standing protectively in front of young man {BOY_DESC}, "
            f"arms spread wide facing aggressive zombie horde, "
            f"heroic pose, blue glowing lines on her skin pulsing bright, "
            f"dramatic backlight, post-apocalyptic street, cinematic, 8K"
        ),
        "vid_prompt": (
            "zombie girl standing protectively in front of young man, "
            "arms spread wide facing aggressive zombie horde, "
            "heroic protective pose, blue glow on her skin, "
            "dramatic backlight, intense action moment"
        ),
        "speaker": "female",
        "text": "不准碰他！他是我的人！你们谁都不准动他！我会保护他的...就算我变成了这样...我也要保护他！"
    }
}

# ============================================================
# 第2集《相处篇》场景数据
# ============================================================
EP2_SCENES = {
    1: {
        "title": "一起逛街",
        "ref_prompt": (
            f"zombie girl {GIRL_DESC} and young man {BOY_DESC} "
            f"walking hand-in-hand through abandoned shopping mall, "
            f"she wears a cute found sunhat, sweet romantic atmosphere, "
            f"soft skylight, peaceful moment, cinematic, 8K"
        ),
        "vid_prompt": (
            "abandoned shopping mall, zombie girl and young man walking hand in hand, "
            "she wears a cute sunhat, sweet romantic atmosphere, "
            "soft natural light from skylights, peaceful"
        ),
        "speaker": "male",
        "text": "哈哈，恁看这帽子中不中？戴恁头上真好看！咱俩这样逛街，跟正常情侣似的。"
    },
    2: {
        "title": "学习使用手机",
        "ref_prompt": (
            f"zombie girl {GIRL_DESC} trying to use smartphone clumsily, "
            f"young man {BOY_DESC} teaching her patiently, "
            f"cozy corner of abandoned building with candles, "
            f"warm intimate domestic scene, soft candlelight, cinematic, 8K"
        ),
        "vid_prompt": (
            "cozy corner of abandoned building, candlelight, "
            "zombie girl clumsily tapping smartphone screen, "
            "young man guides her hand patiently, "
            "warm intimate domestic moment"
        ),
        "speaker": "male",
        "text": "这个叫手机，恁这样按...诶对了对了！恁学嘞还不赖来！再试试这个，能拍照嘞。"
    },
    3: {
        "title": "分享食物",
        "ref_prompt": (
            f"young man {BOY_DESC} offering canned food to zombie girl {GIRL_DESC}, "
            f"she looks at it curiously with head tilted, "
            f"campfire glow in safe hideout, intimate tender moment, cinematic, 8K"
        ),
        "vid_prompt": (
            "safe hideout with campfire glow, "
            "young man offering canned food to zombie girl, "
            "she looks curiously, tries to eat, he helps gently, "
            "intimate tender moment"
        ),
        "speaker": "male",
        "text": "饿了吧？来，尝尝这个...诶恁慢点吃，没人跟恁抢！好吃不？虽然不是啥好东西..."
    },
    4: {
        "title": "夜晚守候",
        "ref_prompt": (
            f"zombie girl {GIRL_DESC} sitting by broken window at night, "
            f"watching over sleeping young man {BOY_DESC}, "
            f"moonlight illuminating her pale face, "
            f"blue glowing lines softly pulsing, peaceful romantic, cinematic, 8K"
        ),
        "vid_prompt": (
            "night scene, zombie girl sitting by broken window, "
            "moonlight on her pale face, blue glow pulsing softly, "
            "sleeping young man in background, "
            "peaceful romantic atmosphere"
        ),
        "speaker": "female",
        "text": "守...守护你...月亮好亮...以前...我也喜欢看月亮吗？记不清了...但是，有你在，真好。"
    },
    5: {
        "title": "温馨时刻",
        "ref_prompt": (
            f"couple sitting together by campfire in safe hideout, "
            f"zombie girl {GIRL_DESC} resting head on young man {BOY_DESC}'s shoulder, "
            f"looking at stars through broken roof, "
            f"warm firelight and cool moonlight, intimate cozy, cinematic, 8K"
        ),
        "vid_prompt": (
            "couple sitting by campfire, zombie girl resting on man's shoulder, "
            "stars visible through broken roof, "
            "warm firelight mixed with cool moonlight, "
            "intimate cozy moment"
        ),
        "speaker": "male",
        "text": "恁看那星星，跟恁眼睛一样亮...咱俩这样也怪好嘞。虽然世界变成这样了，但有恁在身边，俺就觉得啥都值了。"
    }
}


# ============================================================
# 工具函数
# ============================================================
def get_duration(path):
    r = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'csv=p=0', path],
        capture_output=True, text=True
    )
    try:
        return float(r.stdout.strip())
    except:
        return 0


def queue_and_wait(workflow, timeout=900, desc=""):
    """提交工作流并等待完成"""
    r = requests.post(f"{COMFYUI_URL}/prompt", json={"prompt": workflow})
    result = r.json()
    if "prompt_id" not in result:
        print(f"    FAIL: {result}", flush=True)
        return None
    
    pid = result["prompt_id"]
    print(f"    Submitted: {pid[:8]}", flush=True)
    
    start = time.time()
    while time.time() - start < timeout:
        h = requests.get(f"{COMFYUI_URL}/history/{pid}").json()
        if pid in h:
            outputs = h[pid].get("outputs", {})
            if outputs:
                return outputs
        time.sleep(10)
    
    print(f"    TIMEOUT after {timeout}s", flush=True)
    return None


# ============================================================
# 步骤1：生成参考图 (SDXL)
# ============================================================
def generate_ref_images(scenes, ep_dir):
    """使用 Flux 生成参考图"""
    ref_dir = os.path.join(ep_dir, "ref_images")
    
    print("=" * 50)
    print("步骤1: 生成参考图 (SDXL)")
    print("=" * 50)
    
    for scene_num, data in scenes.items():
        out_file = os.path.join(ref_dir, f"scene_{scene_num:02d}.png")
        if os.path.exists(out_file):
            print(f"  [{scene_num:02d}] exists, skip", flush=True)
            continue
        
        prompt = data["ref_prompt"]
        seed = random.randint(1, 2**32)
        
        # SD 1.5 txt2img workflow (faster with --lowvram)
        workflow = {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "v1-5-pruned-emaonly.safetensors"}
            },
            "2": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": prompt, "clip": ["1", 1]}
            },
            "3": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "low quality, blurry, distorted, ugly, deformed", "clip": ["1", 1]}
            },
            "4": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": REF_W, "height": REF_H, "batch_size": 1}
            },
            "5": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["1", 0],
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "latent_image": ["4", 0],
                    "seed": seed,
                    "steps": 25,
                    "cfg": 7.5,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1
                }
            },
            "6": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["5", 0], "vae": ["1", 2]}
            },
            "7": {
                "class_type": "SaveImage",
                "inputs": {"images": ["6", 0], "filename_prefix": f"ref_ep1_{scene_num:02d}"}
            }
        }
        
        print(f"  [{scene_num:02d}] {data['title']}...", flush=True)
        outputs = queue_and_wait(workflow, timeout=600, desc=f"ref_{scene_num}")
        
        if outputs:
            # Download the generated image
            for nid, out in outputs.items():
                if "images" in out:
                    for img in out["images"]:
                        fn = img["filename"]
                        src = os.path.join(r"D:\ai_projects\ComfyUI\output", fn)
                        if os.path.exists(src):
                            shutil.copy2(src, out_file)
                            print(f"    Done: {os.path.getsize(out_file)//1024}KB", flush=True)


# ============================================================
# 步骤2：img2vid (WanFirstLastFrameToVideo)
# ============================================================
def generate_videos(scenes, ep_dir):
    """使用 Wan img2vid 生成视频"""
    ref_dir = os.path.join(ep_dir, "ref_images")
    scenes_dir = os.path.join(ep_dir, "scenes")
    
    print("\n" + "=" * 50)
    print("步骤2: 生成视频 (Wan img2vid)")
    print("=" * 50)
    
    for scene_num, data in scenes.items():
        webp_file = os.path.join(scenes_dir, f"scene_{scene_num:02d}.webp")
        ref_img = os.path.join(ref_dir, f"scene_{scene_num:02d}.png")
        
        if os.path.exists(webp_file):
            print(f"  [{scene_num:02d}] exists, skip", flush=True)
            continue
        
        if not os.path.exists(ref_img):
            print(f"  [{scene_num:02d}] no ref image, skip", flush=True)
            continue
        
        prompt = data["vid_prompt"]
        seed = random.randint(1, 2**32)
        
        # img2vid workflow using WanFirstLastFrameToVideo
        # First, upload the reference image by saving it to ComfyUI input
        # We'll use LoadImage with the filename
        ref_filename = os.path.basename(ref_img)
        # Copy to ComfyUI input directory
        input_dir = r"D:\ai_projects\ComfyUI\input"
        input_path = os.path.join(input_dir, ref_filename)
        shutil.copy2(ref_img, input_path)
        
        workflow = {
            "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "wan2.1-t2v-1.3b\\diffusion_pytorch_model.safetensors", "weight_dtype": "default"}},
            "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5xxl_encoder.safetensors", "type": "wan"}},
            "3": {"class_type": "VAELoader", "inputs": {"vae_name": "Wan2.1_VAE.pth"}},
            "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
            "5": {"class_type": "CLIPTextEncode", "inputs": {"text": "low quality, blurry, distorted, ugly, deformed", "clip": ["2", 0]}},
            "6": {"class_type": "LoadImage", "inputs": {"image": ref_filename}},
            "7": {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"}},
            "8": {"class_type": "CLIPVisionEncode", "inputs": {"clip_vision": ["7", 0], "image": ["6", 0], "crop": "center"}},
            "9": {
                "class_type": "WanFirstLastFrameToVideo",
                "inputs": {
                    "positive": ["4", 0],
                    "negative": ["5", 0],
                    "vae": ["3", 0],
                    "width": VID_W,
                    "height": VID_H,
                    "length": LENGTH,
                    "batch_size": 1,
                    "start_image": ["6", 0],
                    "clip_vision_start_image": ["8", 0]
                }
            },
            "10": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["9", 0], "negative": ["9", 1], "latent_image": ["9", 2], "seed": seed, "steps": STEPS, "cfg": 6.5, "sampler_name": "euler", "scheduler": "normal", "denoise": 1}},
            "11": {"class_type": "VAEDecode", "inputs": {"samples": ["10", 0], "vae": ["3", 0]}},
            "12": {"class_type": "SaveImage", "inputs": {"images": ["11", 0], "filename_prefix": "zombie_v4"}},
            "13": {"class_type": "SaveAnimatedWEBP", "inputs": {"images": ["11", 0], "filename_prefix": "zombie_v4_video", "fps": FPS, "lossless": False, "quality": 90, "method": "default"}}
        }
        
        print(f"  [{scene_num:02d}] {data['title']}...", flush=True)
        outputs = queue_and_wait(workflow, timeout=900, desc=f"vid_{scene_num}")
        
        if outputs:
            for nid, out in outputs.items():
                if "gifs" in out:
                    for g in out["gifs"]:
                        fn = g["filename"]
                        src = os.path.join(r"D:\ai_projects\ComfyUI\output", fn)
                        if os.path.exists(src):
                            shutil.copy2(src, webp_file)
                            print(f"    Done: {os.path.getsize(webp_file)//1024}KB", flush=True)
        
        # Clean up input
        if os.path.exists(input_path):
            os.remove(input_path)


# ============================================================
# 步骤3-6：后期处理
# ============================================================
def postprocess(scenes, ep_dir, ep_num):
    """WEBP→MP4 + TTS + 字幕 + 拼接"""
    scenes_dir = os.path.join(ep_dir, "scenes")
    tts_dir = os.path.join(ep_dir, "tts")
    final_dir = os.path.join(ep_dir, "final")
    
    # 3. WEBP → MP4
    print("\n" + "=" * 50)
    print("步骤3: WEBP → MP4")
    print("=" * 50)
    
    for scene_num in scenes:
        webp = os.path.join(scenes_dir, f"scene_{scene_num:02d}.webp")
        mp4 = os.path.join(scenes_dir, f"scene_{scene_num:02d}.mp4")
        
        if not os.path.exists(webp):
            print(f"  [{scene_num:02d}] skip", flush=True)
            continue
        if os.path.exists(mp4) and os.path.getsize(mp4) > 1000:
            print(f"  [{scene_num:02d}] exists", flush=True)
            continue
        
        temp_dir = tempfile.mkdtemp(prefix=f"wan_{scene_num}_")
        try:
            from PIL import Image
            img = Image.open(webp)
            n = getattr(img, 'n_frames', 1)
            for i in range(n):
                img.seek(i)
                img.convert('RGB').save(os.path.join(temp_dir, f'frame_{i:04d}.png'))
            
            cmd = f'ffmpeg -y -framerate {FPS} -i "{temp_dir}/frame_%04d.png" -vf "scale={TARGET_W}:{TARGET_H}:flags=lanczos" -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p "{mp4}" 2>NUL'
            ret = os.system(cmd)
            if ret == 0:
                print(f"  [{scene_num:02d}] OK ({os.path.getsize(mp4)//1024}KB, {n}f)", flush=True)
            else:
                print(f"  [{scene_num:02d}] FAIL", flush=True)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    # 4. TTS
    print("\n" + "=" * 50)
    print("步骤4: TTS 配音")
    print("=" * 50)
    
    tts_durations = {}
    for scene_num, data in scenes.items():
        mp3 = os.path.join(tts_dir, f"scene_{scene_num:02d}.mp3")
        if os.path.exists(mp3) and os.path.getsize(mp3) > 100:
            dur = get_duration(mp3)
            tts_durations[scene_num] = dur
            print(f"  [{scene_num:02d}] exists ({dur:.1f}s)", flush=True)
            continue
        
        voice = "zh-CN-YunxiNeural" if data["speaker"] == "male" else "zh-CN-XiaoxiaoNeural"
        cmd = ['edge-tts', '--voice', voice, '--rate=-20%', '--pitch=+5Hz', '--text', data["text"], '--write-media', mp3]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and os.path.exists(mp3):
            dur = get_duration(mp3)
            tts_durations[scene_num] = dur
            print(f"  [{scene_num:02d}] OK ({dur:.1f}s)", flush=True)
        else:
            print(f"  [{scene_num:02d}] FAIL", flush=True)
    
    # 5. 合并 + 字幕
    print("\n" + "=" * 50)
    print("步骤5: 合并音视频 + 字幕")
    print("=" * 50)
    
    for scene_num, data in scenes.items():
        mp4_in = os.path.join(scenes_dir, f"scene_{scene_num:02d}.mp4")
        mp3_in = os.path.join(tts_dir, f"scene_{scene_num:02d}.mp3")
        merged = os.path.join(final_dir, f"scene_{scene_num:02d}.mp4")
        sub = os.path.join(final_dir, f"scene_{scene_num:02d}_sub.mp4")
        
        if not os.path.exists(mp4_in) or not os.path.exists(mp3_in):
            print(f"  [{scene_num:02d}] skip", flush=True)
            continue
        
        # Merge
        dur = tts_durations.get(scene_num, 5.0)
        cmd = f'ffmpeg -y -stream_loop -1 -i "{mp4_in}" -i "{mp3_in}" -t {dur:.3f} -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -c:a aac -b:a 128k -map 0:v:0 -map 1:a:0 -shortest "{merged}" 2>NUL'
        os.system(cmd)
        
        # Subtitle
        text = data["text"].replace("'", "\\'")
        vf = f"drawtext=fontfile='{FONT}':text='{text}':fontsize={FONT_SIZE}:fontcolor=white:borderw=2:bordercolor=black:x=(w-text_w)/2:y=h-text_h-20"
        cmd = f'ffmpeg -y -i "{merged}" -vf "{vf}" -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -c:a copy "{sub}" 2>NUL'
        ret = os.system(cmd)
        if ret == 0:
            print(f"  [{scene_num:02d}] OK ({get_duration(sub):.1f}s)", flush=True)
        else:
            print(f"  [{scene_num:02d}] FAIL", flush=True)
    
    # 6. 拼接
    print("\n" + "=" * 50)
    print("步骤6: 拼接")
    print("=" * 50)
    
    title = f"第{'一二'[ep_num-1]}集_{'相遇篇' if ep_num==1 else '相处篇'}"
    concat_file = os.path.join(final_dir, "concat.txt")
    output = os.path.join(V4_DIR, f"{title}.mp4")
    
    available = []
    for s in sorted(scenes.keys()):
        f = os.path.join(final_dir, f"scene_{s:02d}_sub.mp4")
        if os.path.exists(f):
            available.append(f)
    
    with open(concat_file, 'w') as fh:
        for f in available:
            fh.write(f"file '{f}'\n")
    
    cmd = f'ffmpeg -y -f concat -safe 0 -i "{concat_file}" -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -c:a aac -b:a 128k "{output}" 2>NUL'
    ret = os.system(cmd)
    if ret == 0:
        dur = get_duration(output)
        sz = os.path.getsize(output) // 1024
        print(f"  {title}: {dur:.1f}s, {sz}KB", flush=True)
    else:
        print(f"  {title}: FAIL", flush=True)


# ============================================================
# 主流程
# ============================================================
def main():
    print("=" * 60)
    print("《我的女友是丧尸》v4 - SDXL参考图 + Wan img2vid")
    print("=" * 60)
    print(f"参考图: {REF_W}×{REF_H}")
    print(f"视频: {TARGET_W}×{TARGET_H}@{FPS}fps, {LENGTH}帧")
    print()
    
    # 第1集
    print("\n" + "🎬" * 20)
    print("第1集《相遇篇》")
    print("🎬" * 20)
    generate_ref_images(EP1_SCENES, EP_DIR[1])
    generate_videos(EP1_SCENES, EP_DIR[1])
    postprocess(EP1_SCENES, EP_DIR[1], ep_num=1)
    
    # 第2集
    print("\n" + "🎬" * 20)
    print("第2集《相处篇》")
    print("🎬" * 20)
    generate_ref_images(EP2_SCENES, EP_DIR[2])
    generate_videos(EP2_SCENES, EP_DIR[2])
    postprocess(EP2_SCENES, EP_DIR[2], ep_num=2)
    
    print("\n" + "=" * 60)
    print("v4 完成！")
    print(f"输出目录: {V4_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
