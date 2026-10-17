#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A 路线 v3：从 Aiden 原版 71 节点工作流适配本机（区别于 v1/v2 的从零简化链）。

保留 Aiden 原版的结构主干：
  - SelfLiftAvatarH3TST（tau 0.2 谱张力校正）→ SelfLiftAvatarH3Sampler
    （6/8 NFE 双阶段：低分辨 6 步 → h3_upscaler_lms 提升 → 高分辨收尾）
  - 音频遮罩组：VAEEncodeAudio → SetLatentNoiseMask(SolidMask 0) → LTXVConcatAVLatent
  - FunControlNetApply(0.45/0/0.75) 置于 BlockSparse 之前
  - ConditioningZeroOut 作负向

仅替换缺失插件（全部有本机验证过的等价物）：
  H3SigmaRefiner → BasicScheduler(simple, 8)   [cosine 间距的近似，已注明偏差]
  RMBG-2.0       → 核心 LoadBackgroundRemovalModel(BiRefNet) + RemoveBackground
  ImageBlend V2  → 核心 ImageCompositeMasked（灰底 #878787 合成）
  LayerStyle 缩放 → 核心 ImageScale
  VOSR2 / MMH3 放大支路 → 整支路删除（16GB 不可行，出片后外挂超分）
  easy positive  → PrimitiveStringMultiline

只提交不轮询；产物用 tools/motion_fidelity_qa.py 做四闸门验收。
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

COMFY_URL = "http://127.0.0.1:8188"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROMPT = (
    "subject_definitions:\n"
    "<Subject 1> is the target character in <Picture 1>: a gorgeous young Asian woman with delicate facial "
    "features, bright expressive eyes, a captivating sweet smile, and long dark brown wavy hair, wearing the "
    "complete authentic four-piece lingerie ensemble exactly as in <Picture 1>: pink floral embroidered bra, "
    "matching low-rise lace panties, thin black vertical garter straps, and wide black lace thigh bands.\n"
    "<Subject 2> is the dance performance in <Video 1>.\n"
    "<Video 1> is a grayscale geometry reference: the figure is rendered as a normal-mapped white model. It "
    "encodes ONLY per-frame body 3D shape, orientation and limb positions. Read the motion from it frame by "
    "frame; ignore its surface appearance entirely.\n\n"
    "summary:\n"
    "[reference generation] Reproduce <Video 1>'s per-frame body geometry and choreography — every turn, bend, "
    "side-facing pose and limb crossing, exact timing and rhythm — while strictly keeping <Subject 1>'s face, "
    "hair, body and her four-piece lingerie outfit from <Picture 1>.\n\n"
    "detailed_description:\n"
    "Photorealistic full-motion video of <Subject 1> dancing in medium full-body framing, synchronized to the "
    "music. Follow the geometry reference pose-for-pose, frame-for-frame, preserving small motions and pauses "
    "without skipping or re-choreographing. Keep the pink lace bra, panties, black garter straps and thigh "
    "bands from <Picture 1> intact. Tidy warm indoor room, soft natural light, crisp detail, no distortion."
)


PROMPT_NATURAL = (
    "subject_definitions:\n"
    "<Subject 1> is the target character in <Picture 1>: a gorgeous young Asian woman with delicate facial "
    "features, bright expressive eyes, a captivating sweet smile, and long dark brown wavy hair, wearing the "
    "complete authentic four-piece lingerie ensemble exactly as in <Picture 1>: pink floral embroidered bra, "
    "matching low-rise lace panties, thin black vertical garter straps, and wide black lace thigh bands.\n"
    "<Subject 2> is the dance performance, arm choreography, hip bouncing rhythm and facial expressions in <Video 1>.\n"
    "<Video 1> is the motion source video. It provides the full choreography sequence, tempo, rhythmic hip "
    "bounces, hand gestures and body turns. Its costume and background must be completely ignored and discarded.\n\n"
    "summary:\n"
    "[reference generation] Faithfully transfer <Subject 2>'s complete dance choreography from <Video 1> to "
    "<Subject 1>, preserving the exact timing, rhythm and musical synchronization while strictly maintaining "
    "<Subject 1>'s facial appearance, long wavy hair, body shape and her authentic four-piece lingerie set "
    "from <Picture 1>.\n\n"
    "detailed_description:\n"
    "A high quality, photorealistic full-motion video of <Subject 1> dancing gracefully in medium full-body "
    "framing, synchronized to the music. Her face and body faithfully replicate <Picture 1> in every frame. "
    "She wears the complete authentic four-piece outfit: the pink floral lace bra, matching panties, visible "
    "thin black vertical garter straps, and wide black lace thigh bands. Tidy warm indoor room, soft natural "
    "lighting, fluid motion, crisp detail, no blur, no distortion, no watermarks."
)


def free_vram():
    try:
        q = json.load(urllib.request.urlopen(f"{COMFY_URL}/queue"))
        if q.get("queue_running") or q.get("queue_pending"):
            print("[VRAM] 队列非空，跳过 /free", flush=True)
            return
    except Exception:
        pass
    try:
        data = json.dumps({"unload_models": True, "free_memory": True}).encode("utf-8")
        urllib.request.urlopen(urllib.request.Request(
            f"{COMFY_URL}/free", data=data, headers={"Content-Type": "application/json"}))
        print("[VRAM] /free 已执行", flush=True)
    except Exception as e:
        print(f"[VRAM WARN] {e}", flush=True)


def build(length=73, mp=0.3, cn_strength=0.45, cn_end=0.75, steps=8,
          transition_step=6, ref_img="jia_ref.jpg", ref_vid="runcha_dance.mp4",
          moge="moge_3_vitl_fp16.safetensors", ref_video_mode="white_model",
          use_controlnet=True, prompt_mode="natural"):
    p = {
        # ---- 参考图 / 驱动视频 ----
        "1": {"class_type": "LoadImage", "inputs": {"image": ref_img}},
        "2": {"class_type": "VHS_LoadVideo",
              "inputs": {"video": ref_vid, "force_rate": 24, "custom_width": 0, "custom_height": 0,
                         "frame_load_cap": length, "skip_first_frames": 0, "select_every_nth": 1,
                         "format": "AnimateDiff"}},
        # ---- 白模合成支路（核心节点复刻 Aiden #32→#100→#68→#67→#92）----
        "30": {"class_type": "ImageScale",
               "inputs": {"image": ["2", 0], "upscale_method": "lanczos", "width": 415, "height": 736,
                          "crop": "disabled"}},
        "50": {"class_type": "LoadBackgroundRemovalModel", "inputs": {"bg_removal_name": "BiRefNet-general.safetensors"}},
        "51": {"class_type": "RemoveBackground", "inputs": {"bg_removal_model": ["50", 0], "image": ["30", 0]}},
        # 灰底画布必须是 length 帧的批次：comfy 的 composite() 返回 destination，
        # 批长 = destination.shape[0]。用单帧灰底（SolidMask→MaskToImage）会把整条
        # 白模支路压成 1 帧 → ref_video 不足 5 帧直接报错、control_video 退化成单张重复。
        "53": {"class_type": "EmptyImage",
               "inputs": {"width": 415, "height": 736, "batch_size": length, "color": 0x878787}},
        "55": {"class_type": "ImageCompositeMasked",
               "inputs": {"destination": ["53", 0], "source": ["30", 0], "x": 0, "y": 0,
                          "resize_source": True, "mask": ["51", 0]}},
        "44": {"class_type": "LoadMoGeModel", "inputs": {"model_name": moge}},
        "45": {"class_type": "MoGeInference",
               "inputs": {"moge_model": ["44", 0], "image": ["55", 0], "resolution_level": 9,
                          "fov_x_degrees": 0.0, "batch_size": 4, "force_projection": True,
                          "apply_mask": True, "refine_steps": 3}},
        "46": {"class_type": "MoGeRender", "inputs": {"moge_geometry": ["45", 0], "output": "normal_opengl"}},
        "54": {"class_type": "ImageCompositeMasked",
               "inputs": {"destination": ["53", 0], "source": ["46", 0], "x": 0, "y": 0,
                          "resize_source": True, "mask": ["51", 0]}},
        # ---- 加载器 ----
        "5": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
        "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_minimax_h3_int8_convrot.safetensors", "type": "minimax", "device": "default"}},
        "2v": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_int8_convrot.safetensors"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
        # ---- 模型链（Aiden 顺序：SigmaShift→Attn→LoRA×2→Chunk→ControlNet→BlockSparse→TST）----
        "7": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["5", 0], "shift_video": 12.0, "shift_audio": 3.0}},
        "8": {"class_type": "ModelAttentionBackend", "inputs": {"model": ["7", 0], "attention": "comfy kitchen attention"}},
        "6": {"class_type": "LoraLoaderModelOnly",
              "inputs": {"model": ["8", 0], "lora_name": "Motion_Repair_V2.safetensors", "strength_model": 0.3}},
        "9": {"class_type": "LoraLoaderModelOnly",
              "inputs": {"model": ["6", 0], "lora_name": "minimax_h3_DMAD_4step_full_lora_avg_rank_39_bf16.safetensors", "strength_model": 1.0}},
        "14": {"class_type": "MiniMaxChunkFeedForward", "inputs": {"model": ["9", 0], "chunks": 4, "seq_threshold": 4096}},
        # ---- 条件（ref2va 主条件 + ZeroOut 负向）----
        "19": {"class_type": "ResolutionSelector",
               "inputs": {"aspect_ratio": "9:16 (Portrait Widescreen)", "megapixels": mp, "multiple": 32}},
        "20": {"class_type": "PrimitiveStringMultiline", "inputs": {"value": PROMPT if prompt_mode == "geometry" else PROMPT_NATURAL}},
        "12": {"class_type": "MiniMaxH3ReferenceToVideo",
               "inputs": {"clip": ["3", 0], "vae": ["2v", 0], "audio_vae": ["4", 0],
                          # Autogrow 输入必须用扁平点号键 —— 嵌套字典会被服务端静默丢弃（实测）
                          "ref_images.ref_image_0": ["1", 0],
                          "ref_videos.ref_video_0": (["54", 0] if ref_video_mode == "white_model" else ["2", 0]),
                          "ref_video_audios.ref_video_audio_0": ["2", 2],
                          "prompt": ["20", 0], "width": ["19", 0], "height": ["19", 1],
                          "length": length, "ref_image_size": "max"}},
        "21": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["12", 0]}},
        # ---- 音频遮罩组（Aiden #49→#132→#134→#133→#135）----
        "49": {"class_type": "TrimAudioDuration",
               "inputs": {"audio": ["2", 2], "start_index": 0.0, "duration": round(length / 24.0, 4)}},
        "132": {"class_type": "VAEEncodeAudio", "inputs": {"audio": ["49", 0], "vae": ["4", 0]}},
        "134": {"class_type": "SolidMask", "inputs": {"value": 0.0, "width": 1, "height": 1}},
        "133": {"class_type": "SetLatentNoiseMask", "inputs": {"samples": ["132", 0], "mask": ["134", 0]}},
        "135": {"class_type": "LTXVConcatAVLatent",
                "inputs": {"video_latent": ["12", 1], "audio_latent": ["133", 0]}},
        # ---- SelfLift 双阶段采样（Aiden #20/#26/#28）----
        "26": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "28": {"class_type": "BasicScheduler",
               "inputs": {"model": ["15", 0], "scheduler": "simple", "steps": steps, "denoise": 1.0}},
        "20s": {"class_type": "SelfLiftAvatarH3Sampler",
                "inputs": {"low_res_model": ["15", 0], "positive": ["12", 0], "negative": ["21", 0],
                           "vae": ["2v", 0], "latent_image": ["135", 0], "sampler": ["26", 0],
                           "sigmas": ["28", 0], "seed": 210, "cfg": 1.0,
                           "transition_step": transition_step, "lowres_scale": 0.5, "rho": 0.0,
                           "w_min": 0.5, "w_max": 1.0,
                           "upscaler_model": "h3_upscaler_lms_v0.1_fp32.safetensors",
                           "highres_tiling": False}},
        # ---- 输出 ----
        "36": {"class_type": "VAEDecode", "inputs": {"samples": ["20s", 0], "vae": ["2v", 0]}},
        "33": {"class_type": "VHS_VideoCombine",
               "inputs": {"images": ["36", 0], "audio": ["2", 2], "frame_rate": 24.0, "loop_count": 0,
                          "filename_prefix": "PLACEHOLDER", "format": "video/h264-mp4",
                          "pix_fmt": "yuv420p", "crf": 16, "save_metadata": False,
                          "trim_to_audio": False, "pingpong": False, "save_output": True}},
    }
    # ---- 控制网条件挂接（在 BlockSparse 之前，Aiden 顺序）----
    cn_out = ["14", 0]
    if use_controlnet:
        p["127"] = {"class_type": "ModelPatchLoader",
                    "inputs": {"name": "minimax_h3_fun_controlnet_union_2.0_pruned_int8_convrot.safetensors"}}
        p["126"] = {"class_type": "MiniMaxH3FunControlNetApply",
                    "inputs": {"model": ["14", 0], "model_patch": ["127", 0], "vae": ["2v", 0],
                               "strength": cn_strength, "start_percent": 0.0, "end_percent": cn_end,
                               "control_video": ["54", 0]}}
        cn_out = ["126", 0]
    p["11"] = {"class_type": "BlockSparseAttention",
               "inputs": {"model": cn_out, "selection": "sol-attn", "selection.tau": 1.1,
                          "start_percent": 0.2, "end_percent": 1.0, "dense_blocks": "",
                          "min_tokens": 12288, "extra_tokens": 256,
                          "sink_conditioning": "exact_kv_and_rows", "verbose": False}}
    p["15"] = {"class_type": "SelfLiftAvatarH3TST", "inputs": {"model": ["11", 0], "tau": 0.2, "log_diagnostics": False}}
    return p


def main():
    ap = argparse.ArgumentParser(description="A 路线 v3：Aiden 原图适配（SelfLift 完整采样）提交器")
    ap.add_argument("--length", type=int, default=73, help="帧数（17n+5；首测 73≈3s）")
    ap.add_argument("--mp", type=float, default=0.3, help="画布 MP（16GB 首测 0.3）")
    ap.add_argument("--steps", type=int, default=8)
    ap.add_argument("--transition-step", type=int, default=6, help="SelfLift 低分辨步数（论文 6/8）")
    ap.add_argument("--cn-strength", type=float, default=0.45)
    ap.add_argument("--cn-end", type=float, default=0.75)
    ap.add_argument("--ref-video-mode", choices=["white_model", "real"], default="white_model",
                    help="ref_video 喂白模合成图（Aiden 原版）还是真实驱动视频（隔离实验用）")
    ap.add_argument("--no-controlnet", action="store_true", help="关闭 ControlNet（ref_video 强制 real）")
    ap.add_argument("--prompt-mode", choices=["natural", "geometry"], default="natural",
                    help="natural=正常舞蹈描述（默认）；geometry=白模几何描述（v3 原版，已证会污染身份）")
    ap.add_argument("--tag", default="h3_selflift_smoke")
    ap.add_argument("--ref-image", default=None)
    ap.add_argument("--video", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--dump-api", default=None)
    args = ap.parse_args()

    outdir = os.path.join(ROOT, "output", date.today().strftime("%Y-%m-%d"), "motion_optimize", args.tag)
    os.makedirs(outdir, exist_ok=True)
    ref_img = os.path.basename(args.ref_image) if args.ref_image else "jia_ref.jpg"
    ref_vid = os.path.basename(args.video) if args.video else "runcha_dance.mp4"

    p = build(length=args.length, mp=args.mp, cn_strength=args.cn_strength, cn_end=args.cn_end,
              steps=args.steps, transition_step=args.transition_step, ref_img=ref_img, ref_vid=ref_vid,
              ref_video_mode=("real" if args.no_controlnet else args.ref_video_mode),
              use_controlnet=not args.no_controlnet, prompt_mode=args.prompt_mode)
    p["33"]["inputs"]["filename_prefix"] = "%s/motion_optimize/%s/jia_selflift" % (
        date.today().strftime("%Y-%m-%d"), args.tag)
    print("节点数=%d 长度=%d 画布=%sMP 步数=%d(SelfLift %d+%d)" %
          (len(p), args.length, args.mp, args.steps, args.transition_step, args.steps - args.transition_step), flush=True)

    if args.dump_api:
        with open(args.dump_api, "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False, indent=2)
        print("已写出 API 工作流: %s" % args.dump_api, flush=True)
        return 0

    if args.dry_run:
        info = json.load(urllib.request.urlopen(f"{COMFY_URL}/object_info"))
        miss = sorted({v["class_type"] for v in p.values()} - set(info))
        print("缺失节点类型:", miss if miss else "无")
        return 0 if not miss else 1

    try:
        res = json.loads(urllib.request.urlopen(urllib.request.Request(
            f"{COMFY_URL}/prompt",
            data=json.dumps({"prompt": p, "client_id": "h3-selflift"}).encode("utf-8"),
            headers={"Content-Type": "application/json"})).read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print("[提交失败]", e.read().decode("utf-8")[:2500]); return 1
    if res.get("node_errors"):
        print("[提交失败 node_errors]", json.dumps(res["node_errors"], ensure_ascii=False)[:2500]); return 1
    pid = res.get("prompt_id")
    sec = 420 * args.length / 73.0
    print("  prompt_id    : %s" % pid)
    print("  产物目录     : %s" % outdir)
    print("  预计完成时间 : 约 %.1f 分钟（SelfLift 6/8 双阶段 + 模型加载）" % (sec / 60.0))
    rec = {"prompt_id": pid, "tag": args.tag, "length": args.length, "mp": args.mp,
           "steps": args.steps, "transition_step": args.transition_step,
           "cn_strength": args.cn_strength, "cn_end": args.cn_end, "out_dir": outdir}
    with open(os.path.join(outdir, "submit.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
