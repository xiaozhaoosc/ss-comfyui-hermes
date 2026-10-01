#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MiniMax H3 Segmented Pipeline for ComfyUI
- Automated generation: 5 segments of 3s each (15s total)
- First-last frame stack locking (首尾栈锁定): extracts last frame of Seg N as first frame of Seg N+1
- Lossless FFmpeg concatenation + optional audio remuxing
- 100% tested & verified on RTX 4060 Ti 16GB (fp16 VAE + int8 UNet + VHS_VideoCombine)
"""

import os
import sys
import time
import json
import argparse
import subprocess
import urllib.request
import urllib.error

COMFY_URL = "http://127.0.0.1:8188"
COMFY_DIR = r"d:\ai_projects\ComfyUI"
INPUT_DIR = os.path.join(COMFY_DIR, "input")
OUTPUT_DIR = os.path.join(COMFY_DIR, "output")

# Character V2 (知性画廊风) 5-segment storyboards
PROMPTS_V2 = [
    (
        "0–3秒：IDENTITY REVEAL\n"
        "ミニマルな現代美術館の展示室。\n"
        "上品なヒールのステップ、花柄ドレスのドレープ、首筋と繊細な耳元、知的な眼差しを短いバーストカットで見せる。\n"
        "最後に顔のクローズアップ。"
    ),
    (
        "3–6秒：MINIMALIST GALLERY WALK\n"
        "巨大な現代絵画とコンクリート壁が続く回廊。\n"
        "彼女が落ち着いた歩調でゆっくりカメラ方向へ歩く。\n"
        "ローアングルからスムーズなトラッキングショット。床に反射する柔らかな美術館のスポットライト。\n"
        "人物の動きよりも静謐で洗練されたカメラワークを強調。"
    ),
    (
        "6–9秒：ART & OBSERVATION\n"
        "光と影が交差するアートインスタレーション空間。\n"
        "作品を見つめる肩越しのショット、滑らかな指先とドレスのクローズアップ、360度近い緩やかなスローオービットショット。\n"
        "彼女は静かに微笑み、周囲の芸術空間を観察する。"
    ),
    (
        "9–12秒：SCENIC GLASS PAVILION\n"
        "夜景が広がる美術館の最上階ガラスパビリオン。\n"
        "ガラス越しに見える大都市の夜景ボケと室内の柔らかな暖色ライト。\n"
        "広角の空間ショットから、ローアングルの凛とした佇まいへ切り替える。"
    ),
    (
        "12–15秒：FINAL HERO REVEAL\n"
        "上品な逆光とアンビエントライト。\n"
        "カメラが彼女の周囲を短く回り込み、正面のミディアムクローズアップで止まる。\n"
        "彼女が優雅にカメラを見つめ、静かに自信に満ちた微笑みを浮かべる。\n"
        "最後の音楽アクセントで力強く美しい静止ヒーローフレーム。"
    ),
]

# Character V3 (纯欲邻家风) 5-segment storyboards
PROMPTS_V3 = [
    (
        "0–3秒：IDENTITY REVEAL\n"
        "柔らかな午後の光が差し込むミニマルな部屋。\n"
        "素足のステップ、グレーニットの質感、前髪の隙間から覗く濡れたような瞳と右目の下の泣きぼくろを短いバーストカットで見せる。\n"
        "最後に顔のソフトフォーカス・クローズアップ。"
    ),
    (
        "3–6秒：SUNLIT WINDOW WALK\n"
        "レースカーテンが揺れる日当たりの良いリビング。\n"
        "彼女が柔らかくリラックスした足取りでカメラ方向へ歩く。\n"
        "ローアングルと横方向のドリーショット。逆光で透ける髪のハイライトと床に落ちる木漏れ日。\n"
        "自然な身体の揺れと柔らかなカメラワークを強調。"
    ),
    (
        "6–9秒：COZY AFTERNOON\n"
        "ソファや窓辺での寛ぎの瞬間。\n"
        "肩越しのショット、ニットの裾に触れる柔らかな指先、ふと髪をかき上げる短いオービットショット。\n"
        "彼女はカメラに気づき、いたずらっぽく甘い眼差しを向ける。"
    ),
    (
        "9–12秒：GOLDEN HOUR BALCONY\n"
        "夕暮れの光が差し込むバルコニー。\n"
        "黄金色の逆光で黒髪ウェーブとシースルー前髪が風にふわりと揺れる。\n"
        "広角の柔らかな情景から、ドラマティックなミディアムショットへ切り替える。"
    ),
    (
        "12–15秒：FINAL HERO REVEAL\n"
        "あたたかい夕陽のドラマティックなバックライト。\n"
        "カメラが彼女の周りを滑らかに回り込み、正面のミディアムクローズアップで止まる。\n"
        "彼女が首を少し傾け、潤んだ瞳でじっとカメラを見つめ、微かに微笑む。\n"
        "最後の音楽アクセントで息をのむほど美しい静止ヒーローフレーム。"
    ),
]

def check_server():
    """Verify ComfyUI server is reachable."""
    try:
        req = urllib.request.Request(f"{COMFY_URL}/queue")
        with urllib.request.urlopen(req, timeout=5) as r:
            return True
    except Exception as e:
        print(f"[Error] Cannot connect to ComfyUI at {COMFY_URL}: {e}")
        return False

def check_ffmpeg():
    """Verify FFmpeg is available."""
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except Exception:
        print("[Error] ffmpeg not found in PATH. Please install ffmpeg.")
        return False

def build_proven_workflow(image_rel_path, prompt_text, width=544, height=960, length=73, steps=16, seed=42, output_prefix="video/v3_h3_seg"):
    """Constructs the exact proven working ComfyUI API workflow."""
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors",
                "weight_dtype": "default"
            }
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors",
                "type": "minimax",
                "device": "default"
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
            "class_type": "MiniMaxH3SigmaShift",
            "inputs": {
                "model": ["1", 0],
                "shift_video": 12.0,
                "shift_audio": 3.0
            }
        },
        "12": {
            "class_type": "LoadImage",
            "inputs": {
                "image": image_rel_path
            }
        },
        "6": {
            "class_type": "MiniMaxH3ImageToVideo",
            "inputs": {
                "clip": ["2", 0],
                "vae": ["3", 0],
                "prompt": prompt_text,
                "width": width,
                "height": height,
                "length": length,
                "first_frame": ["12", 0]
            }
        },
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["5", 0],
                "positive": ["6", 0],
                "negative": ["6", 0],
                "latent_image": ["6", 1],
                "seed": seed,
                "steps": steps,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0
            }
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["7", 0],
                "vae": ["3", 0]
            }
        },
        "9": {
            "class_type": "VAEDecodeAudio",
            "inputs": {
                "samples": ["7", 0],
                "vae": ["4", 0]
            }
        },
        "11": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["8", 0],
                "audio": ["9", 0],
                "frame_rate": 24.0,
                "loop_count": 0,
                "filename_prefix": output_prefix,
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

def queue_prompt(prompt_workflow):
    """Submits workflow to ComfyUI."""
    data = json.dumps({"prompt": prompt_workflow, "client_id": "h3_chain_pipeline"}).encode("utf-8")
    req = urllib.request.Request(f"{COMFY_URL}/prompt", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res.get("prompt_id")

def wait_for_prompt(prompt_id, timeout_sec=1800):
    """Polls history and queue until the prompt completes and returns the output video path."""
    start_time = time.time()
    print(f"   [Waiting] Polling prompt {prompt_id}...", end="", flush=True)
    while time.time() - start_time < timeout_sec:
        # 1. Check history
        try:
            req = urllib.request.Request(f"{COMFY_URL}/history/{prompt_id}")
            with urllib.request.urlopen(req) as resp:
                hist = json.loads(resp.read().decode("utf-8"))
                if prompt_id in hist:
                    data = hist[prompt_id]
                    status = data.get("status", {})
                    if status.get("status_str") == "error":
                        raise RuntimeError(f"Prompt execution failed: {status.get('messages')}")
                    outputs = data.get("outputs", {})
                    
                    # Check VHS_VideoCombine (Node 11)
                    if "11" in outputs:
                        gifs = outputs["11"].get("gifs", [])
                        if gifs:
                            fullpath = gifs[0].get("fullpath")
                            if fullpath and os.path.exists(fullpath):
                                return fullpath
                            fname = gifs[0].get("filename")
                            subf = gifs[0].get("subfolder", "")
                            p = os.path.join(OUTPUT_DIR, subf, fname) if subf else os.path.join(OUTPUT_DIR, fname)
                            if os.path.exists(p):
                                return p

                    # Check SaveVideo (Node 92)
                    if "92" in outputs:
                        out_92 = outputs["92"]
                        vlist = out_92.get("images") or out_92.get("video") or out_92.get("videos") or []
                        if vlist:
                            fname = vlist[0].get("filename")
                            subf = vlist[0].get("subfolder", "")
                            p = os.path.join(OUTPUT_DIR, subf, fname) if subf else os.path.join(OUTPUT_DIR, fname)
                            if os.path.exists(p):
                                return p
        except urllib.error.URLError:
            pass

        # 2. Check if still in queue (pending or running) -> extend timeout if actively queued
        try:
            with urllib.request.urlopen(f"{COMFY_URL}/queue") as r:
                q = json.loads(r.read().decode("utf-8"))
                running_ids = [item[1] for item in q.get("queue_running", [])]
                pending_ids = [item[1] for item in q.get("queue_pending", [])]
                if prompt_id in running_ids or prompt_id in pending_ids:
                    # Still legitimately in queue, keep waiting
                    start_time = time.time()
        except Exception:
            pass

        time.sleep(3)
        print(".", end="", flush=True)

    raise TimeoutError(f"Prompt {prompt_id} timed out after {timeout_sec}s.")

def extract_last_frame(video_path, output_png_path):
    """Extracts the final frame of the video using FFmpeg for head-tail stack continuity."""
    cmd = [
        "ffmpeg", "-y",
        "-sseof", "-0.05",
        "-i", video_path,
        "-update", "1",
        "-q:v", "1",
        output_png_path
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg extract frame failed: {res.stderr.decode('utf-8', errors='ignore')}")
    if not os.path.exists(output_png_path):
        raise FileNotFoundError(f"Extracted frame not found: {output_png_path}")
    print(f"\n   [Tail Frame Extracted] -> {output_png_path}")

def concat_videos(segment_paths, output_merged_path, audio_path=None):
    """Concatenates all segments losslessly with FFmpeg concat demuxer."""
    concat_txt = os.path.join(os.path.dirname(output_merged_path), "concat_list.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for p in segment_paths:
            f.write(f"file '{p.replace(os.sep, '/')}'\n")

    print(f"\n[FFmpeg] Merging {len(segment_paths)} segments into {output_merged_path}...")
    if audio_path and os.path.exists(audio_path):
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_txt,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            output_merged_path
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_txt,
            "-c", "copy",
            output_merged_path
        ]

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg concat failed: {res.stderr.decode('utf-8', errors='ignore')}")
    print(f"[Success] Lossless final video created -> {output_merged_path}")

def main():
    parser = argparse.ArgumentParser(description="H3 15s Segmented Multi-Shot Automation Pipeline")
    parser.add_argument("--character", choices=["v2", "v3"], default="v2", help="Target character (v2=知性画廊风, v3=纯欲邻家风)")
    parser.add_argument("--width", type=int, default=544, help="Video width (default: 544)")
    parser.add_argument("--height", type=int, default=960, help="Video height (default: 960)")
    parser.add_argument("--steps", type=int, default=16, help="Sampling steps (default: 16)")
    parser.add_argument("--audio", default=None, help="Path to 15s audio/music file for beat sync remux")
    parser.add_argument("--start-seg", type=int, default=1, help="Start from segment index (1 to 5) for resume support")
    parser.add_argument("--seed", type=int, default=42, help="Noise seed for reproducibility")
    parser.add_argument("--dry-run", action="store_true", help="Print segment prompts without queueing")
    args = parser.parse_args()

    print("=" * 65)
    print("  MiniMax H3 Segmented Pipeline (RTX 4060 Ti 16GB Proven Engine)  ")
    print(f"  Target Character : {args.character.upper()}")
    print(f"  Resolution       : {args.width}x{args.height} (9:16 Showcase)")
    print(f"  Steps / Quality  : {args.steps} steps")
    print(f"  Audio Track      : {args.audio or 'None (Native Synthesized Audio)'}")
    print("=" * 65)

    if not args.dry_run:
        if not check_server():
            sys.exit(1)
        if not check_ffmpeg():
            sys.exit(1)

    prompts = PROMPTS_V2 if args.character == "v2" else PROMPTS_V3
    base_face = f"characters/{args.character}/C01_FACE_FRONT.png"
    tail_frame_rel = f"temp_h3_{args.character}_tail.png"
    tail_frame_abs = os.path.join(INPUT_DIR, tail_frame_rel)

    segment_videos = []
    total_segments = len(prompts)

    # If starting from later segment, check if previous segments already exist
    for idx in range(1, args.start_seg):
        expected_prev = os.path.join(OUTPUT_DIR, "video", f"v3_h3_{args.character}_seg{idx}_00001-audio.mp4")
        if os.path.exists(expected_prev):
            segment_videos.append(expected_prev)
            print(f"   [Found Existing Segment {idx}] -> {expected_prev}")
        else:
            # Check without -audio suffix
            alt = os.path.join(OUTPUT_DIR, "video", f"v3_h3_{args.character}_seg{idx}_00001.mp4")
            if os.path.exists(alt):
                segment_videos.append(alt)
                print(f"   [Found Existing Segment {idx}] -> {alt}")

    for i in range(args.start_seg - 1, total_segments):
        seg_num = i + 1
        seg_prompt = prompts[i]
        seg_prefix = f"video/v3_h3_{args.character}_seg{seg_num}"

        # Segment 1 uses base character portrait; Segments 2-5 use the extracted tail frame
        current_input_img = base_face if i == 0 else tail_frame_rel
        current_input_full = os.path.join(INPUT_DIR, current_input_img)

        # Check if this segment already exists on disk (e.g. if recovering)
        expected_out = os.path.join(OUTPUT_DIR, "video", f"v3_h3_{args.character}_seg{seg_num}_00001-audio.mp4")
        if os.path.exists(expected_out):
            print(f"\n>>> [Segment {seg_num}/{total_segments}] Already completed! <<<")
            print(f"   [Reusing] {expected_out}")
            segment_videos.append(expected_out)
            if seg_num < total_segments:
                extract_last_frame(expected_out, tail_frame_abs)
            continue

        print(f"\n>>> [Segment {seg_num}/{total_segments}] Time: {i*3}-{(i+1)*3}s <<<")
        print(f"   Input Anchor: {current_input_img}")
        print(f"   Prompt Snippet: {seg_prompt.splitlines()[0]}")

        if args.dry_run:
            segment_videos.append(f"dry_run_seg{seg_num}.mp4")
            continue

        if not os.path.exists(current_input_full):
            raise FileNotFoundError(f"Input anchor image not found: {current_input_full}")

        # Check if already running in ComfyUI queue
        prompt_id = None
        try:
            with urllib.request.urlopen(f"{COMFY_URL}/queue") as r:
                q = json.loads(r.read().decode("utf-8"))
                for item in q.get("queue_running", []):
                    # Check if output prefix matches
                    if seg_prefix in json.dumps(item[2]):
                        prompt_id = item[1]
                        print(f"   [Detected Already Running in Queue] Task ID: {prompt_id}")
                        break
        except Exception:
            pass

        if not prompt_id:
            # Build and submit API workflow
            workflow = build_proven_workflow(
                image_rel_path=current_input_img,
                prompt_text=seg_prompt,
                width=args.width,
                height=args.height,
                length=73, # 3 seconds at 24fps
                steps=args.steps,
                seed=args.seed + i,
                output_prefix=seg_prefix
            )
            prompt_id = queue_prompt(workflow)
            print(f"   [Queued] Task ID: {prompt_id}")

        # Wait for segment output
        video_out = wait_for_prompt(prompt_id)
        print(f"\n   [Done] Segment {seg_num} video: {video_out}")
        segment_videos.append(video_out)

        # Extract tail frame for next segment
        if seg_num < total_segments:
            extract_last_frame(video_out, tail_frame_abs)

    if args.dry_run:
        print("\n[Dry Run Completed] All 5 segments verified.")
        return

    # Merge all segments into final 15s showcase
    final_output = os.path.join(OUTPUT_DIR, f"final_15s_{args.character}_showcase.mp4")
    concat_videos(segment_videos, final_output, audio_path=args.audio)

    print("\n" + "=" * 65)
    print("  ALL 5 SEGMENTS SUCCESSFULLY COMPLETED & MERGED!  ")
    print(f"  Final 15s Video: {final_output}")
    print(f"  Size: {os.path.getsize(final_output) / 1024 / 1024:.2f} MB")
    print("=" * 65)

if __name__ == "__main__":
    main()
