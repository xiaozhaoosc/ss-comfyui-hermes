import json
import urllib.request
import time
import os
import sys
import subprocess
import cv2

sys.stdout.reconfigure(encoding="utf-8")

COMFY_URL = "http://127.0.0.1:8188"
TODAY = "2026-10-13"
OUTPUT_DIR = os.path.join("output", TODAY, "v6_hq")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def free_vram():
    try:
        data = json.dumps({"unload_models": True, "free_memory": True}).encode("utf-8")
        req = urllib.request.Request(f"{COMFY_URL}/free", data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req)
        print("[VRAM] 成功调用 /free 释放显存模型缓存", flush=True)
    except Exception as e:
        print(f"[VRAM WARN] /free 失败: {e}", flush=True)

def wait_for_server(timeout=60):
    start_t = time.time()
    while time.time() - start_t < timeout:
        try:
            req = urllib.request.Request(f"{COMFY_URL}/system_stats")
            with urllib.request.urlopen(req) as resp:
                if resp.status == 200:
                    print("✅ ComfyUI 服务已就绪！", flush=True)
                    return True
        except Exception:
            time.sleep(2)
    return False

def submit_and_wait(prompt_dict, client_id, timeout=2400):
    p = {"prompt": prompt_dict, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(f"{COMFY_URL}/prompt", data=data, headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req)
        res = json.loads(resp.read().decode('utf-8'))
        pid = res.get("prompt_id")
        print(f"[{client_id}] 成功推入队列，Prompt ID: {pid}", flush=True)
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode('utf-8')
        print(f"[{client_id}] HTTP 错误: {e.code} - {err_msg}", flush=True)
        return False, None, err_msg

    start_t = time.time()
    while time.time() - start_t < timeout:
        time.sleep(5)
        try:
            req = urllib.request.Request(f"{COMFY_URL}/history/{pid}")
            resp = urllib.request.urlopen(req)
            hist = json.loads(resp.read().decode('utf-8'))
            if pid in hist:
                status = hist[pid].get("status", {})
                status_str = status.get("status_str")
                if status_str == "error":
                    err_info = "Unknown execution error"
                    for msg in status.get("messages", []):
                        if msg[0] == "execution_error":
                            err_info = msg[1]
                    print(f"[{client_id}] 执行报错: {err_info}", flush=True)
                    return False, pid, err_info
                if status.get("completed"):
                    outputs = hist[pid].get("outputs", {})
                    print(f"[{client_id}] 执行成功完成！产物输出: {outputs}", flush=True)
                    return True, pid, outputs
        except Exception as e:
            print(f"[{client_id}] 查询轮询状态异常: {e}", flush=True)
    return False, pid, "超时未完成"

def build_hq_prompt(use_sparse_attn=True):
    p = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {
                "image": "jia_ref.jpg"
            }
        },
        "2": {
            "class_type": "VHS_LoadVideo",
            "inputs": {
                "video": "runcha_dance.mp4",
                "force_rate": 24,
                "custom_width": 0,
                "custom_height": 0,
                "frame_load_cap": 277,
                "skip_first_frames": 0,
                "select_every_nth": 1,
                "format": "AnimateDiff"
            }
        },
        "10": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors",
                "weight_dtype": "default"
            }
        },
        "11": {
            "class_type": "MiniMaxH3SigmaShift",
            "inputs": {
                "model": ["10", 0],
                "shift_video": 12.0,
                "shift_audio": 3.0
            }
        },
        "12": {
            "class_type": "ModelAttentionBackend",
            "inputs": {
                "model": ["11", 0],
                "attention": "comfy kitchen attention"
            }
        },
        "13": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["12", 0],
                "lora_name": "minimax_h3_turbo_v4_step600_ema_pruned_comfyui.safetensors",
                "strength_model": 1.0
            }
        },
        "14": {
            "class_type": "MiniMaxChunkFeedForward",
            "inputs": {
                "model": ["13", 0],
                "chunks": 4,
                "seq_threshold": 4096
            }
        },
        "16": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen3vl_32b_minimax_h3_int8_convrot.safetensors",
                "type": "minimax",
                "device": "default"
            }
        },
        "17": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "minimax_h3_video_vae_int8_convrot.safetensors"
            }
        },
        "18": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "minimax_h3_audio_vae_fp32.safetensors"
            }
        },
        "19": {
            "class_type": "ResolutionSelector",
            "inputs": {
                "aspect_ratio": "9:16 (Portrait Widescreen)",
                "megapixels": 0.5,
                "multiple": 32
            }
        },
        "20": {
            "class_type": "PrimitiveStringMultiline",
            "inputs": {
                "value": "subject_definitions:\n<Subject 1> is the target person in <Picture 1>: a young attractive Asian woman with delicate facial features, a gentle sweet smile, and long dark brown wavy hair flowing over her shoulders. She has a slender, graceful body figure with bare midriff and long legs, wearing the exact delicate two-piece pink floral and black lace lingerie set shown in <Picture 1>. Strictly preserve her exact identity, facial structure, smile, hairstyle, body shape, and exact outfit from <Picture 1> without adding any extra belts, straps, or modifications.\n<Subject 2> is the dance performance in <Video 1>: body posture, hand and arm dance movements, waist swaying, rhythm and timing.\n<Video 1> is the motion source video. It supplies the dance choreography, action order, rhythm and timing. The clothing, headband, and costume in <Video 1> must be completely ignored and discarded.\n\nsummary:\n[reference generation] Transfer <Subject 2>'s dance performance from <Video 1> to <Subject 1>, preserving the source dance sequence, rhythm and timing while strictly and faithfully keeping <Subject 1>'s appearance, face, long hair, body proportions, and her exact two-piece floral lace lingerie outfit from <Picture 1>.\n\nretention_analysis:\n<Subject 1>: fully_preserved - retain identity, face, smile, long wavy hair, slender body, and her authentic floral lace lingerie set strictly from <Picture 1>.\n<Subject 2>: attribute_transfer - transfer observable dance motion, arm and hand gestures, waist movements, rhythm, and timing to <Subject 1>.\n<Video 1>: motion_source - supplies motion timing and sequence only. Do not transfer the maid costume, apron, sleeves, or headband from <Video 1>.\n\ndetailed_description:\nCreate a normal full-colour realistic video of <Subject 1> performing the dance in medium full-body framing.\n[Shot 1] Start in the source clip's initial motion state. Target time t corresponds to source time t. Preserve the full source duration of 277 frames.\nFaithfully reproduce the visible dance movements, arm and hand gestures, and waist swaying from <Video 1> in their original order, rhythm and timing.\n<Picture 1> controls appearance, not posture. Target hair and outfit keep their own shape and design strictly from <Picture 1>: her delicate two-piece pink floral lace lingerie set moves naturally with her body dancing. She has an open, clear face with a natural smile. Absolutely no face mask, no tie, no shirt, no jeans, no extra waist belts.\nFollow the camera framing to capture her full body dancing gestures clearly. Clean indoor room background, natural soft lighting, high visual realism, no artifacts, no watermarks."
            }
        },
        "21": {
            "class_type": "MiniMaxH3ReferenceToVideo",
            "inputs": {
                "clip": ["16", 0],
                "vae": ["17", 0],
                "audio_vae": ["18", 0],
                "ref_images": {
                    "ref_image_0": ["1", 0]
                },
                "ref_videos": {
                    "ref_video_0": ["2", 0]
                },
                "prompt": ["20", 0],
                "width": ["19", 0],
                "height": ["19", 1],
                "length": 277,
                "ref_image_size": "max"  # 高清 2048px 短边注入，最大化保留蕾丝细带与花瓣微观纹理
            }
        },
        "23": {
            "class_type": "BasicScheduler",
            "inputs": {
                "model": ["15", 0] if use_sparse_attn else ["14", 0],
                "scheduler": "simple",
                "steps": 4,
                "denoise": 1.0
            }
        },
        "24": {
            "class_type": "KSamplerSelect",
            "inputs": {
                "sampler_name": "res_multistep"
            }
        },
        "25": {
            "class_type": "RandomNoise",
            "inputs": {
                "noise_seed": 42
            }
        },
        "22": {
            "class_type": "BasicGuider",
            "inputs": {
                "model": ["15", 0] if use_sparse_attn else ["14", 0],
                "conditioning": ["21", 0]
            }
        },
        "30": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["25", 0],
                "guider": ["22", 0],
                "sampler": ["24", 0],
                "sigmas": ["23", 0],
                "latent_image": ["21", 1]
            }
        },
        "31": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["30", 0],
                "vae": ["17", 0]
            }
        },
        "33": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["31", 0],
                "frame_rate": 24.0,
                "loop_count": 0,
                "filename_prefix": f"{TODAY}/v6_hq/jia_dance_hq_raw",
                "format": "video/h264-mp4",
                "pix_fmt": "yuv420p",
                "crf": 16,  # 高码率编码，保留锐利蕾丝与肤质细节
                "save_metadata": False,
                "trim_to_audio": False,
                "pingpong": False,
                "save_output": True
            }
        }
    }

    if use_sparse_attn:
        p["15"] = {
            "class_type": "BlockSparseAttention",
            "inputs": {
                "model": ["14", 0],
                "selection": "sol-attn",
                "selection.tau": 1.1,
                "start_percent": 0.2,
                "end_percent": 1.0,
                "dense_blocks": "",
                "min_tokens": 12288,
                "extra_tokens": 256,
                "sink_conditioning": "exact_kv_and_rows",
                "verbose": False
            }
        }

    return p

def main():
    print("=" * 65, flush=True)
    print("🚀 MiniMax H3 高画质微观保真动作迁移流水线 (ref_image_size=max + crf=16)", flush=True)
    print("=" * 65, flush=True)

    if not wait_for_server(timeout=60):
        print("❌ ComfyUI 服务启动超时，请检查服务状态", flush=True)
        sys.exit(1)

    free_vram()

    # 1. 提交推理 (max 高清参考模式)
    print("\n--- 正在启动高清渲染 (16GB 独占, 全量 277 帧, 2048px 原图注入) ---", flush=True)
    prompt = build_hq_prompt(use_sparse_attn=True)
    ok, pid, out = submit_and_wait(prompt, "v6-hq-sparse", timeout=2400)

    # 2. 自愈降级
    if not ok:
        print(f"\n⚠️ 稀疏版本未通过 ({out})，自动降级为原生 kitchen attention...", flush=True)
        free_vram()
        prompt_fallback = build_hq_prompt(use_sparse_attn=False)
        ok, pid, out = submit_and_wait(prompt_fallback, "v6-hq-kitchen", timeout=2400)

    if ok:
        print("\n🎉🎉🎉 高清画面渲染成功完成！正在自动合流原视频音频与抽帧... 🎉🎉🎉", flush=True)
        try:
            raw_mp4 = out['33']['gifs'][0]['fullpath']
        except Exception:
            raw_mp4 = os.path.join(OUTPUT_DIR, "jia_dance_hq_raw_00001.mp4")

        # 音频合成
        final_mp4 = os.path.join(OUTPUT_DIR, "jia_dance_hq_with_audio.mp4")
        audio_src = os.path.abspath("input/runcha_dance.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-i", raw_mp4,
            "-i", audio_src,
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0?",
            "-shortest",
            final_mp4
        ]
        subprocess.run(cmd, capture_output=True)
        print(f"✅ 最终高清带音频成片: {final_mp4} (大小: {os.path.getsize(final_mp4)} 字节)", flush=True)

        # 抽帧
        frames_dir = os.path.join(OUTPUT_DIR, "frames")
        os.makedirs(frames_dir, exist_ok=True)
        cap = cv2.VideoCapture(final_mp4)
        for i in [0, 70, 140, 210, 270]:
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            r, f = cap.read()
            if r and f is not None:
                cv2.imwrite(os.path.join(frames_dir, f"frame_{i}.jpg"), f)
        cap.release()
        print(f"✅ 采样帧已保存至: {frames_dir}", flush=True)

        free_vram()
        sys.exit(0)
    else:
        print(f"\n❌ 渲染失败: {out}", flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
