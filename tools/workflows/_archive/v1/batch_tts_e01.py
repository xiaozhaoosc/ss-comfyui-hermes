#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《最强末日系统》Stage 4 配音生成脚本
使用 edge-tts 批量生成第 1 话台词配音
音色分配：
- 赵昀: zh-CN-YunxiNeural
- 旁白/系统: zh-CN-XiaoxiaoNeural / zh-CN-YunyangNeural
- 张九斤: zh-CN-YunjianNeural
"""

import asyncio
import os
import re
from pathlib import Path

# 强制走本地代理
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"

import edge_tts

AUDIO_OUT_DIR = Path("D:/ai_projects/末日系统_漫画短剧/04_进度/audio/e01")
SCRIPT_FILE = Path("D:/ai_projects/末日系统_漫画短剧/03_产出/短剧剧本/第001章.md")

VOICE_MAP = {
    "赵昀": "zh-CN-YunxiNeural",
    "旁白": "zh-CN-XiaoxiaoNeural",
    "系统": "zh-CN-YunyangNeural",
    "张九斤": "zh-CN-YunjianNeural"
}

async def generate_tts(text, voice, out_path):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(out_path))

async def main():
    AUDIO_OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(SCRIPT_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    shot_blocks = re.findall(r'## 镜头 (\d+)（.*?）\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
    print(f"🎬 开始生成第 1 话（共 {len(shot_blocks)} 个镜头）配音...")

    for shot_num, shot_content in shot_blocks:
        shot_num = int(shot_num)
        dialogue_match = re.search(r'- \*\*台词/旁白\*\*：「(.+)」', shot_content)
        if not dialogue_match:
            continue
        full_text = dialogue_match.group(1).strip()
        
        # 简单角色切分
        if "：" in full_text:
            speaker, text = full_text.split("：", 1)
        else:
            speaker = "旁白"
            text = full_text

        voice = VOICE_MAP.get(speaker, "zh-CN-XiaoxiaoNeural")
        out_file = AUDIO_OUT_DIR / f"e01_j{shot_num:02d}_{speaker}.mp3"
        print(f"  🎙️ 镜头 {shot_num:02d} [{speaker}]: {text} -> {out_file.name}")
        await generate_tts(text, voice, out_file)

    print("🎉 第 1 话配音生成完毕！")

if __name__ == "__main__":
    asyncio.run(main())
