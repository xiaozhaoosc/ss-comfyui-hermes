import json
import urllib.request
import time
import os
import sys
import shutil

sys.stdout.reconfigure(encoding="utf-8")

COMFY_URL = "http://127.0.0.1:8188"
TODAY = "2026-10-13"
OUTPUT_DIR = os.path.join("output", TODAY, "v6_two_pass")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def free_vram():
    try:
        data = json.dumps({"unload_models": True, "free_memory": True}).encode("utf-8")
        req = urllib.request.Request(f"{COMFY_URL}/free", data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req)
        print("[VRAM] 成功调用 /free 释放显存模型缓存", flush=True)
    except Exception as e:
        print(f"[VRAM WARN] /free 失败: {e}", flush=True)

def submit_and_wait(prompt_dict, client_id, timeout=600):
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

def build_pass2_prompt(normal_video_name, use_sparse_attn=True):
    # Pass 2 prompt
    p2 = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {
                "image": "jia_ref.jpg"
            }
        },
        "2": {
            "class_type": "VHS_LoadVideo",
            "inputs": {
                "video": normal_video_name,
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
                "value": "subject_definitions:\n<Subject 1> is the target person in <Picture 1>: a young attractive Asian woman with long dark wavy hair draping over her shoulders, slender graceful feminine body proportions, delicate facial features with natural gentle expression, wearing a light-pink floral lace off-shoulder camisole top and matching feminine shorts. Full-body / three-quarter standing shot showing complete torso, waist, hips and legs. Preserve her exact identity, face, long wavy hair, body proportions, and outfit from <Picture 1>.\n<Subject 2> is the observable dance performance in <Video 1>: full body posture, hip swaying, waist movements, arm and hand dance gestures, rhythm and timing.\n<Video 1> is the motion-normal reference for the dance clip. It supplies the original action order, posture changes, rhythm and timing, not target appearance or final scene content.\n\nsummary:\n[reference generation] Transfer <Subject 2> dance performance to <Subject 1>, preserving the source dance sequence, rhythm and timing while keeping the target appearance, face, long wavy hair, body proportions, and outfit from <Picture 1>. Maintain full-body / medium full-body framing showing complete body gestures and waist movements.\n\nretention_analysis:\n<Subject 1>: fully_preserved - retain identity, face, long hair, slender body shape, and outfit from <Picture 1> while pose and dance performance change.\n<Subject 2>: attribute_transfer - transfer observable motion, dance, waist movements, and timing to the target anatomy.\n<Video 1>: fully_preserved - retain its defined motion-reference role, excluding visualization colours and source appearance.\n\ndetailed_description:\nCreate a normal full-colour realistic video of <Subject 1> in medium full-body framing.\n[Shot 1] Start in the source clip's initial motion state. Target time t corresponds to source time t; align by actual time if frame rates differ. Preserve the full source duration of 277 frames.\nReproduce the visible body, head, arm, palm, finger, hip, and waist dance changes in their original order. Retain small movements, pauses, amplitude and speed changes.\nThe picture controls appearance, not posture. Target hair and clothes keep their own shapes and respond naturally to the inherited movement.\nTransfer clearly readable facial and mouth changes with a natural smile.\nFollow the requested indoor scene and medium full-body camera framing. Exclude normal visualization colours, wireframes, grids, markers, reference layouts, subtitles and additional shots."
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
                "filename_prefix": f"{TODAY}/v6_two_pass/v6_final_jia_dance",
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
        p2["15"] = {
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

    return p2

def main():
    print("=" * 65, flush=True)
    print("🚀 v6 两段式无人值守自动化跑通流水线 (自动自愈模式)", flush=True)
    print("=" * 65, flush=True)

    # 1. 检查 Pass 1 产物
    normal_video_rel = None
    expected_normal = os.path.join(OUTPUT_DIR, "runcha_normal_ref_00001.mp4")
    if os.path.exists(expected_normal) and os.path.getsize(expected_normal) > 1024:
        print(f"✅ 检测到 Pass 1 女仆舞蹈法线提取视频已就绪: {expected_normal}", flush=True)
        # 复制到 input 目录方便 VHS_LoadVideo 加载
        input_target = os.path.join("input", "v6_normal_ref.mp4")
        shutil.copy2(expected_normal, input_target)
        normal_video_rel = "v6_normal_ref.mp4"
    else:
        print(f"❌ 未找到全量法线视频 {expected_normal}", flush=True)
        sys.exit(1)

    # 阶段 1 结束，强制释放显存
    free_vram()

    # 2. 提交 Pass 2 (首先尝试带 sol-attn 稀疏注意力的版本)
    print("\n--- 正在启动 Pass 2: 纯净扩散主干生成 (16GB 独占, 全量 277 帧) ---", flush=True)
    pass2_prompt = build_pass2_prompt(normal_video_rel, use_sparse_attn=True)
    ok, pid, out = submit_and_wait(pass2_prompt, "v6-pass2-sparse", timeout=1800)

    # 自愈分支：如果稀疏注意力出错，自动降级为原生 kitchen attention
    if not ok:
        print(f"\n⚠️ 稀疏版本执行未成功 ({out})，自动触发自愈逻辑：降级直连原生 kitchen attention...", flush=True)
        free_vram()
        pass2_prompt_fallback = build_pass2_prompt(normal_video_rel, use_sparse_attn=False)
        ok, pid, out = submit_and_wait(pass2_prompt_fallback, "v6-pass2-dense-kitchen", timeout=1800)

    if ok:
        print("\n🎉🎉🎉 v6 动作迁移端到端全链路验证大获成功！🎉🎉🎉", flush=True)
        try:
            final_mp4 = out['33']['gifs'][0]['fullpath']
        except Exception:
            final_mp4 = os.path.join(OUTPUT_DIR, "v6_final_jia_dance_00001.mp4")
        if os.path.exists(final_mp4):
            print(f"成品视频: {final_mp4} (大小: {os.path.getsize(final_mp4)} 字节)", flush=True)
        free_vram()
        sys.exit(0)
    else:
        print(f"\n❌ Pass 2 最终失败: {out}", flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
