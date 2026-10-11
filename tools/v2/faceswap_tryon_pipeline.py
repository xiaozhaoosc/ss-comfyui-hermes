"""
人物换脸+换装组合流水线
用法:
  图片: python faceswap_tryon_pipeline.py --mode image --input photo.jpg --face face.jpg --garment shirt.jpg --output result.jpg
  视频: python faceswap_tryon_pipeline.py --mode video --input video.mp4 --face face.jpg --garment shirt.jpg --output result.mp4

流程: 换脸 → 姿态检测 → 人体解析遮罩 → IDM-VTON 换装
"""
import os, sys, argparse, time, shutil, subprocess
import numpy as np
import cv2
import torch
from PIL import Image, ImageFilter
from pathlib import Path

# 动态计算 ComfyUI 根目录，保证可移植性
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(CURRENT_DIR) == 'v2':
    COMFY_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
elif os.path.basename(CURRENT_DIR) == 'tools':
    COMFY_ROOT = os.path.dirname(CURRENT_DIR)
else:
    COMFY_ROOT = r'D:\ai_projects\ComfyUI'

sys.path.insert(0, COMFY_ROOT)
sys.path.insert(0, os.path.join(COMFY_ROOT, 'custom_nodes', 'ComfyUI-IDM-VTON'))

import gc
def clear_vram():
    """清理 PyTorch 占用的显存和内存垃圾"""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


# ============================================================
# 1. Face Swap Module (insightface + GFPGAN)
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
        # 选最大人脸
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
# 2. Pose + Mask Module (DWPose via comfyui_controlnet_aux)
# ============================================================
class PoseMaskGenerator:
    def __init__(self):
        print('[PoseMask] Loading DWPose (ONNX)...')
        if os.path.join(COMFY_ROOT, 'custom_nodes') not in sys.path:
            sys.path.insert(0, os.path.join(COMFY_ROOT, 'custom_nodes'))
        from comfyui_controlnet_aux.src.custom_controlnet_aux.dwpose import DwposeDetector
        
        self.dwpose_detector = DwposeDetector.from_pretrained(
            'yzd-v/DWPose',       # pose repo
            'yzd-v/DWPose',       # det repo
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
        """从已有姿态图文件加载"""
        return Image.open(pose_path).convert('RGB').resize(target_size)
    
    def generate_mask(self, person_pil, target_size=(384, 512),
                      protect_face=True, protect_expand=10, feather=5):
        """生成服装区域遮罩（支持面部保护）

        Args:
            person_pil: PIL Image
            target_size: (w, h) 输出尺寸
            protect_face: 是否排除面部/头发/墨镜区域
            protect_expand: 保护区域扩展像素
            feather: 边缘羽化像素
        """
        orig_w, orig_h = person_pil.size
        img_resized = person_pil.resize((512, 512), Image.BILINEAR)

        img_np = np.array(img_resized).astype(np.float32) / 255.0
        img_np = (img_np - np.array([0.406, 0.456, 0.485])) / np.array([0.225, 0.224, 0.229])
        img_np = img_np.transpose(2, 0, 1)[np.newaxis].astype(np.float32)

        input_name = self.parsing_session.get_inputs()[0].name
        output = self.parsing_session.run(None, {input_name: img_np})
        prob_map = output[0][0]  # (18, 128, 128)
        parsing_128 = np.argmax(prob_map, axis=0).astype(np.uint8)

        # 上采样到原始分辨率
        from PIL import Image as PILImage
        parsing_pil = PILImage.fromarray(parsing_128)
        parsing = np.array(parsing_pil.resize((orig_w, orig_h), PILImage.NEAREST))

        # ATR: 4=upper-clothes, 7=dress, 8=belt
        clothing_labels = [4, 7, 8]
        cloth_mask = np.isin(parsing, clothing_labels).astype(np.uint8) * 255

        if protect_face:
            # 保护: 2=hair, 3=sunglasses, 11=face
            protect_labels = [2, 3, 11]
            protect_mask = np.isin(parsing, protect_labels).astype(np.uint8) * 255

            # 扩展保护区域
            if protect_expand > 0:
                kernel = cv2.getStructuringElement(
                    cv2.MORPH_ELLIPSE,
                    (protect_expand * 2 + 1, protect_expand * 2 + 1)
                )
                protect_mask = cv2.dilate(protect_mask, kernel, iterations=1)

            # 从服装 mask 中减去保护区域
            cloth_mask = cv2.bitwise_and(cloth_mask, cv2.bitwise_not(protect_mask))

            # 形态学闭运算
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
            cloth_mask = cv2.morphologyEx(cloth_mask, cv2.MORPH_CLOSE, kernel)

            # 边缘羽化
            if feather > 0:
                k = feather * 2 + 1
                cloth_mask = cv2.GaussianBlur(cloth_mask, (k, k), 0)

        mask_pil = PILImage.fromarray(cloth_mask, mode='L').resize(target_size, PILImage.NEAREST)
        return mask_pil


# ============================================================
# 3. IDM-VTON Virtual Try-On Module
# ============================================================
class VirtualTryOn:
    def __init__(self, garment_desc='garment'):
        print('[TryOn] Loading IDM-VTON pipeline...')
        from diffusers import AutoencoderKL, DDPMScheduler
        from transformers import AutoTokenizer, CLIPImageProcessor, CLIPVisionModelWithProjection, CLIPTextModel, CLIPTextModelWithProjection
        from src.idm_vton.unet_hacked_tryon import UNet2DConditionModel
        from src.idm_vton.unet_hacked_garmnet import UNet2DConditionModel as UNet2DConditionModel_ref
        from src.idm_vton.tryon_pipeline import StableDiffusionXLInpaintPipeline as TryonPipeline
        import folder_paths
        
        WP = os.path.join(folder_paths.models_dir, 'IDM-VTON')
        dt = torch.float16
        dev = 'cuda'
        
        sched = DDPMScheduler.from_pretrained(WP, subfolder='scheduler')
        vae = AutoencoderKL.from_pretrained(WP, subfolder='vae', torch_dtype=dt).to(dev).eval()
        unet = UNet2DConditionModel.from_pretrained(WP, subfolder='unet', torch_dtype=dt).to(dev).eval()
        ie = CLIPVisionModelWithProjection.from_pretrained(WP, subfolder='image_encoder', torch_dtype=dt).to(dev).eval()
        te1 = CLIPTextModel.from_pretrained(WP, subfolder='text_encoder', torch_dtype=dt).to(dev).eval()
        te2 = CLIPTextModelWithProjection.from_pretrained(WP, subfolder='text_encoder_2', torch_dtype=dt).to(dev).eval()
        ue = UNet2DConditionModel_ref.from_pretrained(WP, subfolder='unet_encoder', torch_dtype=dt).to(dev).eval()
        tok1 = AutoTokenizer.from_pretrained(WP, subfolder='tokenizer', use_fast=False)
        tok2 = AutoTokenizer.from_pretrained(WP, subfolder='tokenizer_2', use_fast=False)
        
        self.pipe = TryonPipeline.from_pretrained(
            WP, unet=unet, vae=vae, feature_extractor=CLIPImageProcessor(),
            text_encoder=te1, text_encoder_2=te2, tokenizer=tok1, tokenizer_2=tok2,
            scheduler=sched, image_encoder=ie, torch_dtype=dt,
        )
        self.pipe.unet_encoder = ue
        self.pipe = self.pipe.to(dev)
        self.pipe.weight_dtype = dt
        self.dt = dt
        self.dev = dev
        self.garment_desc = garment_desc
        print(f'[TryOn] Ready. GPU: {torch.cuda.memory_allocated()/1024**3:.1f}GB')
    
    def tryon(self, person_pil, garment_pil, mask_pil, pose_pil,
              w=384, h=512, steps=20, seed=42):
        """执行换装推理"""
        from torchvision import transforms
        
        tt = transforms.Compose([transforms.ToTensor(), transforms.Normalize([0.5], [0.5])])
        
        person_resized = person_pil.convert('RGB').resize((w, h))
        garment_resized = garment_pil.convert('RGB').resize((w, h))
        mask_resized = mask_pil.convert('RGB').resize((w, h))
        pose_resized = pose_pil.convert('RGB').resize((w, h))
        
        negative_prompt = 'low quality, blurry'
        
        with torch.no_grad(), torch.amp.autocast('cuda'), torch.inference_mode():
            prompt = 'model is wearing ' + self.garment_desc
            (pe, npe, pp, npp) = self.pipe.encode_prompt(
                prompt=prompt, device=torch.device(self.dev),
                num_images_per_prompt=1, do_classifier_free_guidance=True,
                negative_prompt=negative_prompt,
            )
            prompt_c = ['a photo of ' + self.garment_desc]
            (pec, _, _, _) = self.pipe.encode_prompt(
                prompt=prompt_c, device=torch.device(self.dev),
                num_images_per_prompt=1, do_classifier_free_guidance=False,
                negative_prompt=[negative_prompt],
            )
            
            pt = tt(pose_resized).unsqueeze(0).to(self.dev, self.dt)
            gt = tt(garment_resized).unsqueeze(0).to(self.dev, self.dt)
            
            result = self.pipe(
                prompt_embeds=pe, negative_prompt_embeds=npe,
                pooled_prompt_embeds=pp, negative_pooled_prompt_embeds=npp,
                num_inference_steps=steps, generator=torch.Generator(self.dev).manual_seed(seed),
                strength=0.9, pose_img=pt, text_embeds_cloth=pec,
                cloth=gt, mask_image=mask_resized, image=person_resized,
                height=h, width=w, ip_adapter_image=garment_resized, guidance_scale=2.0,
            )
        
        return result[0][0]


# ============================================================
# 4. Pipeline Orchestrator
# ============================================================
def process_image(args):
    """处理单张图片"""
    t0 = time.time()
    
    # 初始化模块
    swapper = None
    if not args.skip_faceswap:
        swapper = FaceSwapper()
    
    tryon = VirtualTryOn(garment_desc=args.garment_desc)
    
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
        if not args.pose:  # pose_mask 已初始化
            pass
        else:
            pose_mask = PoseMaskGenerator()
        print('[Step 3/4] Human Parsing Mask...')
        mask_img = pose_mask.generate_mask(swapped_pil, target_size=(w, h))
    print(f'  Mask: {mask_img.size}')
    
    # Step 4: 换装
    print('[Step 4/4] Virtual Try-On...')
    garment_pil = Image.open(args.garment).convert('RGB')
    result = tryon.tryon(swapped_pil, garment_pil, mask_img, pose_img,
                         w=w, h=h, steps=args.steps, seed=args.seed)
    
    # 保存结果
    result.save(args.output)
    # 清理显存
    clear_vram()
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
    
    tryon = VirtualTryOn(garment_desc=args.garment_desc)
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
    
    # Manual torso mask 模式：白=服装区(30%-95%高度)，黑=脸区(顶部)
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
    
    # fps：优先使用命令行参数，否则从源视频读取
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
    skip_n = max(1, args.frame_skip)  # 每 N 帧处理一帧
    
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
            # 帧跳过策略：每隔 skip_n 帧处理一次，中间帧复用上一帧结果
            if i % skip_n != 0 and last_result is not None:
                # 复用上一帧结果
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
            
            # 姿态 + 遮罩（使用预生成或实时检测）
            if fixed_pose:
                pose_img = fixed_pose.resize((w, h))
            else:
                pose_img = pose_mask_gen.generate_pose(swapped_pil, target_size=(w, h))
            if fixed_mask:
                mask_img = fixed_mask.resize((w, h))
            else:
                mask_img = pose_mask_gen.generate_mask(swapped_pil, target_size=(w, h))
            
            # 换装
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
    
    # 第一次合成：生成包含换脸换装的视频流（暂时为无音频视频）
    subprocess.run(['ffmpeg', '-f', 'concat', '-safe', '0', '-i', concat_file,
                    '-c:v', 'libx264', '-an', '-pix_fmt', 'yuv420p',
                    args.output, '-y'], capture_output=True, check=True)
    
    # 尝试检测原视频中是否存在音频，并将其合并回输出视频中
    has_audio = False
    try:
        audio_check = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-select_streams', 'a', '-show_entries', 'stream=codec_type', '-of', 'csv=p=0', args.input],
            capture_output=True, text=True
        ).stdout.strip()
        if 'audio' in audio_check:
            has_audio = True
    except Exception:
        pass

    if has_audio:
        print("\n[音频] 检测到原视频含有音频轨道，正在合并音频轨道...")
        temp_output = args.output + '.temp.mp4'
        merge_cmd = ['ffmpeg', '-y', '-i', args.output, '-i', args.input, 
                     '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-shortest', temp_output]
        res = subprocess.run(merge_cmd, capture_output=True)
        if res.returncode == 0 and os.path.exists(temp_output) and os.path.getsize(temp_output) > 10000:
            try:
                os.remove(args.output)
                os.rename(temp_output, args.output)
                print("  [音频] 音频已成功并回最终视频")
            except Exception as e:
                print(f"  [音频] 替换最终文件失败: {e}")
        else:
            print("  [音频] 音频合并失败，保留无音视频")
            if os.path.exists(temp_output):
                try: os.remove(temp_output)
                except: pass
    else:
        print("\n[音频] 原视频不包含音频轨道，跳过音频恢复。")

    # 清理显存与临时目录
    clear_vram()
    if not args.keep_tmp:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    
    print(f'\n✅ 完成! 耗时 {time.time()-t0:.1f}s')
    print(f'   输出: {args.output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='人物换脸+换装组合流水线')
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
                        help='mask生成模式: auto=ATR人体解析(默认), manual=手动torso mask(白=服装区30%-95%高度, 黑=脸区顶部)')
    
    args = parser.parse_args()
    
    if args.mode == 'image':
        process_image(args)
    else:
        process_video(args)
