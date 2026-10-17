import json
import urllib.request
import time
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

COMFY_URL = "http://127.0.0.1:8188"
TODAY = "2026-10-13"
OUTPUT_DIR = os.path.join("output", TODAY, "v6_white_model")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def free_vram():
    try:
        data = json.dumps({"unload_models": True, "free_memory": True}).encode("utf-8")
        req = urllib.request.Request(f"{COMFY_URL}/free", data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req)
        print("[VRAM] 成功调用 /free 释放显存模型缓存", flush=True)
    except Exception as e:
        print(f"[VRAM WARN] /free 失败: {e}", flush=True)

def submit_and_wait(prompt_dict, client_id, timeout=1800):
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

def build_whitemodel_prompt(use_sparse_attn=True):
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
                "video": "v6_white_model_ref.mp4",
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
                "value": "subject_definitions:\n<Subject 1> is the target person in <Picture 1>. Preserve identity, facial features, long wavy hair, body proportions, clothing and outfit strictly from <Picture 1>. The picture defines her appearance; it does not prescribe a static pose.\n<Subject 2> is the observable performance in <Video 1>: body, head, arms, palms, fingers, waist movements, plus clearly readable facial and mouth changes.\n<Video 1> is the motion-normal reference (white model) for the selected clip. It supplies the original action order, posture changes, rhythm and timing, not target appearance or final scene content.\n\nsummary:\n[reference generation] Transfer <Subject 2> to <Subject 1>, preserving the source sequence, rhythm and timing while strictly keeping the target appearance, face, hairstyle, body shape, and outfit from <Picture 1>. Generate only movements actually present in <Video 1>.\n\nretention_analysis:\n<Subject 1>: fully_preserved - retain identity, face, hairstyle, body proportions, and outfit from <Picture 1> while pose and performance change.\n<Subject 2>: attribute_transfer - transfer observable motion, dance gestures, waist movements, and timing to the target anatomy.\n<Video 1>: fully_preserved - retain its defined motion-reference role, excluding visualization colours and source appearance.\n\ndetailed_description:\nCreate a normal full-colour realistic video of <Subject 1> in a medium full-body framing.\n[Shot 1] Start in the source clip's initial motion state. Target time t corresponds to source time t; align by actual time if frame rates differ. Preserve the full source duration of 277 frames.\nReproduce the visible body, head, arm, palm, finger, hip, and waist dance changes in their original order. Retain small movements, pauses, amplitude and speed changes. Each body part follows its own source motion with the original coordination.\nThe picture controls appearance, not posture. Target hair and clothes keep their own shapes and design strictly from <Picture 1>, and respond naturally to the inherited movement; do not change her clothing to other styles.\nTransfer clearly readable facial expressions and mouth changes with a natural smile.\nFollow the requested scene and camera framing. High visual quality, natural skin textures, clean indoor background, no artifacts, no watermarks."
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
                "ref_image_size": "match"
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
                "filename_prefix": f"{TODAY}/v6_white_model/jia_dance_whitemodel",
                "format": "video/h264-mp4",
                "pix_fmt": "yuv420p",
                "crf": 19,
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
    print("🚀 MiniMax H3 3D白模参考动作迁移 (零彩色伪影/原装服饰严格保持)", flush=True)
    print("=" * 65, flush=True)

    free_vram()

    # 1. 优先尝试带 sol-attn 稀疏注意力的版本
    print("\n--- 正在启动 3D 白模参考迁移渲染 (16GB 独占, 全量 277 帧) ---", flush=True)
    prompt = build_whitemodel_prompt(use_sparse_attn=True)
    ok, pid, out = submit_and_wait(prompt, "v6-whitemodel-sparse", timeout=1800)

    # 2. 自愈降级
    if not ok:
        print(f"\n⚠️ 稀疏版本未通过 ({out})，自动降级为原生 kitchen attention...", flush=True)
        free_vram()
        prompt_fallback = build_whitemodel_prompt(use_sparse_attn=False)
        ok, pid, out = submit_and_wait(prompt_fallback, "v6-whitemodel-kitchen", timeout=1800)

    if ok:
        print("\n🎉🎉🎉 白模动作迁移渲染成功完成！🎉🎉🎉", flush=True)
        try:
            final_mp4 = out['33']['gifs'][0]['fullpath']
        except Exception:
            final_mp4 = os.path.join(OUTPUT_DIR, "jia_dance_whitemodel_00001.mp4")
        if os.path.exists(final_mp4):
            print(f"成品视频: {final_mp4} (大小: {os.path.getsize(final_mp4)} 字节)", flush=True)
        free_vram()
        sys.exit(0)
    else:
        print(f"\n❌ 白模动作迁移失败: {out}", flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
