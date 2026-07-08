#!/usr/bin/env python3
"""
视频换装流水线（关键帧 + 光流插值）
流程:
  1. 提取全部帧 + 关键帧
  2. FaceProtectMask 生成面部保护遮罩
  3. IDM-VTON 仅对关键帧换装
  4. 光流插值: 用原视频运动场把换装结果 warp 到每帧
  5. 合成视频（保留音频）

用法:
  python video_outfit_faceswap.py \\
    --input output/batch_faceswap/1_faceswap.mp4 \\
    --garment input/todo/face/model1/model1face.png \\
    --garment-desc "white casual t-shirt" \\
    --output output/outfit_1.mp4
"""
import os, sys, json, time, shutil, subprocess, argparse
import numpy as np
import cv2
import torch
from pathlib import Path
from PIL import Image

COMFY_ROOT = r'D:\ai_projects\ComfyUI'
sys.path.insert(0, COMFY_ROOT)


# ============================================================
# 1. Face-Protected Mask Generator
# ============================================================
class FaceProtectMaskGen:
    """生成服装遮罩，排除面部/头发/墨镜区域"""

    def __init__(self, clothing_labels=(4, 7, 8), protect_labels=(2, 3, 11),
                 protect_expand=10, feather=5):
        import onnxruntime as ort
        import folder_paths
        parsing_path = os.path.join(
            folder_paths.models_dir, 'IDM-VTON', 'humanparsing', 'parsing_atr.onnx'
        )
        if not os.path.exists(parsing_path):
            raise FileNotFoundError(f'parsing_atr.onnx not found at {parsing_path}')
        print(f'[Mask] Loading {parsing_path}...')
        self.session = ort.InferenceSession(
            parsing_path, providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
        )
        self.clothing_labels = list(clothing_labels)
        self.protect_labels = list(protect_labels)
        self.protect_expand = protect_expand
        self.feather = feather
        print(f'[Mask] Ready. protect={self.protect_labels}')

    def generate(self, person_pil, target_size=None):
        """返回 (mask_pil, preview_pil)"""
        orig_w, orig_h = person_pil.size
        img_resized = person_pil.convert('RGB').resize((512, 512), Image.BILINEAR)
        img_np = np.array(img_resized).astype(np.float32) / 255.0
        img_np = (img_np - np.array([0.406, 0.456, 0.485])) / np.array([0.225, 0.224, 0.229])
        img_np = img_np.transpose(2, 0, 1)[np.newaxis].astype(np.float32)

        output = self.session.run(None, {self.session.get_inputs()[0].name: img_np})
        parsing_128 = np.argmax(output[0][0], axis=0).astype(np.uint8)
        parsing = np.array(Image.fromarray(parsing_128).resize((orig_w, orig_h), Image.NEAREST))

        cloth_mask = np.isin(parsing, self.clothing_labels).astype(np.uint8) * 255
        protect_mask = np.isin(parsing, self.protect_labels).astype(np.uint8) * 255

        if self.protect_expand > 0:
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                          (self.protect_expand*2+1, self.protect_expand*2+1))
            protect_mask = cv2.dilate(protect_mask, k, iterations=1)

        result = cv2.bitwise_and(cloth_mask, cv2.bitwise_not(protect_mask))
        result = cv2.morphologyEx(result, cv2.MORPH_CLOSE,
                                  cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
        if self.feather > 0:
            result = cv2.GaussianBlur(result, (self.feather*2+1, self.feather*2+1), 0)

        if target_size:
            result = cv2.resize(result, target_size, interpolation=cv2.INTER_NEAREST)

        return Image.fromarray(result, mode='L')


# ============================================================
# 2. ComfyUI API Client
# ============================================================
class ComfyAPI:
    def __init__(self, host='127.0.0.1', port=8188):
        import urllib.request
        self.base = f'http://{host}:{port}'
        urllib.request.urlopen(f'{self.base}/system_stats', timeout=5)
        print(f'[ComfyAPI] Connected to {self.base}')

    def upload(self, path):
        import urllib.request
        boundary = '----HermesBoundary'
        fname = os.path.basename(path)
        with open(path, 'rb') as f:
            data = f.read()
        body = (f'--{boundary}\r\n'
                f'Content-Disposition: form-data; name="image"; filename="{fname}"\r\n'
                f'Content-Type: image/png\r\n\r\n').encode() + data + f'\r\n--{boundary}--\r\n'.encode()
        req = urllib.request.Request(f'{self.base}/upload/image', data=body,
                                     headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
        return json.loads(urllib.request.urlopen(req).read())

    def queue_and_wait(self, workflow, timeout=300):
        import urllib.request
        data = json.dumps({'prompt': workflow}).encode()
        req = urllib.request.Request(f'{self.base}/prompt', data=data,
                                     headers={'Content-Type': 'application/json'})
        pid = json.loads(urllib.request.urlopen(req).read())['prompt_id']
        print(f'  [API] Prompt {pid} queued')
        t0 = time.time()
        while time.time() - t0 < timeout:
            h = json.loads(urllib.request.urlopen(f'{self.base}/history/{pid}').read())
            if pid in h:
                return h[pid]
            time.sleep(2)
        raise TimeoutError(f'Prompt {pid} timeout {timeout}s')

    def idm_vton(self, person_path, garment_path, mask_path, garment_desc,
                 w=768, h=1024, steps=30, seed=42, prefix='outfit'):
        pn = self.upload(person_path).get('name', os.path.basename(person_path))
        gn = self.upload(garment_path).get('name', os.path.basename(garment_path))
        mn = self.upload(mask_path).get('name', os.path.basename(mask_path))

        # 记录上传前已有的 output 文件
        output_dir = os.path.join(COMFY_ROOT, 'output')
        before = set(os.listdir(output_dir))

        wf = {
            "1": {"class_type": "LoadImage", "inputs": {"image": pn, "upload": "image"}},
            "2": {"class_type": "LoadImage", "inputs": {"image": gn, "upload": "image"}},
            "3": {"class_type": "LoadImage", "inputs": {"image": mn, "upload": "image"}},
            "4": {"class_type": "DWPreprocessor", "inputs": {
                "image": ["1", 0], "detect_hand": "enable", "detect_body": "enable",
                "detect_face": "enable", "resolution": 768, "bbox_detector": "yolox_l.onnx"}},
            "5": {"class_type": "PipelineLoader", "inputs": {"weight_dtype": "float16"}},
            "6": {"class_type": "IDM-VTON", "inputs": {
                "pipeline": ["5", 0], "human_img": ["1", 0], "pose_img": ["4", 0],
                "mask_img": ["3", 0], "garment_img": ["2", 0],
                "garment_description": garment_desc,
                "negative_prompt": "low quality, blurry, distorted",
                "width": w, "height": h, "num_inference_steps": steps,
                "guidance_scale": 2.0, "strength": 1.0, "seed": seed}},
            "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": prefix}},
        }
        history = self.queue_and_wait(wf)

        # 方法1: 从 history outputs 找
        for nid, out in history.get('outputs', {}).items():
            if 'images' in out:
                for img in out['images']:
                    fname = img.get('filename', '')
                    # ComfyUI 可能返回子目录路径
                    src = os.path.join(output_dir, fname)
                    if os.path.exists(src):
                        return src
                    # 也试试去掉子目录
                    src2 = os.path.join(output_dir, os.path.basename(fname))
                    if os.path.exists(src2):
                        return src2

        # 方法2: diff output 目录找新文件
        after = set(os.listdir(output_dir))
        new_files = sorted(after - before)
        for f in new_files:
            if f.startswith(prefix) and f.endswith('.png'):
                return os.path.join(output_dir, f)

        # 方法3: 按时间戳找最新匹配文件
        import glob
        candidates = sorted(glob.glob(os.path.join(output_dir, f'{prefix}*00001_.png')),
                            key=os.path.getmtime, reverse=True)
        if candidates:
            return candidates[0]

        return None


# ============================================================
# 3. Optical Flow Interpolation
# ============================================================
    def idm_vton_faceprotect(self, person_path, garment_path, garment_desc,
                             clothing_labels='4,7,8', protect_labels='2,3,11',
                             protect_expand=10, feather=5,
                             w=768, h=1024, steps=30, seed=42, prefix='outfit'):
        """使用 FaceProtectMask + DensePose + IDM-VTON 换装"""
        pn = self.upload(person_path).get('name', os.path.basename(person_path))
        gn = self.upload(garment_path).get('name', os.path.basename(garment_path))

        # 记录上传前已有的 output 文件
        output_dir = os.path.join(COMFY_ROOT, 'output')
        before = set(os.listdir(output_dir))

        wf = {
            "1": {"class_type": "LoadImage", "inputs": {"image": pn, "upload": "image"}},
            "2": {"class_type": "LoadImage", "inputs": {"image": gn, "upload": "image"}},
            "4": {"class_type": "DWPreprocessor", "inputs": {
                "image": ["1", 0], "detect_hand": "enable", "detect_body": "enable",
                "detect_face": "enable", "resolution": 768, "bbox_detector": "yolox_l.onnx"}},
            "5": {"class_type": "PipelineLoader", "inputs": {"weight_dtype": "float16"}},
            "8": {"class_type": "FaceProtectMask", "inputs": {
                "image": ["1", 0], "clothing_labels": clothing_labels,
                "protect_labels": protect_labels, "protect_expand": protect_expand,
                "feather": feather}},
            "10": {"class_type": "MaskToImage", "inputs": {"mask": ["8", 0]}},
            "6": {"class_type": "IDM-VTON", "inputs": {
                "pipeline": ["5", 0], "human_img": ["1", 0], "pose_img": ["4", 0],
                "mask_img": ["10", 0], "garment_img": ["2", 0],
                "garment_description": garment_desc,
                "negative_prompt": "low quality, blurry, distorted",
                "width": w, "height": h, "num_inference_steps": steps,
                "guidance_scale": 2.0, "strength": 1.0, "seed": seed}},
            "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": prefix}},
        }
        history = self.queue_and_wait(wf)

        # 方法1: 从 history outputs 找
        for nid, out in history.get('outputs', {}).items():
            if 'images' in out:
                for img in out['images']:
                    fname = img.get('filename', '')
                    src = os.path.join(output_dir, fname)
                    if os.path.exists(src):
                        return src
                    src2 = os.path.join(output_dir, os.path.basename(fname))
                    if os.path.exists(src2):
                        return src2

        # 方法2: diff output 目录找新文件
        after = set(os.listdir(output_dir))
        new_files = sorted(after - before)
        for f in new_files:
            if f.startswith(prefix) and f.endswith('.png'):
                return os.path.join(output_dir, f)

        # 方法3: 按时间戳找最新匹配文件
        import glob
        candidates = sorted(glob.glob(os.path.join(output_dir, f'{prefix}*00001_.png')),
                            key=os.path.getmtime, reverse=True)
        if candidates:
            return candidates[0]

        return None
def warp_with_flow(img, flow):
    """用光流场 warp 一张图"""
    h, w = flow.shape[:2]
    flow_map = flow.copy()
    flow_map[:, :, 0] += np.arange(w)
    flow_map[:, :, 1] += np.arange(h)[:, np.newaxis]
    flow_map = flow_map.astype(np.float32)
    return cv2.remap(img, flow_map[:, :, 0], flow_map[:, :, 1], cv2.INTER_LINEAR)


def compute_flow(prev_frame, curr_frame):
    """计算两帧之间的光流 (Farneback)"""
    gray1 = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)
    return cv2.calcOpticalFlowFarneback(
        gray1, gray2, None, 0.5, 3, 15, 3, 5, 1.2, 0
    )


def interpolate_keyframes(original_frames, swapped_keyframes, keyframe_indices,
                          total_frames):
    """用光流在关键帧之间插值生成全部帧。

    原理:
      - 对于每个中间帧，找到前后两个关键帧
      - 计算原视频中: 关键帧→中间帧 的光流
      - 用该光流 warp 换装后的关键帧
      - 前后两个 warp 结果用 alpha 混合
    """
    result_frames = []
    kf_set = set(keyframe_indices)
    n_kf = len(keyframe_indices)

    for i in range(total_frames):
        # 找到前后关键帧
        left_kf = 0
        right_kf = n_kf - 1
        for ki in range(n_kf):
            if keyframe_indices[ki] <= i:
                left_kf = ki
            if keyframe_indices[ki] >= i:
                right_kf = ki
                break

        if left_kf == right_kf:
            # 精确命中关键帧
            result_frames.append(swapped_keyframes[left_kf])
            continue

        # alpha: 0=全用左关键帧, 1=全用右关键帧
        left_idx = keyframe_indices[left_kf]
        right_idx = keyframe_indices[right_kf]
        span = right_idx - left_idx
        alpha = (i - left_idx) / span if span > 0 else 0.0

        # 光流 warp: 从左关键帧 warp 到当前帧
        flow_L = compute_flow(original_frames[left_idx], original_frames[i])
        warped_L = warp_with_flow(swapped_keyframes[left_kf], flow_L)

        # 光流 warp: 从右关键帧 warp 到当前帧
        flow_R = compute_flow(original_frames[right_idx], original_frames[i])
        warped_R = warp_with_flow(swapped_keyframes[right_kf], flow_R)

        # alpha 混合
        blended = cv2.addWeighted(warped_L, 1 - alpha, warped_R, alpha, 0)
        result_frames.append(blended)

    return result_frames


# ============================================================
# 4. Video Utilities
# ============================================================
def get_video_info(path):
    # Stream info: width,height,fps
    stream = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-select_streams', 'v:0',
         '-show_entries', 'stream=r_frame_rate,width,height',
         '-of', 'csv=p=0', path],
        capture_output=True, text=True).stdout.strip().split(',')
    # Format info: duration
    dur_str = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
         '-of', 'csv=p=0', path],
        capture_output=True, text=True).stdout.strip()
    w, h = int(stream[0]), int(stream[1])
    fps_str = stream[2].strip()
    fps = float(fps_str.split('/')[0]) / float(fps_str.split('/')[1]) if '/' in fps_str else float(fps_str)
    dur = float(dur_str)
    return {'fps': fps, 'duration': dur, 'width': w, 'height': h}


def extract_all_frames(path, out_dir):
    """提取全部帧（保持原始帧率）"""
    os.makedirs(out_dir, exist_ok=True)
    subprocess.run([
        'ffmpeg', '-i', path,
        os.path.join(out_dir, 'frame_%06d.png'), '-y'
    ], capture_output=True, check=True)
    return sorted(Path(out_dir).glob('frame_*.png'))


def composite_video(frames_dir, output, fps, audio_src=None):
    cmd = ['ffmpeg', '-framerate', str(fps), '-start_number', '1',
           '-i', os.path.join(frames_dir, 'frame_%06d.png')]
    if audio_src:
        cmd += ['-i', audio_src, '-c:a', 'aac', '-map', '0:v:0', '-map', '1:a:0?']
    cmd += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', output, '-y']
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f'  ffmpeg error: {r.stderr[-500:]}')
        raise RuntimeError('composite failed')
    return output


# ============================================================
# 5. Pipeline
# ============================================================
def run(args):
    t0 = time.time()
    tmp = args.output + '_tmp'
    os.makedirs(tmp, exist_ok=True)

    # ── Step 0: 视频信息 ──
    info = get_video_info(args.input)
    total_frames = int(info['duration'] * info['fps'])
    print(f'\n输入: {args.input}')
    print(f'  {info["width"]}x{info["height"]}, {info["fps"]:.1f}fps, '
          f'{info["duration"]:.1f}s, ~{total_frames} frames')

    # ── Step 1: 提取全部帧 ──
    print(f'\n[Step 1/5] 提取全部帧...')
    all_frames_dir = os.path.join(tmp, 'all_frames')
    all_frames = extract_all_frames(args.input, all_frames_dir)
    actual_total = len(all_frames)
    print(f'  提取到 {actual_total} 帧')

    # 选取关键帧索引 (每 N 帧取一个)
    kf_step = max(1, int(args.keyframe_interval * info['fps']))
    kf_indices = list(range(0, actual_total, kf_step))
    # 确保最后一帧也是关键帧
    if kf_indices[-1] != actual_total - 1:
        kf_indices.append(actual_total - 1)
    print(f'  关键帧间隔: {kf_step} 帧 ({args.keyframe_interval}s), 共 {len(kf_indices)} 个关键帧')

    # ── Step 2: 生成面部保护遮罩 ──
    print(f'\n[Step 2/5] 生成面部保护遮罩...')
    mask_gen = FaceProtectMaskGen(
        clothing_labels=[int(x) for x in args.clothing_labels.split(',')],
        protect_labels=[int(x) for x in args.protect_labels.split(',')],
        protect_expand=args.protect_expand, feather=args.feather
    )

    masks_dir = os.path.join(tmp, 'masks')
    os.makedirs(masks_dir, exist_ok=True)

    for i, kf_idx in enumerate(kf_indices):
        frame = cv2.imread(str(all_frames[kf_idx]))
        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        mask = mask_gen.generate(pil_img, target_size=(args.width, args.height))
        mask.save(os.path.join(masks_dir, f'mask_{i:04d}.png'))
    print(f'  生成 {len(kf_indices)} 个遮罩')

    # ── Step 3: IDM-VTON 关键帧换装 ──
    print(f'\n[Step 3/5] IDM-VTON 关键帧换装 (ComfyUI API)...')
    client = ComfyAPI(host=args.comfy_host, port=args.comfy_port)
    garment_abs = os.path.abspath(args.garment)

    results_dir = os.path.join(tmp, 'swapped_kf')
    os.makedirs(results_dir, exist_ok=True)
    swapped_kf_paths = []

    for i, kf_idx in enumerate(kf_indices):
        kf_path = str(all_frames[kf_idx])
        dst = os.path.join(results_dir, f'kf_{i:04d}.png')

        # 断点续传: 已有结果跳过
        if os.path.exists(dst) and os.path.getsize(dst) > 1000:
            swapped_kf_paths.append(dst)
            print(f'  [{i+1}/{len(kf_indices)}] Frame {kf_idx} → 已存在，跳过')
            continue

        mask_path = os.path.join(masks_dir, f'mask_{i:04d}.png')
        prefix = f'outfit_kf_{i:04d}'

        print(f'  [{i+1}/{len(kf_indices)}] Frame {kf_idx}...')
        try:
            result_path = client.idm_vton(
                kf_path, garment_abs, mask_path, args.garment_desc,
                w=args.width, h=args.height, steps=args.steps,
                seed=args.seed, prefix=prefix
            )
            if result_path:
                dst = os.path.join(results_dir, f'kf_{i:04d}.png')
                shutil.copy2(result_path, dst)
                swapped_kf_paths.append(dst)
                print(f'    ✓ {os.path.basename(result_path)}')
            else:
                # fallback: 用原帧
                dst = os.path.join(results_dir, f'kf_{i:04d}.png')
                shutil.copy2(kf_path, dst)
                swapped_kf_paths.append(dst)
                print(f'    ⚠ 无输出，用原帧')
        except Exception as e:
            dst = os.path.join(results_dir, f'kf_{i:04d}.png')
            shutil.copy2(kf_path, dst)
            swapped_kf_paths.append(dst)
            print(f'    ❌ {e}')

    # ── Step 4: 光流插值 ──
    print(f'\n[Step 4/5] 光流插值 ({actual_total} 帧)...')

    # 读取全部原始帧 (BGR)
    orig_frames = []
    for fp in all_frames:
        orig_frames.append(cv2.imread(str(fp)))

    # 读取换装关键帧 (BGR)
    swapped_kf_imgs = []
    for p in swapped_kf_paths:
        img = cv2.imread(str(p))
        if img is not None:
            # resize 到原始视频分辨率
            img = cv2.resize(img, (info['width'], info['height']))
        swapped_kf_imgs.append(img)

    # 光流插值
    result_frames = interpolate_keyframes(
        orig_frames, swapped_kf_imgs, kf_indices, actual_total
    )

    # 保存插值结果
    out_frames_dir = os.path.join(tmp, 'output_frames')
    os.makedirs(out_frames_dir, exist_ok=True)
    for i, frame in enumerate(result_frames):
        cv2.imwrite(os.path.join(out_frames_dir, f'frame_{i+1:06d}.png'), frame)
        if (i + 1) % 100 == 0:
            print(f'  帧 {i+1}/{actual_total}')
    print(f'  插值完成')

    # ── Step 5: 合成视频 ──
    print(f'\n[Step 5/5] 合成视频...')
    composite_video(out_frames_dir, args.output, info['fps'], audio_src=args.input)

    # 完成
    if os.path.exists(args.output):
        size_mb = os.path.getsize(args.output) / 1e6
        print(f'\n✅ 完成! 耗时 {time.time()-t0:.0f}s')
        print(f'   输出: {args.output} ({size_mb:.1f}MB)')
        print(f'   关键帧: {len(kf_indices)}, 总帧: {actual_total}')
        print(f'   面部保护: ✓')
    else:
        print(f'\n❌ 失败')

    if not args.keep_tmp:
        shutil.rmtree(tmp, ignore_errors=True)
        print(f'   临时文件已清理')
    else:
        print(f'   临时文件: {tmp}')


def main():
    p = argparse.ArgumentParser(description='视频换装 (关键帧+光流插值)')
    p.add_argument('--input', required=True, help='换脸视频')
    p.add_argument('--garment', required=True, help='服装图片')
    p.add_argument('--output', required=True, help='输出视频')
    p.add_argument('--garment-desc', default='garment', help='服装描述')
    p.add_argument('--comfy-host', default='127.0.0.1')
    p.add_argument('--comfy-port', type=int, default=8188)
    p.add_argument('--width', type=int, default=768)
    p.add_argument('--height', type=int, default=1024)
    p.add_argument('--steps', type=int, default=30)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--clothing-labels', default='4,7,8')
    p.add_argument('--protect-labels', default='2,3,11')
    p.add_argument('--protect-expand', type=int, default=10)
    p.add_argument('--feather', type=int, default=5)
    p.add_argument('--keyframe-interval', type=float, default=1.0,
                   help='关键帧间隔(秒)')
    p.add_argument('--keep-tmp', action='store_true')

    args = p.parse_args()
    if not os.path.exists(args.input):
        print(f'❌ 输入不存在: {args.input}'); sys.exit(1)
    if not os.path.exists(args.garment):
        print(f'❌ 服装不存在: {args.garment}'); sys.exit(1)
    run(args)


if __name__ == '__main__':
    main()
