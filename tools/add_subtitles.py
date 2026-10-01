#!/usr/bin/env python3
"""Wan2.1 字幕叠加工具 - 为生成的视频添加中文字幕"""
import subprocess
import os
import json
import sys

def add_subtitle(video_path, subtitle_text, output_path, font_size=28):
    """使用 FFmpeg 为视频添加字幕"""
    # 转义特殊字符
    subtitle_text = subtitle_text.replace("'", "'\\''").replace(":", "\\:")
    
    # 构建 FFmpeg 命令
    cmd = [
        'ffmpeg', '-y', '-i', video_path,
        '-vf', (
            f"drawtext=text='{subtitle_text}'"
            f":fontfile=C\\\\:/Windows/Fonts/msyh.ttc"
            f":fontsize={font_size}"
            f":fontcolor=white"
            f":borderw=2"
            f":bordercolor=black"
            f":x=(w-text_w)/2"
            f":y=h-60"
        ),
        '-c:a', 'copy',
        output_path
    ]
    
    print(f"处理: {os.path.basename(video_path)}")
    print(f"字幕: {subtitle_text}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"错误: {result.stderr[:200]}")
        return False
    return True

def batch_add_subtitles(input_dir, output_dir, prompts_file):
    """批量为视频添加字幕"""
    with open(prompts_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 遍历所有剧集和场景
    for ep_name, ep_data in data['episodes'].items():
        for scene_name, scene_data in ep_data['scenes'].items():
            # 查找对应的视频文件
            video_name = f"wan_{ep_name}-{scene_name}_00001.mp4"
            video_path = os.path.join(input_dir, video_name)
            subtitle = scene_data.get('subtitle', '')
            
            if os.path.exists(video_path) and subtitle:
                output_path = os.path.join(output_dir, video_name)
                add_subtitle(video_path, subtitle, output_path)
            else:
                if not os.path.exists(video_path):
                    print(f"跳过 {video_name}: 文件不存在")
                elif not subtitle:
                    print(f"跳过 {video_name}: 无字幕")

if __name__ == '__main__':
    input_dir = 'D:/OLLAMA_MODELS/output/wan2/我的女友是丧尸'
    output_dir = 'D:/OLLAMA_MODELS/output/wan2/我的女友是丧尸_字幕版'
    prompts_file = 'D:/ai_projects/ComfyUI/workflows/wan2_zombie_girlfriend_prompts.json'
    
    print("=== Wan2.1 字幕叠加工具 ===")
    batch_add_subtitles(input_dir, output_dir, prompts_file)
    print("\n完成！字幕版视频在:", output_dir)
