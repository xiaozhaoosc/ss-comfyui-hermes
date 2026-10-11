"""换脸引擎：抽象 CPU/GPU 统一接口，支持进度回调与取消"""
from __future__ import annotations

import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np

from .media_utils import (
    get_video_fps,
    imread_unicode,
    imwrite_unicode,
    merge_videos,
    split_video,
)

# 进度回调签名：(stage, current, total, message) -> None
# stage: "init" | "split" | "frame" | "preview" | "merge" | "audio" | "done" | "error"
# "preview" 阶段：message 为已换脸帧的输出路径，用于 GUI 流式预览
ProgressCallback = Callable[[str, int, int, str], None]


@dataclass
class EngineConfig:
    """引擎运行配置"""
    face_source: str            # 人脸源图片路径
    video_source: str           # 视频源（文件或目录）
    output_dir: str             # 输出目录
    bgm_source: Optional[str] = None    # BGM 文件或目录
    bgm_random: bool = False    # BGM 目录随机选
    keep_original_audio: bool = True    # 保留原音
    bgm_volume: float = 0.5     # BGM 音量 0~1
    original_volume: float = 1.0  # 原音音量 0~1
    use_gpu: bool = True        # 是否使用 GPU
    max_segment_sec: float = 15.0
    fps: int = 25
    enable_gfpgan: bool = True  # 是否启用 GFPGAN 修复


@dataclass
class EngineResult:
    """单次处理结果"""
    success: bool
    output_path: str = ""
    error: str = ""
    frames_processed: int = 0
    elapsed_sec: float = 0.0


class FaceSwapEngine:
    """换脸引擎：CPU/GPU 统一接口

    通过 providers 参数切换：
    - GPU: ['CUDAExecutionProvider']
    - CPU: ['CPUExecutionProvider']
    """

    # 模型路径（相对于 ComfyUI 根目录）
    MODEL_PATH = "models/insightface/inswapper_128.onnx"
    GFPGAN_PATH = "models/facerestore_models/GFPGANv1.4.pth"

    def __init__(self, config: EngineConfig, progress_cb: ProgressCallback = None,
                 cancel_check: Callable[[], bool] = None):
        self.config = config
        self.progress_cb = progress_cb or (lambda *a: None)
        self.cancel_check = cancel_check or (lambda: False)
        self._cancelled = False

        # 运行时缓存
        self._app = None
        self._swapper = None
        self._restorer = None
        self._source_img = None
        self._source_faces = None
        self._source_angle = 0.0  # 源人脸倾斜角度（度），用于角度过滤

    def _emit(self, stage: str, current: int, total: int, msg: str = ""):
        self.progress_cb(stage, current, total, msg)

    def _check_cancel(self) -> bool:
        if self.cancel_check():
            self._cancelled = True
            return True
        return False

    # ---------- 模型初始化 ----------

    def _resolve_model_paths(self):
        """解析模型路径：优先环境变量，回退 ComfyUI 根 / exe 同级 / cwd"""
        # Why: 依赖 __file__ 的 parents[3] 在不同启动方式下不稳定，
        # 改用 app.py 注入的 FACESWAP_MODELS_ROOT 环境变量作为权威来源
        candidates = []
        env_root = os.environ.get('FACESWAP_MODELS_ROOT')
        if env_root:
            candidates.append(Path(env_root))
        candidates.append(Path(os.getcwd()))
        candidates.append(Path(__file__).resolve().parents[3])  # faceswap_app -> tools -> ComfyUI
        if getattr(os.sys, 'frozen', False):
            candidates.append(Path(os.path.dirname(os.sys.executable)))
        # 去重
        seen = set()
        unique = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                unique.append(c)

        swapper_path = None
        gfpgan_path = None
        for root in unique:
            p1 = root / self.MODEL_PATH
            p2 = root / self.GFPGAN_PATH
            if swapper_path is None and p1.exists():
                swapper_path = str(p1)
            if gfpgan_path is None and p2.exists():
                gfpgan_path = str(p2)
        return swapper_path, gfpgan_path

    def init_models(self):
        """初始化模型，根据 use_gpu 选择 providers"""
        from insightface.app import FaceAnalysis
        from insightface.model_zoo import get_model

        providers = (['CUDAExecutionProvider', 'CPUExecutionProvider']
                     if self.config.use_gpu else ['CPUExecutionProvider'])

        # GPU 模式下优化 CUDA EP 配置
        # Why: 默认 cudnn_conv_algo_search=EXHAUSTIVE 每帧都搜索最优卷积算法，
        # 改为 DEFAULT 可省去搜索开销（仅首次推理时搜索一次）
        if self.config.use_gpu:
            self._register_cudnn_path()
            provider_options = [
                {
                    'cudnn_conv_algo_search': 'DEFAULT',
                },
                {}
            ]
        else:
            provider_options = [{}]

        self._emit("init", 0, 1, f"加载 FaceAnalysis (providers={providers[0]})")

        # 检测版：用于目标帧检测（每帧调用），仅加载 detection 模块
        # Why: swapper.get() 只需要 target_face.kps（来自 detection），不需要 landmark/genderage/recognition
        self._app = FaceAnalysis(
            name='buffalo_l', providers=providers, provider_options=provider_options,
            allowed_modules=['detection'],
        )
        self._app.prepare(ctx_id=0, det_size=(640, 640))

        # 源人脸版：用于源人脸检测（仅一次性），加载 detection + recognition
        # Why: inswapper 需要 source_face.normed_embedding（来自 recognition）
        #   不加载 landmark 模块，避免对某些图片 landmark_3d_68 推理返回 None 导致崩溃
        self._app_full = FaceAnalysis(
            name='buffalo_l', providers=providers, provider_options=provider_options,
            allowed_modules=['detection', 'recognition'],
        )
        self._app_full.prepare(ctx_id=0, det_size=(640, 640))

        swapper_path, gfpgan_path = self._resolve_model_paths()
        if swapper_path is None:
            raise FileNotFoundError(f"未找到 inswapper_128.onnx，请检查 models/insightface/ 目录")

        self._emit("init", 0, 1, f"加载 swapper: {Path(swapper_path).name}")
        self._swapper = get_model(
            swapper_path,
            providers=providers,
            provider_options=provider_options,
        )

        # 验证 CUDA 是否真正生效（防止静默 fallback 后用户不知情）
        if self.config.use_gpu:
            actual = self._swapper.session.get_providers()
            if 'CUDAExecutionProvider' not in actual:
                raise RuntimeError(
                    f"GPU 模式但 CUDA 未生效！swapper 实际 providers={actual}。"
                    f"请检查 cuDNN/CUDA 是否正确安装。已 fallback 到 CPU，速度会很慢。"
                )
            self._emit("init", 0, 1, f"CUDA 验证通过: {actual[0]}")

        if self.config.enable_gfpgan and gfpgan_path:
            try:
                from gfpgan import GFPGANer
                self._restorer = GFPGANer(
                    model_path=gfpgan_path,
                    upscale=1, arch='clean', channel_multiplier=2, bg_upsampler=None
                )
                self._emit("init", 0, 1, "GFPGAN 已加载")
            except Exception as e:
                self._emit("init", 0, 1, f"GFPGAN 加载失败(已忽略): {e}")
                self._restorer = None
        else:
            self._restorer = None

        self._emit("init", 1, 1, "模型就绪")

    @staticmethod
    def _register_cudnn_path():
        """注册 torch 自带的 cuDNN DLL 路径到 DLL 搜索路径"""
        try:
            import torch
            torch_lib = os.path.join(os.path.dirname(torch.__file__), 'lib')
            if os.path.isdir(torch_lib):
                os.add_dll_directory(torch_lib)
                os.environ['PATH'] = torch_lib + os.pathsep + os.environ.get('PATH', '')
        except Exception:
            pass

    def load_source_face(self):
        """加载并检测源人脸"""
        self._emit("init", 0, 1, f"检测源人脸: {Path(self.config.face_source).name}")
        img = imread_unicode(self.config.face_source)
        if img is None:
            raise ValueError(f"无法读取源人脸图片: {self.config.face_source}")

        # 缩小检测尺寸提速
        h, w = img.shape[:2]
        if max(h, w) > 800:
            small = cv2.resize(img, (320, int(320 * h / w)))
        else:
            small = img

        # 检测人脸：先缩小图，失败则回退原图，最后回退多尺寸自动检测
        # Why: 打包环境里缩小图可能触发 insightface 内部异常，原图检测更稳定
        faces = self._detect_faces_robust(small, img)
        if not faces:
            raise ValueError(f"源图片未检测到人脸: {self.config.face_source}")

        self._source_img = img
        self._source_faces = faces
        self._source_angle = self._compute_face_angle(faces[0])
        self._emit("init", 1, 1,
                   f"源人脸检测: {len(faces)} 个, 角度: {self._source_angle:.1f}°")

    @staticmethod
    def _compute_face_angle(face) -> float:
        """计算人脸倾斜角度（基于双眼连线）

        Why: 用于角度过滤，跳过与源人脸角度差异过大的帧避免 inswapper 变形
        """
        if face.kps is None:
            return 0.0
        left_eye, right_eye = face.kps[0], face.kps[1]
        return float(np.degrees(np.arctan2(
            right_eye[1] - left_eye[1],
            right_eye[0] - left_eye[0]
        )))

    @staticmethod
    def _compute_yaw_ratio(face) -> float:
        """计算 yaw 比值（鼻子到左眼距离 / 鼻子到右眼距离）

        Why: 双眼连线角度只能检测 roll(倾斜), 无法检测 yaw(侧脸)
              yaw_ratio 接近 1 = 正面, <0.5 = 侧脸
        """
        if face.kps is None:
            return 1.0
        left_eye, right_eye, nose = face.kps[0], face.kps[1], face.kps[2]
        d_left = float(np.linalg.norm(nose - left_eye))
        d_right = float(np.linalg.norm(nose - right_eye))
        if max(d_left, d_right) <= 0:
            return 1.0
        return min(d_left, d_right) / max(d_left, d_right)

    def _detect_faces_robust(self, small: np.ndarray, original: np.ndarray) -> list:
        """多策略人脸检测，任一策略成功即返回

        策略顺序：缩小图 → 原图 → 自动多尺寸
        Why: 打包后 insightface 对特定尺寸的图像可能内部出错，
             多策略回退确保至少有一种方式能完成检测
        """
        # 策略1：缩小图检测（用完整版 app，需要 recognition 生成 embedding）
        try:
            faces = self._app_full.get(small)
            if faces:
                return faces
        except Exception as e:
            self._emit("init", 0, 1, f"缩小图检测失败，尝试原图: {e}")

        # 策略2：原图检测
        try:
            faces = self._app_full.get(original)
            if faces:
                return faces
        except Exception as e:
            self._emit("init", 0, 1, f"原图检测失败，尝试多尺寸: {e}")

        # 策略3：自动多尺寸检测（det_size=(0,0) 触发 insightface 默认多尺寸）
        try:
            self._app_full.det_size = [(128, 128), (640, 640)]
            self._app_full.prepare(ctx_id=0, det_size=(0, 0))
            faces = self._app_full.get(original)
            # 恢复默认检测尺寸
            self._app_full.prepare(ctx_id=0, det_size=(640, 640))
            return faces or []
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            raise RuntimeError(
                f"人脸检测全部失败: {e}\n"
                f"追踪信息:\n{tb}"
            ) from e

    # ---------- 单段处理 ----------

    def _process_segment(self, seg_path: str, seg_output: str, fps: float) -> int:
        """处理单个视频片段（全内存管道），返回写入帧数

        优化点：
        - cv2.VideoCapture 直接读帧（不落盘）
        - cv2.VideoWriter 直接编码（无 ffmpeg pipe 阻塞）
        - 跳帧检测：每 3 帧检测一次，中间帧复用 bbox
        - 禁用 genderage/recognition 子模型
        """
        if self._check_cancel():
            return 0

        import subprocess

        cap = cv2.VideoCapture(seg_path)
        if not cap.isOpened():
            shutil.copy2(seg_path, seg_output)
            return 0

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        orig_fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        frame_interval = max(1, round(orig_fps / fps)) if orig_fps > 0 else 1

        # 用 cv2.VideoWriter 编码（纯内存，无 pipe 阻塞）
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(seg_output, fourcc, fps, (width, height))
        if not writer.isOpened():
            cap.release()
            shutil.copy2(seg_path, seg_output)
            return 0

        self._emit("split", 0, total_frames, f"处理 {total_frames} 帧 ({width}x{height})")
        t0 = time.time()
        written = 0
        frame_idx = 0
        skipped_by_angle = 0  # 因角度差异过大跳过的帧数

        # 跳帧检测：每 detect_interval 帧检测一次
        detect_interval = 3
        last_faces = []
        last_angle_ok = True  # 缓存角度是否在阈值内（跳帧中间帧复用）

        # 角度过滤阈值
        # Why: inswapper 对大角度差异换脸会变形
        #   - roll 差异 >60° → 头部严重倾斜, inswapper 对齐失败导致变形
        #   - yaw_ratio <0.5 → 侧脸, 源正面 embedding 与目标侧脸不匹配导致变形
        ROLL_THRESHOLD = 60.0
        YAW_RATIO_MIN = 0.5

        preview_dir = seg_path + "_preview"
        os.makedirs(preview_dir, exist_ok=True)

        try:
            while True:
                if self._check_cancel():
                    break

                ret, frame = cap.read()
                if not ret:
                    break

                frame_idx += 1
                if frame_idx % frame_interval != 0:
                    continue

                # 跳帧检测：每 detect_interval 帧检测一次
                if written % detect_interval == 0:
                    try:
                        last_faces = self._app.get(frame)
                    except Exception:
                        last_faces = []
                    # 检测角度是否在阈值内
                    if last_faces:
                        best = max(last_faces,
                                   key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]))
                        target_roll = self._compute_face_angle(best)
                        target_yaw = self._compute_yaw_ratio(best)
                        roll_ok = abs(target_roll - self._source_angle) <= ROLL_THRESHOLD
                        yaw_ok = target_yaw >= YAW_RATIO_MIN
                        last_angle_ok = roll_ok and yaw_ok
                    else:
                        last_angle_ok = False

                if last_faces and last_angle_ok:
                    best = max(last_faces,
                               key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]))
                    try:
                        result = self._swapper.get(frame.copy(), best, self._source_faces[0], paste_back=True)
                    except Exception:
                        result = frame
                    if self._restorer:
                        try:
                            _, _, restored = self._restorer.enhance(
                                result, has_aligned=False, only_center_face=False,
                                paste_back=True, weight=0.5
                            )
                            if restored is not None:
                                result = restored
                        except Exception:
                            pass
                    if result is None:
                        result = frame
                else:
                    # 角度差异过大或未检测到人脸：保留原帧
                    result = frame
                    if last_faces and not last_angle_ok:
                        skipped_by_angle += 1

                writer.write(result)
                written += 1

                if written % 5 == 0:
                    preview_path = os.path.join(preview_dir, f"frame_{written:04d}.jpg")
                    cv2.imwrite(preview_path, result, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    self._emit("preview", written, total_frames, preview_path)

                if written % 10 == 0:
                    elapsed = time.time() - t0
                    fps_proc = written / elapsed if elapsed > 0 else 0
                    eta = (total_frames - frame_idx) / fps_proc if fps_proc > 0 else 0
                    skip_info = f" 跳过{skipped_by_angle}帧" if skipped_by_angle > 0 else ""
                    self._emit("frame", written, total_frames,
                               f"{written}/{total_frames} ({fps_proc:.1f}帧/s 剩余{eta:.0f}s{skip_info})")

        finally:
            cap.release()
            writer.release()

        if skipped_by_angle > 0:
            self._emit("frame", written, total_frames,
                       f"角度过滤: 跳过 {skipped_by_angle}/{written} 帧 "
                       f"(roll>{ROLL_THRESHOLD}° 或 yaw<{YAW_RATIO_MIN})")

        # 用 ffmpeg 把原视频的音频合并到输出视频
        # Why: cv2.VideoWriter 不支持音频，需要后处理合并
        if written > 0:
            audio_tmp = seg_output + "_audio.mp4"
            cmd = [
                'ffmpeg', '-y',
                '-i', seg_output,           # 换脸后的视频（无音频）
                '-i', seg_path,             # 原视频（有音频）
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-map', '0:v:0', '-map', '1:a:0?',
                '-shortest',
                audio_tmp,
            ]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if r.returncode == 0:
                shutil.move(audio_tmp, seg_output)
            # 如果音频合并失败，保留无音频的视频

        shutil.rmtree(preview_dir, ignore_errors=True)
        return written

    # ---------- 主流程 ----------

    def process_single_video(self, video_path: str) -> EngineResult:
        """处理单个视频"""
        t_start = time.time()
        try:
            if self._app is None:
                self.init_models()
                self.load_source_face()

            if self._check_cancel():
                return EngineResult(False, error="已取消")

            video_path = str(video_path)
            orig_fps = get_video_fps(video_path)
            use_fps = max(orig_fps, self.config.fps)
            self._emit("split", 0, 1, f"原始帧率 {orig_fps:.2f}, 使用 {use_fps}")

            # 分段
            temp_dir = tempfile.mkdtemp(prefix=f"faceswap_{Path(video_path).stem}_")
            segments, duration = split_video(video_path, temp_dir, self.config.max_segment_sec)
            self._emit("split", 1, 1, f"时长 {duration:.1f}s, {len(segments)} 段")

            swapped = []
            total_frames = 0
            for idx, seg in enumerate(segments):
                if self._check_cancel():
                    return EngineResult(False, error="已取消")
                seg_out = seg.replace(".mp4", "_swapped.mp4")
                self._emit("split", idx, len(segments),
                           f"片段 {idx+1}/{len(segments)}")
                n = self._process_segment(seg, seg_out, use_fps)
                swapped.append(seg_out)
                total_frames += n

            if self._check_cancel():
                return EngineResult(False, error="已取消")

            # 合并
            self._emit("merge", 0, 1, "合并片段")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            face_stem = Path(self.config.face_source).stem
            out_name = f"{Path(video_path).stem}_{face_stem}_{timestamp}.mp4"
            final_output = os.path.join(self.config.output_dir, out_name)
            os.makedirs(self.config.output_dir, exist_ok=True)

            temp_merged = os.path.join(temp_dir, "merged.mp4")
            if len(swapped) == 1:
                shutil.move(swapped[0], temp_merged)
            else:
                merge_videos(swapped, temp_merged)

            # 混音 BGM
            if self.config.bgm_source:
                from .audio_mixer import mix_bgm
                self._emit("audio", 0, 1, "混音 BGM")
                mix_bgm(
                    temp_merged, final_output,
                    bgm_source=self.config.bgm_source,
                    bgm_random=self.config.bgm_random,
                    keep_original_audio=self.config.keep_original_audio,
                    bgm_volume=self.config.bgm_volume,
                    original_volume=self.config.original_volume,
                )
            else:
                shutil.copy2(temp_merged, final_output)

            shutil.rmtree(temp_dir, ignore_errors=True)

            elapsed = time.time() - t_start
            self._emit("done", 1, 1, f"完成: {Path(final_output).name} ({elapsed:.0f}s)")
            return EngineResult(True, output_path=final_output,
                                frames_processed=total_frames, elapsed_sec=elapsed)

        except Exception as e:
            return EngineResult(False, error=str(e))

    def process_batch(self) -> list[EngineResult]:
        """批量处理目录下所有视频"""
        from .media_utils import list_videos
        videos = list_videos(self.config.video_source)
        if not videos:
            return [EngineResult(False, error="视频目录为空")]

        if self._app is None:
            self.init_models()
            self.load_source_face()

        results = []
        for i, v in enumerate(videos):
            if self._check_cancel():
                break
            self._emit("init", i, len(videos), f"任务 {i+1}/{len(videos)}: {v.name}")
            r = self.process_single_video(str(v))
            results.append(r)
        return results
