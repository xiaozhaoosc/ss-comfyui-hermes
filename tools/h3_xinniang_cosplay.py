#!/usr/bin/env python3
"""古风新娘 Cosplay 视频 - H3 t2v 单段生成（960×544，124帧 ≈ 5.2s）

内容：红色抹胸金纹紧身衣 + 流苏短裙 + 肉色长筒袜黑绑带 + 红色凤冠白花珠串，
静态走秀姿态（身体微侧、一手轻抚腹部），镜头缓慢推进，微笑逐渐加深的微表情变化。

用法:
  python tools/h3_xinniang_cosplay.py        # 提交 t2v 单段
"""
import json, urllib.request, uuid, sys

BASE = "http://127.0.0.1:8188"
OUT_PREFIX = "xinniang_cosplay/seg1"

STYLE_SUFFIX = (", real photography, ultra high detail, cinematic lighting, "
                "soft natural light, saturated colors, shallow depth of field, "
                "film grain, high-class fashion showcase, no AI artifacts, "
                "no deformed hands, no extra limbs, clean composition")

PROMPT = (
    "A stunning young East Asian bride in traditional Chinese wedding costume performing a "
    "graceful static catwalk pose showcase, not dancing. She wears a red strapless "
    "tight-fitting short dress with golden brocade embroidery on the chest and a low "
    "neckline, a matching red short skirt with golden tassels along the hem, "
    "flesh-toned thigh-high stockings with a black strap decoration on the outer thigh. "
    "An ornate red phoenix crown headdress studded with delicate white flowers and bead "
    "strings adorns her head; her long lustrous black hair flows down over her shoulders "
    "with part elegantly swept up beneath the crown, and a simple pendant necklace hangs "
    "at her neck. Her body leans slightly to one side, one hand gently resting on her "
    "abdomen and the other hanging naturally, a confident yet coquettish pose. She wears a "
    "sweet smile with bright playful luminous eyes; as the camera slowly pushes in, her "
    "smile gradually deepens and her gaze turns lively and expressive, cute and charming. "
    "Background music is a cheerful female-sung Japanese pop song, light and upbeat with "
    "a strong rhythm, creating a relaxed and joyful atmosphere."
) + STYLE_SUFFIX

NEG = "blurry, low quality, deformed, cartoon, anime style, extra fingers, extra limbs, watermark, text, dancing motion"

def post(path, payload):
    req = urllib.request.Request(f"{BASE}{path}", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode(errors='replace')[:800]}")
        raise

def build():
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors", "type": "minimax"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "4": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["1", 0], "shift_video": 12.0, "shift_audio": 3.0}},
        "5": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
            "clip": ["2", 0], "vae": ["3", 0], "prompt": PROMPT,
            "width": 960, "height": 544, "length": 124}},
        "6": {"class_type": "KSampler", "inputs": {
            "model": ["4", 0], "seed": 20260905, "steps": 28, "cfg": 1.0,
            "sampler_name": "euler", "scheduler": "simple",
            "positive": ["5", 0], "negative": ["5", 0], "latent_image": ["5", 1], "denoise": 1.0}},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["3", 0]}},
        "8": {"class_type": "VHS_VideoCombine", "inputs": {
            "images": ["7", 0], "frame_rate": 24.0, "loop_count": 0,
            "filename_prefix": OUT_PREFIX, "format": "video/h264-mp4",
            "pingpong": False, "save_output": True}},
    }

if __name__ == '__main__':
    wf = build()
    r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
    pid = r.get("prompt_id")
    print(f"✓ 古风新娘 Cosplay 单段已提交 pid={pid}")
    if pid:
        with open(r"D:\ai_projects\ComfyUI\tools\h3_xinniang_pid.json", "w") as f:
            json.dump({"pid": pid}, f)