#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A 路线：MiniMax H3 ref2va + H3 Fun ControlNet（MoGe 法线 control_video）动作迁移提交器。

与 tools/run_ultimate_motion_transfer.py 的区别：
  - 模型链上插入 ModelPatchLoader + MiniMaxH3FunControlNetApply（**逐帧几何约束**，
    参数照抄 Aiden 原版：strength 0.45 / start 0.0 / end 0.75，且位于 BlockSparseAttention 之前）；
  - 控制信号 = MoGe 法线图（`normal_opengl`），并**同时**作为 `ref_video` 喂给 H3 语义塔：
    这样"动作几何"参与条件，而服饰外观只来自 `ref_image`（避免参考视频里的女仆装污染）。
  - 关闭控制网时即为原"纯 ref2va"基线，便于 A/B 对照。

只提交 + 汇报，**不轮询**；提交后用 GET /history/<prompt_id> 手动查询。
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

COMFY_URL = "http://127.0.0.1:8188"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"

PROMPT = (
    "subject_definitions:\n"
    "<Subject 1> is the target character in <Picture 1>: a gorgeous young Asian woman with delicate facial "
    "features, bright expressive eyes, a captivating sweet smile, and long dark brown wavy hair cascading over "
    "her shoulders. She has a slender graceful figure with bare midriff and long smooth legs, wearing the "
    "complete authentic four-piece lingerie ensemble exactly as depicted in <Picture 1>: 1) a delicate pink "
    "floral embroidered bra with thin black straps and lace trim, 2) matching low-rise pink and black lace "
    "panties, 3) thin black vertical garter suspension straps along her thighs, and 4) wide black floral lace "
    "thigh bands encircling each upper thigh.\n"
    "<Subject 2> is the dance performance in <Video 1>.\n"
    "<Video 1> is a grayscale geometry/normal reference: it encodes ONLY the body's per-frame 3D shape, "
    "orientation and limb positions. Read the motion from it frame by frame and ignore its surface appearance.\n\n"
    "summary:\n"
    "[reference generation] Reproduce <Video 1>'s per-frame body geometry and choreography — every turn, bend, "
    "side-facing pose and limb crossing, with its exact timing and rhythm — while strictly keeping <Subject 1>'s "
    "face, hair, body shape and her four-piece lingerie outfit from <Picture 1>.\n\n"
    "detailed_description:\n"
    "A photorealistic full-motion video of <Subject 1> dancing in medium full-body framing, synchronized to the "
    "music. Follow the geometry reference pose-for-pose, frame-for-frame, preserving small motions and pauses "
    "without skipping, compressing or re-choreographing. Keep the pink floral lace bra, matching panties, thin "
    "black vertical garter straps and wide black lace thigh bands from <Picture 1> intact in every frame. "
    "Tidy warm indoor room, soft natural light, crisp detail, no blur, no distortion, no watermark."
)


def free_vram():
    try:
        q = json.load(urllib.request.urlopen(f"{COMFY_URL}/queue"))
        if q.get("queue_running") or q.get("queue_pending"):
            print("[VRAM] 队列非空，跳过 /free（避免打断排队中的任务）", flush=True)
            return
    except Exception:
        pass
    try:
        data = json.dumps({"unload_models": True, "free_memory": True}).encode("utf-8")
        req = urllib.request.Request(f"{COMFY_URL}/free", data=data,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req)
        print("[VRAM] /free 已释放模型缓存", flush=True)
    except Exception as e:
        print(f"[VRAM WARN] /free 失败: {e}", flush=True)


def wait_for_server(timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(f"{COMFY_URL}/system_stats") as r:
                if r.status == 200:
                    print("ComfyUI 服务已就绪", flush=True)
                    return True
        except Exception:
            time.sleep(2)
    return False


def submit(prompt_dict, client_id):
    payload = json.dumps({"prompt": prompt_dict, "client_id": client_id}).encode("utf-8")
    req = urllib.request.Request(f"{COMFY_URL}/prompt", data=payload,
                                headers={"Content-Type": "application/json"})
    try:
        res = json.loads(urllib.request.urlopen(req).read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return None, e.read().decode("utf-8")
    if res.get("node_errors"):
        return None, json.dumps(res["node_errors"], ensure_ascii=False)[:3000]
    return res.get("prompt_id"), None


def build(use_controlnet=True, use_sparse=True, vae_name="minimax_h3_video_vae_int8_convrot.safetensors",
          unet="minimax_h3_ref2va_pruned_int8_convrot.safetensors",
          lora="minimax_h3_DMAD_4step_full_lora_avg_rank_39_bf16.safetensors",
          ref_img="jia_ref.jpg", ref_vid="runcha_dance.mp4", length=277, mp=0.5,
          moge="moge_3_vitl_fp16.safetensors", cn_strength=0.45, cn_end=0.75,
          steps=8, sampler="euler", white_model_ref=True, bg_w=656, bg_h=1164):
    p = {
        "1": {"class_type": "LoadImage", "inputs": {"image": ref_img}},
        "2": {"class_type": "VHS_LoadVideo",
              "inputs": {"video": ref_vid, "force_rate": 24, "custom_width": 0, "custom_height": 0,
                         "frame_load_cap": length, "skip_first_frames": 0, "select_every_nth": 1,
                         "format": "AnimateDiff"}},
        "10": {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": "default"}},
        "11": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["10", 0], "shift_video": 12.0, "shift_audio": 3.0}},
        "12": {"class_type": "ModelAttentionBackend", "inputs": {"model": ["11", 0], "attention": "comfy kitchen attention"}},
        # 双 LoRA 贴齐 Aiden 原版：Motion_Repair_V2(0.3) 动作修复 + 4步 turbo(1.0)
        "13": {"class_type": "LoraLoaderModelOnly",
               "inputs": {"model": ["12", 0], "lora_name": "Motion_Repair_V2.safetensors", "strength_model": 0.3}},
        "13b": {"class_type": "LoraLoaderModelOnly",
                "inputs": {"model": ["13", 0], "lora_name": lora, "strength_model": 1.0}},
        "14": {"class_type": "MiniMaxChunkFeedForward", "inputs": {"model": ["13b", 0], "chunks": 4, "seq_threshold": 4096}},
        "16": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_minimax_h3_int8_convrot.safetensors", "type": "minimax", "device": "default"}},
        "17": {"class_type": "VAELoader", "inputs": {"vae_name": vae_name}},
        "18": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
        "19": {"class_type": "ResolutionSelector", "inputs": {"aspect_ratio": "9:16 (Portrait Widescreen)", "megapixels": mp, "multiple": 32}},
        "20": {"class_type": "PrimitiveStringMultiline", "inputs": {"value": PROMPT}},
    }
    # 控制分支：Aiden 白模合成（BiRefNet 抠图 -> MoGe 法线 -> 按人像掩码贴回灰底）
    control_src = None
    if use_controlnet:
        if white_model_ref:
            # 复刻 Aiden #100(RMBG)->#68->#67->#92 链路（核心节点实现）：
            # 驱动帧 -> BiRefNet 人像 mask -> 原帧贴灰底(#878787) -> MoGe 法线 -> 法线按 mask 贴回灰底
            p["50"] = {"class_type": "LoadBackgroundRemovalModel", "inputs": {"bg_removal_name": "BiRefNet-general.safetensors"}}
            p["51"] = {"class_type": "RemoveBackground", "inputs": {"bg_removal_model": ["50", 0], "image": ["2", 0]}}
            p["52"] = {"class_type": "SolidMask", "inputs": {"value": 0.529, "width": bg_w, "height": bg_h}}
            p["53"] = {"class_type": "MaskToImage", "inputs": {"mask": ["52", 0]}}
            p["55"] = {"class_type": "ImageCompositeMasked",
                       "inputs": {"destination": ["53", 0], "source": ["2", 0], "x": 0, "y": 0,
                                  "resize_source": True, "mask": ["51", 0]}}
            p["44"] = {"class_type": "LoadMoGeModel", "inputs": {"model_name": moge}}
            p["45"] = {"class_type": "MoGeInference",
                       "inputs": {"moge_model": ["44", 0], "image": ["55", 0],
                                  "resolution_level": 9, "fov_x_degrees": 0.0, "batch_size": 4,
                                  "force_projection": True, "apply_mask": True, "refine_steps": 3}}
            p["46"] = {"class_type": "MoGeRender", "inputs": {"moge_geometry": ["45", 0], "output": "normal_opengl"}}
            p["54"] = {"class_type": "ImageCompositeMasked",
                       "inputs": {"destination": ["53", 0], "source": ["46", 0], "x": 0, "y": 0,
                                  "resize_source": True, "mask": ["51", 0]}}
            control_src = ["54", 0]
        else:
            p["44"] = {"class_type": "LoadMoGeModel", "inputs": {"model_name": moge}}
            p["45"] = {"class_type": "MoGeInference",
                       "inputs": {"moge_model": ["44", 0], "image": ["2", 0],
                                  "resolution_level": 9, "fov_x_degrees": 0.0, "batch_size": 4,
                                  "force_projection": True, "apply_mask": True, "refine_steps": 3}}
            p["46"] = {"class_type": "MoGeRender", "inputs": {"moge_geometry": ["45", 0], "output": "normal_opengl"}}
            control_src = ["46", 0]
        p["47"] = {"class_type": "ModelPatchLoader", "inputs": {"name": "minimax_h3_fun_controlnet_union_2.0_pruned_int8_convrot.safetensors"}}
        p["48"] = {"class_type": "MiniMaxH3FunControlNetApply",
                   "inputs": {"model": ["14", 0], "model_patch": ["47", 0], "vae": ["17", 0],
                              "strength": cn_strength, "start_percent": 0.0, "end_percent": cn_end,
                              "control_video": control_src}}
    # 主干模型链尾（控制网之后接稀疏注意力，与 Aiden 原版顺序一致）
    model_tail = ["48", 0] if use_controlnet else ["14", 0]
    if use_sparse:
        p["15"] = {"class_type": "BlockSparseAttention",
                   "inputs": {"model": model_tail, "selection": "sol-attn", "selection.tau": 1.1,
                              "start_percent": 0.2, "end_percent": 1.0, "dense_blocks": "",
                              "min_tokens": 12288, "extra_tokens": 256,
                              "sink_conditioning": "exact_kv_and_rows", "verbose": False}}
        model_tail = ["15", 0]

    ref_videos = {"ref_video_0": control_src} if (use_controlnet and control_src) else {"ref_video_0": ["2", 0]}
    p["21"] = {"class_type": "MiniMaxH3ReferenceToVideo",
               "inputs": {"clip": ["16", 0], "vae": ["17", 0], "audio_vae": ["18", 0],
                          "ref_images": {"ref_image_0": ["1", 0]},
                          "ref_videos": ref_videos,
                          "ref_video_audios": {"ref_video_audio_0": ["2", 2]},
                          "prompt": ["20", 0], "width": ["19", 0], "height": ["19", 1],
                          "length": length, "ref_image_size": "max"}}
    p["23"] = {"class_type": "BasicScheduler", "inputs": {"model": model_tail, "scheduler": "simple", "steps": steps, "denoise": 1.0}}
    p["24"] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": sampler}}
    p["25"] = {"class_type": "RandomNoise", "inputs": {"noise_seed": 42}}
    p["22"] = {"class_type": "BasicGuider", "inputs": {"model": model_tail, "conditioning": ["21", 0]}}
    p["30"] = {"class_type": "SamplerCustomAdvanced",
               "inputs": {"noise": ["25", 0], "guider": ["22", 0], "sampler": ["24", 0],
                          "sigmas": ["23", 0], "latent_image": ["21", 1]}}
    p["31"] = {"class_type": "VAEDecode", "inputs": {"samples": ["30", 0], "vae": ["17", 0]}}
    p["33"] = {"class_type": "VHS_VideoCombine",
               "inputs": {"images": ["31", 0], "audio": ["2", 2], "frame_rate": 24.0, "loop_count": 0,
                          "filename_prefix": "PLACEHOLDER", "format": "video/h264-mp4",
                          "pix_fmt": "yuv420p", "crf": 16, "save_metadata": False,
                          "trim_to_audio": False, "pingpong": False, "save_output": True}}
    return p


def main():
    ap = argparse.ArgumentParser(description="H3 + Fun ControlNet（白模法线）动作迁移提交器")
    ap.add_argument("--no-controlnet", action="store_true", help="关闭控制网（纯 ref2va 基线对照）")
    ap.add_argument("--no-white-model-ref", action="store_true",
                    help="ref_video/control 直喂法线图（旧做法）；默认用 BiRefNet+MoGe 合成的灰底白模（Aiden #92 做法）")
    ap.add_argument("--length", type=int, default=277)
    ap.add_argument("--mp", type=float, default=0.5)
    ap.add_argument("--steps", type=int, default=8, help="采样步数（Aiden 原版 8；4 步下 ControlNet 不咬合）")
    ap.add_argument("--sampler", default="euler", help="采样器（Aiden 原版 euler）")
    ap.add_argument("--cn-strength", type=float, default=0.6)
    ap.add_argument("--cn-end", type=float, default=0.9)
    ap.add_argument("--bg-w", type=int, default=656, help="白模灰底宽度（=驱动视频宽）")
    ap.add_argument("--bg-h", type=int, default=1164, help="白模灰底高度（=驱动视频高）")
    ap.add_argument("--moge", default="moge_3_vitl_fp16.safetensors")
    ap.add_argument("--ref-image", default=None)
    ap.add_argument("--video", default=None)
    ap.add_argument("--tag", default=None, help="产物子目录名（默认 h3_controlnet / h3_ref2va_base）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--dump-api", default=None, help="只把 API 格式工作流写出到该路径并退出（供 api2canvas 转 UI 版）")
    args = ap.parse_args()

    tag = args.tag or ("h3_ref2va_base" if args.no_controlnet else "h3_controlnet")
    outdir = os.path.join(ROOT, "output", date.today().strftime("%Y-%m-%d"), "motion_optimize", tag)
    os.makedirs(outdir, exist_ok=True)
    ref_img = os.path.basename(args.ref_image) if args.ref_image else "jia_ref.jpg"
    ref_vid = os.path.basename(args.video) if args.video else "runcha_dance.mp4"

    p = build(use_controlnet=not args.no_controlnet, length=args.length, mp=args.mp,
              moge=args.moge, cn_strength=args.cn_strength, cn_end=args.cn_end,
              ref_img=ref_img, ref_vid=ref_vid, steps=args.steps, sampler=args.sampler,
              white_model_ref=not args.no_white_model_ref, bg_w=args.bg_w, bg_h=args.bg_h)
    p["33"]["inputs"]["filename_prefix"] = "%s/motion_optimize/%s/jia_h3cn" % (
        date.today().strftime("%Y-%m-%d"), tag)
    print("节点数 = %d, 控制网 = %s, 白模ref = %s, 步数 = %d, 长度 = %d, 画布 = %sMP"
          % (len(p), "OFF" if args.no_controlnet else "ON",
             "OFF" if args.no_white_model_ref else "ON", args.steps, args.length, args.mp), flush=True)

    if args.dump_api:
        with open(args.dump_api, "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False, indent=2)
        print("已写出 API 工作流: %s（供 tools/api2canvas.py 转 UI 版）" % args.dump_api, flush=True)
        return 0

    if args.dry_run:
        info = json.load(urllib.request.urlopen(f"{COMFY_URL}/object_info"))
        miss = sorted({v["class_type"] for v in p.values()} - set(info))
        print("缺失节点类型:", miss if miss else "无")
        return 0 if not miss else 1

    if not wait_for_server(60):
        print("ComfyUI 未就绪"); return 1
    free_vram()
    pid, err = submit(p, "h3-%s" % tag)
    if not pid:
        print("[提交失败]", err); return 1
    sec = 280 * args.steps / 4.0
    print("  prompt_id    : %s" % pid)
    print("  产物目录     : %s" % outdir)
    print("  预计完成时间 : 约 %.1f 分钟（%d 步 + 稀疏注意力，含模型加载）" % (sec / 60.0, args.steps))
    print("  本次不轮询，请用 GET /history/%s 手动查询。" % pid)
    rec = {"prompt_id": pid, "tag": tag, "controlnet": not args.no_controlnet,
           "white_model_ref": not args.no_white_model_ref, "steps": args.steps,
           "sampler": args.sampler, "length": args.length, "mp": args.mp,
           "cn_strength": args.cn_strength, "cn_end": args.cn_end, "moge": args.moge,
           "ref_image": ref_img, "video": ref_vid, "out_dir": outdir}
    with open(os.path.join(outdir, "submit.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
