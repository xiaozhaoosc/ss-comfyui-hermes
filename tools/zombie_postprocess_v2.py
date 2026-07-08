#!/usr/bin/env python3
"""
《我的女友是丧尸》v2 后期处理脚本
WEBP→MP4, TTS, 字幕, 合并, 分集拼接
"""

import os
import subprocess
import sys

OUTPUT_DIR = r"D:\ai_projects\ComfyUI\output\zombie_girlfriend"
V2_DIR = os.path.join(OUTPUT_DIR, "v2")
SCENES_DIR = os.path.join(V2_DIR, "scenes")
TTS_DIR = os.path.join(V2_DIR, "tts")
FINAL_DIR = os.path.join(V2_DIR, "final")
TEMP_DIR = os.path.join(V2_DIR, "temp")

for d in [V2_DIR, TTS_DIR, FINAL_DIR, TEMP_DIR]:
    os.makedirs(d, exist_ok=True)

# v2 配置
FPS = 12
TARGET_W = 640
TARGET_H = 384
FONT_SIZE = 20  # 640宽对应20px
FONT_PATH = "C\\\\:/Windows/Fonts/msyh.ttc"  # ffmpeg drawtext 格式

SCENE_LINES = {
    1: {"speaker": "male", "text": "我地个娘来！这丧尸咋嫩多！快跑快跑！"},
    2: {"speaker": "male", "text": "嘘...别出声...千万别出声...老天爷保佑..."},
    3: {"speaker": "male", "text": "恁...恁别过来啊！俺...俺身上没肉！诶？恁咋不动了？"},
    4: {"speaker": "female", "text": "手...手..."},
    5: {"speaker": "female", "text": "不准...碰他！"},
    6: {"speaker": "male", "text": "哈哈，恁看这帽子中不中？戴恁头上真好看！"},
    7: {"speaker": "male", "text": "这个叫手机，恁这样按...诶对了对了！恁学嘞还不赖来！"},
    8: {"speaker": "male", "text": "饿了吧？来，尝尝这个...诶恁慢点吃，没人跟恁抢！"},
    9: {"speaker": "female", "text": "守...守护你..."},
    10: {"speaker": "male", "text": "恁看那星星，跟恁眼睛一样亮...咱俩这样也怪好嘞。"},
    11: {"speaker": "male", "text": "不好！门要顶不住了！恁快从后门跑！"},
    12: {"speaker": "female", "text": "不准！碰！他！"},
    13: {"speaker": "male", "text": "没事儿没事儿...就蹭破点皮...恁别哭啊..."},
    14: {"speaker": "female", "text": "不要...离开..."},
    15: {"speaker": "female", "text": "药！找到了！"},
    16: {"speaker": "male", "text": "恁...恁是...我的丧尸女孩？天呐...我好了？"},
    17: {"speaker": "female", "text": "在...一直...在..."},
    18: {"speaker": "male", "text": "俺知道俺配不上恁...但是俺想跟恁过一辈子！恁愿意不？"},
    19: {"speaker": "male", "text": "不管世界变成啥样，俺都要跟恁在一起。这是俺对恁嘞承诺。"},
    20: {"speaker": "male", "text": "看，太阳出来了。新的一天开始了。咱们嘞故事，才刚开始。"},
}

EPISODES = {
    1: {"title": "第一集_相遇篇", "scenes": [1,2,3,4,5]},
    2: {"title": "第二集_相处篇", "scenes": [6,7,8,9,10]},
    3: {"title": "第三集_危机篇", "scenes": [11,12,13,14,15]},
    4: {"title": "第四集_重生篇", "scenes": [16,17,18,19,20]},
}


def run_cmd(cmd, desc=""):
    """执行命令"""
    print(f"  -> {desc}" if desc else f"  -> {cmd[:80]}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f"  ❌ 错误: {result.stderr[:200]}")
        return False
    return True


def step1_webp_to_mp4():
    """步骤1: WEBP→MP4（正确帧率）"""
    print("\n=== 步骤1: WEBP → MP4 ===")
    import glob

    webp_files = sorted(glob.glob(os.path.join(SCENES_DIR, "*.webp")))
    if not webp_files:
        print("  ⚠️ 没有找到WEBP文件，跳过")
        return

    for webp in webp_files:
        basename = os.path.splitext(os.path.basename(webp))[0]
        mp4_out = os.path.join(SCENES_DIR, f"{basename}.mp4")

        # 使用 Pillow 拆帧 + ffmpeg 合成（解决 WEBP 兼容性）
        temp_frames = os.path.join(TEMP_DIR, basename)
        os.makedirs(temp_frames, exist_ok=True)

        # Pillow 拆帧
        cmd_pil = (
            f'python3 -c "'
            f"from PIL import Image; "
            f"img = Image.open('{webp.replace(chr(92), chr(92)+chr(92))}'); "
            f"n = getattr(img, 'n_frames', 1); "
            f"for i in range(n): "
            f"  img.seek(i); "
            f"  img.convert('RGB').save('{temp_frames.replace(chr(92), chr(92)+chr(92))}/frame_%04d.png' % i)"
            f'"'
        )
        if not run_cmd(cmd_pil, f"拆帧 {basename}"):
            continue

        # ffmpeg 合成 MP4，统一帧率
        cmd_ff = (
            f'ffmpeg -y -framerate {FPS} -i "{temp_frames}/frame_%04d.png" '
            f'-vf "scale={TARGET_W}:{TARGET_H}:flags=lanczos" '
            f'-c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p '
            f'"{mp4_out}" 2>/dev/null'
        )
        if run_cmd(cmd_ff, f"合成 {basename}.mp4"):
            print(f"  ✅ {basename}.mp4")
        else:
            print(f"  ❌ {basename}.mp4 失败")

        # 清理临时帧
        import shutil
        shutil.rmtree(temp_frames, ignore_errors=True)

    print("  WEBP→MP4 完成")


def step2_generate_tts():
    """步骤2: 生成TTS配音"""
    print("\n=== 步骤2: 生成TTS配音 ===")

    for scene_num, line_info in SCENE_LINES.items():
        out_file = os.path.join(TTS_DIR, f"scene_{scene_num:02d}.mp3")
        if os.path.exists(out_file):
            print(f"  [{scene_num:02d}] 已存在，跳过")
            continue

        voice = "zh-CN-YunxiNeural" if line_info["speaker"] == "male" else "zh-CN-XiaoxiaoNeural"
        text = line_info["text"]

        # edge-tts 命令
        cmd = (
            f'edge-tts --voice "{voice}" '
            f'--rate "-10%" '
            f'--pitch "+5Hz" '
            f'--text "{text}" '
            f'--write-media "{out_file}" 2>/dev/null'
        )
        if run_cmd(cmd, f"TTS scene_{scene_num:02d}"):
            print(f"  ✅ scene_{scene_num:02d}.mp3")
        else:
            print(f"  ❌ scene_{scene_num:02d} 失败")

    print("  TTS生成完成")


def step3_merge_audio_video():
    """步骤3: 合并音视频（以TTS时长为准）"""
    print("\n=== 步骤3: 合并音视频 ===")

    for scene_num in range(1, 21):
        mp4_in = os.path.join(SCENES_DIR, f"scene_{scene_num:02d}.mp4")
        mp3_in = os.path.join(TTS_DIR, f"scene_{scene_num:02d}.mp3")
        mp4_out = os.path.join(FINAL_DIR, f"scene_{scene_num:02d}.mp4")

        if not os.path.exists(mp4_in):
            print(f"  [{scene_num:02d}] ⚠️ 视频不存在，跳过")
            continue
        if not os.path.exists(mp3_in):
            print(f"  [{scene_num:02d}] ⚠️ 音频不存在，跳过")
            continue

        # 获取TTS音频时长
        cmd_dur = f'ffprobe -v quiet -show_entries format=duration -of csv=p=0 "{mp3_in}" 2>/dev/null'
        result = subprocess.run(cmd_dur, shell=True, capture_output=True, text=True)
        try:
            tts_dur = float(result.stdout.strip())
        except:
            tts_dur = 6.0

        # 合并：视频循环到TTS时长，然后叠加音频
        # 使用 -stream_loop 让视频循环，-t 截断到TTS时长
        cmd = (
            f'ffmpeg -y -stream_loop -1 -i "{mp4_in}" -i "{mp3_in}" '
            f'-t {tts_dur:.3f} '
            f'-c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p '
            f'-c:a aac -b:a 128k '
            f'-map 0:v:0 -map 1:a:0 '
            f'-shortest '
            f'"{mp4_out}" 2>/dev/null'
        )
        if run_cmd(cmd, f"合并 scene_{scene_num:02d}"):
            print(f"  ✅ scene_{scene_num:02d}.mp4 ({tts_dur:.1f}s)")
        else:
            print(f"  ❌ scene_{scene_num:02d} 合并失败")

    print("  音视频合并完成")


def step4_add_subtitles():
    """步骤4: 添加字幕"""
    print("\n=== 步骤4: 添加字幕 ===")

    for scene_num, line_info in SCENE_LINES.items():
        mp4_in = os.path.join(FINAL_DIR, f"scene_{scene_num:02d}.mp4")
        mp4_out = os.path.join(FINAL_DIR, f"scene_{scene_num:02d}_sub.mp4")

        if not os.path.exists(mp4_in):
            continue

        text = line_info["text"].replace("'", "\u2019").replace(":", "\uff1a")

        # drawtext: 白字黑边，居中底部
        cmd = (
            f'ffmpeg -y -i "{mp4_in}" '
            f"-vf \"drawtext=fontfile={FONT_PATH}:"
            f"text='{text}':"
            f"fontsize={FONT_SIZE}:"
            f"fontcolor=white:"
            f"borderw=2:"
            f"bordercolor=black:"
            f"x=(w-text_w)/2:"
            f"y=h-text_h-20\" "
            f'-c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p '
            f'-c:a copy '
            f'"{mp4_out}" 2>/dev/null'
        )
        if run_cmd(cmd, f"字幕 scene_{scene_num:02d}"):
            print(f"  ✅ scene_{scene_num:02d}_sub.mp4")
        else:
            print(f"  ❌ scene_{scene_num:02d} 字幕失败")

    print("  字幕添加完成")


def step5_concat_episodes():
    """步骤5: 分集拼接（带淡入淡出）"""
    print("\n=== 步骤5: 分集拼接 ===")

    for ep_num, ep_info in EPISODES.items():
        title = ep_info["title"]
        scenes = ep_info["scenes"]
        concat_file = os.path.join(TEMP_DIR, f"concat_ep{ep_num}.txt")
        output = os.path.join(FINAL_DIR, f"{title}.mp4")

        # 写入concat文件
        with open(concat_file, 'w', encoding='utf-8') as f:
            for s in scenes:
                scene_file = os.path.join(FINAL_DIR, f"scene_{s:02d}_sub.mp4")
                # 使用正斜杠避免Windows路径问题
                scene_file_fwd = scene_file.replace("\\", "/")
                f.write(f"file '{scene_file_fwd}'\n")

        # 拼接
        cmd = (
            f'ffmpeg -y -f concat -safe 0 -i "{concat_file}" '
            f'-c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p '
            f'-c:a aac -b:a 128k '
            f'"{output}" 2>/dev/null'
        )
        if run_cmd(cmd, f"拼接 {title}"):
            # 获取时长
            dur_cmd = f'ffprobe -v quiet -show_entries format=duration -of csv=p=0 "{output}"'
            dur = subprocess.run(dur_cmd, shell=True, capture_output=True, text=True).stdout.strip()
            print(f"  ✅ {title}.mp4 ({dur}s)")
        else:
            print(f"  ❌ {title} 拼接失败")

    print("  分集拼接完成")


def main():
    print("=" * 60)
    print("《我的女友是丧尸》v2 - 后期处理")
    print("=" * 60)

    step1_webp_to_mp4()
    step2_generate_tts()
    step3_merge_audio_video()
    step4_add_subtitles()
    step5_concat_episodes()

    print("\n" + "=" * 60)
    print("✅ v2 后期处理完成！")
    print(f"输出目录: {FINAL_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
