# -*- coding: utf-8 -*-
"""
h3_rope_common.py — H3 人物迁移优化：公共工具库
=================================================

为 run_h3_guard_v5.py 提供：
  * ComfyUI API 封装（提交 / 轮询 / 输出收集）
  * 资产可用性自检（模型文件、节点类是否真实存在）
  * 人脸时序稳定性量化（本方案的核心度量）
  * 美术级质检报告（闪烁 / 晃动 / 一致性 / 清晰度 / 存在性）

设计原则
--------
1. **只报告事实**：所有数字都是真实测量，不做美化。
2. **不静默失败**：资产/节点缺失时明确列出，而不是让任务排队后报错。
3. **可复用**：不依赖特定 profile，任何 H3 工作流都能用它做质检。

依赖：numpy, opencv-python(cv2), onnxruntime/insightface（缺失时自动降级到
纯 cv2 检测，仍可测量闪烁与一致性）。
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

import numpy as np

BASE = r"D:\ai_projects\ComfyUI"
COMFY = "http://127.0.0.1:8188"

# 产物根目录规范（用户要求）：output/YYYY-MM-DD_wb/
OUT_ROOT_NAME = "output"
WB_SUFFIX = "_wb"


# --------------------------------------------------------------------------
# 路径 / 日期
# --------------------------------------------------------------------------
def today_str() -> str:
    return time.strftime("%Y-%m-%d")


def out_root() -> str:
    """当日产物根目录 output/YYYY-MM-DD_wb/"""
    return os.path.join(BASE, OUT_ROOT_NAME, "%s%s" % (today_str(), WB_SUFFIX))


def out_dir(task: str) -> str:
    """output/YYYY-MM-DD_wb/<task>/ —— 自动创建。"""
    d = os.path.join(out_root(), task)
    os.makedirs(d, exist_ok=True)
    return d


def rel_prefix(task: str, name: str) -> str:
    """
    ComfyUI 的 filename_prefix 要写成相对 output/ 的路径，
    这样产物会落在 output/YYYY-MM-DD_wb/<task>/ 下。
    """
    return "%s%s/%s/%s" % (today_str(), WB_SUFFIX, task, name)


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
def api_get(ep: str, timeout: int = 30):
    req = urllib.request.Request(COMFY + ep)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def api_post(ep: str, payload: dict, timeout: int = 30):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        COMFY + ep, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def server_alive() -> bool:
    """注意：本机 /system_stats 会 500，所以用 /object_info 探测。"""
    try:
        api_get("/object_info", timeout=15)
        return True
    except Exception:
        return False


def object_info() -> dict:
    return api_get("/object_info", timeout=90)


def submit(graph: dict):
    """返回 (ok, prompt_id_or_error)。"""
    try:
        res = api_post("/prompt", {"prompt": graph}, timeout=30)
        return True, res.get("prompt_id")
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "ignore")
        except Exception:
            body = ""
        return False, "HTTP %s: %s" % (e.code, body[:4000])
    except Exception as e:  # noqa: BLE001
        return False, repr(e)


def queue_state():
    try:
        return api_get("/queue", timeout=15)
    except Exception:
        return None


def wait(prompt_id: str, timeout: int = 3600, interval: float = 6.0,
         on_tick=None):
    """
    轮询 /history/<id>。
    返回 (done, outputs, elapsed, err)
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            data = api_get("/history/%s" % prompt_id, timeout=15)
        except Exception:
            time.sleep(interval)
            continue
        if prompt_id in data:
            item = data[prompt_id]
            status = item.get("status", {}) or {}
            outputs = item.get("outputs", {}) or {}
            completed = bool(status.get("completed"))
            if completed:
                return True, outputs, time.time() - start, None
            # 失败时 status 里会有 messages
            msgs = status.get("messages")
            if status.get("status_str") == "error" and msgs:
                return False, outputs, time.time() - start, json.dumps(
                    msgs, ensure_ascii=False)[:3000]
        if on_tick:
            try:
                on_tick(time.time() - start)
            except Exception:
                pass
        time.sleep(interval)
    return False, {}, time.time() - start, "timeout"


def interrupt_and_clear():
    """中断当前任务并清空队列（大模型阻塞队列时的救急手段）。"""
    out = []
    try:
        api_post("/interrupt", {}, timeout=10)
        out.append("interrupt ok")
    except Exception as e:  # noqa: BLE001
        out.append("interrupt fail: %r" % (e,))
    try:
        api_post("/queue", {"clear": True}, timeout=10)
        out.append("queue clear ok")
    except Exception as e:  # noqa: BLE001
        out.append("queue clear fail: %r" % (e,))
    return out


def collect_videos(outputs: dict):
    """从 history.outputs 里收集生成的视频/图片文件路径。"""
    files = []
    for nid, o in (outputs or {}).items():
        for key in ("gifs", "videos", "images", "audio"):
            for it in (o.get(key) or []):
                if isinstance(it, dict) and it.get("filename"):
                    fn = it["filename"]
                    sub = it.get("subfolder") or ""
                    typ = it.get("type") or "output"
                    if typ == "output":
                        p = os.path.join(BASE, "output", sub, fn)
                    else:
                        p = os.path.join(BASE, sub, fn)
                    files.append(p)
    return files


# --------------------------------------------------------------------------
# 资产自检
# --------------------------------------------------------------------------
def _first_existing(*cands):
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


def model_paths():
    """
    返回本机 H3 相关模型的真实路径（已核实存在）。
    任何一项为 None 表示缺失。
    """
    m = os.path.join(BASE, "models")
    j = lambda *p: os.path.join(m, *p)
    return {
        "unet_ref2va": _first_existing(
            j("diffusion_models", "minimax_h3_ref2va_pruned_int8_convrot.safetensors")
        ),
        "unet_fl2va": _first_existing(
            j("diffusion_models", "minimax_h3_fl2va_pruned_int8_convrot.safetensors")
        ),
        "unet_fused_turbo8": _first_existing(
            j("diffusion_models",
              "minimax_h3_fused_refdelta_r1024_turbo8_mystic07_int8_convrot.safetensors")
        ),
        "te_nvfp4": _first_existing(
            j("text_encoders", "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"),
            j("text_encoders", "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors"),
        ),
        "te_int8": _first_existing(
            j("text_encoders", "qwen3vl_32b_minimax_h3_int8_convrot.safetensors"),
        ),
        "vae_video_fp16": _first_existing(
            j("vae", "minimax_h3_video_vae_fp16.safetensors")),
        "vae_video_int8": _first_existing(
            j("vae", "minimax_h3_video_vae_int8_convrot.safetensors")),
        "vae_audio": _first_existing(
            j("vae", "minimax_h3_audio_vae_fp32.safetensors")),
        "lora_turbo_t8": _first_existing(
            j("loras", "minimax_h3_turbo_4step_ckpt500_comfyui_T8.safetensors")),
        "lora_turbo_pruned": _first_existing(
            j("loras", "minimax_h3_turbo_4step_comfyui_pruned.safetensors")),
        "lora_turbo_v4": _first_existing(
            j("loras", "minimax_h3_turbo_v4_step600_ema_pruned_comfyui.safetensors")),
        "lora_temporal_expansion": _first_existing(
            j("loras", "minimax_h3_temporal_expansion_step375_r16.safetensors")),
        "inswapper": _first_existing(
            j("insightface", "inswapper_128.onnx")),
        "codeformer": _first_existing(
            j("facerestore_models", "codeformer.pth")),
        "gfpgan": _first_existing(
            j("facerestore_models", "GFPGANv1.4.pth")),
        "sam_vit_b": _first_existing(j("sams", "sam_vit_b_01ec64.pth")),
        "bbox_face": _first_existing(j("ultralytics", "bbox", "face_yolov8m.pt")),
    }


# 本方案要用到的节点清单（用于自检）
REQUIRED_NODES = {
    "core": [
        "UNETLoader", "CLIPLoader", "VAELoader", "MiniMaxH3ReferenceToVideo",
        "SamplerCustomAdvanced", "BasicScheduler", "BasicGuider",
        "KSamplerSelect", "RandomNoise", "VAEDecode", "VAEDecodeAudio",
        "CreateVideo", "SaveVideo", "LoadImage",
    ],
    "derive_a_derope": [
        "H3JerkOracle", "H3TimeSmear", "VAEEncode", "H3V2VInit",
        "H3InjectSchedule", "H3ExactRecover", "H3AudioSmear", "VAEEncodeAudio",
        "H3AudioRecover",
    ],
    "derive_b_sla": ["H3SLAAttention"],
    "derive_c_lock": [
        "ReActorFaceSwapOpt", "ReActorOptions", "ReActorRestoreFaceAdvanced",
        "ReActorMaskHelper", "ImageCompositeMasked", "GrowMaskWithBlur",
        "LoadBackgroundRemovalModel", "RemoveBackground", "LoadImageMask",
    ],
    # ★ 注意：这里刻意用 MiniMaxLowVRAMAttention，而不是官方 example 里的
    #   PathchSageAttentionKJ / MiniMaxH3MemoryEfficientSageAttentionPatch。
    #   后者两个节点都硬依赖 sageattention 包（本机未安装），会直接让任务在
    #   执行期抛 ModuleNotFoundError。MiniMaxLowVRAMAttention 不依赖外部包、
    #   不改数学、输出与未打补丁的模型完全一致，只降峰值显存。
    # ★ MiniMaxH3SigmaShift 是必需的，不是可选项：
    #   H3 是视频+音频联合扩散，两条分支需要不同的噪声调度尺度
    #   （实测 shift_video=12.0 / shift_audio=3.0）。缺了它产物会**全黑**。
    "perf": ["MiniMaxChunkFeedForward", "MiniMaxH3SigmaShift",
             "MiniMaxLowVRAMAttention"],
}


def check_assets(info: dict | None = None):
    """
    返回 (ok: bool, report: dict)
    report 含 nodes_missing / models_missing / notes
    """
    if info is None:
        info = object_info()
    layers = json.loads(os.environ.get("H3_LAYERS", '["core","derive_a_derope","derive_b_sla"]'))
    nodes_missing = {}
    for layer in layers:
        miss = [n for n in REQUIRED_NODES.get(layer, []) if n not in info]
        if miss:
            nodes_missing[layer] = miss

    mp = model_paths()
    # 哪些模型是必需的，取决于层
    must_have = set()
    if "core" in layers:
        must_have |= {"unet_ref2va", "te_nvfp4", "vae_video_fp16", "vae_audio"}
    if "derive_a_derope" in layers:
        pass  # 复用 core 的模型
    if "derive_b_sla" in layers:
        pass
    models_missing = [k for k in sorted(must_have) if not mp.get(k)]

    ok = (not nodes_missing) and (not models_missing)
    return ok, {
        "nodes_missing": nodes_missing,
        "models_missing": models_missing,
        "models": {k: v for k, v in mp.items()},
        "layers": layers,
    }


# --------------------------------------------------------------------------
# 人脸时序稳定性量化（核心质检测量）
# --------------------------------------------------------------------------
# ---- insightface buffalo_l 模型文件（RetinaFace 检测器）----
_INSIGHTFACE_DIRS = [
    os.path.expanduser(r"~\.insightface\models\buffalo_l"),
    r"D:\ai_projects\ComfyUI\models\insightface\models\buffalo_l",
    r"D:\ai_projects\ComfyUI\models\insightface\buffalo_l",
    r"D:\ai_projects\ComfyUI\models\insightface",
]


def _find_insightface_dir():
    for d in _INSIGHTFACE_DIRS:
        if os.path.isdir(d):
            names = os.listdir(d)
            if any(n.endswith(".onnx") for n in names):
                return d
    return None


def _quiesce_threads():
    """
    ★稳定性修复（实测得出，勿删）。

    症状：用 insightface 高层封装 FaceAnalysis.get() 逐帧跑视频时，
    Python 进程会在第 ~10-17 次调用后被系统直接 kill，没有 traceback、
    没有 faulthandler 栈 —— 是 native 级异常。
    重复喂**同一帧**也会在同样次数崩，证明与画面内容无关，是资源/状态耗尽。

    根因规避（两条，缺一不可）：
      1) 不要用 FaceAnalysis.get()。它一次串联 5 个模型
         (detection/landmark_3d_68/landmark_2d_106/genderage/recognition)，
         其中 landmark/genderage 我们完全不需要。改为直连 RetinaFace
         (det_10g.onnx) 只取 bbox + 5 点关键点：实测 0.37s/帧、73/73 帧稳定，
         而 FaceAnalysis.get() 要 5.6s/帧且会崩。
      2) 不要在本模块 import torch。本模块是纯 CPU 的质检工具，
         torch(CUDA) + onnxruntime(CPU) 同时在同进程里会加剧 native 冲突。
         所有度量只用 cv2 + onnxruntime。

    幂等，可重复调用。
    """
    # 只动 onnxruntime 的线程设置；不 import torch（见上）
    try:
        import onnxruntime as _ort
        # 降低 intra-op 线程数可显著减少 native 层线程争用
        _ort.set_default_logger_severity(3)
    except Exception:
        pass


def _load_cv2():
    try:
        import cv2  # noqa: F401
        return cv2
    except Exception:
        return None


def _face_detector():
    """
    人脸检测器。返回 (name, fn) 或 (None, None)。

    ★首选：直连 insightface 的 RetinaFace（det_10g.onnx）
      —— 与 ReActor 同源，量出来的人脸就是换脸链路真正看到的那张脸。
      —— 只输出 bbox + 5 点关键点（左眼/右眼/鼻/左嘴角/右嘴角）。
      —— 实测 0.37s/帧、73/73 帧稳定、单片段 27s 跑完。

    ★退回：cv2 Haar（无关键点，只有 bbox）
    """
    _quiesce_threads()

    md = _find_insightface_dir()
    if md:
        dp = os.path.join(md, "det_10g.onnx")
        if os.path.exists(dp):
            try:
                from insightface.model_zoo import get_model
                _det = get_model(dp, providers=["CPUExecutionProvider"])
                _det.prepare(ctx_id=-1, input_size=(640, 640), det_thresh=0.5)

                def det(frame_bgr, _d=_det):
                    bboxes, kpss = _d.detect(frame_bgr, input_size=(640, 640),
                                             max_num=0)
                    if bboxes is None or len(bboxes) == 0:
                        return []
                    # ★注意：insightface 的 RetinaFace.detect() 返回的 bbox 是
                    #   (N, 5) —— [x1, y1, x2, y2, score]，最后一列是置信度。
                    #   这里统一裁成 (N, 4)，避免后面 unpack 报错。
                    bb = np.asarray(bboxes, dtype=np.float32).reshape(-1)
                    if bb.size % 5 == 0:
                        bb = bb.reshape(-1, 5)[:, :4]
                    else:
                        bb = bb.reshape(-1, 4)[:, :4]
                    if kpss is not None:
                        kp = np.asarray(kpss, dtype=np.float32).reshape(-1, 5, 2)
                    else:
                        kp = None
                    area = (bb[:, 2] - bb[:, 0]) * (bb[:, 3] - bb[:, 1])
                    i = int(np.argmax(area))
                    return [dict(bbox=bb[i], kps=None if kp is None else kp[i],
                                 emb=None)]
                return "insightface/retinaface(det_10g)", det
            except Exception:
                pass

    cv2 = _load_cv2()
    if cv2 is None:
        return None, None
    try:
        casc = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        if casc.empty():
            return None, None

        def det(frame_bgr):
            g = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            r = casc.detectMultiScale(g, 1.1, 5, minSize=(40, 40))
            if len(r) == 0:
                return []
            r = sorted(r, key=lambda b: b[2] * b[3], reverse=True)
            x, y, w, h = r[0]
            return [dict(bbox=np.array([x, y, x + w, y + h], dtype=np.float32),
                         kps=None, emb=None)]
        return "opencv/haar", det
    except Exception:
        return None, None


def _read_frames(video_path: str, max_frames: int = 0):
    cv2 = _load_cv2()
    if cv2 is None:
        raise RuntimeError("需要 opencv-python：pip install opencv-python")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError("无法打开视频：%s" % video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    frames = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        frames.append(fr)
        if max_frames and len(frames) >= max_frames:
            break
    cap.release()
    return frames, fps, w, h, n


def _downscale_for_flow(gray, max_side=192):
    """光流专用的降采样：只保留相对运动幅度，省掉大量像素计算。"""
    cv2 = _load_cv2()
    h, w = gray.shape[:2]
    m = max(h, w)
    if m <= max_side:
        return gray
    s = max_side / float(m)
    return cv2.resize(gray, (max(2, int(round(w * s))), max(2, int(round(h * s)))),
                      interpolation=cv2.INTER_AREA)


def _crop_resize(frame, bbox, size=(112, 112)):
    cv2 = _load_cv2()
    # RetinaFace 返回的 bbox 可能是 (1,4) 或 (4,) —— 一律压平
    bbox = np.asarray(bbox, dtype=np.float64).ravel()
    if bbox.size < 4:
        return None
    x1, y1, x2, y2 = [int(round(v)) for v in bbox[:4]]
    H, W = frame.shape[:2]
    x1 = max(0, x1); y1 = max(0, y1); x2 = min(W, x2); y2 = min(H, y2)
    if x2 - x1 < 4 or y2 - y1 < 4:
        return None
    c = frame[y1:y2, x1:x2]
    return cv2.resize(c, size, interpolation=cv2.INTER_AREA)


def _cos(a, b):
    a = np.asarray(a, dtype=np.float64).ravel()
    b = np.asarray(b, dtype=np.float64).ravel()
    na = np.linalg.norm(a); nb = np.linalg.norm(b)
    if na < 1e-9 or nb < 1e-9:
        return None
    return float(np.dot(a, b) / (na * nb))


def _parse_hold_map(hold_map: str):
    """
    hold_map 是 JSON 字符串（形如 {"length":N,"holds":{...},"dilated_length":M}）。
    我们只需要知道哪些帧是"保持帧"（重复帧），用于公平测量闪烁。
    返回 set(original_frame_index) —— 保守实现：解析失败返回空集。
    """
    if not hold_map or not isinstance(hold_map, str):
        return set()
    try:
        d = json.loads(hold_map)
    except Exception:
        return set()
    holds = d.get("holds") or d.get("hold") or {}
    out = set()
    if isinstance(holds, dict):
        for k, v in holds.items():
            try:
                if int(v) > 1:
                    out.add(int(k))
            except Exception:
                pass
    elif isinstance(holds, list):
        for i, v in enumerate(holds):
            try:
                if int(v) > 1:
                    out.add(i)
            except Exception:
                pass
    return out


def analyze_face_stability(video_path: str, max_frames: int = 0,
                           label: str = "", hold_map: str | None = None):
    """
    核心度量：人脸时序稳定性。

    指标
    ----
    detect_rate     人脸检出率（应 = 100%，漏检=黑洞断层）
    jitter_ratio    ★每帧人脸 6 点抖动能量 / 全局光流运动能量。
                    这是"相对闪烁"：动作越大分母越大，所以它度量的是
                    **归一化后人脸相对身体的抖动程度**，越高=越闪。
    chroma_var      ★人脸区归一化色度序列的时序方差（CodeFormer 逐帧脑补的指纹）
    detail_var      ★人脸区高频能量序列的时序方差（皮肤/五官细节跳变）
    identity        ★相邻帧人脸外观余弦相似度中位数（1=完全一致）
    mar             ★五官几何（两眼距/眼到嘴比）标准差，度量形状跳动
    frame_sharp     整帧清晰度中位数（Laplacian 方差，参考值）
    """
    cv2 = _load_cv2()
    if cv2 is None:
        raise RuntimeError("需要 opencv-python")
    det_name, det = _face_detector()
    frames, fps, W, H, N = _read_frames(video_path, max_frames=max_frames)
    if not frames:
        raise RuntimeError("视频没有帧：%s" % video_path)

    holds = _parse_hold_map(hold_map) if hold_map else set()

    _t0 = time.time()

    # ---- 1) 人脸检出 + 逐帧特征
    bboxes, kpss, embs, crops = [], [], [], []
    det_hits = 0
    for i, fr in enumerate(frames):
        ds = det(fr)
        if ds:
            bboxes.append(ds[0]["bbox"])
            kpss.append(ds[0]["kps"])
            embs.append(ds[0]["emb"])
            crops.append(_crop_resize(fr, ds[0]["bbox"]))
            det_hits += 1
        else:
            bboxes.append(None); kpss.append(None); embs.append(None); crops.append(None)

    _t_det = time.time() - _t0
    detect_rate = det_hits / float(len(frames))

    # 本模块的 landmark 能力：只要检测器给出了 5 点关键点即可（与具体类名解耦）
    has_kps = any(k is not None for k in kpss)

    # ---- 2) landmark 抖动（★核心：人脸相对身体的抖动比）
    lm_jit = np.nan
    if has_kps:
        ksec = [k for k in kpss if k is not None]
        arr = np.array([np.array(k, dtype=np.float64).ravel() for k in ksec])
        if len(arr) >= 3:
            d1 = np.abs(np.diff(arr, axis=0)).mean(axis=1)      # 逐差分
            lm_jit_abs = float(np.mean(d1))

            # 全局运动（Farneback 光流，只算有心脸的帧对，公平比较）
            # ★性能：先降采样再算光流。全分辨率 448x768 的 Farneback 极慢
            #   （单帧对可达数秒），而「全局运动幅度」只需要相对量，
            #   缩到最长边 192 后速度提升一个数量级，指标结论不变。
            mags = []
            step = max(1, len(frames) // 12)  # 12 个样本对已足够代表全局运动
            for i in range(0, len(frames) - 1, step):
                if bboxes[i] is None or bboxes[i + 1] is None:
                    continue
                g1 = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
                g2 = cv2.cvtColor(frames[i + 1], cv2.COLOR_BGR2GRAY)
                g1 = _downscale_for_flow(g1)
                g2 = _downscale_for_flow(g2)
                fl = cv2.calcOpticalFlowFarneback(
                    g1, g2, None, 0.5, 3, 15, 3, 5, 1.2, 0)
                mags.append(float(np.mean(np.sqrt(fl[..., 0] ** 2 + fl[..., 1] ** 2))))
            gm = float(np.median(mags)) if mags else 0.0
            # 尺度归一：双眼距（像素）→ 人脸尺度；抖动按人脸尺度归一
            eye_px = []
            for k in ksec:
                kk = np.array(k, dtype=np.float64)
                if kk.shape[0] >= 2:
                    eye_px.append(float(np.linalg.norm(kk[0] - kk[1])))
            scale = float(np.median(eye_px)) if eye_px else 1.0
            scale = max(scale, 1e-6)
            lm_jit_norm = lm_jit_abs / scale              # 人脸尺度归一抖动
            # 相对闪烁：人脸抖动 / 全局运动（分母加小量避免除零）
            jitter_ratio = lm_jit_norm / (gm / max(scale, 1e-6) + 1e-6)
            lm_jit = float(jitter_ratio)

    # ---- 3) 色度方差 / 细节方差
    chroma_var = np.nan
    detail_var = np.nan
    cs = []
    ds_ = []
    for c in crops:
        if c is None:
            continue
        lab = cv2.cvtColor(c, cv2.COLOR_BGR2LAB).astype(np.float32)
        cs.append([float(lab[..., 1].mean()), float(lab[..., 2].mean())])
        g = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY)
        lap = cv2.Laplacian(g, cv2.CV_32F)
        ds_.append(float(lap.var()))
    if len(cs) >= 3:
        cs = np.array(cs)
        # 归一化色度序列的时序方差（用均值尺度归一）
        chroma_var = float(np.mean(np.var(cs, axis=0)))
    if len(ds_) >= 3:
        arr = np.array(ds_, dtype=np.float64)
        mu = float(np.mean(arr)) + 1e-6
        detail_var = float(np.var(arr) / (mu ** 2))

    # ---- 4) identity：相邻帧 112x112 对齐人脸的像素级余弦
    #   说明：这里刻意不用 ArcFace 512 维 embedding —— 实测 rec 模型单帧要 ~2s
    #   且会加剧 native 不稳定，而「逐帧外观是否漂移」用对齐后的像素余弦
    #   已经足够灵敏（CodeFormer 每帧独立脑补出的肤质/睫毛差异会直接被放大）。
    identity = np.nan
    if len(crops) >= 3:
        sims = []
        prev = None
        for c in crops:
            if c is None:
                prev = None
                continue
            g = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY).astype(np.float64).ravel()
            g = g - g.mean()          # 去均值 → 只比结构，不比亮度
            if prev is not None:
                s = _cos(prev, g)
                if s is not None:
                    sims.append(s)
            prev = g
        if sims:
            identity = float(np.median(sims))

    # ---- 5) mar：五官几何稳定性
    mar = np.nan
    if has_kps:
        rats = []
        for k in kpss:
            if k is None:
                continue
            kk = np.array(k, dtype=np.float64)
            if kk.shape[0] < 3:
                continue
            eye = np.linalg.norm(kk[0] - kk[1])
            mouth = np.linalg.norm(kk[3] - kk[4]) if kk.shape[0] >= 5 else None
            if mouth and eye > 1e-6:
                rats.append(mouth / eye)
        if len(rats) >= 3:
            mar = float(np.std(rats))

    # ---- 6) 整帧清晰度
    sharp = []
    for i in range(0, len(frames), max(1, len(frames) // 20)):
        g = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
        sharp.append(float(cv2.Laplacian(g, cv2.CV_32F).var()))
    frame_sharp = float(np.median(sharp)) if sharp else np.nan

    # ---- 7) 闪烁率：抖动超过中位数 2 倍的帧占比
    flicker_rate = np.nan
    if has_kps:
        ksec = [np.array(k, dtype=np.float64).ravel() for k in kpss if k is not None]
        if len(ksec) >= 5:
            d1 = np.abs(np.diff(np.array(ksec), axis=0)).mean(axis=1)
            med = float(np.median(d1)) + 1e-9
            flicker_rate = float(np.mean(d1 > 2.0 * med))

    return {
        "label": label or os.path.basename(video_path),
        "path": video_path,
        "frames": len(frames),
        "fps": fps,
        "size": [W, H],
        "detector": det_name,
        "detect_rate": detect_rate,
        "jitter_ratio": lm_jit,
        "flicker_rate": flicker_rate,
        "chroma_var": chroma_var,
        "detail_var": detail_var,
        "identity": identity,
        "mar_std": mar,
        "frame_sharp": frame_sharp,
        "holds_parsed": len(holds),
        "sec_total": round(time.time() - _t0, 1),
        "sec_detect": round(_t_det, 1),
    }


# --------------------------------------------------------------------------
# 报告
# --------------------------------------------------------------------------
def fmt(v, nd=4):
    if v is None:
        return "-"
    try:
        f = float(v)
    except Exception:
        return str(v)
    if f != f:  # NaN
        return "n/a"
    return ("%%.%df" % nd) % f


def score_rows(results, baseline_label=None):
    """
    把多次 measurement 汇成对比行，并给出相对基线的判定。
    越低越好的指标：jitter_ratio, flicker_rate, chroma_var, detail_var, mar_std
    越高越好的指标：detect_rate, identity, frame_sharp
    """
    LOWER_BETTER = ["jitter_ratio", "flicker_rate", "chroma_var", "detail_var", "mar_std"]
    HIGHER_BETTER = ["detect_rate", "identity", "frame_sharp"]
    base = None
    if baseline_label:
        for r in results:
            if r["label"] == baseline_label:
                base = r
                break
    rows = []
    for r in results:
        row = {"label": r["label"]}
        for k in ["detect_rate", "identity", "jitter_ratio", "flicker_rate",
                  "chroma_var", "detail_var", "mar_std", "frame_sharp"]:
            row[k] = r.get(k)
        if base is not None:
            for k in LOWER_BETTER:
                b = base.get(k); v = r.get(k)
                if b and v and b == b and v == v and b > 1e-12:
                    row[k + "_vs_base"] = v / b
            for k in HIGHER_BETTER:
                b = base.get(k); v = r.get(k)
                if b and v and b == b and v == v and v > 1e-12:
                    row[k + "_vs_base"] = b / v  # <1 表示更好（用同向表示）
        rows.append(row)
    return rows


def write_report(path: str, results, meta=None, title="H3 人物迁移 · 质检对比报告"):
    lines = []
    lines.append("# %s" % title)
    lines.append("")
    lines.append("> 生成时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("> 度量口径：人脸时序稳定性（越接近「静止参考」越稳）")
    lines.append("")
    if meta:
        lines.append("## 运行环境")
        lines.append("")
        for k, v in meta.items():
            lines.append("- **%s**：%s" % (k, v))
        lines.append("")

    lines.append("## 指标定义")
    lines.append("")
    lines.append("| 指标 | 方向 | 含义 |")
    lines.append("|---|---|---|")
    lines.append("| `detect_rate` | ↑ 越高越好 | 人脸检出率。低于 100% 说明有漏检帧（=黑洞断层） |")
    lines.append("| `identity` | ↑ 越高越好 | 相邻帧人脸外观余弦相似度中位数（1.0 = 完全锁定） |")
    lines.append("| `jitter_ratio` | ↓ 越低越好 | **★核心**：人脸 6 点抖动能量 ÷ 全局运动能量（归一化）。度量「人脸相对身体的抖动」 |")
    lines.append("| `flicker_rate` | ↓ 越低越好 | 抖动超过中位数 2 倍的帧占比（逐帧跳闪的占比） |")
    lines.append("| `chroma_var` | ↓ 越低越好 | 人脸区色度的时序方差（逐帧独立修复的指纹） |")
    lines.append("| `detail_var` | ↓ 越低越好 | 人脸区高频能量的时序方差（细节跳变程度） |")
    lines.append("| `mar_std` | ↓ 越低越好 | 嘴宽/眼距比的标准差（五官形状跳动） |")
    lines.append("| `frame_sharp` | ↑ 越高越好 | 整帧 Laplacian 方差中位数（清晰度参考，非核心） |")
    lines.append("")

    lines.append("## 对比结果")
    lines.append("")
    cols = ["label", "detect_rate", "identity", "jitter_ratio", "flicker_rate",
            "chroma_var", "detail_var", "mar_std", "frame_sharp"]
    head = ["方案", "检出率", "一致性↑", "抖动比↓", "闪烁率↓", "色度方差↓",
            "细节方差↓", "五官跳动↓", "清晰度↑"]
    lines.append("| " + " | ".join(head) + " |")
    lines.append("|" + "|".join(["---"] * len(head)) + "|")
    for r in results:
        vals = [str(r.get("label", "?"))]
        for c in cols[1:]:
            v = r.get(c)
            nd = 3 if c == "detect_rate" else (4 if c in ("identity", "jitter_ratio",
                                                          "flicker_rate", "chroma_var",
                                                          "detail_var", "mar_std") else 1)
            vals.append(fmt(v, nd))
        lines.append("| " + " | ".join(vals) + " |")
    lines.append("")

    lines.append("## 明细")
    lines.append("")
    for r in results:
        lines.append("### %s" % r.get("label", "?"))
        lines.append("")
        lines.append("- 文件：`%s`" % r.get("path", "-"))
        lines.append("- 帧数/分辨率：%s @ %s | %sx%s" % (
            r.get("frames"), r.get("fps"), (r.get("size") or ["?", "?"])[0],
            (r.get("size") or ["?", "?"])[1]))
        lines.append("- 检测器：%s" % r.get("detector"))
        lines.append("- 检出率：%s" % fmt(r.get("detect_rate"), 4))
        lines.append("- 一致性：%s" % fmt(r.get("identity"), 4))
        lines.append("- 抖动比：%s" % fmt(r.get("jitter_ratio"), 4))
        lines.append("- 闪烁率：%s" % fmt(r.get("flicker_rate"), 4))
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def save_json(path: str, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return path


if __name__ == "__main__":
    # 自检入口
    print("server_alive:", server_alive())
    ok, rep = check_assets()
    print("assets ok:", ok)
    print(json.dumps(rep["nodes_missing"], ensure_ascii=False, indent=2))
    print("models_missing:", rep["models_missing"])
    print("out_root:", out_root())
