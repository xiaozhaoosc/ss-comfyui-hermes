# -*- coding: utf-8 -*-
"""动作克隆 —— 轨道二：Pose 骨架提取。

把一段参考视频逐帧转成 ControlNet 可直接消费的骨架序列：
    - OpenPose 风格黑底彩色骨架 PNG 序列（pose_frames/frame_XXXXXX.png）
    - 骨架视频（pose.mp4，帧率跟随源视频）
    - 关键点 JSON（keypoints.json，OpenPose-18 布局）

支持两种后端：
    - dwpose  （默认，本机权重已齐备，输出 body18 + 左右手21 + 脸70）
    - yolov8  （轻量备选，ultralytics YOLOv8-Pose，COCO-17 -> OpenPose-18 映射，无手/脸）

单主体策略：只处理画面中“主体”一人（body 关键点置信度之和最大者）。

用法示例：
    python pose_extract.py --video ref.mp4 --max-frames 20 --no-video
    python pose_extract.py --video ref.mp4 --backend yolov8
"""

import argparse
import json
import os
import sys
import time
from datetime import date

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# 路径与常量
# ---------------------------------------------------------------------------
# 本文件所在目录（tools/motion_clone），用于 import 同目录的平滑模块
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

# 仓库根目录（本文件上溯三级：tools/motion_clone -> tools -> 仓库根）
REPO_ROOT = os.path.dirname(os.path.dirname(_THIS_DIR))

# DWPose 源码根（其下才有 custom_controlnet_aux 包）
DWPOSE_SRC = r"D:\ai_projects\ComfyUI\custom_nodes\comfyui_controlnet_aux\src"
# DWPose 权重目录
CKPT_DIR = r"D:\ai_projects\ComfyUI\custom_nodes\comfyui_controlnet_aux\ckpts\yzd-v\DWPose"

# 关键点数量约定
N_BODY = 18
N_HAND = 21
N_FACE = 70

# 从平滑模块 import（不修改该文件）
from smooth_kalman import smooth_sequence  # noqa: E402


# ---------------------------------------------------------------------------
# COCO-17 -> OpenPose-18 映射（yolov8 后端专用）
# ---------------------------------------------------------------------------
# ultralytics COCO-17 索引：0鼻 1左眼 2右眼 3左耳 4右耳 5左肩 6右肩 7左肘 8右肘
#                          9左腕 10右腕 11左胯 12右胯 13左膝 14右膝 15左踝 16右踝
# OpenPose-18 输出：
#   0鼻 1颈 2右肩 3右肘 4右腕 5左肩 6左肘 7左腕 8右胯 9右膝 10右踝
#   11左胯 12左膝 13左踝 14右眼 15左眼 16右耳 17左耳
_COCO_TO_OPENPOSE = [
    0,    # op0  鼻   <- coco0
    -1,   # op1  颈   <- 左右肩中点（特殊处理）
    6,    # op2  右肩 <- coco6
    8,    # op3  右肘 <- coco8
    10,   # op4  右腕 <- coco10
    5,    # op5  左肩 <- coco5
    7,    # op6  左肘 <- coco7
    9,    # op7  左腕 <- coco9
    12,   # op8  右胯 <- coco12
    14,   # op9  右膝 <- coco14
    16,   # op10 右踝 <- coco16
    11,   # op11 左胯 <- coco11
    13,   # op12 左膝 <- coco13
    15,   # op13 左踝 <- coco15
    2,    # op14 右眼 <- coco2
    1,    # op15 左眼 <- coco1
    4,    # op16 右耳 <- coco4
    3,    # op17 左耳 <- coco3
]


def _coco17_to_openpose18(coco_pts):
    """把一个人物的 COCO-17 关键点映射成 OpenPose-18。

    coco_pts: List[(x, y, conf)]，长度 17，元素可能为 None。
    返回: List[(x, y, conf) 或 None]，长度 18。
    """
    op = [None] * N_BODY
    for op_idx, coco_idx in enumerate(_COCO_TO_OPENPOSE):
        if coco_idx == -1:
            continue  # 颈稍后单独合成
        p = coco_pts[coco_idx] if coco_idx < len(coco_pts) else None
        op[op_idx] = p

    # 颈 = 左右肩（coco5 / coco6）中点，conf 取两者较小值
    ls = coco_pts[5]
    rs = coco_pts[6]
    if ls is not None and rs is not None:
        op[1] = ((ls[0] + rs[0]) / 2.0,
                 (ls[1] + rs[1]) / 2.0,
                 min(ls[2], rs[2]))
    elif ls is not None:
        op[1] = ls
    elif rs is not None:
        op[1] = rs
    return op


# ---------------------------------------------------------------------------
# 后端加载与推理
# ---------------------------------------------------------------------------
def _prepare_dwpose_import():
    """在 import controlnet_aux 之前做好准备（设置环境变量、注入源码路径）。"""
    # 必须在 import controlnet_aux 之前设置（防止 NPU / MMCV 初始化报错）
    os.environ.setdefault("NPU_DEVICE_COUNT", "0")
    os.environ.setdefault("MMCV_WITH_OPS", "0")

    if DWPOSE_SRC not in sys.path:
        sys.path.insert(0, DWPOSE_SRC)


def load_dwpose_backend():
    """加载 DWPose 后端，返回一个 infer(img_rgb) -> List[PoseResult] 的可调用对象。"""
    _prepare_dwpose_import()

    from custom_controlnet_aux.dwpose import DwposeDetector  # noqa: E402

    det = DwposeDetector.from_pretrained(
        CKPT_DIR,
        pretrained_det_model_or_path=CKPT_DIR,
        det_filename="yolox_l.onnx",           # 检测器（YOLOX-L）
        pose_filename="dw-ll_ucoco_384.onnx",  # 姿态估计
        torchscript_device="cuda",
    )

    def infer(img_rgb):
        # 输入必须是 RGB；无检测到人时返回空列表
        return det.detect_poses(img_rgb)

    return infer


def load_yolov8_backend(weights):
    """加载 YOLOv8-Pose 后端，返回一个 infer(img_rgb) -> List[dict] 的可调用对象。"""
    try:
        from ultralytics import YOLO
    except Exception as exc:  # 未安装
        print("未安装 ultralytics，无法使用 yolov8 后端。原始错误：%s" % exc)
        sys.exit(2)

    try:
        model = YOLO(weights)
    except Exception as exc:
        # 典型情况：离线下无法自动下载权重
        print("需要联网下载权重 `yolov8n-pose.pt`，或通过 `--yolov8-weights` 指定本地路径")
        print("原始错误：%s" % exc)
        sys.exit(2)

    def infer(img_rgb):
        # ultralytics 自动批处理；这里单帧推理
        results = model.predict(img_rgb, verbose=False)
        res = results[0]
        people = []
        if res.keypoints is None:
            return people
        xy = res.keypoints.xy.cpu().numpy()       # (n, 17, 2)
        conf = res.keypoints.conf
        conf = conf.cpu().numpy() if conf is not None else np.ones(xy.shape[:2], dtype=float)
        for i in range(xy.shape[0]):
            coco = [
                (float(xy[i, k, 0]), float(xy[i, k, 1]), float(conf[i, k]))
                for k in range(xy.shape[1])
            ]
            people.append(coco)
        return people

    return infer


# ---------------------------------------------------------------------------
# 归一化：把后端原始输出统一成 (body18, left_hand21, right_hand21, face70)
# 每个元素为 (x, y, conf) 或 None；手/脸整体不可用时为 None。
# ---------------------------------------------------------------------------
def _kp_list_to_pts(kp_list, n):
    """把 List[Optional[Keypoint]] 转成定长的 [(x, y, conf) 或 None]。"""
    if kp_list is None:
        return None
    pts = []
    for i in range(n):
        k = kp_list[i] if i < len(kp_list) else None
        if k is None:
            pts.append(None)
        else:
            pts.append((float(k.x), float(k.y), float(k.score)))
    return pts


def normalize_dwpose_frame(poses):
    """从 DWPose 的 List[PoseResult] 里选出主体，返回 (parts, detected_people)。

    parts = (body18, left_hand21, right_hand21, face70) 或 None（该帧无人）。
    """
    detected_people = len(poses)
    if detected_people == 0:
        return None, detected_people

    def body_score(p):
        kps = p.body.keypoints
        return sum(k.score for k in kps if k is not None)

    # 单主体策略：取 body 关键点置信度之和最大者
    best = max(poses, key=body_score)

    body = _kp_list_to_pts(best.body.keypoints, N_BODY)
    # 极端情况下 keypoints 全为 None 也补齐成定长
    if body is None:
        body = [None] * N_BODY
    left_hand = _kp_list_to_pts(best.left_hand, N_HAND)
    right_hand = _kp_list_to_pts(best.right_hand, N_HAND)
    face = _kp_list_to_pts(best.face, N_FACE)
    return (body, left_hand, right_hand, face), detected_people


def normalize_yolov8_frame(people):
    """从 YOLOv8-Pose 的 List[COCO-17] 里选出主体，返回 (parts, detected_people)。"""
    detected_people = len(people)
    if detected_people == 0:
        return None, detected_people

    def coco_score(coco):
        return sum(p[2] for p in coco if p is not None)

    best = max(people, key=coco_score)
    body = _coco17_to_openpose18(best)
    # yolov8 后端不产出 hand / face
    return (body, None, None, None), detected_people


# ---------------------------------------------------------------------------
# 平滑
# ---------------------------------------------------------------------------
def smooth_part(part_frames, conf_thresh):
    """对某个部件跨帧的关键点序列做平滑。

    part_frames: List[List[(x, y, conf) 或 None]] 或 List[None]（整体不可用）。
    若整体不可用（全为 None，例如 yolov8 的手/脸），原样返回。
    """
    if all(f is None for f in part_frames):
        return part_frames
    # 把整体为 None 的帧替换成对应长度的 None 列表，保证结构一致
    n_kp = None
    for f in part_frames:
        if f is not None:
            n_kp = len(f)
            break
    fixed = [f if f is not None else [None] * n_kp for f in part_frames]
    return smooth_sequence(fixed, conf_thresh=conf_thresh)


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------
def render_skeleton(W, H, body, left_hand, right_hand, face, dw_util, Keypoint):
    """把一帧的关键点渲染成 (H, W, 3) 的 RGB 骨架图（黑底彩骨）。"""
    canvas = np.zeros((H, W, 3), dtype=np.uint8)

    def to_kps(pts, n):
        if pts is None:
            return None
        return [Keypoint(p[0], p[1], p[2], i) if p is not None else None
                for i, p in enumerate(pts[:n])]

    body_kps = to_kps(body, N_BODY)
    if body_kps is None:
        body_kps = [None] * N_BODY
    left_kps = to_kps(left_hand, N_HAND)
    right_kps = to_kps(right_hand, N_HAND)
    face_kps = to_kps(face, N_FACE)

    canvas = dw_util.draw_bodypose(canvas, body_kps)
    canvas = dw_util.draw_handpose(canvas, left_kps)
    canvas = dw_util.draw_handpose(canvas, right_kps)
    canvas = dw_util.draw_facepose(canvas, face_kps)
    return canvas


# ---------------------------------------------------------------------------
# JSON 输出辅助
# ---------------------------------------------------------------------------
def _fmt_part(pts, n):
    """把部件关键点序列格式化成 JSON 结构。不可用时返回 None。"""
    if pts is None:
        return None
    out = []
    for i in range(n):
        p = pts[i] if i < len(pts) else None
        if p is None:
            out.append([0.0, 0.0, 0.0])
        else:
            out.append([round(float(p[0]), 2),
                        round(float(p[1]), 2),
                        round(float(p[2]), 2)])
    return out


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="动作克隆轨道二：从参考视频提取 OpenPose-18 骨架序列 / 视频 / JSON。")
    parser.add_argument("--video", required=True, help="参考视频路径（必填）")
    parser.add_argument("--outdir", default=None,
                        help="输出目录；未指定时默认 output/<日期>/motion_clone/<视频名>/")
    parser.add_argument("--backend", choices=["dwpose", "yolov8"], default="dwpose",
                        help="Pose 后端，默认 dwpose")
    parser.add_argument("--no-smooth", action="store_true", help="关闭关键点平滑")
    parser.add_argument("--conf-thresh", type=float, default=0.3,
                        help="平滑模块的置信度阈值，默认 0.3")
    parser.add_argument("--max-frames", type=int, default=0,
                        help="只处理前 N 帧（0 = 全部），便于快速冒烟")
    parser.add_argument("--yolov8-weights", default="yolov8n-pose.pt",
                        help="yolov8 后端权重路径，默认 yolov8n-pose.pt")
    parser.add_argument("--no-video", action="store_true",
                        help="不合成 pose.mp4，只输出 PNG + JSON")
    return parser.parse_args(argv)


def default_outdir(video_path):
    """未指定 --outdir 时的默认输出目录。"""
    stem = os.path.splitext(os.path.basename(video_path))[0]
    today = date.today().strftime("%Y-%m-%d")
    return os.path.join(REPO_ROOT, "output", today, "motion_clone", stem)


def main(argv=None):
    args = parse_args(argv)

    video_path = os.path.abspath(args.video)
    if not os.path.isfile(video_path):
        print("错误：找不到视频文件：%s" % video_path)
        sys.exit(1)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("错误：无法打开视频（可能编码不受支持或文件损坏）：%s" % video_path)
        sys.exit(1)

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    src_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    if fps <= 0.0:
        print("警告：源视频 fps 缺失或为 0，合成骨架视频时改用 24.0。")
        fps = 24.0

    print("=" * 60)
    print("动作克隆 · 轨道二 Pose 骨架提取")
    print("源视频      : %s" % video_path)
    print("分辨率      : %d x %d" % (W, H))
    print("源 fps      : %.3f" % fps)
    print("抽帧总数    : %s" % (src_frame_count if src_frame_count > 0 else "未知"))
    print("后端        : %s" % args.backend)
    print("平滑        : %s" % ("关闭" if args.no_smooth else "开启"))
    print("=" * 60)

    # ---------- 输出目录 ----------
    outdir = os.path.abspath(args.outdir) if args.outdir else default_outdir(video_path)
    frames_dir = os.path.join(outdir, "pose_frames")
    os.makedirs(frames_dir, exist_ok=True)

    # ---------- 加载后端 ----------
    t_load = time.time()
    if args.backend == "dwpose":
        infer = load_dwpose_backend()
        norm_fn = normalize_dwpose_frame
    else:
        infer = load_yolov8_backend(args.yolov8_weights)
        norm_fn = normalize_yolov8_frame
    print("后端加载完成，耗时 %.2f 秒。" % (time.time() - t_load))

    # 骨架绘制工具（两个后端共用 OpenPose-18 布局的绘制函数）
    _prepare_dwpose_import()
    from custom_controlnet_aux.dwpose import util as dw_util  # noqa: E402
    from custom_controlnet_aux.dwpose.types import Keypoint  # noqa: E402

    # ---------- 逐帧推理 ----------
    t_start = time.time()
    raw_frames = []      # 每帧: {"parts": (body,lh,rh,face) 或 None, "detected_people": int}
    frame_index = 0
    limit = args.max_frames if args.max_frames and args.max_frames > 0 else None

    while True:
        if limit is not None and frame_index >= limit:
            break
        ret, frame_bgr = cap.read()
        if not ret:
            break

        img_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        poses = infer(img_rgb)
        parts, detected = norm_fn(poses)
        raw_frames.append({"parts": parts, "detected_people": detected})

        frame_index += 1
        if frame_index % 20 == 0:
            print("  已处理 %d 帧 ..." % frame_index)

    cap.release()
    processed = len(raw_frames)

    if processed == 0:
        print("错误：未能从视频中读取任何帧。")
        sys.exit(1)

    print("推理完成，共处理 %d 帧，耗时 %.2f 秒。" % (processed, time.time() - t_start))

    # ---------- 平滑 ----------
    if args.no_smooth:
        final_frames = raw_frames
    else:
        # 拆成四个部件的跨帧序列
        def collect(part_idx):
            seq = []
            for f in raw_frames:
                parts = f["parts"]
                seq.append(parts[part_idx] if parts is not None else None)
            return seq

        body_seq = smooth_part(collect(0), args.conf_thresh)
        lh_seq = smooth_part(collect(1), args.conf_thresh)
        rh_seq = smooth_part(collect(2), args.conf_thresh)
        face_seq = smooth_part(collect(3), args.conf_thresh)

        final_frames = []
        for i, f in enumerate(raw_frames):
            if f["parts"] is None:
                parts = None
            else:
                parts = (body_seq[i], lh_seq[i], rh_seq[i], face_seq[i])
            final_frames.append({"parts": parts,
                                 "detected_people": f["detected_people"]})

    # ---------- 渲染 + 写盘 + JSON ----------
    t_render = time.time()
    video_writer = None
    pose_mp4_path = os.path.join(outdir, "pose.mp4")
    if not args.no_video:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        video_writer = cv2.VideoWriter(pose_mp4_path, fourcc, fps, (W, H))
        if not video_writer.isOpened():
            print("警告：VideoWriter 打开失败，跳过 pose.mp4 合成。")
            video_writer = None

    json_frames = []
    for i, f in enumerate(final_frames):
        parts = f["parts"]
        if parts is None:
            body = lh = rh = face = None
        else:
            body, lh, rh, face = parts

        # 渲染骨架（两个后端统一用 DWPose 的绘制工具，保持 OpenPose-18 布局）
        canvas_rgb = render_skeleton(
            W, H,
            body, lh, rh, face,
            dw_util, Keypoint,
        )

        canvas_bgr = cv2.cvtColor(canvas_rgb, cv2.COLOR_RGB2BGR)
        png_path = os.path.join(frames_dir, "frame_%06d.png" % i)
        cv2.imwrite(png_path, canvas_bgr)
        if video_writer is not None:
            video_writer.write(canvas_bgr)

        # JSON 帧结构
        if parts is None:
            json_frames.append({
                "frame_index": i,
                "detected_people": f["detected_people"],
                "people": [],
            })
        else:
            json_frames.append({
                "frame_index": i,
                "detected_people": f["detected_people"],
                "people": [{
                    "body": _fmt_part(body, N_BODY),
                    "left_hand": _fmt_part(lh, N_HAND),
                    "right_hand": _fmt_part(rh, N_HAND),
                    "face": _fmt_part(face, N_FACE),
                }],
            })

        if (i + 1) % 20 == 0:
            print("  已渲染 %d / %d 帧 ..." % (i + 1, processed))

    if video_writer is not None:
        video_writer.release()

    # ---------- 写 keypoints.json ----------
    json_obj = {
        "source_video": video_path,
        "fps": round(float(fps), 3),
        "width": W,
        "height": H,
        "total_frames": src_frame_count if src_frame_count > 0 else processed,
        "processed_frames": processed,
        "backend": args.backend,
        "smoothed": not args.no_smooth,
        "conf_thresh": args.conf_thresh,
        "keypoint_format": "openpose18",
        "counts": {
            "body": N_BODY,
            "left_hand": N_HAND,
            "right_hand": N_HAND,
            "face": N_FACE,
        },
        "frames": json_frames,
    }

    json_path = os.path.join(outdir, "keypoints.json")
    with open(json_path, "w", encoding="utf-8") as fp:
        json.dump(json_obj, fp, ensure_ascii=False, indent=2)

    elapsed = time.time() - t_start
    print("-" * 60)
    print("骨架 PNG 目录 : %s" % frames_dir)
    if video_writer is not None:
        print("骨架视频     : %s" % pose_mp4_path)
    print("关键点 JSON  : %s" % json_path)
    print("渲染耗时     : %.2f 秒" % (time.time() - t_render))
    print("总耗时       : %.2f 秒，处理帧数 %d" % (elapsed, processed))
    print("下一步：可把 pose_frames/ 直接丢给 OpenPose ControlNet 使用。")
    print("-" * 60)


if __name__ == "__main__":
    main()