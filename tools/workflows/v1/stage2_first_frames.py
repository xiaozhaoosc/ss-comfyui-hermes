#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《最强末日系统》Stage 2：批量生成 41 张 first_frame（前 5 话）
B 版策略：同一话内统一底座
- Flux fp8：整话叙事格（大部分镜头）
- Counterfeit-V3.0：打斗特效特写格 / 封面重打
"""

import json
import requests
import time
import os
import re
import sys
from pathlib import Path

COMFYUI_URL = "http://127.0.0.1:8188"
OUTPUT_DIR = Path("D:/ai_projects/ComfyUI/output/zqmr")
SCRIPT_DIR = Path("D:/ai_projects/末日系统_漫画短剧/03_产出/短剧剧本")
WORKFLOW_DIR = Path("D:/ai_projects/ComfyUI/workflows/v1")

# 国漫强化尾缀（美术风格文档确认）
STYLE_SUFFIX = "(donghua style, Chinese anime style, detailed illustration, dramatic lighting, cinematic composition, high quality, 8k, masterpiece)"
COMEDY_SUFFIX = "(comedy style, exaggerated expression, bright lighting)"
ACTION_SUFFIX = "(dynamic action, motion blur, energy effects, speed lines)"

NEGATIVE_PROMPT = "EasyNegativeV2, worst quality, low quality, blurry, distorted, deformed, ugly, bad anatomy, bad proportions, extra limbs, cloned face, disfigured, gross proportions, malformed limbs, missing arms, missing legs, extra arms, extra legs, fused fingers, too many fingers, long neck, username, watermark, signature"

# 前 5 话文件（当前只跑第 1 话验收）
CHAPTER_FILES = [
    "第001章.md",
]

# 打斗特效特写格标记（用 Counterfeit）
# 当前策略：整话统一 Counterfeit，ACTION_SHOTS 仅用于标记动作镜头追加尾缀
ACTION_SHOTS = {
    1: [6],  # 第1话镜头6：金色光芒包裹，系统宣布资格
    2: [7],  # 第2话镜头7：军刀斩杀红内裤丧尸
    3: [2],  # 第3话镜头2：加技能点，战意升腾
    4: [],   # 第4话：待补充
    5: [],   # 第5话：待补充
}


def parse_script(filepath):
    """解析短剧剧本，提取镜头信息"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 提取镜头块
    shots = []
    # 匹配：## 镜头 N（时间）... 到下一个 ## 或文件结束
    shot_blocks = re.findall(r'## 镜头 (\d+)（.*?）\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
    
    for shot_num, shot_content in shot_blocks:
        shot_num = int(shot_num)
        
        # 提取场景
        scene_match = re.search(r'- \*\*场景\*\*：(.+)', shot_content)
        scene = scene_match.group(1).strip() if scene_match else ""
        
        # 提取画面描述
        desc_match = re.search(r'- \*\*画面描述\*\*：(.+)', shot_content)
        description = desc_match.group(1).strip() if desc_match else ""
        
        # 提取英文提示词
        prompt_match = re.search(r'```\n(.+?)\n```', shot_content, re.DOTALL)
        prompt_en = prompt_match.group(1).strip() if prompt_match else ""
        
        # 提取台词
        dialogue_match = re.search(r'- \*\*台词/旁白\*\*：「(.+)」', shot_content)
        dialogue = dialogue_match.group(1).strip() if dialogue_match else ""
        
        # 提取音效
        sound_match = re.search(r'- \*\*音效/BGM\*\*：(.+)', shot_content)
        sound = sound_match.group(1).strip() if sound_match else ""
        
        shots.append({
            'shot_num': shot_num,
            'scene': scene,
            'description': description,
            'prompt_en': prompt_en,
            'dialogue': dialogue,
            'sound': sound,
        })
    
    return shots


def enhance_prompt(prompt_en, is_action=False, is_comedy=False):
    """增强提示词：追加国漫风格尾缀"""
    # 清理原有提示词中的质量词（避免重复）
    prompt_clean = re.sub(r',?\s*(8k|masterpiece|best quality|high quality|detailed)', '', prompt_en, flags=re.IGNORECASE)
    
    # 基础尾缀
    suffix = STYLE_SUFFIX
    
    # 动作镜头追加
    if is_action:
        suffix = ACTION_SUFFIX + ", " + suffix
    
    # 搞笑镜头追加
    if is_comedy:
        suffix = COMEDY_SUFFIX + ", " + suffix
    
    return f"{prompt_clean}, {suffix}"


def is_comedy_shot(description, dialogue):
    """判断是否为搞笑镜头"""
    comedy_keywords = ['搞笑', '吐槽', '嫌弃', '崩溃', '狼狈', '尴尬', '中二', '喜剧', '乌鸦叫', '啪']
    text = description + dialogue
    return any(kw in text for kw in comedy_keywords)


def build_flux_api_workflow(positive_prompt, negative_prompt, seed, filename_prefix, width=512, height=768):
    """构建 Flux fp8 API 格式工作流（备用，低显存模式）"""
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
                "clip_name1": "clip_l.safetensors",
                "clip_name2": "t5xxl_fp8_e4m3fn.safetensors",
                "type": "flux"
            }
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "flux-vae-bf16.safetensors"
            }
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["2", 0],
                "text": positive_prompt
            }
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["2", 0],
                "text": negative_prompt
            }
        },
        "6": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": width,
                "height": height,
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
                "steps": 20,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0
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
                "filename_prefix": filename_prefix
            }
        }
    }


def build_counterfeit_api_workflow(positive_prompt, negative_prompt, seed, filename_prefix, width=512, height=768):
    """构建 Counterfeit-V3.0 API 格式工作流"""
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": "Counterfeit-V3.0_fp16.safetensors"
            }
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["1", 1],
                "text": positive_prompt
            }
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["1", 1],
                "text": negative_prompt
            }
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1
            }
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
                "seed": seed,
                "steps": 20,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0
            }
        },
        "6": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["5", 0],
                "vae": ["1", 2]
            }
        },
        "7": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["6", 0],
                "filename_prefix": filename_prefix
            }
        }
    }


def submit_workflow(workflow, client_id="zqmr_stage2"):
    """提交工作流到 ComfyUI"""
    payload = {
        "prompt": workflow,
        "client_id": client_id
    }
    try:
        response = requests.post(f"{COMFYUI_URL}/prompt", json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result.get("prompt_id")
    except Exception as e:
        print(f"提交失败: {e}")
        return None


def wait_for_completion(prompt_id, timeout=300):
    """等待生成完成"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{COMFYUI_URL}/history/{prompt_id}", timeout=10)
            if response.status_code == 200:
                history = response.json()
                if prompt_id in history:
                    status = history[prompt_id].get("status", {})
                    if status.get("completed", False):
                        return True
                    elif status.get("status_str") == "error":
                        print(f"生成出错: {status}")
                        return False
        except Exception as e:
            print(f"查询状态出错: {e}")
        time.sleep(2)
    print("等待超时")
    return False


def check_output(filename):
    """检查输出文件是否存在"""
    output_path = OUTPUT_DIR / filename
    return output_path.exists()


def main():
    print("=" * 60)
    print("《最强末日系统》Stage 2：批量生成 41 张 first_frame")
    print("B 版策略：同一话内统一底座")
    print("=" * 60)
    
    # 检查 ComfyUI
    try:
        requests.get(f"{COMFYUI_URL}/system_stats", timeout=5)
        print("✅ ComfyUI 连接正常")
    except:
        print("❌ 无法连接 ComfyUI")
        sys.exit(1)
    
    # 确保输出目录存在
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    total_shots = 0
    success_count = 0
    failed_shots = []
    
    for chapter_idx, chapter_file in enumerate(CHAPTER_FILES, 1):
        chapter_path = SCRIPT_DIR / chapter_file
        if not chapter_path.exists():
            print(f"⚠️ 剧本不存在: {chapter_file}")
            continue
        
        print(f"\n{'=' * 60}")
        print(f"📖 第 {chapter_idx} 话: {chapter_file}")
        print(f"{'=' * 60}")
        
        # 解析剧本
        shots = parse_script(chapter_path)
        print(f"  发现 {len(shots)} 个镜头")
        
        # 获取该话的打斗特效格
        action_shots = ACTION_SHOTS.get(chapter_idx, [])
        
        for shot in shots:
            total_shots += 1
            shot_num = shot['shot_num']
            is_action = shot_num in action_shots
            is_comedy = is_comedy_shot(shot['description'], shot['dialogue'])
            
            # 决定底座：整话统一 Counterfeit-V3.0（16GB 显存更稳）
            use_counterfeit = True
            model_name = "Counterfeit-V3.0"
            
            # 增强提示词
            enhanced_prompt = enhance_prompt(shot['prompt_en'], is_action, is_comedy)
            
            # 生成文件名
            filename_prefix = f"zqmr/e{chapter_idx:02d}_j{shot_num:02d}"
            expected_filename = f"e{chapter_idx:02d}_j{shot_num:02d}_00001_.png"
            
            # 种子 = 章节 * 1000 + 镜头号
            seed = chapter_idx * 1000 + shot_num
            
            print(f"\n  🎬 镜头 {shot_num} | 底座: {model_name} | 动作: {is_action} | 搞笑: {is_comedy}")
            print(f"     场景: {shot['scene']}")
            print(f"     描述: {shot['description'][:50]}...")
            
            # 构建工作流
            if use_counterfeit:
                workflow = build_counterfeit_api_workflow(
                    enhanced_prompt, NEGATIVE_PROMPT, seed, filename_prefix
                )
            else:
                workflow = build_flux_api_workflow(
                    enhanced_prompt, NEGATIVE_PROMPT, seed, filename_prefix
                )
            
            # 提交
            prompt_id = submit_workflow(workflow)
            if not prompt_id:
                print(f"     ❌ 提交失败")
                failed_shots.append((chapter_idx, shot_num))
                continue
            
            print(f"     ⏳ 生成中... (prompt_id: {prompt_id[:8]}...)")
            
            # 等待完成
            if wait_for_completion(prompt_id, timeout=600):
                # 检查输出（ComfyUI 会在 prefix 后加 _00001_.png）
                actual_files = list(OUTPUT_DIR.glob(f"e{chapter_idx:02d}_j{shot_num:02d}_*.png"))
                if actual_files:
                    print(f"     ✅ 成功: {actual_files[0].name}")
                    success_count += 1
                else:
                    print(f"     ⚠️ 完成但文件未找到")
                    failed_shots.append((chapter_idx, shot_num))
            else:
                print(f"     ❌ 生成失败/超时")
                failed_shots.append((chapter_idx, shot_num))
    
    # 汇总
    print(f"\n{'=' * 60}")
    print("📊 Stage 2 结果汇总")
    print(f"{'=' * 60}")
    print(f"总镜头数: {total_shots}")
    print(f"成功: {success_count}")
    print(f"失败: {len(failed_shots)}")
    
    if failed_shots:
        print(f"\n失败镜头: {failed_shots}")
    
    if success_count == total_shots:
        print(f"\n🎉 Stage 2 全部完成！")
        print(f"📁 输出目录: {OUTPUT_DIR}")
    else:
        print(f"\n⚠️ Stage 2 部分完成 ({success_count}/{total_shots})")
    
    return 0 if success_count == total_shots else 1


if __name__ == "__main__":
    sys.exit(main())
