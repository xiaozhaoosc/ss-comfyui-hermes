#!/usr/bin/env python3
"""
《我的女友是丧尸》TTS配音 + 字幕 + 合并 + 拼接
Edge TTS 生成 → FFmpeg 字幕叠加 → 音视频合并 → 4集拼接
"""

import asyncio
import edge_tts
import os
import subprocess
import json

OUTPUT_DIR = r"D:\ai_projects\ComfyUI\output\zombie_girlfriend"
TTS_DIR = os.path.join(OUTPUT_DIR, "tts")
FINAL_DIR = os.path.join(OUTPUT_DIR, "final")

os.makedirs(TTS_DIR, exist_ok=True)
os.makedirs(FINAL_DIR, exist_ok=True)

# 男主用 YunxiNeural (活泼阳光), 女主/旁白用 XiaoxiaoNeural (温暖)
VOICE_MALE = "zh-CN-YunxiNeural"
VOICE_FEMALE = "zh-CN-XiaoxiaoNeural"

# 20个场景台词 (带徐州方言风味)
SCENES = {
    1: {"voice": VOICE_MALE, "text": "这日子没法过了！外头全是丧尸，俺得赶紧找个地方躲起来！"},
    2: {"voice": VOICE_MALE, "text": "嘘...别出声...千万别叫它们发现了...老天爷，吓死俺了。"},
    3: {"voice": VOICE_MALE, "text": "哎？这个丧尸...她咋不咬人呢？长得还挺好看嘞..."},
    4: {"voice": VOICE_FEMALE, "text": "嗯...嗯..."},
    5: {"voice": VOICE_MALE, "text": "她...她居然在保护我？一个丧尸在保护我？这到底是咋回事？"},
    6: {"voice": VOICE_MALE, "text": "走，俺带你去逛街！虽然商场都废了，但咱也得有点仪式感不是？"},
    7: {"voice": VOICE_MALE, "text": "来来来，这样按，对对对，你学嘞还挺快嘞！"},
    8: {"voice": VOICE_MALE, "text": "饿了吧？来，吃点东西。虽然你可能不饿，但俺觉得你还是得尝尝。"},
    9: {"voice": VOICE_MALE, "text": "她总是这样...俺睡着了她就在旁边守着...比闹钟还准时。"},
    10: {"voice": VOICE_MALE, "text": "你看那个星星，像不像你的眼睛？嗯...虽然你现在眼睛有点红..."},
    11: {"voice": VOICE_MALE, "text": "不好！外头来了一大群丧尸！快快快，把门堵上！"},
    12: {"voice": VOICE_MALE, "text": "她...她居然对着那些丧尸吼？就为了保护我？"},
    13: {"voice": VOICE_MALE, "text": "没事没事，就擦破点皮，别哭了别哭了，俺又没死。"},
    14: {"voice": VOICE_FEMALE, "text": "嗯...嗯嗯..."},
    15: {"voice": VOICE_MALE, "text": "药！找到药了！太好了，有救了有救了！"},
    16: {"voice": VOICE_MALE, "text": "我...我没死？她一直在我旁边守着？眼圈都红了..."},
    17: {"voice": VOICE_MALE, "text": "别怕了，有俺在呢，以后咱俩再也不分开了。"},
    18: {"voice": VOICE_MALE, "text": "虽然俺没有钻戒，但这个银勺子戒指...你能接受不？嫁给我吧！"},
    19: {"voice": VOICE_MALE, "text": "我愿意。虽然没有亲朋好友，但这夕阳...比啥都美。"},
    20: {"voice": VOICE_MALE, "text": "新的世界，新的开始。走吧，咱去看看前头还有啥。"},
}

# 字幕时间轴 (每场景5秒, 帧率8fps, 41帧)
SCENE_DURATION = 5.125  # 41帧 / 8fps

async def generate_tts():
    """生成TTS配音"""
    print("🎙️ 生成TTS配音...", flush=True)
    for scene_num, scene_info in SCENES.items():
        mp3_path = os.path.join(TTS_DIR, f"scene_{scene_num:02d}.mp3")
        if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0:
            print(f"  ⏭ 跳过 scene_{scene_num:02d} (已存在)", flush=True)
            continue
        
        communicate = edge_tts.Communicate(
            text=scene_info["text"],
            voice=scene_info["voice"],
            rate="+10%",
            pitch="+0Hz"
        )
        await communicate.save(mp3_path)
        size_kb = os.path.getsize(mp3_path) // 1024
        print(f"  ✅ scene_{scene_num:02d} ({size_kb}KB)", flush=True)
    
    print("🎙️ TTS配音完成!", flush=True)

def generate_srt():
    """生成SRT字幕文件"""
    print("📝 生成SRT字幕...", flush=True)
    srt_path = os.path.join(OUTPUT_DIR, "subtitles.srt")
    
    lines = []
    for scene_num, scene_info in SCENES.items():
        start_sec = (scene_num - 1) * SCENE_DURATION
        end_sec = start_sec + 3.0  # 字幕显示3秒
        
        start_h = int(start_sec // 3600)
        start_m = int((start_sec % 3600) // 60)
        start_s = int(start_sec % 60)
        start_ms = int((start_sec % 1) * 1000)
        
        end_h = int(end_sec // 3600)
        end_m = int((end_sec % 3600) // 60)
        end_s = int(end_sec % 60)
        end_ms = int((end_sec % 1) * 1000)
        
        lines.append(f"{scene_num}")
        lines.append(f"{start_h:02d}:{start_m:02d}:{start_s:02d},{start_ms:03d} --> {end_h:02d}:{end_m:02d}:{end_s:02d},{end_ms:03d}")
        lines.append(scene_info["text"])
        lines.append("")
    
    with open(srt_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"  ✅ 字幕文件: {srt_path}", flush=True)
    return srt_path

def merge_audio_video():
    """每个场景: TTS配音 + 视频合并"""
    print("🎬 合并音视频...", flush=True)
    for scene_num in SCENES.keys():
        video_path = os.path.join(OUTPUT_DIR, f"scene_{scene_num:02d}_{list(SCENES.values())[scene_num-1]}.mp4") if False else None
        
        # 找到对应的视频文件
        video_file = None
        for f in os.listdir(OUTPUT_DIR):
            if f.startswith(f"scene_{scene_num:02d}_") and f.endswith('.mp4') and os.path.getsize(os.path.join(OUTPUT_DIR, f)) > 0:
                video_file = os.path.join(OUTPUT_DIR, f)
                break
        
        if not video_file:
            print(f"  ❌ scene_{scene_num:02d} 视频不存在", flush=True)
            continue
        
        tts_file = os.path.join(TTS_DIR, f"scene_{scene_num:02d}.mp3")
        if not os.path.exists(tts_file):
            print(f"  ❌ scene_{scene_num:02d} TTS不存在", flush=True)
            continue
        
        merged_file = os.path.join(FINAL_DIR, f"scene_{scene_num:02d}.mp4")
        
        # 视频循环到TTS长度, 然后合并
        cmd = [
            'ffmpeg', '-y',
            '-stream_loop', '-1', '-i', video_file,
            '-i', tts_file,
            '-c:v', 'libx264', '-c:a', 'aac',
            '-shortest',
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            merged_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        if result.returncode == 0:
            size_kb = os.path.getsize(merged_file) // 1024
            print(f"  ✅ scene_{scene_num:02d} ({size_kb}KB)", flush=True)
        else:
            print(f"  ❌ scene_{scene_num:02d} 合并失败", flush=True)

def add_subtitles():
    """给合并后的视频添加字幕"""
    print("📺 叠加字幕...", flush=True)
    
    srt_path = os.path.join(OUTPUT_DIR, "subtitles.srt")
    if not os.path.exists(srt_path):
        print("  ❌ 字幕文件不存在", flush=True)
        return
    
    # 使用中文字体
    font_path = "C\\\\:/Windows/Fonts/msyh.ttc"
    
    for scene_num in SCENES.keys():
        input_file = os.path.join(FINAL_DIR, f"scene_{scene_num:02d}.mp4")
        if not os.path.exists(input_file):
            continue
        
        output_file = os.path.join(FINAL_DIR, f"scene_{scene_num:02d}_sub.mp4")
        
        # 计算该场景的字幕时间偏移
        time_offset = (scene_num - 1) * SCENE_DURATION
        
        # 用 drawtext 直接写入字幕文字
        text = SCENES[scene_num]["text"]
        # 转义特殊字符
        text_escaped = text.replace("'", "'\\''").replace(":", "\\:")
        
        cmd = [
            'ffmpeg', '-y',
            '-i', input_file,
            '-vf', f"drawtext=fontfile='{font_path}':text='{text_escaped}':fontcolor=white:fontsize=24:borderw=2:bordercolor=black:x=(w-text_w)/2:y=h-60",
            '-c:v', 'libx264', '-c:a', 'copy',
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            output_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        if result.returncode == 0:
            print(f"  ✅ scene_{scene_num:02d} 字幕完成", flush=True)
        else:
            print(f"  ❌ scene_{scene_num:02d} 字幕失败: {result.stderr[-200:]}", flush=True)

def concat_episodes():
    """按4集拼接视频"""
    print("🎞️ 拼接4集...", flush=True)
    
    episodes = {
        1: "第一集_相遇篇",
        2: "第二集_相处篇",
        3: "第三集_危机篇",
        4: "第四集_重生篇",
    }
    scene_ranges = {
        1: range(1, 6),
        2: range(6, 11),
        3: range(11, 16),
        4: range(16, 21),
    }
    
    for ep_num, ep_title in episodes.items():
        # 创建 concat 文件列表
        concat_file = os.path.join(FINAL_DIR, f"concat_ep{ep_num}.txt")
        scene_files = []
        
        for scene_num in scene_ranges[ep_num]:
            # 优先用带字幕的版本
            sub_file = os.path.join(FINAL_DIR, f"scene_{scene_num:02d}_sub.mp4")
            normal_file = os.path.join(FINAL_DIR, f"scene_{scene_num:02d}.mp4")
            
            if os.path.exists(sub_file):
                scene_files.append(sub_file)
            elif os.path.exists(normal_file):
                scene_files.append(normal_file)
        
        if not scene_files:
            print(f"  ❌ {ep_title} 没有可用的场景文件", flush=True)
            continue
        
        with open(concat_file, 'w', encoding='utf-8') as f:
            for sf in scene_files:
                f.write(f"file '{sf}'\n")
        
        output_file = os.path.join(FINAL_DIR, f"{ep_title}.mp4")
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat', '-safe', '0',
            '-i', concat_file,
            '-c:v', 'libx264', '-c:a', 'aac',
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            output_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode == 0:
            size_mb = os.path.getsize(output_file) / 1024 / 1024
            print(f"  ✅ {ep_title} ({size_mb:.1f}MB)", flush=True)
        else:
            print(f"  ❌ {ep_title} 拼接失败", flush=True)

async def main():
    print("=" * 50, flush=True)
    print("🧟 《我的女友是丧尸》后期处理流水线", flush=True)
    print("=" * 50, flush=True)
    
    # Step 1: TTS配音
    await generate_tts()
    
    # Step 2: 字幕
    generate_srt()
    
    # Step 3: 音视频合并
    merge_audio_video()
    
    # Step 4: 字幕叠加
    add_subtitles()
    
    # Step 5: 拼接4集
    concat_episodes()
    
    print("\n" + "=" * 50, flush=True)
    print("🎉 全部完成!", flush=True)
    print(f"📁 成品目录: {FINAL_DIR}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())