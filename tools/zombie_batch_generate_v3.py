#!/usr/bin/env python3
"""
《我的女友是丧尸》批量视频生成脚本 v3
使用正确的 Wan2.1 API 格式
"""

import json
import requests
import time
import os
import random

# ComfyUI API 配置
COMFYUI_URL = "http://127.0.0.1:8188"
OUTPUT_DIR = r"\\192.168.1.9\ComfyUI-Output\wan2\我的女友是丧尸"

# 20个场景的优化 prompt
SCENE_PROMPTS = {
    1: {"title": "丧尸来袭", "prompt": "cinematic movie still of terrifying zombie horde shambles through destroyed city street at dusk. Broken cars, shattered glass, debris everywhere. Dark ominous atmosphere with orange sunset light. Cinematic horror movie style, dramatic lighting, 4K quality, film grain."},
    2: {"title": "躲藏求生", "prompt": "cinematic movie still of young East Asian man hiding behind overturned bus, holding breath, peeking through broken window with wide fearful eyes. Zombies wandering in background. Tense suspenseful atmosphere, dim lighting, 4K quality, film grain."},
    3: {"title": "初次相遇", "prompt": "cinematic movie still in abandoned supermarket, young East Asian man and beautiful zombie girl with pale skin, dark circles, messy long black hair, wearing torn pink dress, gentle confused expression. Soft beam of light from broken skylight. Romantic tension, bittersweet moment, 4K quality."},
    4: {"title": "决定同行", "prompt": "cinematic movie still of zombie girl extending hand to young man, movements slightly stiff but gentle. He hesitates then reaches out. Close-up of hands almost touching with soft backlight creating silhouette effect. Emotional hopeful moment, 4K quality, film grain."},
    5: {"title": "保护时刻", "prompt": "cinematic movie still of zombie girl stepping in front of young man protectively, spreading arms wide, growling at aggressive zombies. Dramatic lighting, heroic pose, showing loyalty and love. Post-apocalyptic urban setting, 4K quality, film grain."},
    6: {"title": "一起逛街", "prompt": "cinematic movie still of zombie girlfriend and human boyfriend walking hand-in-hand through abandoned shopping mall. She wears cute hat. Sweet romantic atmosphere, soft natural light from skylights. 4K quality, film grain."},
    7: {"title": "学习使用手机", "prompt": "cinematic movie still in cozy corner of abandoned building, zombie girl trying to use smartphone clumsily. Young man teaches her patiently. Warm domestic scene, soft candlelight, 4K quality, film grain, intimate moment."},
    8: {"title": "分享食物", "prompt": "cinematic movie still of young man offering can of food to zombie girlfriend. She looks curiously, tries to eat but struggles. He helps her gently. Intimate moment, warm candlelight, 4K quality, film grain."},
    9: {"title": "夜晚守候", "prompt": "cinematic movie still of zombie girl sitting by window at night, watching over sleeping boyfriend. Moonlight illuminates pale face. Peaceful romantic atmosphere, beautiful moonlight composition, 4K quality, film grain."},
    10: {"title": "温馨时刻", "prompt": "cinematic movie still of couple sitting together by campfire in safe hideout. She rests head on his shoulder, looking at stars through broken roof. Cozy intimate moment, warm firelight mixed with cool moonlight, 4K quality."},
    11: {"title": "丧尸围攻", "prompt": "cinematic movie still of massive horde of aggressive zombies surrounding safe house, clawing at doors and windows. Dark threatening atmosphere, dramatic shadows, intense action scene, 4K quality, film grain, horror movie style."},
    12: {"title": "保护反击", "prompt": "cinematic movie still of zombie girlfriend standing at doorway facing horde alone, letting out powerful scream. Protects boyfriend with own body. Heroic dramatic lighting, powerful pose, 4K quality, film grain."},
    13: {"title": "受伤时刻", "prompt": "cinematic movie still during escape, young man scratched by zombie. Zombie girl panics with tears, bandaging his wound with torn dress. Emotional close-up, dramatic lighting, 4K quality, film grain."},
    14: {"title": "病毒危机", "prompt": "cinematic movie still of young man falling ill from infection, tossing with fever. Zombie girl stays by his side, wiping forehead with cool cloth. Tender emotional scene, soft lighting, 4K quality, film grain."},
    15: {"title": "找到解药", "prompt": "cinematic movie still in abandoned hospital, zombie girl finding vial of medicine, holding it up to light with hope in eyes. Dramatic backlight creates halo effect. Moment of hope, 4K quality, film grain."},
    16: {"title": "解药生效", "prompt": "cinematic movie still of young man opening eyes to see zombie girlfriend watching over with tears of joy. Soft morning light through broken windows. Emotional reunion, warm lighting, 4K quality, film grain."},
    17: {"title": "互相依偎", "prompt": "cinematic movie still of couple sitting together, holding each other close after ordeal. She leans into him, he wraps arms around her. Intimate tender moment, soft focus, beautiful composition, 4K quality."},
    18: {"title": "许下承诺", "prompt": "cinematic movie still under cherry blossom tree in abandoned park, young man kneeling with ring. Zombie girl covers mouth in surprise, tears streaming. Romantic beautiful scene, petals falling, 4K quality, film grain."},
    19: {"title": "夕阳婚礼", "prompt": "cinematic movie still of couple exchanging vows in abandoned church at sunset. Golden light through stained glass windows. She wears makeshift wedding dress. Beautiful romantic ceremony, warm sunset colors, 4K quality."},
    20: {"title": "新世界希望", "prompt": "cinematic movie still of couple standing together on rooftop at dawn, looking over city. Sun rises casting golden light over ruins. They hold hands. Hopeful beautiful composition, epic scale, 4K quality, film grain."}
}

def create_api_workflow(prompt, seed=None):
    """创建 API 格式的工作流"""
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
                "text": "low quality, blurry, distorted, ugly, deformed",
                "clip": ["2", 0]
            }
        },
        "6": {
            "class_type": "EmptyWanLatentVideo",
            "inputs": {
                "width": 640,
                "height": 384,
                "length": 41,
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
                "steps": 20,
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
                "filename_prefix": "wan21_test"
            }
        },
        "10": {
            "class_type": "SaveAnimatedWEBP",
            "inputs": {
                "images": ["8", 0],
                "filename_prefix": "wan21_video",
                "fps": 8,
                "lossless": False,
                "quality": 80,
                "method": "default"
            }
        }
    }

def queue_prompt(workflow):
    """提交 prompt 到 ComfyUI"""
    p = {"prompt": workflow}
    data = json.dumps(p).encode('utf-8')
    req = requests.post(f"{COMFYUI_URL}/prompt", data=data)
    return json.loads(req.text)

def get_history(prompt_id):
    """获取生成历史"""
    req = requests.get(f"{COMFYUI_URL}/history/{prompt_id}")
    return json.loads(req.text)

def wait_for_completion(prompt_id, timeout=300):
    """等待生成完成"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        history = get_history(prompt_id)
        if prompt_id in history:
            outputs = history[prompt_id].get('outputs', {})
            if outputs:
                return outputs
        time.sleep(2)
    return None

def download_video(outputs, scene_num, title):
    """下载生成的视频"""
    for node_id, node_output in outputs.items():
        if 'gifs' in node_output:
            for gif_info in node_output['gifs']:
                filename = gif_info['filename']
                subfolder = gif_info.get('subfolder', '')
                
                if subfolder:
                    url = f"{COMFYUI_URL}/view?filename={filename}&subfolder={subfolder}&type=output"
                else:
                    url = f"{COMFYUI_URL}/view?filename={filename}&type=output"
                
                req = requests.get(url)
                if req.status_code == 200:
                    output_filename = f"scene_{scene_num:02d}_{title}.mp4"
                    output_path = os.path.join(OUTPUT_DIR, output_filename)
                    
                    with open(output_path, 'wb') as f:
                        f.write(req.content)
                    
                    print(f"✅ 下载完成: {output_filename}")
                    return output_path
    
    # 如果没有 gifs，检查是否有 images
    for node_id, node_output in outputs.items():
        if 'images' in node_output:
            for img_info in node_output['images']:
                filename = img_info['filename']
                subfolder = img_info.get('subfolder', '')
                
                if subfolder:
                    url = f"{COMFYUI_URL}/view?filename={filename}&subfolder={subfolder}&type=output"
                else:
                    url = f"{COMFYUI_URL}/view?filename={filename}&type=output"
                
                req = requests.get(url)
                if req.status_code == 200:
                    output_filename = f"scene_{scene_num:02d}_{title}.png"
                    output_path = os.path.join(OUTPUT_DIR, output_filename)
                    
                    with open(output_path, 'wb') as f:
                        f.write(req.content)
                    
                    print(f"✅ 下载完成: {output_filename}")
                    return output_path
    
    print(f"❌ 未找到场景 {scene_num} 的输出文件")
    return None

def main():
    """主函数"""
    print("🧟 《我的女友是丧尸》批量视频生成")
    print("=" * 50)
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    results = []
    for scene_num, scene_info in SCENE_PROMPTS.items():
        print(f"\n🎬 生成场景 {scene_num}: {scene_info['title']}")
        
        try:
            workflow = create_api_workflow(scene_info['prompt'])
            result = queue_prompt(workflow)
            prompt_id = result['prompt_id']
            print(f"   提交成功，ID: {prompt_id}")
            
            print("   等待生成...")
            outputs = wait_for_completion(prompt_id, timeout=300)
            
            if outputs:
                video_path = download_video(outputs, scene_num, scene_info['title'])
                if video_path:
                    results.append({'scene': scene_num, 'title': scene_info['title'], 'path': video_path, 'status': 'success'})
                else:
                    results.append({'scene': scene_num, 'title': scene_info['title'], 'path': None, 'status': 'download_failed'})
            else:
                print(f"   ❌ 场景 {scene_num} 生成超时")
                results.append({'scene': scene_num, 'title': scene_info['title'], 'path': None, 'status': 'timeout'})
                
        except Exception as e:
            print(f"   ❌ 场景 {scene_num} 生成失败: {e}")
            results.append({'scene': scene_num, 'title': scene_info['title'], 'path': None, 'status': 'error', 'error': str(e)})
        
        time.sleep(2)
    
    print("\n" + "=" * 50)
    print("📊 生成统计:")
    success_count = sum(1 for r in results if r['status'] == 'success')
    print(f"   成功: {success_count}/20")
    print(f"   失败: {20 - success_count}/20")
    
    log_path = os.path.join(OUTPUT_DIR, "generation_log.json")
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n📁 结果日志: {log_path}")
    print(f"📂 输出目录: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()