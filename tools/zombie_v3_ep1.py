#!/usr/bin/env python3
"""
《我的女友是丧尸》v3 - 第1集打磨
核心优化：扩充短场景台词，TTS语速降低，确保每场景5-8秒
"""

import os
import subprocess
import shutil
import tempfile
import random
import json
import requests
import time

# 配置
COMFYUI_URL = "http://127.0.0.1:8188"
V3_DIR = r"D:\ai_projects\ComfyUI\output\zombie_girlfriend\v3"
EP1_DIR = os.path.join(V3_DIR, "EP01")
SCENES_DIR = os.path.join(EP1_DIR, "scenes")
TTS_DIR = os.path.join(EP1_DIR, "tts")
FINAL_DIR = os.path.join(EP1_DIR, "final")
TEMP_DIR = os.path.join(EP1_DIR, "temp")

for d in [V3_DIR, EP1_DIR, SCENES_DIR, TTS_DIR, FINAL_DIR, TEMP_DIR]:
    os.makedirs(d, exist_ok=True)

# 技术参数
WIDTH = 1280       # 请求分辨率（实际输出640）
HEIGHT = 768
LENGTH = 81        # 帧数
FPS = 12           # 帧率
STEPS = 25         # 采样步数
TARGET_W = 640     # 实际输出分辨率
TARGET_H = 384
FONT = "C\\:/Windows/Fonts/msyh.ttc"
FONT_SIZE = 20

# 角色描述（保持一致性）
CHARACTER_DESC = (
    "beautiful young East Asian woman zombie, age 20, "
    "long straight black hair to waist, very pale white skin, "
    "dark circles under eyes with smudged dark makeup, "
    "wearing torn dirty pink dress with lace details, "
    "subtle dark veins on neck, gentle soft expression, slightly vacant eyes"
)

STYLE_DESC = (
    "cinematic movie still, anamorphic lens, shallow depth of field, "
    "film grain, color grading, professional cinematography, 4K quality, "
    "dramatic lighting, atmospheric"
)

NEGATIVE = (
    "low quality, blurry, distorted, ugly, deformed, extra limbs, "
    "bad anatomy, watermark, text, logo, nsfw, oversaturated"
)

# =====================================================
# v3 第1集场景数据 - 优化台词长度
# =====================================================
EP1_SCENES = {
    1: {
        "title": "丧尸来袭",
        "prompt": f"{STYLE_DESC}, terrifying zombie horde shambles through destroyed city street at dusk, broken cars shattered glass debris everywhere, dark ominous atmosphere orange sunset light, horror movie style dramatic lighting",
        "speaker": "male",
        # 原: "我地个娘来！这丧尸咋嫩多！快跑快跑！" (13字, 5.5s)
        # v3: 扩充叙事
        "text": "我地个娘来！前面那是啥？丧尸！咋嫩多！快跑快跑！别回头！往那边巷子里钻！"
    },
    2: {
        "title": "躲藏求生",
        "prompt": f"{STYLE_DESC}, young East Asian man age 25 with short black hair wearing worn jacket hiding behind overturned bus, holding breath peeking through broken window with wide fearful eyes, zombies wandering in background, tense suspenseful dim lighting",
        "speaker": "male",
        # 原: "嘘...别出声...千万别出声...老天爷保佑..." (16字, 4.4s)
        # v3: 扩充紧张感
        "text": "嘘...别出声...千万别出声...那丧尸就在外面晃悠...老天爷保佑，千万别让它们发现咱...再等等...再等等..."
    },
    3: {
        "title": "初次相遇",
        "prompt": f"{STYLE_DESC}, in abandoned supermarket, young East Asian man and {CHARACTER_DESC}, soft beam of light from broken skylight, romantic tension bittersweet moment, warm soft lighting",
        "speaker": "male",
        # 原: "恁...恁别过来啊！俺...俺身上没肉！诶？恁咋不动了？" (22字, 7.7s)
        # v3: 保持（时长合适）
        "text": "恁...恁别过来啊！俺...俺身上没肉！诶？恁咋不动了？恁跟别的丧尸不一样？恁...恁能听懂俺说话？"
    },
    4: {
        "title": "决定同行",
        "prompt": f"{STYLE_DESC}, zombie girl {CHARACTER_DESC} extending hand to young man, movements slightly stiff but gentle, he hesitates then reaches out, close-up of hands almost touching, soft backlight creating silhouette, emotional hopeful moment",
        "speaker": "female",
        # 原: "手...手..." (3字, 1.4s) ← 严重过短！
        # v3: 大幅扩充，表达丧尸女孩的内心挣扎
        "text": "手...我的手...以前...以前是温暖的吗？我想不起来了...但是，我想牵你的手...可以吗？"
    },
    5: {
        "title": "保护时刻",
        "prompt": f"{STYLE_DESC}, zombie girl {CHARACTER_DESC} stepping in front of young man protectively, spreading arms wide growling at aggressive zombies, dramatic lighting heroic pose showing loyalty, post-apocalyptic urban setting",
        "speaker": "female",
        # 原: "不准...碰他！" (5字, 1.8s) ← 严重过短！
        # v3: 扩充保护宣言
        "text": "不准碰他！他是我的人！你们谁都不准动他！我会保护他的...就算我变成了这样...我也要保护他！"
    }
}


def create_api_workflow(prompt, seed=None):
    """创建工作流"""
    if seed is None:
        seed = random.randint(1, 2**32)
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "wan2.1-t2v-1.3b\\diffusion_pytorch_model.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5xxl_encoder.safetensors", "type": "wan"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "Wan2.1_VAE.pth"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": NEGATIVE, "clip": ["2", 0]}},
        "6": {"class_type": "Wan22ImageToVideoLatent", "inputs": {"vae": ["3", 0], "width": WIDTH, "height": HEIGHT, "length": LENGTH, "batch_size": 1}},
        "7": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["6", 0], "seed": seed, "steps": STEPS, "cfg": 6.5, "sampler_name": "euler", "scheduler": "normal", "denoise": 1}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "zombie_v3"}},
        "10": {"class_type": "SaveAnimatedWEBP", "inputs": {"images": ["8", 0], "filename_prefix": "zombie_v3_video", "fps": FPS, "lossless": False, "quality": 90, "method": "default"}}
    }


def get_duration(path):
    """获取音视频时长"""
    r = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'csv=p=0', path],
        capture_output=True, text=True
    )
    try:
        return float(r.stdout.strip())
    except:
        return 0


def step1_generate_tts():
    """步骤1: 生成TTS配音（语速降低20%）"""
    print("=" * 50)
    print("步骤1: 生成TTS配音")
    print("=" * 50)
    
    results = {}
    for scene_num, data in EP1_SCENES.items():
        out_file = os.path.join(TTS_DIR, f"scene_{scene_num:02d}.mp3")
        voice = "zh-CN-YunxiNeural" if data["speaker"] == "male" else "zh-CN-XiaoxiaoNeural"
        
        # 语速降低20%，让台词更从容
        cmd = [
            'edge-tts', '--voice', voice,
            '--rate=-20%', '--pitch=+5Hz',
            '--text', data["text"],
            '--write-media', out_file
        ]
        
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and os.path.exists(out_file):
            dur = get_duration(out_file)
            sz = os.path.getsize(out_file) // 1024
            print(f"  [{scene_num:02d}] {data['title']}: {dur:.1f}s, {sz}KB", flush=True)
            results[scene_num] = dur
        else:
            print(f"  [{scene_num:02d}] FAIL: {r.stderr[:100]}", flush=True)
            results[scene_num] = 0
    
    return results


def step2_generate_video():
    """步骤2: 生成视频"""
    print("\n" + "=" * 50)
    print("步骤2: 生成视频")
    print("=" * 50)
    
    for scene_num, data in EP1_SCENES.items():
        webp_file = os.path.join(SCENES_DIR, f"scene_{scene_num:02d}.webp")
        if os.path.exists(webp_file):
            print(f"  [{scene_num:02d}] exists, skip", flush=True)
            continue
        
        print(f"  [{scene_num:02d}] Generating {data['title']}...", flush=True)
        
        workflow = create_api_workflow(data["prompt"])
        try:
            r = requests.post(f"{COMFYUI_URL}/prompt", json={"prompt": workflow})
            result = r.json()
            
            if "prompt_id" not in result:
                print(f"    FAIL: {result}", flush=True)
                continue
            
            pid = result["prompt_id"]
            print(f"    Submitted: {pid[:8]}", flush=True)
            
            # 等待完成
            start = time.time()
            while time.time() - start < 600:
                h = requests.get(f"{COMFYUI_URL}/history/{pid}").json()
                if pid in h:
                    outputs = h[pid].get("outputs", {})
                    if outputs:
                        for nid, out in outputs.items():
                            if "gifs" in out:
                                for g in out["gifs"]:
                                    fn = g["filename"]
                                    src = os.path.join(r"D:\ai_projects\ComfyUI\output", fn)
                                    if os.path.exists(src):
                                        shutil.copy2(src, webp_file)
                                        sz = os.path.getsize(webp_file) // 1024
                                        print(f"    Done: {sz}KB", flush=True)
                        break
                time.sleep(5)
            else:
                print(f"    TIMEOUT", flush=True)
        
        except Exception as e:
            print(f"    ERROR: {e}", flush=True)


def step3_webp_to_mp4():
    """步骤3: WEBP转MP4"""
    print("\n" + "=" * 50)
    print("步骤3: WEBP → MP4")
    print("=" * 50)
    
    for scene_num in EP1_SCENES:
        webp_file = os.path.join(SCENES_DIR, f"scene_{scene_num:02d}.webp")
        mp4_file = os.path.join(SCENES_DIR, f"scene_{scene_num:02d}.mp4")
        
        if not os.path.exists(webp_file):
            print(f"  [{scene_num:02d}] skip (no webp)", flush=True)
            continue
        
        if os.path.exists(mp4_file) and os.path.getsize(mp4_file) > 1000:
            print(f"  [{scene_num:02d}] exists", flush=True)
            continue
        
        temp_dir = tempfile.mkdtemp(prefix=f"wan_{scene_num}_")
        try:
            from PIL import Image
            img = Image.open(webp_file)
            n_frames = getattr(img, 'n_frames', 1)
            
            for i in range(n_frames):
                img.seek(i)
                img.convert('RGB').save(os.path.join(temp_dir, f'frame_{i:04d}.png'))
            
            cmd = f'ffmpeg -y -framerate {FPS} -i "{temp_dir}/frame_%04d.png" -vf "scale={TARGET_W}:{TARGET_H}:flags=lanczos" -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p "{mp4_file}" 2>NUL'
            ret = os.system(cmd)
            
            if ret == 0:
                sz = os.path.getsize(mp4_file) // 1024
                print(f"  [{scene_num:02d}] OK ({sz}KB, {n_frames}f)", flush=True)
            else:
                print(f"  [{scene_num:02d}] FAIL", flush=True)
        
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


def step4_merge_audio_video(tts_durations):
    """步骤4: 合并音视频"""
    print("\n" + "=" * 50)
    print("步骤4: 合并音视频")
    print("=" * 50)
    
    for scene_num in EP1_SCENES:
        mp4_in = os.path.join(SCENES_DIR, f"scene_{scene_num:02d}.mp4")
        mp3_in = os.path.join(TTS_DIR, f"scene_{scene_num:02d}.mp3")
        mp4_out = os.path.join(FINAL_DIR, f"scene_{scene_num:02d}.mp4")
        
        if not os.path.exists(mp4_in) or not os.path.exists(mp3_in):
            print(f"  [{scene_num:02d}] skip", flush=True)
            continue
        
        tts_dur = tts_durations.get(scene_num, 5.0)
        
        cmd = f'ffmpeg -y -stream_loop -1 -i "{mp4_in}" -i "{mp3_in}" -t {tts_dur:.3f} -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -c:a aac -b:a 128k -map 0:v:0 -map 1:a:0 -shortest "{mp4_out}" 2>NUL'
        ret = os.system(cmd)
        
        if ret == 0:
            dur = get_duration(mp4_out)
            print(f"  [{scene_num:02d}] merged ({dur:.1f}s)", flush=True)
        else:
            print(f"  [{scene_num:02d}] FAIL", flush=True)


def step5_add_subtitles():
    """步骤5: 添加字幕"""
    print("\n" + "=" * 50)
    print("步骤5: 添加字幕")
    print("=" * 50)
    
    for scene_num, data in EP1_SCENES.items():
        mp4_in = os.path.join(FINAL_DIR, f"scene_{scene_num:02d}.mp4")
        mp4_out = os.path.join(FINAL_DIR, f"scene_{scene_num:02d}_sub.mp4")
        
        if not os.path.exists(mp4_in):
            print(f"  [{scene_num:02d}] skip", flush=True)
            continue
        
        text = data["text"].replace("'", "\\'")
        vf = f"drawtext=fontfile='{FONT}':text='{text}':fontsize={FONT_SIZE}:fontcolor=white:borderw=2:bordercolor=black:x=(w-text_w)/2:y=h-text_h-20"
        
        cmd = f'ffmpeg -y -i "{mp4_in}" -vf "{vf}" -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -c:a copy "{mp4_out}" 2>NUL'
        ret = os.system(cmd)
        
        if ret == 0:
            dur = get_duration(mp4_out)
            print(f"  [{scene_num:02d}] subtitled ({dur:.1f}s)", flush=True)
        else:
            print(f"  [{scene_num:02d}] FAIL", flush=True)


def step6_concat_episode():
    """步骤6: 拼接第1集"""
    print("\n" + "=" * 50)
    print("步骤6: 拼接第1集")
    print("=" * 50)
    
    concat_file = os.path.join(TEMP_DIR, "concat_ep1.txt")
    output = os.path.join(V3_DIR, "EP01_相遇篇.mp4")
    
    available = []
    for scene_num in sorted(EP1_SCENES.keys()):
        f = os.path.join(FINAL_DIR, f"scene_{scene_num:02d}_sub.mp4")
        if os.path.exists(f):
            available.append(f)
    
    if len(available) < len(EP1_SCENES):
        print(f"  Warning: {len(available)}/{len(EP1_SCENES)} scenes available", flush=True)
    
    if not available:
        print("  No scenes available", flush=True)
        return
    
    with open(concat_file, 'w') as fh:
        for f in available:
            fh.write(f"file '{f}'\n")
    
    cmd = f'ffmpeg -y -f concat -safe 0 -i "{concat_file}" -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -c:a aac -b:a 128k "{output}" 2>NUL'
    ret = os.system(cmd)
    
    if ret == 0:
        dur = get_duration(output)
        sz = os.path.getsize(output) // 1024
        print(f"  EP01_相遇篇: {dur:.1f}s, {sz}KB", flush=True)
    else:
        print("  EP01 FAIL", flush=True)


def main():
    print("=" * 60)
    print("《我的女友是丧尸》v3 - 第1集打磨")
    print("=" * 60)
    print(f"优化目标：扩充短场景台词，每场景5-8秒")
    print(f"技术参数：{TARGET_W}×{TARGET_H}@{FPS}fps, {LENGTH}帧")
    print()
    
    # 执行流水线
    tts_durations = step1_generate_tts()
    step2_generate_video()
    step3_webp_to_mp4()
    step4_merge_audio_video(tts_durations)
    step5_add_subtitles()
    step6_concat_episode()
    
    print("\n" + "=" * 60)
    print("v3 第1集打磨完成！")
    print(f"输出目录: {V3_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
