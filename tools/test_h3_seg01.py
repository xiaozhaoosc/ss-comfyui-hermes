#!/usr/bin/env python3
"""烽火边关 24 段 × 5s 验证（1 段试跑）

基于 fenghuo 7 段实证过的 API 链路（见 api2canvas.py），仅改：
- load_clips 模版简化成命令行参数动态
- 960×544 (比 672×384 大 ~2 倍显示区域)
- 28 步采样
- 124 帧 = 5.17s (标准 17k+5)
- 首段无 first_frame（t2v 起点）

用法: python3 tools/test_h3_seg01.py
"""
import json, urllib.request, uuid, time, sys, os

BASE = "http://127.0.0.1:8188"
OUT = r"D:\ai_projects\ComfyUI\output\fenghuo_24segs"
os.makedirs(OUT, exist_ok=True)

CHARACTER = "年轻中国古代女将，深色重甲，头戴战盔，黑色长发，神情冷峻坚定，手握长刀，骑黑色战马。"
STYLE = ( "史诗级写实电影预告片质感，真实电影摄影，超高细节，真实皮肤毛发，真实盔甲冷兵器，"
 "体积光，烟尘风沙火光，冷暖对比，浅景深，电影级调色，IMAX史诗战争片。镜头自然流畅。"
 "避免AI生成感、人物变形、手部异常、武器结构错误、现代建筑、现代武器、现代服装、卡通游戏CG感。")

def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    # 把详细HTTP错误打印出来
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        print(f"=== HTTP {e.code} 错误内容: {e.read().decode()}[:1500] ===")
        raise

# segment_01 的 prompt + 风格锚定
seg_prompt = "超远景，苍茫中国北方边疆，夕阳即将落下，巨大古代边城矗立在荒漠与群山之间，城墙上旌旗被狂风吹动，远处烽火台燃起狼烟，镜头缓慢向前推进，气氛压抑肃杀。"
prompt = seg_prompt + " " + STYLE

wf = {
    "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
    "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors", "type": "minimax"}},
    "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
    "4": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["1", 0], "shift_video": 12.0, "shift_audio": 3.0}},
    # MiniMax i2v 节点：5
    "5": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
        "clip": ["2", 0], "vae": ["3", 0],
        "prompt": prompt,
        "width": 960, "height": 544, "length": 124}},
    "6": {"class_type": "KSampler", "inputs": {
        "model": ["4", 0], "seed": 42, "steps": 28, "cfg": 1.0,
        "sampler_name": "euler", "scheduler": "simple",
        "positive": ["5", 0], "negative": ["5", 0], "latent_image": ["5", 1], "denoise": 1.0}},
    "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["3", 0]}},
    "10": {"class_type": "VHS_VideoCombine", "inputs": {
        "images": ["7", 0], "frame_rate": 24.0, "loop_count": 0,
        "filename_prefix": "fenghuo_24segs/seg01", "format": "video/h264-mp4",
        "pingpong": False, "save_output": True}},
}

print("提交 seg01_0-5s_边城远景（960×544×28步×124帧≈5.17s）")
r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
pid = r.get('prompt_id')
print(f"✓ PID={pid}")
with open(r'D:\ai_projects\ComfyUI\tools\h3_seg01_pid.txt', 'w') as f:
    f.write(pid)
print("预计 ~10 分钟（960×544 比原 672×384 大 2 倍， 24 段的 task 1)")
