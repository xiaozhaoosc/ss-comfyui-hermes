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
OUTPUT_DIR = os.path.join("output", TODAY, "v6_ultimate")
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

def build_ultimate_prompt(use_sparse_attn=True):
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
                "value": (
                    "subject_definitions:\n"
                    "<Subject 1> is the target character in <Picture 1>: a gorgeous young Asian woman with delicate facial features, bright expressive eyes, a captivating sweet smile, and long dark brown wavy hair cascading gracefully over her shoulders. She has a slender, graceful figure with bare midriff and long smooth legs. She wears the complete authentic four-piece lingerie ensemble exactly as depicted in <Picture 1>: 1) a delicate pink floral embroidered bra with thin black straps and lace trim, 2) matching low-rise pink and black lace panties, 3) thin black vertical garter suspension straps hanging downwards along her thighs, and 4) wide black floral lace thigh bands encircling each upper thigh. Strictly preserve her authentic identity, facial structure, radiant smile, hairstyle, body shape, and every single piece of her lingerie outfit from <Picture 1>, especially the vertical garter straps and black lace thigh bands.\n"
                    "<Subject 2> is the dance performance, arm choreography, hip bouncing rhythm, and singing facial expressions in <Video 1>.\n"
                    "<Video 1> is the motion and audio source video. It provides the full choreography sequence, tempo, rhythmic hip bounces, hand gestures, and singing lip synchronization. The costume, maid dress, white apron, puffed sleeves, and frilled headband in <Video 1> must be completely ignored and discarded.\n\n"
                    "summary:\n"
                    "[reference generation] Faithfully transfer <Subject 2>'s complete dance choreography, rhythmic hip bouncing, arm gestures, and lively smiling expressions from <Video 1> to <Subject 1>, preserving the exact timing, rhythm, and musical synchronization while strictly maintaining <Subject 1>'s facial appearance, long wavy hair, body shape, and her authentic four-piece floral lace lingerie set (including the bra, panties, vertical garter straps, and black lace thigh bands) from <Picture 1>.\n\n"
                    "retention_analysis:\n"
                    "<Subject 1>: fully_preserved - strictly retain her authentic Asian face, delicate eyes, sweet smile, long wavy dark brown hair, slender toned body, bare midriff, and her authentic four-piece pink and black lace lingerie set with vertical garter straps and black lace thigh bands from <Picture 1>.\n"
                    "<Subject 2>: attribute_transfer - transfer the full-body dance movements, arm positions, hip sway, rhythmic bounce, head tilts, and lively singing facial expressions to <Subject 1>.\n"
                    "<Video 1>: motion_source - provides the dance actions and musical rhythm. Discard the maid outfit and headband.\n\n"
                    "detailed_description:\n"
                    "A high quality, photorealistic full-motion video of <Subject 1> dancing gracefully in medium full-body framing, synchronized to the music across all 277 frames.\n"
                    "[Shot 1] Start in the exact initial motion state of <Video 1>. Full duration is 277 frames at 24fps.\n"
                    "Choreography and expressions timeline:\n"
                    "- From frame 0 to frame 96 (0 to 4 seconds): <Subject 1> places both hands firmly on her hips with elbows pointed outward, cheerfully swaying and bouncing her hips left and right to the upbeat musical tempo, smiling sweetly directly at the camera with bright expressive eyes.\n"
                    "- From frame 96 to frame 168 (4 to 7 seconds): <Subject 1> brings her arms in front, horizontally folding her forearms across her chest and upper abdomen, swaying gently to the rhythm, tilting her head adorably with a playful charming smile.\n"
                    "- From frame 168 to frame 277 (7 to 11.5 seconds): <Subject 1> lowers her hands gracefully beside her hips, bouncing rhythmically with the dance beats, her mouth and lips moving naturally in sync with the song lyrics as if singing along, maintaining vivid, cheerful eye contact and energetic sweet smiles.\n"
                    "Appearance and wardrobe consistency:\n"
                    "<Subject 1>'s face and body faithfully replicate <Picture 1>. She wears the complete authentic four-piece outfit: the pink floral lace bra, matching panties, visible thin black vertical garter straps, and wide black floral lace thigh bands encircling her upper thighs. Her skin is radiant and smooth with bare midriff and toned legs. Her long dark brown wavy hair moves naturally with her dance motions.\n"
                    "The setting is a tidy, warm indoor room with soft natural lighting, realistic depth of field, fluid motion, crisp high-definition details, perfectly preserved outfit accessories, no blurring, no distortion, no watermarks."
                )
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
                "ref_video_audios": {
                    "ref_video_audio_0": ["2", 2]
                },
                "prompt": ["20", 0],
                "width": ["19", 0],
                "height": ["19", 1],
                "length": 277,
                "ref_image_size": "max"  # 2048px 短边超清特征分辨率，完美锚定细带与蕾丝花纹
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
                "audio": ["2", 2],
                "frame_rate": 24.0,
                "loop_count": 0,
                "filename_prefix": f"{TODAY}/v6_ultimate/jia_ultimate_dance_raw",
                "format": "video/h264-mp4",
                "pix_fmt": "yuv420p",
                "crf": 16,
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
    print("=" * 70, flush=True)
    print("🚀 MiniMax H3 终极高保真多模态动作迁移流水线 (Audio-Synced + Ref-Image Max + 4-Piece Lingerie)", flush=True)
    print("=" * 70, flush=True)

    if not wait_for_server(timeout=60):
        print("❌ ComfyUI 服务启动超时，请检查服务状态", flush=True)
        sys.exit(1)

    free_vram()

    # 1. 提交推理 (带稀疏注意力加速)
    print("\n--- 正在启动终极渲染 (16GB 独占, 全量 277 帧, 音频接入, 2048px 注入) ---", flush=True)
    prompt = build_ultimate_prompt(use_sparse_attn=True)
    ok, pid, out = submit_and_wait(prompt, "v6-ultimate-sparse", timeout=2400)

    # 2. 自愈降级 (如果稀疏注意力不兼容则自动降级为原生 kitchen attention)
    if not ok:
        print(f"\n⚠️ 稀疏版本未通过 ({out})，自动降级为原生 kitchen attention...", flush=True)
        free_vram()
        prompt_fallback = build_ultimate_prompt(use_sparse_attn=False)
        ok, pid, out = submit_and_wait(prompt_fallback, "v6-ultimate-kitchen", timeout=2400)

    if ok:
        print("\n🎉🎉🎉 终极渲染成功完成！正在校验产物并封装高保真音画合流... 🎉🎉🎉", flush=True)
        try:
            raw_mp4 = out['33']['gifs'][0]['fullpath']
        except Exception:
            raw_mp4 = os.path.join(OUTPUT_DIR, "jia_ultimate_dance_raw_00001.mp4")

        final_mp4 = os.path.join(OUTPUT_DIR, "jia_ultimate_dance_master.mp4")
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
        print(f"✅ 最终高清带音频母带成片: {final_mp4} (大小: {os.path.getsize(final_mp4)} 字节)", flush=True)

        # 采样抽帧验收 (关键时序动作核验)
        frames_dir = os.path.join(OUTPUT_DIR, "verification_frames")
        os.makedirs(frames_dir, exist_ok=True)
        cap = cv2.VideoCapture(final_mp4)
        sample_indices = {
            "sec_01_hip_hands": 30,    # 0~4s 双手叉腰摇摆
            "sec_05_arms_fold": 120,   # 4~7s 双手交叠胸前歪头笑
            "sec_09_sing_bounce": 210, # 7~11.5s 双手下垂随律动歌唱对口型
            "sec_11_climax": 260       # 尾声高潮
        }
        for name, idx in sample_indices.items():
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            r, f = cap.read()
            if r and f is not None:
                cv2.imwrite(os.path.join(frames_dir, f"{name}_f{idx}.jpg"), f)
        cap.release()
        print(f"✅ 关键时序动作验收帧已保存至: {frames_dir}", flush=True)

        free_vram()
        sys.exit(0)
    else:
        print(f"\n❌ 渲染失败: {out}", flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
