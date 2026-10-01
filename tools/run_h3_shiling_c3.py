
def ensure_date_prefix(p):
    today = datetime.date.today().strftime('%Y-%m-%d')
    if not p.startswith(today):
        return f'{today}/{p}'
    return p
import json
import urllib.request
import urllib.error
import time
import datetime
import os
import sys

COMFY = 'http://127.0.0.1:8188'

PROMPT_TEXT = ''''subject_definitions:
<Subject 1> is the young woman shown in <Picture 1>, featuring long wavy dark hair with delicate front bangs, refined almond-shaped eyes, clear porcelain skin, and a slender curvy hourglass body figure.
<Subject 2> is the elegant Parisian outdoor street cafe shown in <Picture 2>, with Parisian facade, cafe seating, green foliage, and natural daylight.
<Video 1> is the source motion reference video providing the full body rhythmic dance performance, torso turns, and arm gestures.

summary:
[reference generation + video editing] The target video recreates the continuous dance performance from <Video 1>, replacing the performer's face, body figure, and hairstyle with <Subject 1>, and placing her in <Subject 2>.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - facial features, body shape, and long wavy hairstyle with front bangs are fully preserved.
<Subject 2> (appears in [Shot 1]): fully_preserved - Parisian cafe architecture and ambient outdoor daylight are fully preserved.
<Video 1> (motion and timing structure): fully_preserved - dance choreography, arm movements, and bodily rhythm are replicated.

detailed_description:
The target video uses a high-end cinematic vertical dance lookbook style with realistic skin texture, volumetric daylight, and natural hair physics.
[Shot 1] A medium full-length vertical shot frames <Subject 1> performing the dance from <Video 1> in <Subject 2>. Her long dark wavy hair with neat bangs sways gracefully as she sways her hips and moves her arms rhythmically. Her expression is charming and engaging, looking toward the camera with natural confidence.

overall_soundscape:
Gentle fabric rustle and ambient outdoor atmosphere continue smoothly.

non_diegetic_music:
N/A'''

def build_workflow(
    video='shiling_dance_wave.mp4',
    char_img='characters/v3/C02_BODY_FRONT.png',
    bg_img='7a879d8b75dd70e19eb9402ef9a97e9a417156407952177431a493d35a2c1cde.jpg' if os.path.exists('D:/ai_projects/ComfyUI/input/7a879d8b75dd70e19eb9402ef9a97e9a417156407952177431a493d35a2c1cde.jpg') else 'bg_paris_terrace.jpg',
    width=448,
    height=768,
    length=73,
    prefix='shiling_h3_c3_test'
):
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
                "image": char_img
            }
        },
        "9": {
            "class_type": "LoadImage",
            "inputs": {
                "image": bg_img
            }
        },
        "10": {
            "class_type": "VHS_LoadVideo",
            "inputs": {
                "video": video,
                "force_rate": 24.0,
                "custom_width": width,
                "custom_height": height,
                "frame_load_cap": length,
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
                "width": width,
                "height": height,
                "length": length,
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
        "20": {
            "class_type": "LoadImage",
            "inputs": {
                "image": "characters/v3/C01_FACE_FRONT.png"
            }
        },
        "21": {
            "class_type": "ReActorFaceSwap",
            "inputs": {
                "input_image": ["17", 0],
                "source_image": ["20", 0],
                "enabled": True,
                "swap_model": "inswapper_128.onnx",
                "facedetection": "YOLOv5l",
                "face_restore_model": "codeformer.pth",
                "face_restore_visibility": 1.0,
                "codeformer_weight": 0.95,
                "detect_gender_input": "no",
                "detect_gender_source": "no",
                "input_faces_index": "0",
                "source_faces_index": "0",
                "console_log_level": 1
            }
        },
        "19": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["21", 0],
                "audio": ["10", 2],
                "frame_rate": 24.0,
                "loop_count": 0,
                "filename_prefix": ensure_date_prefix(prefix),
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

def submit_task(wf):
    data = json.dumps({'prompt': wf}).encode('utf-8')
    req = urllib.request.Request(f'{COMFY}/prompt', data=data, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            res = json.loads(resp.read().decode('utf-8'))
            pid = res.get('prompt_id')
            print(f'Submitted H3 Ref2VA Task successfully! Prompt ID: {pid}')
            return pid
    except urllib.error.HTTPError as e:
        err = e.read().decode('utf-8')
        print(f'Failed to submit: HTTP {e.code} - {err}')
        return None
    except Exception as e:
        print(f'Failed: {e}')
        return None

def wait_task(pid, timeout=1800):
    print(f'Waiting for H3 task {pid} to complete...')
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(f'{COMFY}/history/{pid}')
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if pid in data:
                    item = data[pid]
                    status = item.get('status', {})
                    outputs = item.get('outputs', {})
                    completed = status.get('completed', False)
                    elapsed = time.time() - start
                    print(f'H3 Task completed: {completed}, outputs: {len(outputs)}, elapsed: {elapsed:.1}s')
                    return True, outputs, elapsed
        except Exception:
            pass_ = None
        time.sleep(5)
    return False, {}, time.time() - start

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Run H3 Ref2VA Person & Motion Migration')
    parser.add_argument('--video', default='shiling_dance_wave.mp4', help='Input video')
    parser.add_argument('--char', default='characters/v3/C02_BODY_FRONT.png', help='Character reference image')
    parser.add_argument('--bg', default='bg_paris_terrace.jpg', help='Background image')
    parser.add_argument('--width', type=int, default=448, help='Video width')
    parser.add_argument('--height', type=int, default=768, help='Video height')
    parser.add_argument('--length', type=int, default=73, help='Frame length (17*N+5)')
    parser.add_argument('--prefix', default='shiling_h3_c3', help='Output prefix')
    parser.add_argument('--save-only', action='store_true', help='Only save workflow')
    args = parser.parse_args()

    wf = build_workflow(
        video=args.video,
        char_img=args.char,
        bg_img=args.bg,
        width=args.width,
        height=args.height,
        length=args.length,
        prefix=args.prefix
    )
    out_json = 'D:/ai_projects/ComfyUI/workflows/v4/h3_shiling_ref2va_v4_api.json'
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(wf, f, indent=2, ensure_ascii=False)
    print(f'Saved H3 workflow to: {out_json}')

    if args.save_only:
        return

    pid = submit_task(wf)
    if pid:
        success, outputs, elapsed = wait_task(pid, timeout=1800)
        if success:
            print(f'H3 RUNSUCCESSFUL! Outputs: {json.dumps(outputs, indent=2)}')
        else:
            print('H3 run timed out or failed.')

if __name__ == '__main__':
    main()
