
def ensure_date_prefix(p):
    today = datetime.date.today().strftime('%Y-%m-%d')
    if not p.startswith(today):
        return f'{today}/{p}'
    return p
"""
run_h3_ootd_ref2va.py - Run MiniMax-H3 Ref2VA multimodal video regeneration trial
"""
import json
import urllib.request
import urllib.error
import time
import datetime
import os
import sys

COMFY = "http://127.0.0.1:8188"

# 6-section Ref2VA Prompt formatted according to official MiniMax H3 Prompt Guide
PROMPT_TEXT = """subject_definitions:
<Subject 1> is the young woman shown in <Picture 1>, featuring long wavy dark hair with delicate bangs, refined almond-shaped eyes, and clear skin.
<Subject 2> is the elegant beige outdoor setting in <Picture 2>, with soft warm architectural lighting and natural stone textures.
<Video 1> is the source motion reference video providing the full body movement, pose timing, and dress flow.

summary:
[reference generation + video editing] The target video recreates the continuous fashion performance from <Video 1>, replacing the woman's face and hairstyle with <Subject 1>, and placing her in the architectural setting of <Subject 2>.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - facial features, eye shape, lip curvature, and long wavy hairstyle with front bangs are fully preserved.
<Subject 2> (appears in [Shot 1]): fully_preserved - background architecture, beige stone textures, and ambient warm daylight are fully preserved.
<Video 1> (motion and timing structure): fully_preserved - bodily rotation, stepping action, and outfit dynamics are replicated.

detailed_description:
The target video uses a high-end cinematic fashion lookbook style with realistic skin texture, volumetric daylight, and natural hair physics.
[Shot 1] A full-length vertical shot frames <Subject 1> standing in <Subject 2>, wearing the white halter-neck dress from <Video 1>. Her long dark wavy hair with neat bangs moves softly in the light breeze as she gently turns her torso toward the camera, shifting her weight from one leg to the other. The camera maintains a smooth, steady medium-long framing with minimal camera shake. Her expression remains calm and poised, looking directly toward the lens with a subtle smile.

overall_soundscape:
Gentle fabric rustle and subtle ambient outdoor room tone continue smoothly throughout the sequence.

non_diegetic_music:
N/A"""

def build_workflow():
    wf = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "minimax_h3_fused_refdelta_r1024_turbo8_mystic07_int8_convrot.safetensors",
                "weight_dtype": "default"
            }
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors",
                "type": "minimax"
            }
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "minimax_h3_video_vae_fp16.safetensors"
            }
        },
        "4": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "minimax_h3_audio_vae_fp32.safetensors"
            }
        },
        "5": {
            "class_type": "MiniMaxChunkFeedForward",
            "inputs": {
                "model": ["1", 0],
                "chunks": 4,
                "seq_threshold": 4096
            }
        },
        "6": {
            "class_type": "H3SLAAttention",
            "inputs": {
                "model": ["5", 0],
                "sparsity_ratio": 0.9,
                "block_size": "64",
                "chunk_size": 8192,
                "pad_to": 0,
                "apply_to_self": True,
                "apply_to_cross": True
            }
        },
        "7": {
            "class_type": "MiniMaxH3SigmaShift",
            "inputs": {
                "model": ["6", 0],
                "shift_video": 12.0,
                "shift_audio": 3.0
            }
        },
        "8": {
            "class_type": "LoadImage",
            "inputs": {
                "image": "characters/v3/C01_FACE_FRONT.png"
            }
        },
        "9": {
            "class_type": "LoadImage",
            "inputs": {
                "image": "base_refine_08_beige_outdoor_00001_.png"
            }
        },
        "10": {
            "class_type": "VHS_LoadVideo",
            "inputs": {
                "video": "ootd_target.mp4",
                "force_rate": 24.0,
                "custom_width": 448,
                "custom_height": 768,
                "frame_load_cap": 107,
                "skip_first_frames": 0,
                "select_every_nth": 1,
                "format": "AnimateDiff"
            }
        },
        "11": {
            "class_type": "MiniMaxH3ReferenceToVideo",
            "inputs": {
                "clip": ["2", 0],
                "vae": ["3", 0],
                "audio_vae": ["4", 0],
                "prompt": PROMPT_TEXT,
                "width": 448,
                "height": 768,
                "length": 107,
                "ref_image_size": "match",
                "ref_images.ref_image_0": ["8", 0],
                "ref_images.ref_image_1": ["9", 0],
                "ref_videos.ref_video_0": ["10", 0]
            }
        },
        "12": {
            "class_type": "BasicScheduler",
            "inputs": {
                "model": ["7", 0],
                "scheduler": "simple",
                "steps": 4,
                "denoise": 1.0
            }
        },
        "13": {
            "class_type": "BasicGuider",
            "inputs": {
                "model": ["7", 0],
                "conditioning": ["11", 0]
            }
        },
        "14": {
            "class_type": "KSamplerSelect",
            "inputs": {
                "sampler_name": "res_multistep"
            }
        },
        "15": {
            "class_type": "RandomNoise",
            "inputs": {
                "noise_seed": 42
            }
        },
        "16": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["15", 0],
                "guider": ["13", 0],
                "sampler": ["14", 0],
                "sigmas": ["12", 0],
                "latent_image": ["11", 1]
            }
        },
        "17": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["16", 0],
                "vae": ["3", 0]
            }
        },
        "18": {
            "class_type": "VAEDecodeAudio",
            "inputs": {
                "samples": ["16", 0],
                "vae": ["4", 0]
            }
        },
        "19": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["17", 0],
                "audio": ["18", 0],
                "frame_rate": 24.0,
                "loop_count": 0,
                "filename_prefix": "ootd_h3_ref2va_v3",
                "format": "video/h264-mp4",
                "pix_fmt": "yuv420p",
                "crf": 19,
                "save_metadata": True,
                "trim_to_audio": False,
                "pingpong": False,
                "save_output": True
            }
        }
    }
    return wf

def main():
    wf = build_workflow()
    api_path = r"D:\ai_projects\ComfyUI\workflows\v3\h3_ref2va_ootd_api.json"
    with open(api_path, "w", encoding="utf-8") as f:
        json.dump(wf, f, indent=2, ensure_ascii=False)
    print(f"Saved API workflow to {api_path}")

    # Submit to ComfyUI
    data = json.dumps({"prompt": wf}).encode("utf-8")
    req = urllib.request.Request(f"{COMFY}/prompt", data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            pid = res.get("prompt_id")
            print(f"Submitted H3 Ref2VA Task successfully! Prompt ID: {pid}")
            return pid
    except urllib.error.HTTPError as e:
        err = e.read().decode('utf-8')
        print(f"Failed to submit: HTTP {e.code} - {err}")
        return None
    except Exception as e:
        print(f"Failed: {e}")
        return None

if __name__ == "__main__":
    main()
