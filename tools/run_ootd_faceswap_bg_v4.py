
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
import argparse

COMFY = 'http://127.0.0.1:8188'

def build_workflow_v4(
    video='ootd_target.mp4',
    bg_image='bg_paris_terrace.jpg',
    char_image='characters/v3/C01_FACE_FRONT.png',
    width=540,
    height=960,
    fps=25.0,
    frame_load_cap=60,
    select_every_nth=1,
    facedetection='retinaface_resnet50',
    face_restore_model='codeformer.pth',
    face_restore_visibility=1.0,
    codeformer_weight=0.85,
    bg_blur=10,
    blur_radius=4.5,
    lerp_alpha=0.8,
    prefix='ootd_swap_bg_v4'
):
    wf = {
        '1': {
            'class_type': 'VHS_LoadVideo',
            'inputs': {
                'video': video,
                'force_rate': float(fps),
                'custom_width': int(width),
                'custom_height': int(height),
                'frame_load_cap': int(frame_load_cap),
                'skip_first_frames': 0,
                'select_every_nth': int(select_every_nth),
                'format': 'AnimateDiff'
            }
        },
        '2': {
            'class_type': 'LoadImage',
            'inputs': {
                'image': char_image
            }
        },
        '10': {
            'class_type': 'ReActorFaceSwap',
            'inputs': {
                'input_image': ['1', 0],
                'source_image': ['2', 0],
                'enabled': True,
                'swap_model': 'inswapper_128.onnx',
                'facedetection': 'YOLOv5l',
                'face_restore_model': face_restore_model,
                'face_restore_visibility': float(face_restore_visibility),
                'codeformer_weight': float(codeformer_weight),
                'detect_gender_input': 'no',
                'detect_gender_source': 'no',
                'input_faces_index': '0',
                'source_faces_index': '0',
                'console_log_level': 1
            }
        },
        '20': {
            'class_type': 'LoadImage',
            'inputs': {
                'image': bg_image
            }
        },
        '21': {
            'class_type': 'ImageScale',
            'inputs': {
                'image': ['20', 0],
                'upscale_method': 'lanczos',
                'width': int(width),
                'height': int(height),
                'crop': 'center'
            }
        },
        '27': {
            'class_type': 'ImageBlur',
            'inputs': {
                'image': ['21', 0],
                'blur_radius': int(bg_blur),
                'sigma': float(bg_blur) / 2.0
            }
        },
        '25': {
            'class_type': 'RepeatImageBatch',
            'inputs': {
                'image': ['27', 0] if bg_blur > 0 else ['21', 0],
                'amount': ['1', 1]
            }
        },
        '22': {
            'class_type': 'LoadBackgroundRemovalModel',
            'inputs': {
                'bg_removal_name': 'BiRefNet-general.safetensors'
            }
        },
        '23': {
            'class_type': 'RemoveBackground',
            'inputs': {
                'bg_removal_model': ['22', 0],
                'image': ['10', 0]
            }
        },
        '26': {
            'class_type': 'GrowMaskWithBlur',
            'inputs': {
                'mask': ['23', 0],
                'expand': 0,
                'incremental_expandrate': 0.0,
                'tapered_corners': True,
                'flip_input': False,
                'blur_radius': float(blur_radius),
                'lerp_alpha': float(lerp_alpha),
                'decay_factor': 1.0,
                'fill_holes': False
            }
        },
        '24': {
            'class_type': 'ImageCompositeMasked',
            'inputs': {
                'destination': ['25', 0],
                'source': ['10', 0],
                'mask': ['26', 0],
                'x': 0,
                'y': 0,
                'resize_source': False
            }
        },
        '11': {
            'class_type': 'VHS_VideoCombine',
            'inputs': {
                'images': ['24', 0],
                'audio': ['1', 2],
                'frame_rate': float(fps),
                'loop_count': 0,
                'filename_prefix': ensure_date_prefix(prefix),
                'format': 'video/h264-mp4',
                'pix_fmt': 'yuv420p',
                'crf': 20,
                'save_metadata': True,
                'trim_to_audio': False,
                'pingpong': False,
                'save_output': True
            }
        }
    }
    return wf

def submit_workflow(wf):
    data = json.dumps({'prompt': wf}).encode('utf-8')
    req = urllib.request.Request(f'{COMFY}/prompt', data=data, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            res = json.loads(resp.read().decode('utf-8'))
            pid = res.get('prompt_id')
            print(f'Submitted Task! Prompt ID: {pid}')
            return pid
    except urllib.error.HTTPError as e:
        err = e.read().decode('utf-8')
        print(f'Failed to submit: HTTP {e.code} - {err}')
        return None
    except Exception as e:
        print(f'Failed: {e}')
        return None

def wait_for_task(pid, timeout=900):
    print(f'Waiting for prompt {pid} to complete...')
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            req = urllib.request.Request(f'{COMFY}/history/{pid}')
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if pid in data:
                    item = data[pid]
                    status = item.get('status', {})
                    outputs = item.get('outputs', {})
                    completed = status.get('completed', False)
                    elapsed = time.time() - start_time
                    print(f'Task completed: {completed}, outputs count: {len(outputs)}, elapsed: {elapsed:.1f}s')
                    return True, outputs, elapsed
        except Exception:
            pass
        time.sleep(3)
    return False, {}, time.time() - start_time

def main():
    parser = argparse.ArgumentParser(description='Run FaceSwap + Background Replacement (v4)')
    parser.add_argument('--video', default='14912638572466341957.mp4', help='Input video name in ComfyUI/input')
    parser.add_argument('--bg', default='bg_paris_terrace.jpg', help='Background image name in ComfyUI/input')
    parser.add_argument('--char', default='characters/v3/C01_FACE_FRONT.png', help='Character face image')
    parser.add_argument('--width', type=int, default=540, help='Video width (default 540 for fast testing)')
    parser.add_argument('--height', type=int, default=960, help='Video height (default 960 for fast testing)')
    parser.add_argument('--fps', type=float, default=25.0, help='Video frame rate (default 25.0)')
    parser.add_argument('--frames', type=int, default=60, help='Frame load cap (default 60 for fast testing, 0 for all)')
    parser.add_argument('--face-restore', default='codeformer.pth', help='Face restore model (GFPGANv1.4.pth / codeformer.pth / none)')
    parser.add_argument('--visibility', type=float, default=1.0, help='Face restore visibility (default 1.0)')
    parser.add_argument('--codeformer-weight', type=float, default=0.95, help='Codeformer fidelity weight (default 0.95)')
    parser.add_argument('--bg-blur', type=int, default=10, help='Background depth of field blur radius (default 10)')
    parser.add_argument('--blur-radius', type=float, default=3.5, help='Mask feather blur radius (default 3.5)')
    parser.add_argument('--lerp-alpha', type=float, default=0.8, help='Temporal mask interpolation alpha (default 0.8)')
    parser.add_argument('--prefix', default='ootd_swap_bg_v4', help='Output filename prefix')
    parser.add_argument('--save-only', action='store_true', help='Only save workflow JSON without submitting')
    
    args = parser.parse_args()

    # 1. Build and save standard production API workflow (full video cap=0)
    wf_production = build_workflow_v4(
        video=args.video,
        bg_image=args.bg,
        char_image=args.char,
        width=args.width,
        height=args.height,
        fps=args.fps,
        frame_load_cap=0,
        facedetection='retinaface_resnet50',
        face_restore_model=args.face_restore,
        face_restore_visibility=args.visibility,
        codeformer_weight=args.codeformer_weight,
        bg_blur=args.bg_blur,
        blur_radius=args.blur_radius,
        lerp_alpha=args.lerp_alpha,
        prefix=args.prefix
    )
    
    # Save to workflows/v4 and workflows/v3 for compatibility
    paths_to_save = [
        r'D:/ai_projects/ComfyUI/workflows/v4\ootd_faceswap_bg_v4_api.json',
        r'D:/ai_projects/ComfyUI/workflows/v3\ootd_faceswap_bg_v4_api.json'
    ]
    for p in paths_to_save:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(wf_production, f, indent=2, ensure_ascii=False)
        print(f'[v4 Saved] Full-length workflow saved to: {p}')

    # Also save a test profile workflow with fast frame_load_cap=60
    wf_test_preset = build_workflow_v4(
        video=args.video,
        bg_image=args.bg,
        width=args.width,
        height=args.height,
        fps=args.fps,
        frame_load_cap=60,
        facedetection='retinaface_resnet50',
        face_restore_model=args.face_restore,
        face_restore_visibility=args.visibility,
        blur_radius=args.blur_radius,
        lerp_alpha=args.lerp_alpha,
        prefix=args.prefix + '_fast_test'
    )
    test_path = r'D:/ai_projects/ComfyUI/workflows/v4\ootd_faceswap_bg_v4_test_api.json'
    with open(test_path, 'w', encoding='utf-8') as f:
        json.dump(wf_test_preset, f, indent=2, ensure_ascii=False)
    print(f'[v4 Test Saved] Fast-testing workflow (60 frames) saved to: {test_path}')

    if args.save_only:
        return

    # 2. Build test workflow with specified frames
    wf_run = build_workflow_v4(
        video=args.video,
        bg_image=args.bg,
        char_image=args.char,
        width=args.width,
        height=args.height,
        fps=args.fps,
        frame_load_cap=args.frames,
        facedetection='retinaface_resnet50',
        face_restore_model=args.face_restore,
        face_restore_visibility=args.visibility,
        codeformer_weight=args.codeformer_weight,
        bg_blur=args.bg_blur,
        blur_radius=args.blur_radius,
        lerp_alpha=args.lerp_alpha,
        prefix=args.prefix
    )

    pid = submit_workflow(wf_run)
    if not pid:
        return

    success, outputs, elapsed = wait_for_task(pid, timeout=900)
    if success:
        print(f'SUCCESS! Outputs: {json.dumps(outputs, indent=2)}')
    else:
        print('Execution timed out or failed.')

if __name__ == '__main__':
    main()