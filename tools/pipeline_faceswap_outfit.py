#!/usr/bin/env python3
"""
完整的「换脸 → 换装」组合流水线

架构:
  Stage 1: Face Swap        原视频 + 源人脸 → 换脸视频
  Stage 2: Frame Extract     换脸视频 → 全部帧 + 关键帧索引
  Stage 3: Mask Generation   关键帧 → 面部保护遮罩 (ATR 解析)
  Stage 4: Outfit Swap       关键帧 + 服装图 → 换装关键帧 (IDM-VTON via ComfyUI API)
  Stage 5: Flow Interp       原帧 + 换装关键帧 → 全部换装帧 (Farneback 光流)
  Stage 6: Compose           全部帧 + 原音频 → 最终视频

每个 stage 的中间产物保存在 <output_dir>/ 下，支持断点续传。
跳过已有结果的 stage（除非 --force）。

用法:
  # 完整流水线
  python pipeline_faceswap_outfit.py run \\
    --video input/todo/swap_face/1.mp4 \\
    --face input/todo/face/model1/model1face.png \\
    --garment input/vton/garment.jpg \\
    --garment-desc "white casual t-shirt" \\
    --output-dir output/pipeline_1

  # 只跑换装（已有换脸视频）
  python pipeline_faceswap_outfit.py run \\
    --video output/batch_faceswap/1_faceswap.mp4 \\
    --skip-faceswap \\
    --garment input/vton/garment.jpg \\
    --output-dir output/pipeline_1

  # 只跑某个 stage
  python pipeline_faceswap_outfit.py stage --stage 4 \\
    --output-dir output/pipeline_1 --garment input/vton/garment.jpg
"""
import os
import sys
import json
import time
import shutil
import subprocess
import argparse
from pathlib import Path

COMFY_ROOT = r'D:\ai_projects\ComfyUI'
sys.path.insert(0, COMFY_ROOT)


# ============================================================
# Pipeline State Management
# ============================================================
class PipelineState:
    """管理 pipeline 进度状态，支持断点续传"""

    def __init__(self, output_dir):
        self.state_file = os.path.join(output_dir, '.pipeline_state.json')
        self.output_dir = output_dir
        self._load()

    def _load(self):
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                self.data = json.load(f)
        else:
            self.data = {'stages': {}, 'config': {}}

    def save(self):
        os.makedirs(self.output_dir, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def is_done(self, stage_name):
        return self.data['stages'].get(stage_name, {}).get('status') == 'done'

    def mark_done(self, stage_name, outputs=None, elapsed=0):
        self.data['stages'][stage_name] = {
            'status': 'done',
            'outputs': outputs or {},
            'elapsed': round(elapsed, 1),
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        self.save()

    def mark_error(self, stage_name, error):
        self.data['stages'][stage_name] = {
            'status': 'error',
            'error': str(error),
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        self.save()

    def summary(self):
        lines = ['Pipeline State:']
        for name, info in self.data.get('stages', {}).items():
            status = info.get('status', '?')
            elapsed = info.get('elapsed', 0)
            icon = '✅' if status == 'done' else '❌' if status == 'error' else '⏳'
            lines.append(f'  {icon} {name}: {status} ({elapsed}s)')
        return '\n'.join(lines)


# ============================================================
# Stage 1: Face Swap
# ============================================================
def stage_faceswap(state, video_path, face_path, output_dir, fps=25, max_segment=15):
    """调用 batch_faceswap.py 进行视频换脸"""
    if state.is_done('1_faceswap'):
        out = state.data['stages']['1_faceswap']['outputs']['video']
        print(f'[Stage 1] 已完成，跳过: {out}')
        return out

    print(f'\n{"="*60}')
    print(f'[Stage 1/6] Face Swap')
    print(f'  视频: {video_path}')
    print(f'  人脸: {face_path}')
    print(f'{"="*60}')

    t0 = time.time()
    swap_output = os.path.join(output_dir, '1_faceswapped')
    os.makedirs(swap_output, exist_ok=True)

    cmd = [
        sys.executable, os.path.join(COMFY_ROOT, 'tools', 'batch_faceswap.py'),
        '--video-dir', os.path.dirname(video_path),
        '--face-dir', os.path.dirname(face_path),
        '--output-dir', swap_output,
        '--fps', str(fps),
        '--max-segment', str(max_segment),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=COMFY_ROOT)

    if result.returncode != 0:
        state.mark_error('1_faceswap', result.stderr[-500:])
        print(f'  ❌ 失败: {result.stderr[-300:]}')
        raise RuntimeError('Face swap failed')

    # 找输出视频
    video_name = Path(video_path).stem
    out_video = os.path.join(swap_output, f'{video_name}_faceswap.mp4')
    if not os.path.exists(out_video):
        # 尝试找任何 mp4
        mp4s = list(Path(swap_output).glob('*.mp4'))
        if mp4s:
            out_video = str(mp4s[0])
        else:
            state.mark_error('1_faceswap', 'No output video found')
            raise FileNotFoundError(f'No faceswap output in {swap_output}')

    elapsed = time.time() - t0
    state.mark_done('1_faceswap', {'video': out_video}, elapsed)
    print(f'  ✅ 完成 ({elapsed:.0f}s): {out_video}')
    return out_video


# ============================================================
# Stage 2: Frame Extract
# ============================================================
def stage_extract_frames(state, video_path, output_dir, keyframe_interval=1.0):
    """提取全部帧 + 计算关键帧索引"""
    if state.is_done('2_extract'):
        info = state.data['stages']['2_extract']['outputs']
        print(f'[Stage 2] 已完成，跳过: {info["total_frames"]} frames, {info["n_keyframes"]} keyframes')
        return info

    print(f'\n{"="*60}')
    print(f'[Stage 2/6] Extract Frames')
    print(f'  视频: {video_path}')
    print(f'  关键帧间隔: {keyframe_interval}s')
    print(f'{"="*60}')

    t0 = time.time()
    frames_dir = os.path.join(output_dir, '2_frames')
    os.makedirs(frames_dir, exist_ok=True)

    # 获取视频信息
    probe = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-select_streams', 'v:0',
         '-show_entries', 'stream=r_frame_rate,width,height',
         '-show_entries', 'format=duration', '-of', 'json', video_path],
        capture_output=True, text=True
    )
    info = json.loads(probe.stdout)
    stream = info['streams'][0]
    w, h = stream['width'], stream['height']
    fps_str = stream['r_frame_rate']
    if '/' in fps_str:
        num, den = fps_str.split('/')
        fps = float(num) / float(den)
    else:
        fps = float(fps_str)
    duration = float(info['format']['duration'])

    # 提取全部帧
    subprocess.run([
        'ffmpeg', '-i', video_path,
        os.path.join(frames_dir, 'frame_%06d.png'), '-y'
    ], capture_output=True, check=True)

    all_frames = sorted(Path(frames_dir).glob('frame_*.png'))
    total = len(all_frames)

    # 计算关键帧索引
    kf_step = max(1, int(keyframe_interval * fps))
    kf_indices = list(range(0, total, kf_step))
    if kf_indices[-1] != total - 1:
        kf_indices.append(total - 1)

    elapsed = time.time() - t0
    outputs = {
        'frames_dir': frames_dir,
        'total_frames': total,
        'fps': fps,
        'width': w,
        'height': h,
        'duration': duration,
        'keyframe_interval': keyframe_interval,
        'kf_step': kf_step,
        'kf_indices': kf_indices,
        'n_keyframes': len(kf_indices),
    }
    state.mark_done('2_extract', outputs, elapsed)
    print(f'  ✅ {total} 帧, {len(kf_indices)} 关键帧 (间隔 {kf_step} 帧), {elapsed:.0f}s')
    return outputs


# ============================================================
# Stage 3: Mask Generation
# ============================================================
def stage_generate_masks(state, output_dir, clothing_labels='4,7,8',
                         protect_labels='2,3,11', protect_expand=10, feather=5,
                         width=768, height=1024):
    """生成面部保护遮罩"""
    if state.is_done('3_masks'):
        print(f'[Stage 3] 已完成，跳过')
        return state.data['stages']['3_masks']['outputs']

    print(f'\n{"="*60}')
    print(f'[Stage 3/6] Generate Face-Protected Masks')
    print(f'{"="*60}')

    t0 = time.time()
    extract_info = state.data['stages']['2_extract']['outputs']
    frames_dir = extract_info['frames_dir']
    kf_indices = extract_info['kf_indices']

    masks_dir = os.path.join(output_dir, '3_masks')
    os.makedirs(masks_dir, exist_ok=True)

    # 初始化 mask 生成器
    from tools.video_outfit_faceswap import FaceProtectMaskGen
    mask_gen = FaceProtectMaskGen(
        clothing_labels=[int(x) for x in clothing_labels.split(',')],
        protect_labels=[int(x) for x in protect_labels.split(',')],
        protect_expand=protect_expand, feather=feather
    )

    from PIL import Image
    import cv2

    for i, kf_idx in enumerate(kf_indices):
        mask_path = os.path.join(masks_dir, f'mask_{i:04d}.png')
        if os.path.exists(mask_path):
            continue
        frame_path = os.path.join(frames_dir, f'frame_{kf_idx+1:06d}.png')
        if not os.path.exists(frame_path):
            # fallback: 用 sorted list 找
            all_f = sorted(Path(frames_dir).glob('frame_*.png'))
            if kf_idx < len(all_f):
                frame_path = str(all_f[kf_idx])

        frame = cv2.imread(frame_path)
        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        mask = mask_gen.generate(pil_img, target_size=(width, height))
        mask.save(mask_path)

        if (i + 1) % 10 == 0:
            print(f'  遮罩 {i+1}/{len(kf_indices)}')

    elapsed = time.time() - t0
    outputs = {'masks_dir': masks_dir, 'n_masks': len(kf_indices)}
    state.mark_done('3_masks', outputs, elapsed)
    print(f'  ✅ {len(kf_indices)} 个遮罩, {elapsed:.0f}s')
    return outputs

# ============================================================
# Stage 3.5: SDXL Inpaint (去除原服装)
# ============================================================
def stage_inpaint_clothing(state, output_dir, 
                           prompt="bare skin, naked torso, smooth skin texture",
                           steps=30, cfg=7.5, seed=42,
                           comfy_host='127.0.0.1', comfy_port=8188):
    """使用 SDXL Inpaint 去除原服装区域"""
    if state.is_done('3.5_inpaint'):
        print('[Stage 3.5] 已完成，跳过')
        return state.data['stages']['3.5_inpaint']['outputs']
    
    print(f'\n{"="*60}')
    print(f'[Stage 3.5/6] SDXL Inpaint (去除原服装)')
    print(f'  Prompt: {prompt}')
    print(f'{"="*60}')
    
    t0 = time.time()
    from tools.inpaint_clothing import inpaint_keyframes
    
    extract_info = state.data['stages']['2_extract']['outputs']
    frames_dir = extract_info['frames_dir']
    kf_indices = extract_info['kf_indices']
    
    masks_dir = state.data['stages']['3_masks']['outputs']['masks_dir']
    inpaint_dir = os.path.join(output_dir, '3.5_inpainted')
    
    inpaint_keyframes(
        frames_dir, masks_dir, inpaint_dir, kf_indices,
        prompt=prompt, steps=steps, cfg=cfg, seed=seed,
        comfy_host=comfy_host, comfy_port=comfy_port
    )
    
    elapsed = time.time() - t0
    outputs = {'inpaint_dir': inpaint_dir, 'n_inpainted': len(kf_indices)}
    state.mark_done('3.5_inpaint', outputs, elapsed)
    print(f'  ✅ {len(kf_indices)} 关键帧 inpaint 完成, {elapsed:.0f}s')
    return outputs



# ============================================================
# Stage 4: IDM-VTON Outfit Swap
def stage_outfit_swap(state, output_dir, garment_path, garment_desc='garment',
                      width=768, height=1024, steps=30, seed=42,
                      comfy_host='127.0.0.1', comfy_port=8188):
    """IDM-VTON 关键帧换装"""
    if state.is_done('4_outfit'):
        print(f'[Stage 4] 已完成，跳过')
        return state.data['stages']['4_outfit']['outputs']

    print(f'\n{"="*60}')
    print(f'[Stage 4/6] IDM-VTON Outfit Swap (keyframes)')
    print(f'  服装: {garment_path}')
    print(f'  描述: {garment_desc}')
    print(f'{"="*60}')

    t0 = time.time()
    from tools.video_outfit_faceswap import ComfyAPI

    extract_info = state.data['stages']['2_extract']['outputs']
    frames_dir = extract_info['frames_dir']
    kf_indices = extract_info['kf_indices']

    results_dir = os.path.join(output_dir, '4_swapped_kf')
    os.makedirs(results_dir, exist_ok=True)

    client = ComfyAPI(host=comfy_host, port=comfy_port)
    garment_abs = os.path.abspath(garment_path)

    for i, kf_idx in enumerate(kf_indices):
        dst = os.path.join(results_dir, f'kf_{i:04d}.png')
        if os.path.exists(dst) and os.path.getsize(dst) > 1000:
            print(f'  [{i+1}/{len(kf_indices)}] Frame {kf_idx} → 已存在，跳过')
            continue

        all_f = sorted(Path(frames_dir).glob('frame_*.png'))
        kf_path = str(all_f[kf_idx]) if kf_idx < len(all_f) else str(all_f[-1])
        prefix = f'outfit_kf_{i:04d}'

        print(f'  [{i+1}/{len(kf_indices)}] Frame {kf_idx}...')
        try:
            result_path = client.idm_vton_faceprotect(
                kf_path, garment_abs, garment_desc,
                w=width, h=height, steps=steps, seed=seed, prefix=prefix
            )
            if result_path and os.path.exists(result_path):
                shutil.copy2(result_path, dst)
                print(f'    ✓')
            else:
                shutil.copy2(kf_path, dst)
                print(f'    ⚠ 无输出，用原帧')
        except Exception as e:
            shutil.copy2(kf_path, dst)
            print(f'    ❌ {e}，用原帧')

    elapsed = time.time() - t0
    outputs = {'results_dir': results_dir, 'n_swapped': len(kf_indices)}
    state.mark_done('4_outfit', outputs, elapsed)
    print(f'  ✅ {len(kf_indices)} 关键帧换装完成, {elapsed:.0f}s')
    return outputs


# ============================================================
# Stage 5: Optical Flow Interpolation
# ============================================================
def stage_interpolate(state, output_dir, video_path):
    """光流插值: 关键帧结果 → 全部帧"""
    if state.is_done('5_interp'):
        print(f'[Stage 5] 已完成，跳过')
        return state.data['stages']['5_interp']['outputs']

    print(f'\n{"="*60}')
    print(f'[Stage 5/6] Optical Flow Interpolation')
    print(f'{"="*60}')

    t0 = time.time()
    from tools.video_outfit_faceswap import interpolate_keyframes
    import cv2

    extract_info = state.data['stages']['2_extract']['outputs']
    frames_dir = extract_info['frames_dir']
    kf_indices = extract_info['kf_indices']
    total = extract_info['total_frames']
    w_out = extract_info['width']
    h_out = extract_info['height']

    results_dir = state.data['stages']['4_outfit']['outputs']['results_dir']
    out_frames_dir = os.path.join(output_dir, '5_interp_frames')
    os.makedirs(out_frames_dir, exist_ok=True)

    # 读取原始帧
    all_frames = sorted(Path(frames_dir).glob('frame_*.png'))
    orig_frames = [cv2.imread(str(f)) for f in all_frames]

    # 读取换装关键帧
    swapped_kf = []
    for i in range(len(kf_indices)):
        p = os.path.join(results_dir, f'kf_{i:04d}.png')
        img = cv2.imread(p)
        if img is not None:
            img = cv2.resize(img, (w_out, h_out))
        swapped_kf.append(img)

    # 光流插值
    result_frames = interpolate_keyframes(orig_frames, swapped_kf, kf_indices, total)

    # 保存
    for i, frame in enumerate(result_frames):
        cv2.imwrite(os.path.join(out_frames_dir, f'frame_{i+1:06d}.png'), frame)
        if (i + 1) % 200 == 0:
            print(f'  帧 {i+1}/{total}')

    elapsed = time.time() - t0
    outputs = {'interp_frames_dir': out_frames_dir, 'total_frames': total}
    state.mark_done('5_interp', outputs, elapsed)
    print(f'  ✅ {total} 帧插值完成, {elapsed:.0f}s')
    return outputs


# ============================================================
# Stage 6: Video Composition
# ============================================================
def stage_compose(state, output_dir, video_path, output_name='final.mp4'):
    """合成最终视频（保留原始音频）"""
    if state.is_done('6_compose'):
        out = state.data['stages']['6_compose']['outputs']['video']
        print(f'[Stage 6] 已完成，跳过: {out}')
        return out

    print(f'\n{"="*60}')
    print(f'[Stage 6/6] Compose Final Video')
    print(f'{"="*60}')

    t0 = time.time()
    extract_info = state.data['stages']['2_extract']['outputs']
    fps = extract_info['fps']
    interp_dir = state.data['stages']['5_interp']['outputs']['interp_frames_dir']

    output_path = os.path.join(output_dir, output_name)

    cmd = [
        'ffmpeg', '-framerate', str(fps), '-start_number', '1',
        '-i', os.path.join(interp_dir, 'frame_%06d.png'),
        '-i', video_path,
        '-c:v', 'libx264', '-c:a', 'aac',
        '-map', '0:v:0', '-map', '1:a:0?',
        '-pix_fmt', 'yuv420p', '-crf', '18',
        output_path, '-y'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        state.mark_error('6_compose', result.stderr[-500:])
        raise RuntimeError(f'Video compose failed: {result.stderr[-300:]}')

    elapsed = time.time() - t0
    size_mb = os.path.getsize(output_path) / 1e6
    state.mark_done('6_compose', {'video': output_path, 'size_mb': round(size_mb, 1)}, elapsed)
    print(f'  ✅ {output_path} ({size_mb:.1f}MB), {elapsed:.0f}s')
    return output_path


# ============================================================
# Pipeline Orchestrator
# ============================================================
def run_pipeline(args):
    """运行完整 pipeline"""
    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)
    state = PipelineState(output_dir)

    video_path = os.path.abspath(args.video)
    t_total = time.time()

    print(f'\n{"#"*60}')
    print(f'# Pipeline: Face Swap → Outfit Swap')
    print(f'# 输入: {video_path}')
    print(f'# 输出: {output_dir}')
    print(f'# Garment: {args.garment}')
    print(f'{"#"*60}')

    # Stage 1: Face Swap (可跳过)
    if args.skip_faceswap:
        print('\n[Stage 1/6] Face Swap: SKIPPED (using input video directly)')
        faceswap_video = video_path
    else:
        if not args.face:
            print('❌ 需要 --face 参数（源人脸图片）')
            sys.exit(1)
        faceswap_video = stage_faceswap(
            state, video_path, args.face, output_dir,
            fps=args.fps, max_segment=args.max_segment
        )

    # Stage 2: Extract Frames
    extract_info = stage_extract_frames(
        state, faceswap_video, output_dir,
        keyframe_interval=args.keyframe_interval
    )

    # Stage 3: Mask Generation
    stage_generate_masks(
        state, output_dir,
        clothing_labels=args.clothing_labels,
        protect_labels=args.protect_labels,
        protect_expand=args.protect_expand,
        feather=args.feather,
        width=args.width, height=args.height
    )
    # Stage 4: IDM-VTON Outfit Swap
    stage_outfit_swap(
        state, output_dir,
        garment_path=args.garment,
        garment_desc=args.garment_desc,
        width=args.width, height=args.height,
        steps=args.steps, seed=args.seed,
        comfy_host=args.comfy_host, comfy_port=args.comfy_port
    )

    # Stage 5: Optical Flow Interpolation
    stage_interpolate(state, output_dir, faceswap_video)

    # Stage 6: Compose
    output_video = stage_compose(
        state, output_dir, faceswap_video,
        output_name=args.output_name
    )

    # Summary
    total_elapsed = time.time() - t_total
    print(f'\n{"#"*60}')
    print(f'# Pipeline 完成! 总耗时 {total_elapsed:.0f}s ({total_elapsed/60:.1f}min)')
    print(f'# 输出: {output_video}')
    print(f'{"#"*60}')
    print(state.summary())


def run_stage(args):
    """运行单个 stage"""
    output_dir = os.path.abspath(args.output_dir)
    state = PipelineState(output_dir)

    video_path = state.data.get('config', {}).get('video', '')
    if args.video:
        video_path = os.path.abspath(args.video)

    stage = args.stage
    if stage == 1:
        stage_faceswap(state, video_path, args.face, output_dir)
    elif stage == 2:
        stage_extract_frames(state, video_path, output_dir,
                             keyframe_interval=args.keyframe_interval)
    elif stage == 3:
        stage_generate_masks(state, output_dir)
    elif stage == 3.5:
        stage_inpaint_clothing(state, output_dir, seed=args.seed, comfy_host=args.comfy_host, comfy_port=args.comfy_port)
    elif stage == 4:
        stage_outfit_swap(state, output_dir, args.garment,
                          garment_desc=args.garment_desc)
    elif stage == 5:
        stage_interpolate(state, output_dir, video_path)
    elif stage == 6:
        stage_compose(state, output_dir, video_path)


def main():
    parser = argparse.ArgumentParser(
        description='换脸→换装 组合流水线',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest='command')

    # run 子命令
    p_run = sub.add_parser('run', help='运行完整流水线')
    p_run.add_argument('--video', required=True, help='输入视频')
    p_run.add_argument('--face', default=None, help='源人脸图片（换脸用）')
    p_run.add_argument('--garment', required=True, help='目标服装图片')
    p_run.add_argument('--garment-desc', default='garment', help='服装描述')
    p_run.add_argument('--output-dir', required=True, help='输出目录')
    p_run.add_argument('--output-name', default='final.mp4', help='最终视频文件名')
    p_run.add_argument('--skip-faceswap', action='store_true', help='跳过换脸（直接用输入视频）')

    # 通用参数
    p_run.add_argument('--comfy-host', default='127.0.0.1')
    p_run.add_argument('--comfy-port', type=int, default=8188)
    p_run.add_argument('--width', type=int, default=768)
    p_run.add_argument('--height', type=int, default=1024)
    p_run.add_argument('--steps', type=int, default=30)
    p_run.add_argument('--seed', type=int, default=42)
    p_run.add_argument('--fps', type=int, default=25)
    p_run.add_argument('--max-segment', type=int, default=15)
    p_run.add_argument('--keyframe-interval', type=float, default=1.0)
    p_run.add_argument('--clothing-labels', default='4,7,8')
    p_run.add_argument('--protect-labels', default='2,3,11')
    p_run.add_argument('--protect-expand', type=int, default=10)
    p_run.add_argument('--feather', type=int, default=5)

    # stage 子命令
    p_stage = sub.add_parser('stage', help='运行单个 stage')
    p_stage.add_argument('--stage', type=int, required=True, choices=[1, 2, 3, 3.5, 4, 5, 6])
    p_stage.add_argument('--video', default=None)
    p_stage.add_argument('--face', default=None)
    p_stage.add_argument('--garment', default=None)
    p_stage.add_argument('--garment-desc', default='garment')
    p_stage.add_argument('--output-dir', required=True)
    p_stage.add_argument('--keyframe-interval', type=float, default=1.0)
    p_stage.add_argument('--comfy-host', default='127.0.0.1')
    p_stage.add_argument('--comfy-port', type=int, default=8188)
    p_stage.add_argument('--width', type=int, default=768)
    p_stage.add_argument('--height', type=int, default=1024)
    p_stage.add_argument('--steps', type=int, default=30)

    # status 子命令
    p_status = sub.add_parser('status', help='查看 pipeline 状态')
    p_status.add_argument('--output-dir', required=True)

    args = parser.parse_args()

    if args.command == 'run':
        run_pipeline(args)
    elif args.command == 'stage':
        run_stage(args)
    elif args.command == 'status':
        state = PipelineState(args.output_dir)
        print(state.summary())
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
