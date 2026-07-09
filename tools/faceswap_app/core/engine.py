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

    def _emit(self, stage: str, current: int, total: int, msg: str = ""):
        self.progress_cb(stage, current, total, msg)

    def _check_cancel(self) -> bool:
        if self.cancel_check():
            self._cancelled = True
            return True
        return False

    # ---------- 模型初始化 ----------

    def _resolve_model_paths(self):
        """解析模型路径：优先 ComfyUI 根，回退 exe 同级"""
        candidates = [
            Path(os.getcwd()),
            Path(__file__).resolve().parents[3],  # faceswap_app -> tools -> ComfyUI
            Path(os.path.dirname(os.sys.executable)) if getattr(os.sys, 'frozen', False) else Path.cwd(),
        ]
        swapper_path = None
        gfpgan_path = None
        for root in candidates:
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

        # GPU 模式下注册 torch 自带的 cuDNN DLL 路径，避免 onnxruntime 静默 fallback CPU。
        # Why: onnxruntime-gpu 加载 onnxruntime_providers_cuda.dll 依赖 cudnn64_9.dll，
        # 但该 DLL 不在系统 PATH 中（torch 自带在 torch/lib/ 下），导致 CUDA 无法初始化。
        if self.config.use_gpu:
            self._register_cudnn_path()

        self._emit("init", 0, 1, f"加载 FaceAnalysis (providers={providers[0]})")
        self._app = FaceAnalysis(name='buffalo_l', providers=providers)
        self._app.prepare(ctx_id=0, det_size=(640, 640))

        swapper_path, gfpgan_path = self._resolve_model_paths()
        if swapper_path is None:
            raise FileNotFoundError(f"未找到 inswapper_128.onnx，请检查 models/insightface/ 目录")

        self._emit("init", 0, 1, f"加载 swapper: {Path(swapper_path).name}")
        self._swapper = get_model(swapper_path, providers=providers)

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
        faces = self._app.get(small)
        if not faces:
            raise ValueError(f"源图片未检测到人脸: {self.config.face_source}")

        self._source_img = img
        self._source_faces = faces
        self._emit("init", 1, 1, f"源人脸检测: {len(faces)} 个")

    # ---------- 单段处理 ----------

    def _process_segment(self, seg_path: str, seg_output: str, fps: float) -> int:
        """处理单个视频片段，返回写入帧数"""
        if self._check_cancel():
            return 0

        frames_dir = seg_path + "_frames"
        output_frames_dir = seg_path + "_swapped"
        for d in (frames_dir, output_frames_dir):
            if os.path.exists(d):
                shutil.rmtree(d, ignore_errors=True)
            os.makedirs(d, exist_ok=True)

        # 提取帧
        import subprocess
        subprocess.run([
            'ffmpeg', '-i', seg_path,
            '-vf', f'fps={fps}',
            os.path.join(frames_dir, 'frame_%04d.png'), '-y'
        ], capture_output=True, text=True)

        frames = sorted(Path(frames_dir).glob('frame_*.png'))
        if not frames:
            shutil.copy2(seg_path, seg_output)
            return 0

        self._emit("split", 0, len(frames), f"提取 {len(frames)} 帧")
        t0 = time.time()
        written = 0

        for i, frame_path in enumerate(frames):
            if self._check_cancel():
                return written

            # 统一用 out_frame_path 表示该帧在 output_frames_dir 下的输出路径
            # Why: 便于循环末尾发送 preview 回调，避免重复拼接
            out_frame_path = os.path.join(output_frames_dir, frame_path.name)
            target = imread_unicode(frame_path)
            if target is None:
                placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
                imwrite_unicode(out_frame_path, placeholder)
                written += 1
            else:
                target_faces = self._app.get(target)
                if not target_faces:
                    imwrite_unicode(out_frame_path, target)
                    written += 1
                else:
                    best = max(target_faces,
                               key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]))
                    result = self._swapper.get(target.copy(), best, self._source_faces[0], paste_back=True)
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
                    imwrite_unicode(out_frame_path, result)
                    written += 1

            # 每 5 帧发送已换脸帧路径，供 GUI 流式预览
            if (i + 1) % 5 == 0:
                self._emit("preview", i + 1, len(frames), out_frame_path)

            # 每帧或每 50 帧上报进度
            if (i + 1) % 10 == 0 or (i + 1) == len(frames):
                elapsed = time.time() - t0
                fps_proc = (i + 1) / elapsed if elapsed > 0 else 0
                eta = (len(frames) - i - 1) / fps_proc if fps_proc > 0 else 0
                self._emit("frame", i + 1, len(frames),
                           f"{i+1}/{len(frames)} ({fps_proc:.1f}帧/s 剩余{eta:.0f}s)")

        # 合成视频（含原音）
        import subprocess
        cmd = [
            'ffmpeg',
            '-start_number', '1',
            '-framerate', str(fps),
            '-i', os.path.join(output_frames_dir, 'frame_%04d.png'),
            '-i', seg_path,
            '-c:v', 'libx264', '-c:a', 'aac',
            '-map', '0:v:0', '-map', '1:a:0?',
            '-pix_fmt', 'yuv420p',
            seg_output, '-y'
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg 合成失败: {r.stderr[-300:]}")

        # 清理
        shutil.rmtree(frames_dir, ignore_errors=True)
        shutil.rmtree(output_frames_dir, ignore_errors=True)
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
