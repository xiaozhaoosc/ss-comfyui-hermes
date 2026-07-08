#!/usr/bin/env python3
"""
我的女友是丧尸 - 自动化生成流水线
功能：视频生成 + TTS配音 + 字幕叠加 + 合并输出
"""
import json
import os
import subprocess
import urllib.request
import time

WORKFLOW_FILE = 'D:/ai_projects/ComfyUI/workflows/zombie_girlfriend_script.json'
OUTPUT_DIR = 'D:/OLLAMA_MODELS/output/wan2/我的女友是丧尸'
FINAL_DIR = 'D:/OLLAMA_MODELS/output/wan2/我的女友是丧尸_成品'

def load_script():
    with open(WORKFLOW_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_video(scene, character_desc):
    """提交视频生成任务到 ComfyUI"""
    prompt = {
        '4': {'class_type': 'CLIPTextEncode', 'inputs': {
            'text': scene['prompt'] + ', ' + character_desc,
            'clip': ['2', 0]}},
        '5': {'class_type': 'CLIPTextEncode', 'inputs': {
            'text': 'low quality, blurry, distorted face, western face, blonde hair, watermark',
            'clip': ['2', 0]}},
        '2': {'class_type': 'CLIPLoader', 'inputs': {'clip_name': 'umt5xxl_encoder.safetensors', 'type': 'wan'}},
        '1': {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'wan2.1-t2v-1.3b\\\\diffusion_pytorch_model.safetensors', 'weight_dtype': 'default'}},
        '3': {'class_type': 'VAELoader', 'inputs': {'vae_name': 'Wan2.1_VAE.pth'}},
        '6': {'class_type': 'EmptyLatentImage', 'inputs': {'width': 832, 'height': 480, 'batch_size': 11}},
        '7': {'class_type': 'KSampler', 'inputs': {
            'seed': 42, 'steps': 25, 'cfg': 7.0, 'sampler_name': 'euler', 'scheduler': 'normal', 'denoise': 1.0,
            'model': ['1', 0], 'positive': ['4', 0], 'negative': ['5', 0], 'latent_image': ['6', 0]}},
        '8': {'class_type': 'VAEDecode', 'inputs': {'samples': ['7', 0], 'vae': ['3', 0]}},
        '9': {'class_type': 'VHS_VideoCombine', 'inputs': {
            'images': ['8', 0], 'frame_rate': 16, 'loop_count': 0,
            'filename_prefix': scene['id'],
            'format': 'video/h264-mp4', 'pingpong': False, 'save_output': True}}
    }
    
    req = urllib.request.Request('http://localhost:8188/prompt',
        data=json.dumps({'prompt': prompt}).encode(),
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as r:
            result = json.loads(r.read())
            return result.get('prompt_id')
    except Exception as e:
        print(f'  ❌ 提交失败: {e}')
        return None

def wait_for_completion(prompt_id, timeout=600):
    """等待任务完成"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(f'http://localhost:8188/history/{prompt_id}') as r:
                data = json.loads(r.read())
                for key, val in data.items():
                    status = val.get('status', {}).get('status_str', '')
                    if status == 'success':
                        return True
                    elif status == 'error':
                        return False
        except:
            pass
        time.sleep(10)
    return False

def generate_tts(text, output_path):
    """生成 TTS 音频（使用 Hermes TTS）"""
    # 这里需要调用 Hermes 的 TTS 功能
    # 暂时用占位符
    print(f'  TTS: {text[:30]}...')
    return output_path

def add_subtitle(video_path, subtitle_text, output_path):
    """添加字幕"""
    # 转义特殊字符
    escaped = subtitle_text.replace("'", "'\\''").replace(":", "\\:")
    
    cmd = [
        'ffmpeg', '-y', '-i', video_path,
        '-vf', f"drawtext=text='{escaped}':fontfile=C\\\\:/Windows/Fonts/msyh.ttc:fontsize=28:fontcolor=white:borderw=2:bordercolor=black:x=(w-text_w)/2:y=h-60",
        '-c:a', 'copy', output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0

def merge_video_audio(video_path, audio_path, output_path):
    """合并视频和音频"""
    cmd = [
        'ffmpeg', '-y', '-i', video_path, '-i', audio_path,
        '-c:v', 'copy', '-c:a', 'aac', '-shortest', output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0

def concat_videos(video_list, output_path):
    """拼接多个视频"""
    # 创建临时文件列表
    list_file = output_path + '.txt'
    with open(list_file, 'w') as f:
        for v in video_list:
            f.write(f"file '{v}'\n")
    
    cmd = [
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', list_file,
        '-c', 'copy', output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    os.remove(list_file)
    return result.returncode == 0

def main():
    os.makedirs(FINAL_DIR, exist_ok=True)
    
    script = load_script()
    character = script['character']
    
    print(f"=== {script['title']} 自动生成 ===\n")
    
    for ep in script['episodes']:
        ep_num = ep['episode']
        ep_title = ep['title']
        print(f"\n📺 第{ep_num}集：{ep_title}")
        print("-" * 40)
        
        ep_videos = []
        
        for scene in ep['scenes']:
            scene_id = scene['id']
            print(f"\n🎬 {scene_id}: {scene['subtitle'][:20]}...")
            
            # 1. 生成视频
            print(f"  生成视频中...")
            prompt_id = generate_video(scene, character['description'])
            if prompt_id:
                success = wait_for_completion(prompt_id)
                if success:
                    video_file = f"{OUTPUT_DIR}/{scene_id}_00001.mp4"
                    print(f"  ✅ 视频生成完成")
                    ep_videos.append(video_file)
                else:
                    print(f"  ❌ 视频生成失败")
                    continue
            
            # 2. 生成 TTS
            tts_file = f"{FINAL_DIR}/{scene_id}_tts.mp3"
            generate_tts(scene['tts_text'], tts_file)
            
            # 3. 添加字幕
            if os.path.exists(video_file):
                sub_file = f"{FINAL_DIR}/{scene_id}_sub.mp4"
                add_subtitle(video_file, scene['subtitle'], sub_file)
                
                # 4. 合并音视频
                final_file = f"{FINAL_DIR}/{scene_id}_final.mp4"
                if os.path.exists(tts_file):
                    merge_video_audio(sub_file, tts_file, final_file)
                else:
                    os.rename(sub_file, final_file)
                
                print(f"  ✅ 完成: {final_file}")
        
        # 5. 拼接整集
        if ep_videos:
            ep_final = f"{FINAL_DIR}/EP{ep_num}_{ep_title}.mp4"
            # 这里需要等所有场景完成后再拼接
            print(f"\n📦 整集拼接: {ep_final}")

if __name__ == '__main__':
    main()
