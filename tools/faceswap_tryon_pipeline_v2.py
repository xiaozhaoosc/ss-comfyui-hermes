"""
人物换脸+换装组合流水线 v2 (ComfyUI API 版)
=================================================
v2 修改点 (基于 faceswap_tryon_pipeline.py):
  - 替换 VirtualTryOn (本地 diffusers 推理) → ComfyUITryOnClient (ComfyUI HTTP API)
    原因: 本地 diffusers 与 ComfyUI 服务争抢 GPU 显存, 且依赖 numpy/diffusers 二进制兼容性
    v2:   换装环节统一走 ComfyUI API (与 batch_tryon/video_tryon 架构一致), GPU 由 ComfyUI 统一调度
  - 保留 FaceSwapper (insightface + GFPGAN) 和 PoseMaskGenerator (DWPose + ATR ONNX) 不变
    这两个模块走本地 ONNX 推理, 不依赖 diffusers, 无兼容性问题
  - ComfyUITryOnClient.tryon 接口与原版 VirtualTryOn.tryon 完全兼容 (接收 PIL, 返回 PIL)

用法:
  图片: python tools/faceswap_tryon_pipeline_v2.py --mode image --input photo.jpg --face face.jpg --garment shirt.jpg --output result.jpg
  视频: python tools/faceswap_tryon_pipeline_v2.py --mode video --input video.mp4 --face face.jpg --garment shirt.jpg --output result.mp4

流程: 换脸(insightface) → 姿态检测(DWPose) → 人体解析遮罩(ATR) → IDM-VTON 换装(ComfyUI API)
"""
import os, sys, argparse, time, shutil, subprocess, tempfile, uuid, json
import urllib.request
import numpy as np
import cv2
import torch
from PIL import Image, ImageFilter
from pathlib import Path

COMFY_ROOT = r'D:\ai_projects\ComfyUI'
COMFYUI_URL = "http://127.0.0.1:8188"
sys.path.insert(0, COMFY_ROOT)
sys.path.insert(0, os.path.join(COMFY_ROOT, 'custom_nodes', 'ComfyUI-IDM-VTON'))


# ============================================================
# 0. ComfyUI API Utilities (v2 新增)
# ============================================================
def upload_image(filepath: str) -> str:
    """上传图片到 ComfyUI, 返回内部文件名"""
    fn = os.path.basename(filepath)
    with open(filepath, "rb") as f:
        data = f.read()
    boundary = "----FormBoundary" + uuid.uuid4().hex[:16]
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{fn}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{COMFYUI_URL}/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    resp = json.loads(urllib.request.urlopen(req).read())
    return resp.get("name", fn)


def submit_workflow(workflow: dict, client_id: str = "faceswap") -> str:
    """提交工作流到 ComfyUI, 返回 prompt_id"""
    data = json.dumps({"prompt": workflow, "client_id": client_id}).encode()
    req = urllib.request.Request(
        f"{COMFYUI_URL}/prompt",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    resp = json.loads(urllib.request.urlopen(req).read())
    return resp["prompt_id"]


def wait_for_completion(prompt_id: str, timeout: int = 600) -> dict:
    """轮询 ComfyUI 直到完成, 返回 outputs dict"""
    for _ in range(timeout // 3):
        time.sleep(3)
        try:
            resp = urllib.request.urlopen(f"{COMFYUI_URL}/history/{prompt_id}").read()
            history = json.loads(resp)
            if prompt_id in history:
                status = history[prompt_id].get("status", {})
                if status.get("status_str") == "error":
                    raise RuntimeError(f"ComfyUI error: {status.get('messages', [])}")
                outputs = history[prompt_id].get("outputs", {})
                if outputs:
                    return outputs
        except urllib.error.URLError:
            pass
    raise TimeoutError(f"Prompt {prompt_id} timed out after {timeout}s")


def download_image(filename: str, subfolder: str = "", output_dir: str = None) -> Image.Image:
    """从 ComfyUI 下载输出图片, 返回 PIL Image"""
    url = f"{COMFYUI_URL}/view?filename={filename}"
    if subfolder:
        url += f"&subfolder={subfolder}"
    req = urllib.request.Request(url)
    data = urllib.request.urlopen(req).read()
    import io
    return Image.open(io.BytesIO(data))


def build_tryon_workflow(
    human_name: str, pose_name: str, mask_name: str, garment_name: str,
    description: str, negative: str, width: int, height: int,
    steps: int, guidance: float, strength: float, seed: int,
) -> dict:
    """构建 IDM-VTON ComfyUI 工作流 (与 video_tryon_pipeline 一致)"""
    return {
        "1": {"class_type": "PipelineLoader", "inputs": {"weight_dtype": "float16"}},
        "2": {"class_type": "LoadImage", "inputs": {"image": human_name, "upload": "image"}},
        "3": {"class_type": "LoadImage", "inputs": {"image": pose_name, "upload": "image"}},
        "4": {"class_type": "LoadImage", "inputs": {"image": mask_name, "upload": "image"}},
        "5": {"class_type": "LoadImage", "inputs": {"image": garment_name, "upload": "image"}},
        "10": {"class_type": "IDM-VTON", "inputs": {
            "pipeline": ["1", 0], "human_img": ["2", 0], "pose_img": ["3", 0],
            "mask_img": ["4", 0], "garment_img": ["5", 0],
            "garment_description": description, "negative_prompt": negative,
            "width": width, "height": height, "num_inference_steps": steps,
            "guidance_scale": guidance, "strength": strength, "seed": seed,
        }},
        "11": {"class_type": "SaveImage", "inputs": {"filename_prefix": "tryon_result", "images": ["10", 0]}},
    }


class ComfyUITryOnClient:
    """v2: 替代原版 VirtualTryOn, 走 ComfyUI API 而非本地 diffusers"""
    def __init__(self, garment_desc='garment'):
        print('[TryOn] ComfyUI API mode (v2)')
        try:
            urllib.request.urlopen(f"{COMFYUI_URL}/system_stats", timeout=5)
        except Exception:
            raise RuntimeError(f"ComfyUI not running at {COMFYUI_URL}")
        self.garment_desc = garment_desc
        self._tmpdir = tempfile.mkdtemp(prefix='faceswap_v2_')
        print('[TryOn] Ready (ComfyUI API)')

    def _pil_to_file(self, pil_img: Image.Image, prefix: str) -> str:
        """PIL Image → 临时 PNG 文件路径"""
        path = os.path.join(self._tmpdir, f"{prefix}_{uuid.uuid4().hex[:8]}.png")
        pil_img.convert('RGB').save(path)
        return path

    def tryon(self, person_pil, garment_pil, mask_pil, pose_pil,
              w=384, h=512, steps=20, seed=42):
        """执行换装 (接口与原版 VirtualTryOn.tryon 完全兼容)

        流程: PIL→临时文件→上传→提交工作流→等待→下载结果→返回 PIL
        """
        t0 = time.time()
        # PIL → 临时文件
        human_path = self._pil_to_file(person_pil, 'human')
        garment_path = self._pil_to_file(garment_pil, 'garment')
        mask_path = self._pil_to_file(mask_pil.convert('L'), 'mask')
        pose_path = self._pil_to_file(pose_pil, 'pose')

        # 上传
        human_name = upload_image(human_path)
        garment_name = upload_image(garment_path)
        mask_name = upload_image(mask_path)
        pose_name = upload_image(pose_path)

        # 构建并提交工作流
        workflow = build_tryon_workflow(
            human_name=human_name, pose_name=pose_name, mask_name=mask_name,
            garment_name=garment_name, description='a photo of ' + self.garment_desc,
            negative='low quality, blurry', width=w, height=h, steps=steps,
            guidance=2.0, strength=0.9, seed=seed,
        )
        prompt_id = submit_workflow(workflow, client_id=f"faceswap_{uuid.uuid4().hex[:6]}")

        # 等待完成
        outputs = wait_for_completion(prompt_id)

        # 下载结果
        for node_id, node_out in outputs.items():
            if "images" in node_out:
                for img_info in node_out["images"]:
                    result = download_image(
                        img_info["filename"],
                        img_info.get("subfolder", ""),
                    )
                    print(f'  [TryOn] 完成 ({time.time()-t0:.1f}s)')
                    return result
        raise RuntimeError("No output image from ComfyUI")


# ============================================================
# 1. Face Swap Module (insightface + GFPGAN) — 保持不变
# ============================================================
class FaceSwapper:
    def __init__(self):
        from insightface.app import FaceAnalysis
        from insightface.model_zoo import get_model
        self._FaceAnalysis = FaceAnalysis
        self._get_model = get_model
        print('[FaceSwap] Loading models...')
        self.app = FaceAnalysis(name='buffalo_l',
                                providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
        self.app.prepare(ctx_id=0, det_size=(640, 640))
        self.swapper = get_model(os.path.join(COMFY_ROOT, 'models', 'insightface', 'inswapper_128.onnx'))

        # GFPGAN
        self.restorer = None
        try:
            from gfpgan import GFPGANer
            gfpgan_path = os.path.join(COMFY_ROOT, 'models', 'facerestore_models', 'GFPGANv1.4.pth')
            if os.path.exists(gfpgan_path):
                self.restorer = GFPGANer(model_path=gfpgan_path, upscale=1,
                                         arch='clean', channel_multiplier=2, bg_upsampler=None)
                print('[FaceSwap] GFPGAN loaded')
        except Exception as e:
            print(f'[FaceSwap] GFPGAN not available: {e}')
        print('[FaceSwap] Ready (det_size=640)')

    def detect_source_face(self, face_img_path):
        """检测源人脸（只需一次）"""
        img = cv2.imread(face_img_path)
        h, w = img.shape[:2]
        if max(h, w) > 800:
            scale = 800 / max(h, w)
            img = cv2.resize(img, (int(w * scale), int(h * scale)))
        faces = self.app.get(img)
        if not faces:
            raise ValueError(f'No face detected in {face_img_path}')
        return max(faces, key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]))

    @staticmethod
    def color_correct(original_bgr, result_bgr, face_bbox, margin=30):
        """颜色校正：将换脸区域的色彩统计对齐到原图"""
        x1, y1, x2, y2 = [int(v) for v in face_bbox]
        x1, y1 = max(0, x1-margin), max(0, y1-margin)
        x2, y2 = min(result_bgr.shape[1], x2+margin), min(result_bgr.shape[0], y2+margin)
        orig_face = original_bgr[y1:y2, x1:x2].astype(np.float32)
        result_face = result_bgr[y1:y2, x1:x2].astype(np.float32)
        if orig_face.size == 0 or result_face.size == 0:
            return result_bgr
        for c in range(3):
            o_m, o_s = orig_face[:,:,c].mean(), orig_face[:,:,c].std() + 1e-6
            r_m, r_s = result_face[:,:,c].mean(), result_face[:,:,c].std() + 1e-6
            result_face[:,:,c] = (result_face[:,:,c] - r_m) * (o_s / r_s) + o_m
        result_bgr[y1:y2, x1:x2] = np.clip(result_face, 0, 255).astype(np.uint8)
        return result_bgr

    def swap_frame(self, frame_bgr, source_face):
        """对单帧换脸+增强+颜色校正"""
        target_faces = self.app.get(frame_bgr)
        if not target_faces:
            return frame_bgr

        best = max(target_faces, key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]))
        result = self.swapper.get(frame_bgr.copy(), best, source_face, paste_back=True)

        # 颜色校正
        result = self.color_correct(frame_bgr, result, best.bbox)

        if self.restorer:
            try:
                _, _, restored = self.restorer.enhance(result, has_aligned=False,
                                                       only_center_face=False, paste_back=True, weight=0.5)
                if restored is not None:
                    result = restored
            except:
                pass
        return result


# ============================================================
# 2. Pose + Mask Module (DWPose via comfyui_controlnet_aux) — 保持不变
# ============================================================
class PoseMaskGenerator:
    def __init__(self):
        print('[PoseMask] Loading DWPose (ONNX)...')
        if os.path.join(COMFY_ROOT, 'custom_nodes') not in sys.path:
            sys.path.insert(0, os.path.join(COMFY_ROOT, 'custom_nodes'))
        from comfyui_controlnet_aux.src.custom_controlnet_aux.dwpose import DwposeDetector

        self.dwpose_detector = DwposeDetector.from_pretrained(
            'yzd-v/DWPose',
            'yzd-v/DWPose',
            det_filename='yolox_l.onnx',
            pose_filename='dw-ll_ucoco_384.onnx',
        )

        print('[PoseMask] Loading Human Parsing (ONNX)...')
        import onnxruntime as ort
        parsing_path = os.path.join(COMFY_ROOT, 'models', 'IDM-VTON', 'humanparsing', 'parsing_atr.onnx')
        self.parsing_session = ort.InferenceSession(parsing_path, providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
        print('[PoseMask] Ready')

    def generate_pose(self, person_pil, target_size=(384, 512)):
        """生成 DWPose 姿态图（OpenPose 格式骨架图）"""
        pose_img = self.dwpose_detector(
            person_pil,
            detect_resolution=max(target_size),
            include_body=True,
            include_hand=True,
            include_face=False,
        )
        return pose_img.resize(target_size, Image.BILINEAR)

    def generate_pose_from_file(self, pose_path, target_size=(384, 512)):
        return Image.open(pose_path).convert('RGB').resize(target_size)

    def generate_mask(self, person_pil, target_size=(384, 512),
                      protect_face=True, protect_expand=10, feather=5):
        """生成服装区域遮罩（支持面部保护）"""
        orig_w, orig_h = person_pil.size
        img_resized = person_pil.resize((512, 512), Image.BILINEAR)

        img_np = np.array(img_resized).astype(np.float32) / 255.0
        img_np = (img_np - np.array([0.406, 0.456, 0.485])) / np.array([0.225, 0.224, 0.229])
        img_np = img_np.transpose(2, 0, 1)[np.newaxis].astype(np.float32)

        input_name = self.parsing_session.get_inputs()[0].name
        output = self.parsing_session.run(None, {input_name: img_np})
        prob_map = output[0][0]  # (18, 128, 128)
        parsing_128 = np.argmax(prob_map, axis=0).astype(np.uint8)

        from PIL import Image as PILImage
        parsing_pil = PILImage.fromarray(parsing_128)
        parsing = np.array(parsing_pil.resize((orig_w, orig_h), PILImage.NEAREST))

        # ATR: 4=upper-clothes, 7=dress, 8=belt
        clothing_labels = [4, 7, 8]
        cloth_mask = np.isin(parsing, clothing_labels).astype(np.uint8) * 255

        if protect_face:
            protect_labels = [2, 3, 11]
            protect_mask = np.isin(parsing, protect_labels).astype(np.uint8) * 255

            if protect_expand > 0:
                kernel = cv2.getStructuringElement(
                    cv2.MORPH_ELLIPSE,
                    (protect_expand * 2 + 1, protect_expand * 2 + 1)
                )
                protect_mask = cv2.dilate(protect_mask, kernel, iterations=1)

            cloth_mask = cv2.bitwise_and(cloth_mask, cv2.bitwise_not(protect_mask))

            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
            cloth_mask = cv2.morphologyEx(cloth_mask, cv2.MORPH_CLOSE, kernel)

            if feather > 0:
                k = feather * 2 + 1
                cloth_mask = cv2.GaussianBlur(cloth_mask, (k, k), 0)

        mask_pil = PILImage.fromarray(cloth_mask, mode='L').resize(target_size, PILImage.NEAREST)
        return mask_pil


# ============================================================
# 4. Pipeline Orchestrator (VirtualTryOn → ComfyUITryOnClient)
# ============================================================
def process_image(args):
    """处理单张图片"""
    t0 = time.time()

    # 初始化模块
    swapper = None
    if not args.skip_faceswap:
        swapper = FaceSwapper()

    # v2: ComfyUITryOnClient 替代 VirtualTryOn
    tryon = ComfyUITryOnClient(garment_desc=args.garment_desc)

    # Step 1: 换脸（可跳过）
    if not args.skip_faceswap:
        print('\n[Step 1/4] Face Swap...')
        source_face = swapper.detect_source_face(args.face)
        img_bgr = cv2.imread(args.input)
        swapped_bgr = swapper.swap_frame(img_bgr, source_face)
        swapped_pil = Image.fromarray(cv2.cvtColor(swapped_bgr, cv2.COLOR_BGR2RGB))
        print(f'  Face swapped: {swapped_pil.size}')
    else:
        print('\n[Step 1/4] Face Swap: SKIPPED')
        swapped_pil = Image.open(args.input).convert('RGB')

    # Step 2: 姿态检测（可用预生成文件）
    w, h = args.width, args.height
    if args.pose:
        print(f'[Step 2/4] Pose: loading from {args.pose}')
        pose_img = Image.open(args.pose).convert('RGB').resize((w, h))
    else:
        pose_mask = PoseMaskGenerator()
        print('[Step 2/4] Pose Detection...')
        pose_img = pose_mask.generate_pose(swapped_pil, target_size=(w, h))
    print(f'  Pose: {pose_img.size}')

    # Step 3: 人体解析遮罩（可用预生成文件）
    if args.mask:
        print(f'[Step 3/4] Mask: loading from {args.mask}')
        mask_img = Image.open(args.mask).convert('L').resize((w, h))
    else:
        if not args.pose:
            pass
        else:
            pose_mask = PoseMaskGenerator()
        print('[Step 3/4] Human Parsing Mask...')
        mask_img = pose_mask.generate_mask(swapped_pil, target_size=(w, h))
    print(f'  Mask: {mask_img.size}')

    # Step 4: 换装 (v2: 走 ComfyUI API)
    print('[Step 4/4] Virtual Try-On (ComfyUI API)...')
    garment_pil = Image.open(args.garment).convert('RGB')
    result = tryon.tryon(swapped_pil, garment_pil, mask_img, pose_img,
                         w=w, h=h, steps=args.steps, seed=args.seed)

    # 保存结果
    result.save(args.output)
    print(f'\n✅ 完成! 耗时 {time.time()-t0:.1f}s')
    print(f'   输出: {args.output}')


def process_video(args):
    """处理视频"""
    t0 = time.time()

    # 初始化模块
    swapper = None
    if not args.skip_faceswap:
        swapper = FaceSwapper()
        source_face = swapper.detect_source_face(args.face)

    # v2: ComfyUITryOnClient 替代 VirtualTryOn
    tryon = ComfyUITryOnClient(garment_desc=args.garment_desc)
    garment_pil = Image.open(args.garment).convert('RGB')

    # 预生成的 pose/mask（所有帧共用）
    fixed_pose = None
    fixed_mask = None
    if args.pose:
        fixed_pose = Image.open(args.pose).convert('RGB')
        print(f'[Video] Using fixed pose: {args.pose}')
    if args.mask:
        fixed_mask = Image.open(args.mask).convert('L')
        print(f'[Video] Using fixed mask: {args.mask}')

    # Manual torso mask 模式
    if not fixed_mask and args.mask_mode == 'manual':
        print(f'[Video] Generating manual torso mask ({args.width}x{args.height})')
        mask_arr = np.zeros((args.height, args.width), dtype=np.uint8)
        cloth_start = int(args.height * 0.30)
        cloth_end = int(args.height * 0.95)
        mask_arr[cloth_start:cloth_end, :] = 255
        mask_pil_tmp = Image.fromarray(mask_arr, mode='L')
        mask_pil_tmp = mask_pil_tmp.filter(ImageFilter.GaussianBlur(radius=15))
        fixed_mask = mask_pil_tmp
        print(f'  Torso mask: face=top 30%, clothing=[{cloth_start},{cloth_end}]px')

    need_pose_gen = not fixed_pose
    need_mask_gen = not fixed_mask and args.mask_mode == 'auto'
    if need_pose_gen or need_mask_gen:
        pose_mask_gen = PoseMaskGenerator()
    else:
        pose_mask_gen = None

    # 视频信息
    duration = float(subprocess.run(
        ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'csv=p=0', args.input],
        capture_output=True, text=True
    ).stdout.strip())

    if args.fps:
        fps = args.fps
    else:
        fps_str = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate',
             '-of', 'csv=p=0', args.input],
            capture_output=True, text=True
        ).stdout.strip()
        if '/' in fps_str:
            num, den = fps_str.split('/')
            fps = float(num) / float(den)
        else:
            fps = float(fps_str) if fps_str else 25.0

    w, h = args.width, args.height
    skip_n = max(1, args.frame_skip)

    segment_sec = args.segment_sec
    n_segments = int(np.ceil(duration / segment_sec))

    print(f'\nVideo: {duration:.1f}s, {fps:.1f}fps, skip={skip_n}, {n_segments} segments')

    output_segments = []
    tmp_dir = args.output + '_tmp'
    os.makedirs(tmp_dir, exist_ok=True)

    for seg_idx in range(n_segments):
        start = seg_idx * segment_sec
        seg_input = os.path.join(tmp_dir, f'seg_{seg_idx:03d}.mp4')
        seg_output = os.path.join(tmp_dir, f'out_{seg_idx:03d}.mp4')

        # 分割
        subprocess.run(['ffmpeg', '-i', args.input, '-ss', str(start), '-t', str(segment_sec),
                        '-c:v', 'libx264', '-c:a', 'aac', seg_input, '-y'],
                       capture_output=True, check=True)

        # 提取帧
        frames_dir = os.path.join(tmp_dir, f'frames_{seg_idx:03d}')
        os.makedirs(frames_dir, exist_ok=True)
        subprocess.run(['ffmpeg', '-i', seg_input, '-vf', f'fps={fps}',
                        os.path.join(frames_dir, 'frame_%06d.png'), '-y'],
                       capture_output=True)

        frames = sorted(Path(frames_dir).glob('frame_*.png'))
        out_frames_dir = os.path.join(tmp_dir, f'out_frames_{seg_idx:03d}')
        os.makedirs(out_frames_dir, exist_ok=True)

        total_frames = len(frames)
        processed = 0
        last_result = None
        print(f'\n[Segment {seg_idx+1}/{n_segments}] {total_frames} frames (skip={skip_n})')

        for i, frame_path in enumerate(frames):
            if i % skip_n != 0 and last_result is not None:
                result_bgr = cv2.cvtColor(np.array(last_result), cv2.COLOR_RGB2BGR)
                cv2.imwrite(os.path.join(out_frames_dir, frame_path.name), result_bgr)
                continue

            frame_bgr = cv2.imread(str(frame_path))

            # 换脸（可跳过）
            if not args.skip_faceswap:
                swapped_bgr = swapper.swap_frame(frame_bgr, source_face)
                swapped_pil = Image.fromarray(cv2.cvtColor(swapped_bgr, cv2.COLOR_BGR2RGB))
            else:
                swapped_pil = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))

            # 姿态 + 遮罩
            if fixed_pose:
                pose_img = fixed_pose.resize((w, h))
            else:
                pose_img = pose_mask_gen.generate_pose(swapped_pil, target_size=(w, h))
            if fixed_mask:
                mask_img = fixed_mask.resize((w, h))
            else:
                mask_img = pose_mask_gen.generate_mask(swapped_pil, target_size=(w, h))

            # 换装 (v2: ComfyUI API)
            result = tryon.tryon(swapped_pil, garment_pil, mask_img, pose_img,
                                 w=w, h=h, steps=args.steps, seed=args.seed)
            last_result = result

            result_bgr = cv2.cvtColor(np.array(result), cv2.COLOR_RGB2BGR)
            cv2.imwrite(os.path.join(out_frames_dir, frame_path.name), result_bgr)
            processed += 1

            if processed % 5 == 0 or i == total_frames - 1:
                print(f'  Frame {i+1}/{total_frames} (processed {processed})')

        # 用帧合成视频
        subprocess.run(['ffmpeg', '-framerate', str(fps),
                        '-i', os.path.join(out_frames_dir, 'frame_%06d.png'),
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                        '-start_number', '1',
                        seg_output, '-y'], capture_output=True)

        output_segments.append(seg_output)
        print(f'  Segment {seg_idx+1} done: {processed}/{total_frames} frames processed')

    # 合并所有段
    concat_file = os.path.join(tmp_dir, 'concat.txt')
    with open(concat_file, 'w') as f:
        for seg in output_segments:
            f.write(f"file '{os.path.abspath(seg)}'\n")

    subprocess.run(['ffmpeg', '-f', 'concat', '-safe', '0', '-i', concat_file,
                    '-c:v', 'libx264', '-c:a', 'aac', '-pix_fmt', 'yuv420p',
                    args.output, '-y'], capture_output=True, check=True)

    # 清理
    if not args.keep_tmp:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f'\n✅ 完成! 耗时 {time.time()-t0:.1f}s')
    print(f'   输出: {args.output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='人物换脸+换装组合流水线 v2 (ComfyUI API 版)')
    parser.add_argument('--mode', choices=['image', 'video'], required=True)
    parser.add_argument('--input', required=True, help='输入图片/视频路径')
    parser.add_argument('--face', default=None, help='目标人脸图片路径（skip-faceswap 时可省略）')
    parser.add_argument('--garment', required=True, help='目标服装图片路径')
    parser.add_argument('--output', required=True, help='输出路径')
    parser.add_argument('--garment-desc', default='garment', help='服装描述文字')
    parser.add_argument('--width', type=int, default=384)
    parser.add_argument('--height', type=int, default=512)
    parser.add_argument('--steps', type=int, default=20, help='IDM-VTON 推理步数')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--segment-sec', type=int, default=15, help='视频分段时长(秒)')
    parser.add_argument('--fps', type=float, default=None, help='输出帧率（默认=源帧率）')
    parser.add_argument('--keep-tmp', action='store_true', help='保留临时文件')
    parser.add_argument('--pose', default=None, help='预生成的姿态图路径（跳过姿态检测）')
    parser.add_argument('--mask', default=None, help='预生成的遮罩图路径（跳过人体解析）')
    parser.add_argument('--skip-faceswap', action='store_true', help='跳过换脸步骤（直接用输入图片）')
    parser.add_argument('--frame-skip', type=int, default=1, help='每N帧处理一帧（1=每帧，6=每秒@6fps）')
    parser.add_argument('--mask-mode', choices=['auto', 'manual'], default='auto',
                        help='mask生成模式: auto=ATR人体解析(默认), manual=手动torso mask')

    args = parser.parse_args()

    if args.mode == 'image':
        process_image(args)
    else:
        process_video(args)
