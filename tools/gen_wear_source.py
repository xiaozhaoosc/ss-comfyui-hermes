# -*- coding: utf-8 -*-
"""用 my_flux_lora_v1 产出 3 段多服装参考视频(数据源)。

流程:
  1. FLUX + LoRA -> 3 张同面容不同服装/场景参考图(ohwx woman 触发词)
  2. 复制参考图到 input/wearmix_ref/(H3 LoadImage 需要)
  3. 每张参考图作 H3 ImageToVideo 首帧 -> 生成 1 段视频(锁定人脸+服装)
  4. 输出 oc_output/2026-09-14/wearmix/source/

用法: python tools/gen_wear_source.py   (需 ComfyUI 已启动)
"""
import json, urllib.request, urllib.error, uuid, os, sys, time, shutil, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h3_xinniang_v1 import BASE, build_segment, wait_done, post

COMFY_INPUT = r"D:\ai_projects\ComfyUI\input"
WARMIX_OUT = r"D:\ai_projects\ComfyUI\output\2026-09-14\wearmix"
REF_DIR_INPUT = "wearmix_ref"          # 相对 input 的目录
LORA = "my_flux_lora_v1.safetensors"
UNET = "flux1-dev-fp8.safetensors"
TRIG = "ohwx woman, "
H3_UNET = "minimax_h3_ref2va_pruned_int8_convrot.safetensors"
W, H = 544, 960          # H3 480p 竖屏
FPS = 24
LENGTH = 124             # ≈5.17s

# 3 套服装(同面容不同服装+场景) -> (FLUX提示词补充, 服装caption, 场景caption, H3动作提示词)
OUTFITS = [
    ("wearing a plain white button-up blouse and high-waisted straight blue jeans, "
     "walking on an empty city street at dusk",
     "white blouse, high-waisted blue jeans", "empty city street at dusk",
     "The woman from the reference image slowly turns her head to look at the camera, "
     "adjusts her white blouse sleeve, gentle smile, natural body movement, hair softly "
     "moving in the breeze, photorealistic, cinematic lighting, smooth motion"),
    ("wearing an oversized beige trench coat over a cream knit dress, holding a small "
     "brown handbag, standing beside a cozy cafe window",
     "beige trench coat over cream knit dress", "cozy cafe window, warm light",
     "The woman from the reference image lifts her coffee cup, takes a sip, then turns "
     "and gives a warm smile toward the camera, cozy cafe atmosphere, blurs background, "
     "photorealistic, cinematic, smooth motion"),
    ("wearing a flowing floral print summer maxi dress, standing on a sunlit park "
     "path among green trees and flowers",
     "floral print summer maxi dress", "sunlit park path among green trees",
     "The woman from the reference image turns to face the camera, pushes her hair back, "
     "laughs softly, spins slightly so the dress flares, natural graceful movement, "
     "photorealistic, cinematic lighting, smooth motion"),
]

def flux_ref_wf(prompt, seed, fn_prefix):
    """FLUX + LoRA 出单张参考图"""
    return {
        "2": {"class_type": "UNETLoader", "inputs": {"unet_name": UNET, "weight_dtype": "default"}},
        "4": {"class_type": "DualCLIPLoader", "inputs": {
            "clip_name1": "t5xxl_fp8_e4m3fn.safetensors",
            "clip_name2": "clip_l.safetensors", "type": "flux"}},
        "3": {"class_type": "LoraLoader", "inputs": {
            "model": ["2", 0], "clip": ["4", 0], "lora_name": LORA,
            "strength_model": 1.0, "strength_clip": 1.0}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["3", 1]}},
        "F": {"class_type": "FluxGuidance", "inputs": {"conditioning": ["6", 0], "guidance": 3.5}},
        "22": {"class_type": "BasicGuider", "inputs": {"model": ["3", 0], "conditioning": ["F", 0]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["10", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": fn_prefix, "images": ["8", 0]}},
        "10": {"class_type": "VAELoader", "inputs": {"vae_name": "flux-vae-bf16.safetensors"}},
        "13": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["25", 0], "guider": ["22", 0], "sampler": ["16", 0],
            "sigmas": ["17", 0], "latent_image": ["27", 0]}},
        "16": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "17": {"class_type": "BasicScheduler", "inputs": {
            "scheduler": "simple", "steps": 24, "denoise": 1.0, "model": ["2", 0]}},
        "25": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "27": {"class_type": "EmptySD3LatentImage", "inputs": {"width": 768, "height": 1024, "batch_size": 1}},
    }

def gen_flux_ref(i, outfit_desc):
    """生成第 i 张参考图, 返回保存的绝对路径"""
    os.makedirs(os.path.join(WARMIX_OUT, "ref"), exist_ok=True)
    prefix = f"2026-09-14/wearmix/ref/ref{i:02d}"
    prompt = (TRIG + "a full-length photo of a gorgeous 21-year-old East Asian young woman, " +
              "facing the camera, natural double eyelids, round puppy eyes, soft jawline, " +
              "healthy skin. " + outfit_desc +
              ", 50mm, shallow depth of field, soft daylight, photorealistic")
    wf = flux_ref_wf(prompt, 7000 + i * 10, prefix)
    r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
    pid = r.get("prompt_id")
    print(f"[FLUX] ref{i:02d} pid={pid}", flush=True)
    if not wait_done(pid):
        raise RuntimeError(f"FLUX ref{i:02d} failed")
    # SaveImage 输出到 <WARMIX_OUT>/ref/ref<NN>_00001_.png
    outdir = os.path.join(WARMIX_OUT, "ref")
    cand = sorted(f for f in os.listdir(outdir) if f.startswith(f"ref{i:02d}") and f.endswith(".png"))
    if not cand:
        raise RuntimeError(f"no FLUX ref{i:02d} output")
    return os.path.join(outdir, cand[-1])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-video", type=int, nargs="*", default=None,
                    help="只提交指定段索引(1-3)的 H3 动画, 跳过 FLUX")
    args = ap.parse_args()

    os.makedirs(COMFY_INPUT, exist_ok=True)
    os.makedirs(os.path.join(WARMIX_OUT, "source"), exist_ok=True)
    os.makedirs(os.path.join(COMFY_INPUT, REF_DIR_INPUT), exist_ok=True)

    indices = args.only_video if args.only_video else [1, 2, 3]
    ref_paths = {}

    # 1) FLUX 参考图
    if not args.only_video:
        for i in range(1, 4):
            p = gen_flux_ref(i, OUTFITS[i-1][0])
            dst = os.path.join(COMFY_INPUT, REF_DIR_INPUT, f"ref{i:02d}.png")
            shutil.copy(p, dst)
            ref_paths[i] = os.path.join(REF_DIR_INPUT, f"ref{i:02d}.png").replace("\\", "/")
            print(f"[ref{i:02d}] -> {ref_paths[i]}", flush=True)
    else:
        for i in indices:
            # 用已生成的参考图
            ref_paths[i] = os.path.join(REF_DIR_INPUT, f"ref{i:02d}.png").replace("\\", "/")

    # 2) H3 动画(分段顺序, 复用 build_segment)
    for i in indices:
        _, outfit_cap, scene_cap, motion = OUTFITS[i-1]
        prefix = f"2026-09-14/wearmix/source/outfit{i:02d}"
        seed = 5000 + i * 33
        wf = build_segment(motion, None, seed, prefix, W, H, LENGTH, ref_paths[i])
        r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
        pid = r.get("prompt_id")
        print(f"[H3] outfit{i:02d} pid={pid}", flush=True)
        if not wait_done(pid):
            print(f"[H3] outfit{i:02d} FAILED", flush=True)
            sys.exit(1)
        # 抽取末帧供下段衔接(若需要连续), 这里单段独立无需
    print("=== DONE === 参考视频已生成到 output/2026-09-14/wearmix/source/", flush=True)

if __name__ == "__main__":
    main()