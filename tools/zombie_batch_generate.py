#!/usr/bin/env python3
"""
《我的女友是丧尸》批量视频生成脚本
使用优化后的 Wan2.1 工作流，640×384 分辨率
"""

import json
import requests
import time
import os
import shutil
from pathlib import Path

# ComfyUI API 配置
COMFYUI_URL = "http://127.0.0.1:8188"
OUTPUT_DIR = r"\\192.168.1.9\ComfyUI-Output\wan2\我的女友是丧尸"
WORKFLOW_TEMPLATE = r"D:\ai_projects\ComfyUI\workflows\zombie_optimized_640x384.json"

# 20个场景的优化 prompt
SCENE_PROMPTS = {
    # 第一集：相遇篇
    1: {
        "title": "丧尸来袭",
        "prompt": "cinematic movie still of terrifying zombie horde shambles through destroyed city street at dusk. Broken cars, shattered glass, debris everywhere. Zombies move slowly with jerky motions, clothes torn and dirty. Dark ominous atmosphere with orange sunset light filtering through dust clouds. Cinematic horror movie style, dramatic lighting, 4K quality, film grain, professional photography."
    },
    2: {
        "title": "躲藏求生",
        "prompt": "cinematic movie still of young East Asian man hiding behind overturned bus, holding breath, peeking through broken window with wide fearful eyes. Zombies wandering in background. Tense suspenseful atmosphere, dim lighting, shallow depth of field focusing on worried face. 4K quality, film grain, dramatic lighting."
    },
    3: {
        "title": "初次相遇",
        "prompt": "cinematic movie still in abandoned supermarket, young East Asian man and beautiful zombie girl lock eyes across aisle. She has pale skin, dark circles, messy long black hair, wearing torn pink dress, gentle confused expression rather than aggressive. Soft beam of light from broken skylight illuminates them. Romantic tension, bittersweet moment, cinematic composition, 4K quality."
    },
    4: {
        "title": "决定同行",
        "prompt": "cinematic movie still of zombie girl extending hand to young man, movements slightly stiff but gentle. He hesitates then reaches out to take her hand. Close-up of hands almost touching with soft backlight creating silhouette effect. Emotional hopeful moment, bittersweet romance, dramatic lighting, 4K quality, film grain."
    },
    5: {
        "title": "保护时刻",
        "prompt": "cinematic movie still of zombie girl stepping in front of young man protectively, spreading arms wide, growling at aggressive zombies approaching. Dramatic lighting, heroic pose, showing loyalty and love despite being zombie herself. Post-apocalyptic urban setting, 4K quality, film grain, cinematic composition."
    },
    
    # 第二集：相处篇
    6: {
        "title": "一起逛街",
        "prompt": "cinematic movie still of zombie girlfriend and human boyfriend walking hand-in-hand through abandoned shopping mall. She wears cute hat to hide zombie features. Looking at broken store windows together. Sweet romantic atmosphere, soft natural light from skylights, showing love persists in apocalypse. 4K quality, film grain."
    },
    7: {
        "title": "学习使用手机",
        "prompt": "cinematic movie still in cozy corner of abandoned building, zombie girl trying to use smartphone, movements clumsy but determined. Young man teaches her patiently, pointing at screen. Warm domestic scene, soft lighting from candles, showing normal life together. 4K quality, film grain, intimate moment."
    },
    8: {
        "title": "分享食物",
        "prompt": "cinematic movie still of young man offering can of food to zombie girlfriend. She looks curiously, tries to eat but struggles. He helps her gently. Intimate moment, soft focus on interaction, warm candlelight, showing care and tenderness in unusual relationship. 4K quality, film grain."
    },
    9: {
        "title": "夜晚守候",
        "prompt": "cinematic movie still of zombie girl sitting by window at night, watching over sleeping boyfriend. Moonlight illuminates pale face as she keeps guard protectively. Peaceful romantic atmosphere, beautiful moonlight composition, showing devotion and love. 4K quality, film grain, cinematic."
    },
    10: {
        "title": "温馨时刻",
        "prompt": "cinematic movie still of couple sitting together by campfire in safe hideout. She rests head on his shoulder, both looking at stars through broken roof. Cozy intimate moment, warm firelight mixed with cool moonlight, finding beauty and love in broken world. 4K quality, film grain."
    },
    
    # 第三集：危机篇
    11: {
        "title": "丧尸围攻",
        "prompt": "cinematic movie still of massive horde of aggressive zombies surrounding safe house, clawing at doors and windows trying to get in. Dark threatening atmosphere, dramatic shadows, intense action scene with couple trapped inside. 4K quality, film grain, horror movie style."
    },
    12: {
        "title": "保护反击",
        "prompt": "cinematic movie still of zombie girlfriend standing at doorway facing horde alone, letting out powerful scream making other zombies hesitate. Protects boyfriend with own body. Heroic dramatic lighting, powerful pose showing strength and love. 4K quality, film grain, cinematic."
    },
    13: {
        "title": "受伤时刻",
        "prompt": "cinematic movie still during escape, young man scratched by zombie. Zombie girl panics with tears in eyes, bandaging his wound with torn dress. Emotional close-up on worried faces, dramatic lighting showing danger they face. 4K quality, film grain."
    },
    14: {
        "title": "病毒危机",
        "prompt": "cinematic movie still of young man falling ill from infection, tossing and turning with fever. Zombie girl stays by his side, wiping forehead with cool cloth, refusing to leave. Tender emotional scene, soft lighting, showing unwavering devotion. 4K quality, film grain."
    },
    15: {
        "title": "找到解药",
        "prompt": "cinematic movie still in abandoned hospital, zombie girl finding vial of medicine, holding it up to light with hope in eyes. Dramatic backlight creates halo effect around medicine vial. Moment of hope and relief, cinematic lighting, 4K quality, film grain."
    },
    
    # 第四集：重生篇
    16: {
        "title": "解药生效",
        "prompt": "cinematic movie still of young man's fever breaking, opening eyes to see zombie girlfriend watching over with tears of joy. Soft morning light filters through broken windows. Emotional reunion, warm lighting, showing relief and happiness after crisis. 4K quality, film grain."
    },
    17: {
        "title": "互相依偎",
        "prompt": "cinematic movie still of couple sitting together, holding each other close after ordeal. She leans into him, he wraps arms protectively around her. Intimate tender moment, soft focus on connection, beautiful composition showing deep bond. 4K quality, film grain."
    },
    18: {
        "title": "许下承诺",
        "prompt": "cinematic movie still under cherry blossom tree in abandoned park, young man kneeling holding out ring made from silver spoon. Zombie girl covers mouth in surprise, tears streaming down face. Romantic beautiful scene, petals falling around them, cinematic proposal moment. 4K quality, film grain."
    },
    19: {
        "title": "夕阳婚礼",
        "prompt": "cinematic movie still of couple exchanging vows in abandoned church at sunset. Golden light streams through stained glass windows. She wears makeshift wedding dress, he wears suit jacket. Beautiful romantic ceremony, warm sunset colors, showing love conquers all. 4K quality, film grain."
    },
    20: {
        "title": "新世界希望",
        "prompt": "cinematic movie still of couple standing together on rooftop at dawn, looking over city. Sun rises casting golden light over ruins. They hold hands ready to face future together. Hopeful beautiful composition, epic scale, showing love and hope in new world. 4K quality, film grain."
    }
}

def load_workflow():
    """加载工作流模板"""
    with open(WORKFLOW_TEMPLATE, 'r', encoding='utf-8') as f:
        return json.load(f)

def update_workflow_prompt(workflow, prompt):
    """更新工作流中的 prompt"""
    # 找到正向 prompt 节点 (id=4)
    for node in workflow['nodes']:
        if node['id'] == 4:
            node['widgets_values'][0] = prompt
            break
    return workflow

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
    # 查找视频文件
    for node_id, node_output in outputs.items():
        if 'gifs' in node_output:
            for gif_info in node_output['gifs']:
                filename = gif_info['filename']
                subfolder = gif_info.get('subfolder', '')
                
                # 构建下载 URL
                if subfolder:
                    url = f"{COMFYUI_URL}/view?filename={filename}&subfolder={subfolder}&type=output"
                else:
                    url = f"{COMFYUI_URL}/view?filename={filename}&type=output"
                
                # 下载文件
                req = requests.get(url)
                if req.status_code == 200:
                    # 保存到目标目录
                    output_filename = f"scene_{scene_num:02d}_{title}.mp4"
                    output_path = os.path.join(OUTPUT_DIR, output_filename)
                    
                    with open(output_path, 'wb') as f:
                        f.write(req.content)
                    
                    print(f"✅ 下载完成: {output_filename}")
                    return output_path
    
    print(f"❌ 未找到场景 {scene_num} 的视频文件")
    return None

def main():
    """主函数"""
    print("🧟 《我的女友是丧尸》批量视频生成")
    print("=" * 50)
    
    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 加载工作流模板
    workflow_template = load_workflow()
    
    # 生成所有场景
    results = []
    for scene_num, scene_info in SCENE_PROMPTS.items():
        print(f"\n🎬 生成场景 {scene_num}: {scene_info['title']}")
        
        # 更新 prompt
        workflow = update_workflow_prompt(workflow_template.copy(), scene_info['prompt'])
        
        # 提交生成任务
        try:
            result = queue_prompt(workflow)
            prompt_id = result['prompt_id']
            print(f"   提交成功，ID: {prompt_id}")
            
            # 等待完成
            print("   等待生成...")
            outputs = wait_for_completion(prompt_id, timeout=300)
            
            if outputs:
                # 下载视频
                video_path = download_video(outputs, scene_num, scene_info['title'])
                if video_path:
                    results.append({
                        'scene': scene_num,
                        'title': scene_info['title'],
                        'path': video_path,
                        'status': 'success'
                    })
                else:
                    results.append({
                        'scene': scene_num,
                        'title': scene_info['title'],
                        'path': None,
                        'status': 'download_failed'
                    })
            else:
                print(f"   ❌ 场景 {scene_num} 生成超时")
                results.append({
                    'scene': scene_num,
                    'title': scene_info['title'],
                    'path': None,
                    'status': 'timeout'
                })
                
        except Exception as e:
            print(f"   ❌ 场景 {scene_num} 生成失败: {e}")
            results.append({
                'scene': scene_num,
                'title': scene_info['title'],
                'path': None,
                'status': 'error',
                'error': str(e)
            })
        
        # 短暂延迟，避免过载
        time.sleep(2)
    
    # 输出结果统计
    print("\n" + "=" * 50)
    print("📊 生成统计:")
    success_count = sum(1 for r in results if r['status'] == 'success')
    print(f"   成功: {success_count}/20")
    print(f"   失败: {20 - success_count}/20")
    
    # 保存结果日志
    log_path = os.path.join(OUTPUT_DIR, "generation_log.json")
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n📁 结果日志: {log_path}")
    print(f"📂 输出目录: {OUTPUT_DIR}")
    
    if success_count == 20:
        print("\n🎉 所有场景生成完成！")
        print("下一步：使用 FFmpeg 拼接视频")
    else:
        print(f"\n⚠️ 有 {20 - success_count} 个场景生成失败，请检查日志")

if __name__ == "__main__":
    main()