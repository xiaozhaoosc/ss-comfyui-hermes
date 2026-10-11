"""
一键换装工作流 — 自动生成 mask/pose，支持图片和视频 (v2 优化版)
用法:
  图片: python tryon.py --input photo.jpg --garment shirt.jpg --output result.png
  视频: python tryon.py --input video.mp4 --garment shirt.jpg --output result.mp4 --fps 5 --frame-skip 5
"""
import os, sys, argparse, subprocess

# 动态计算 ComfyUI 根目录，保证可移植性
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(CURRENT_DIR) == 'v2':
    COMFY_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
elif os.path.basename(CURRENT_DIR) == 'tools':
    COMFY_ROOT = os.path.dirname(CURRENT_DIR)
else:
    COMFY_ROOT = r'D:\ai_projects\ComfyUI'

PIPELINE = os.path.join(COMFY_ROOT, 'tools', 'v2', 'faceswap_tryon_pipeline.py')
GEN_MASK = os.path.join(COMFY_ROOT, 'tools', 'gen_mask.py')
FIX_MASK = os.path.join(COMFY_ROOT, 'tools', 'fix_mask.py')
GEN_POSE = os.path.join(COMFY_ROOT, 'tools', 'gen_pose.py')

# 预生成素材缓存目录
CACHE_DIR = os.path.join(COMFY_ROOT, 'input', 'todo', 'tryon_cache')


def ensure_scripts():
    """确保辅助脚本存在"""
    for path in [PIPELINE, GEN_MASK, FIX_MASK, GEN_POSE]:
        if not os.path.exists(path):
            print(f"[ERR] 缺少脚本: {path}")
            sys.exit(1)


def generate_mask_and_pose(input_image):
    """为输入图片/视频自动生成 mask 和 pose"""
    import hashlib
    # 结合文件修改时间和文件大小，避免文件更新时缓存不刷新
    mtime = os.path.getmtime(input_image)
    fsize = os.path.getsize(input_image)
    h = hashlib.md5(f"{input_image}_{mtime}_{fsize}".encode()).hexdigest()[:8]
    cache = os.path.join(CACHE_DIR, h)
    os.makedirs(cache, exist_ok=True)
    
    mask_path = os.path.join(cache, 'mask.png')
    pose_path = os.path.join(cache, 'pose.png')
    
    if os.path.exists(mask_path) and os.path.exists(pose_path):
        print(f"[Cache] 使用缓存: {cache}")
        return pose_path, mask_path
    
    print(f"[生成] 为 {os.path.basename(input_image)} 生成 mask 和 pose...")
    
    # 注入 Python 搜索路径
    sys.path.insert(0, COMFY_ROOT)
    sys.path.insert(0, os.path.join(COMFY_ROOT, 'custom_nodes', 'ComfyUI-IDM-VTON'))
    
    import numpy as np, cv2
    from PIL import Image
    import onnxruntime as ort
    
    # 判断是否为视频文件，若为视频则提取第一帧用于生成遮罩和骨骼
    is_video = input_image.lower().endswith(('.mp4', '.avi', '.mov', '.mkv'))
    ref_image_path = input_image
    if is_video:
        print(f"  [视频预处理] 提取视频首帧用于解析...")
        cap = cv2.VideoCapture(input_image)
        ret, frame = cap.read()
        cap.release()
        if not ret:
            print(f"[ERR] 无法读取视频第一帧: {input_image}")
            sys.exit(1)
        temp_frame_path = os.path.join(cache, 'temp_first_frame.png')
        cv2.imwrite(temp_frame_path, frame)
        ref_image_path = temp_frame_path
    
    # === 生成 Mask ===
    print("  [Mask] 加载解析模型...")
    parsing_path = os.path.join(COMFY_ROOT, 'models', 'IDM-VTON', 'humanparsing', 'parsing_atr.onnx')
    
    # 优先指定 CUDAExecutionProvider 硬件加速
    providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
    try:
        session = ort.InferenceSession(parsing_path, providers=providers)
        print("  [Mask] 已启用 ONNX CUDA 硬件加速")
    except Exception as e:
        print(f"  [Mask] CUDA 初始化失败，退回到 CPU: {e}")
        session = ort.InferenceSession(parsing_path, providers=['CPUExecutionProvider'])
    
    person = Image.open(ref_image_path).convert('RGB')
    orig_w, orig_h = person.size
    
    img_resized = person.resize((512, 512), Image.BILINEAR)
    img_np = np.array(img_resized).astype(np.float32) / 255.0
    img_np = (img_np - np.array([0.406, 0.456, 0.485])) / np.array([0.225, 0.224, 0.229])
    img_np = img_np.transpose(2, 0, 1)[np.newaxis].astype(np.float32)
    
    output = session.run(None, {session.get_inputs()[0].name: img_np})
    raw = output[0]
    if raw.ndim == 4:
        parsing = np.argmax(raw[0], axis=0).astype(np.int32)
    elif raw.ndim == 3:
        parsing = np.argmax(raw, axis=0).astype(np.int32)
    else:
        parsing = raw.squeeze().astype(np.int32)
    
    # 上衣区域：4(Upper-clothes) + 6(Coat)
    mask = np.isin(parsing, [4, 6]).astype(np.uint8) * 255
    
    # 排除头部 (top 25%)
    h, w = mask.shape
    mask[:int(h * 0.25), :] = 0
    
    # 去噪 + 形态学 + 渐变
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    for i in range(1, num_labels):
        if stats[i, cv2.CC_STAT_AREA] < 200:
            mask[labels == i] = 0
    
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=3)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
    _, mask_binary = cv2.threshold(cv2.GaussianBlur(mask, (21, 21), 0), 127, 255, cv2.THRESH_BINARY)
    mask_feathered = cv2.GaussianBlur(mask_binary, (15, 15), 0)
    
    Image.fromarray(mask_feathered).resize((384, 512), Image.NEAREST).save(mask_path)
    print(f"  [Mask] 保存: {mask_path}")
    
    # === 生成 Pose ===
    has_pose_detector = False
    try:
        # 优先尝试从 comfyui_controlnet_aux 加载真正的 DWPose 检测器
        print("  [Pose] 尝试加载 DWPose 姿态检测器...")
        if os.path.join(COMFY_ROOT, 'custom_nodes') not in sys.path:
            sys.path.insert(0, os.path.join(COMFY_ROOT, 'custom_nodes'))
        from comfyui_controlnet_aux.src.custom_controlnet_aux.dwpose import DwposeDetector
        
        detector = DwposeDetector.from_pretrained(
            'yzd-v/DWPose',
            'yzd-v/DWPose',
            det_filename='yolox_l.onnx',
            pose_filename='dw-ll_ucoco_384.onnx',
        )
        print("  [Pose] DwposeDetector 加载成功，开始生成真实姿态...")
        pose_img = detector(person, detect_resolution=512, include_body=True, include_hand=True, include_face=False)
        pose_384 = pose_img.resize((384, 512), Image.BILINEAR)
        pose_384.save(pose_path)
        print(f"  [Pose] 已保存(真实姿态): {pose_path}")
        has_pose_detector = True
    except Exception as e:
        print(f"  [Pose] DwposeDetector 真实检测不可用 ({e})，将使用写死骨骼比例降级方案...")
        
    if not has_pose_detector:
        cx, cy = orig_w // 2, orig_h // 2
        pose_canvas = np.zeros((orig_h, orig_w, 3), dtype=np.uint8)
        head_y, neck_y = int(orig_h * 0.1), int(orig_h * 0.2)
        shoulder_y, elbow_y, hand_y = int(orig_h * 0.25), int(orig_h * 0.4), int(orig_h * 0.55)
        hip_y, knee_y, foot_y = int(orig_h * 0.6), int(orig_h * 0.75), int(orig_h * 0.95)
        shoulder_span = int(orig_w * 0.3)
        
        skeleton = [
            ((cx, head_y), (cx, neck_y), (255, 255, 255)),
            ((cx, neck_y), (cx - shoulder_span, shoulder_y), (255, 0, 0)),
            ((cx, neck_y), (cx + shoulder_span, shoulder_y), (0, 255, 0)),
            ((cx - shoulder_span, shoulder_y), (cx - shoulder_span - 20, elbow_y), (255, 0, 0)),
            ((cx + shoulder_span, shoulder_y), (cx + shoulder_span + 20, elbow_y), (0, 255, 0)),
            ((cx - shoulder_span - 20, elbow_y), (cx - shoulder_span - 10, hand_y), (255, 0, 0)),
            ((cx + shoulder_span + 20, elbow_y), (cx + shoulder_span + 10, hand_y), (0, 255, 0)),
            ((cx, neck_y), (cx - int(orig_w * 0.15), hip_y), (255, 255, 0)),
            ((cx, neck_y), (cx + int(orig_w * 0.15), hip_y), (0, 255, 255)),
            ((cx - int(orig_w * 0.15), hip_y), (cx - int(orig_w * 0.15), knee_y), (255, 255, 0)),
            ((cx + int(orig_w * 0.15), hip_y), (cx + int(orig_w * 0.15), knee_y), (0, 255, 255)),
            ((cx - int(orig_w * 0.15), knee_y), (cx - int(orig_w * 0.15), foot_y), (255, 255, 0)),
            ((cx + int(orig_w * 0.15), knee_y), (cx + int(orig_w * 0.15), foot_y), (0, 255, 255)),
        ]
        for pt1, pt2, color in skeleton:
            cv2.line(pose_canvas, pt1, pt2, color, 2)
            cv2.circle(pose_canvas, pt1, 3, (255, 255, 255), -1)
            cv2.circle(pose_canvas, pt2, 3, (255, 255, 255), -1)
        
        Image.fromarray(pose_canvas).resize((384, 512), Image.BILINEAR).save(pose_path)
        print(f"  [Pose] 已保存(写死骨骼): {pose_path}")
    
    # 清理临时视频帧图片
    if is_video and os.path.exists(ref_image_path):
        try:
            os.remove(ref_image_path)
        except:
            pass
        
    return pose_path, mask_path


def main():
    parser = argparse.ArgumentParser(description='一键换装工作流')
    parser.add_argument('--input', required=True, help='输入图片/视频')
    parser.add_argument('--garment', required=True, help='目标服装图片')
    parser.add_argument('--output', required=True, help='输出路径')
    parser.add_argument('--face', default=None, help='目标人脸（可选，不指定则跳过换脸）')
    parser.add_argument('--garment-desc', default='garment', help='服装描述')
    parser.add_argument('--steps', type=int, default=20, help='推理步数')
    parser.add_argument('--fps', type=float, default=None, help='视频帧率')
    parser.add_argument('--frame-skip', type=int, default=1, help='视频帧跳过')
    parser.add_argument('--pose', default=None, help='姿态图（不指定则自动生成）')
    parser.add_argument('--mask', default=None, help='遮罩图（不指定则自动生成）')
    args = parser.parse_args()
    
    ensure_scripts()
    
    # 自动检测模式
    is_video = args.input.lower().endswith(('.mp4', '.avi', '.mov', '.mkv'))
    mode = 'video' if is_video else 'image'
    
    # 自动生成 mask/pose
    if not args.pose or not args.mask:
        pose_path, mask_path = generate_mask_and_pose(args.input)
        args.pose = args.pose or pose_path
        args.mask = args.mask or mask_path
    
    # 构建命令
    cmd = [sys.executable, PIPELINE,
           '--mode', mode,
           '--input', args.input,
           '--garment', args.garment,
           '--output', args.output,
           '--garment-desc', args.garment_desc,
           '--steps', str(args.steps),
           '--pose', args.pose,
           '--mask', args.mask]
    
    if args.face:
        cmd += ['--face', args.face]
    else:
        cmd += ['--skip-faceswap']
    
    if mode == 'video':
        if args.fps:
            cmd += ['--fps', str(args.fps)]
        cmd += ['--frame-skip', str(args.frame_skip)]
    
    print(f'\n[启动] {mode} 模式')
    print(f'  输入: {args.input}')
    print(f'  服装: {args.garment}')
    print(f'  输出: {args.output}')
    print(f'  步数: {args.steps}')
    print(f'  换脸: {"是" if args.face else "否"}')
    print()
    
    os.chdir(COMFY_ROOT)
    subprocess.run(cmd)


if __name__ == '__main__':
    main()
