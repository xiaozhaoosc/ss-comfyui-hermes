# -*- coding: utf-8 -*-
"""tools/motion_fidelity_qa.py
动作保真客观验收器：把「产物视频」的人体姿态轨迹与「源视频」逐帧比对，
用可复现的数值判定产物是否真的复刻了源动作，而不是"另一支舞"。

为什么需要它：
    H3 ref2va 这类"语义条件"路线，产物的全局运动能量可能与源视频很接近
    （实测 10.19 vs 10.99），但运动能量时序相关只有 r≈-0.19 —— 即节奏、
    重音、转身/弯腰/侧身/交叉动作的时间点跟源完全对不上。肉眼看不准，
    必须用姿态轨迹做量化比对。

判定方法（自证式，不依赖拍脑袋阈值）：
    以源视频自身造两条锚线——
      锚线A 同一段动作：源 vs 源           -> 上限，理论上所有指标满分
      锚线B 时间错位  ：源 vs 源(循环平移半程) -> 下限，代表"完全不同步"的分数
    再把候选产物插在两条锚线之间，得到归一化得分 0~1，>= --pass-score 判通过。
    这样阈值有物理含义：0 等于"和错位一样糟"，1 等于"和源一模一样"。

用法：
    # 离线自检（合成数据，不占 GPU）
    python tools/motion_fidelity_qa.py --self-test

    # 真实比对（自动用 DWPose 抽骨架）
    python tools/motion_fidelity_qa.py --ref-video <源.mp4> --cand-video <产物.mp4> \
        --every 2 --json <输出.json>
"""

import argparse
import json
import os
import sys

import cv2
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_MC_DIR = os.path.join(_HERE, "motion_clone")
if _MC_DIR not in sys.path:
    sys.path.insert(0, _MC_DIR)

# OpenPose-18 身体关键点索引
N_BODY = 18
NECK, RSH, LSH, RHIP, LHIP = 1, 2, 5, 8, 11

# 判定用的指标名
_KEYS = ("traj_corr", "dyn_corr", "orient_corr", "turn_corr", "pose_err")

# 判定阈值：(阈值, 比较符)。标定依据见 evaluate() 文档字符串。
# dyn_corr 不在其中——判别力弱，只作参考。
_THRESH = {"traj_corr": (0.50, ">="), "turn_corr": (0.50, ">="), "pose_err": (0.30, "<=")}


# ---------------------------------------------------------------------------
# 关键点采集
# ---------------------------------------------------------------------------
def kp_from_json(path):
    """读取 pose_extract 产出的 keypoints.json，返回 (T, 18, 3) 数组（缺测填 0）。"""
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    frames = obj.get("frames") or []
    arr = np.zeros((len(frames), N_BODY, 3), dtype=np.float32)
    for i, fr in enumerate(frames):
        people = fr.get("people") or []
        if not people:
            continue
        body = people[0].get("body")
        if not body:
            continue
        for j in range(min(N_BODY, len(body))):
            p = body[j]
            if p is None:
                continue
            arr[i, j] = (float(p[0]), float(p[1]), float(p[2]))
    return arr


def kp_from_video(path, every=1):
    """用 DWPose 逐帧（可跨步）抽骨架，返回 (T, 18, 3)。

    复用 tools/motion_clone/pose_extract.py 的后端加载与归一化，避免重复实现。
    """
    from pose_extract import load_dwpose_backend, normalize_dwpose_frame  # noqa: E402

    infer = load_dwpose_backend()
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError("无法打开视频：%s" % path)
    out = []
    idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if every > 1 and idx % every != 0:
            idx += 1
            continue
        parts, _n = normalize_dwpose_frame(infer(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
        body = parts[0] if parts is not None else None
        row = np.zeros((N_BODY, 3), dtype=np.float32)
        if body is not None:
            for j in range(min(N_BODY, len(body))):
                p = body[j]
                if p is not None:
                    row[j] = (float(p[0]), float(p[1]), float(p[2]))
        out.append(row)
        idx += 1
    cap.release()
    if not out:
        raise RuntimeError("未能从视频读到任何帧：%s" % path)
    return np.stack(out, axis=0)


def smooth_body(arr, conf_thresh=0.3):
    """按 pose_extract 同一组卡尔曼参数平滑骨架，使两侧处理口径一致。

    参考骨架常来自 pose_extract 的平滑输出（`smoothed=true`），而候选是从视频现抽的
    原始骨架。若不平滑候选，候选会带更多高频抖动、被系统性低估相关度（偏保守）。
    加 --smooth 即对两侧都套同一滤波器，消除这一口径差。
    """
    from smooth_kalman import smooth_sequence  # noqa: E402

    frames = []
    for t in range(arr.shape[0]):
        row = []
        for j in range(N_BODY):
            x, y, c = float(arr[t, j, 0]), float(arr[t, j, 1]), float(arr[t, j, 2])
            row.append(None if (c <= 0 or (x == 0.0 and y == 0.0)) else (x, y, c))
        frames.append(row)
    sm = smooth_sequence(frames, conf_thresh=conf_thresh)
    out = np.zeros_like(arr)
    for t in range(arr.shape[0]):
        for j in range(N_BODY):
            p = sm[t][j]
            if p is not None:
                out[t, j] = (p[0], p[1], p[2])
    return out


def _face_embedder(det_thresh=0.5):
    """加载 insightface buffalo_l（RetinaFace 检测 + w600k_r50 识别）。

    直连 model_zoo（不用会崩进程的 FaceAnalysis.get），返回 img_bgr -> 512 维归一化向量。
    """
    from types import SimpleNamespace

    from insightface.model_zoo import get_model
    from char_lib_add import _insightface_dir

    # GPU 优先：onnxruntime-gpu 已装，CUDA 可用时检测/识别全部走 GPU，避免 CPU 满负荷
    try:
        import onnxruntime as _ort
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] \
            if "CUDAExecutionProvider" in _ort.get_available_providers() else ["CPUExecutionProvider"]
    except Exception:
        providers = ["CPUExecutionProvider"]

    md = _insightface_dir()
    det = get_model(str(md / "det_10g.onnx"), providers=providers)
    det.prepare(ctx_id=-1 if providers == ["CPUExecutionProvider"] else 0,
                input_size=(640, 640), det_thresh=det_thresh)
    rec = get_model(str(md / "w600k_r50.onnx"), providers=providers)
    rec.prepare(ctx_id=-1 if providers == ["CPUExecutionProvider"] else 0)

    def embed(img_bgr):
        bboxes, kpss = det.detect(img_bgr, input_size=(640, 640), max_num=0)
        if bboxes is None or len(bboxes) == 0:
            return None
        bb = np.asarray(bboxes, dtype=np.float32).reshape(-1, 5)[:, :4]
        kp = np.asarray(kpss, dtype=np.float32).reshape(-1, 5, 2)
        area = (bb[:, 2] - bb[:, 0]) * (bb[:, 3] - bb[:, 1])
        i = int(np.argmax(area))
        feat = np.asarray(rec.get(img_bgr, SimpleNamespace(kps=kp[i])), dtype=np.float32).reshape(-1)
        return feat / (np.linalg.norm(feat) + 1e-9)

    return embed


def _imread_any(path):
    img = cv2.imread(path)
    if img is None:
        img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    return img


def identity_gate(ref_image, cand_video, every=5, thresh=0.50):
    """身份一致性闸门：参考图人脸向量 vs 产物各帧人脸向量的最大/平均余弦。

    阈值说明：项目内"同身份"建议 cos>=0.60，但生成视频帧受运动模糊/画质影响会偏低，
    因此默认门槛放宽到 0.50（以"出现过的最高相似帧"为准，避免侧脸帧拉低判定）。
    """
    embed = _face_embedder()
    ref_img = _imread_any(ref_image)
    if ref_img is None:
        raise RuntimeError("读不到参考图：%s" % ref_image)
    ref_feat = embed(ref_img)
    if ref_feat is None:
        raise RuntimeError("参考图未检测到人脸：%s" % ref_image)

    cap = cv2.VideoCapture(cand_video)
    if not cap.isOpened():
        raise RuntimeError("打不开产物视频：%s" % cand_video)
    sims = []
    idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if idx % every == 0:
            f = embed(frame)
            if f is not None:
                sims.append(float(np.dot(ref_feat, f)))
        idx += 1
    cap.release()

    if not sims:
        return {"total_frames": idx, "frames_with_face": 0, "max_cos": None,
                "mean_cos": None, "thresh": thresh, "passed": False}
    mx = max(sims)
    return {"total_frames": idx, "frames_with_face": len(sims),
            "max_cos": round(mx, 4), "mean_cos": round(float(np.mean(sims)), 4),
            "thresh": thresh, "passed": bool(mx >= thresh)}


def get_kp(args, which):
    """取某一路关键点：优先用 --kp，否则抽视频骨架。"""
    kp = getattr(args, "%s_kp" % which)
    if kp:
        return kp_from_json(kp)
    vid = getattr(args, "%s_video" % which)
    if not vid:
        raise SystemExit("必须为 %s 提供 --%s-kp 或 --%s-video" % (which, which, which))
    print("  [%s] DWPose 抽骨架：%s (every=%d)" % (which, vid, args.every), flush=True)
    arr = kp_from_video(vid, args.every)
    print("  [%s] 得到 %d 帧关键点" % (which, arr.shape[0]), flush=True)
    return arr


# ---------------------------------------------------------------------------
# 归一化：消掉全局平移与尺度（画幅不同也能比）
# ---------------------------------------------------------------------------
def normalize_body(arr):
    """arr (T,18,3) -> (norm (T,18,2), valid (T,18))。

    逐帧以 neck(1) 为原点、以 |neck-midhip| 为尺度做归一化，
    使姿态对全局平移与人物大小不变，只保留朝向与关节角度。
    """
    T = arr.shape[0]
    norm = np.zeros((T, N_BODY, 2), dtype=np.float64)
    valid = np.zeros((T, N_BODY), dtype=bool)
    for t in range(T):
        conf = arr[t, :, 2]
        xy = arr[t, :, :2]
        v = (conf > 0) & ~((xy[:, 0] == 0) & (xy[:, 1] == 0))
        valid[t] = v
        if not (v[NECK] and v[RHIP] and v[LHIP]):
            continue  # 躯干锚不可用，整帧作废
        midhip = 0.5 * (xy[RHIP] + xy[LHIP])
        scale = float(np.linalg.norm(xy[NECK] - midhip))
        if scale < 1e-3:
            continue
        norm[t] = (xy - xy[NECK]) / scale
    return norm, valid


def resample(norm, valid, samples):
    """把逐帧序列重采样到 samples 个归一化时间桶，返回 (R (samples,18,2), V (samples,18))。"""
    T = norm.shape[0]
    R = np.full((samples, N_BODY, 2), np.nan)
    V = np.zeros((samples, N_BODY), dtype=bool)
    if T < 2:
        return R, V
    t_src = np.linspace(0.0, 1.0, T)
    u = np.linspace(0.0, 1.0, samples)
    for j in range(N_BODY):
        m = valid[:, j]
        if m.sum() < 2:
            continue
        ti = t_src[m]
        if ti[-1] - ti[0] < 1e-6:
            continue
        R[:, j, 0] = np.interp(u, ti, norm[m, j, 0])
        R[:, j, 1] = np.interp(u, ti, norm[m, j, 1])
        V[:, j] = True
    return R, V


# ---------------------------------------------------------------------------
# 指标
# ---------------------------------------------------------------------------
def _shoulder_series(R, V):
    """肩线角度时序（抓转身/侧身）。"""
    out = np.full(R.shape[0], np.nan)
    for i in range(R.shape[0]):
        if V[i, RSH] and V[i, LSH]:
            v = R[i, LSH] - R[i, RSH]
            out[i] = np.arctan2(v[1], v[0])
    return out


def _motion_series(R, V):
    """逐桶总位移（抓节奏/重音）。"""
    out = np.zeros(R.shape[0])
    for i in range(1, R.shape[0]):
        m = V[i] & V[i - 1]
        if m.sum() > 0:
            out[i] = float(np.mean(np.linalg.norm(R[i, m] - R[i - 1, m], axis=1)))
    return out


def _width_series(R, V):
    """归一化肩宽时序（抓转身：人一偏头/侧身，投影肩宽就会缩短）。"""
    out = np.full(R.shape[0], np.nan)
    for i in range(R.shape[0]):
        if V[i, RSH] and V[i, LSH]:
            out[i] = float(np.linalg.norm(R[i, LSH] - R[i, RSH]))
    return out


def _corr(a, b):
    if a.size < 3 or a.std() < 1e-8 or b.std() < 1e-8:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def metrics(A, Av, B, Bv):
    """计算 A(参考) 与 B(候选) 的四项指标。"""
    # 轨迹相关：逐关节逐轴 Pearson 求均值
    rs = []
    n_used = 0
    for j in range(N_BODY):
        m = Av[:, j] & Bv[:, j]
        if m.sum() < 8:
            continue
        n_used += 1
        for ax in (0, 1):
            rs.append(_corr(A[m, j, ax], B[m, j, ax]))
    traj = float(np.nanmean(rs)) if rs else float("nan")

    # 姿态误差：逐桶配对关节的平均归一化欧氏距离（单位=躯干长度）
    errs = []
    for i in range(A.shape[0]):
        m = Av[i] & Bv[i]
        if m.sum() < 4:
            continue
        errs.append(float(np.mean(np.linalg.norm(A[i, m] - B[i, m], axis=1))))
    pose_err = float(np.mean(errs)) if errs else float("nan")

    dyn = _corr(_motion_series(A, Av), _motion_series(B, Bv))

    oa, ob = _shoulder_series(A, Av), _shoulder_series(B, Bv)
    mo = ~np.isnan(oa) & ~np.isnan(ob)
    orient = _corr(np.unwrap(oa[mo]), np.unwrap(ob[mo])) if mo.sum() > 8 else float("nan")

    turn = _corr(_width_series(A, Av), _width_series(B, Bv))

    return {"traj_corr": traj, "dyn_corr": dyn, "orient_corr": orient,
            "turn_corr": turn, "pose_err": pose_err, "joints_used": n_used}


def evaluate(ref, cand, samples):
    """返回对比结果 dict。

    判定用 _THRESH 的固定阈值（已按观测噪声 0.005~0.2 的合成数据标定）：
      traj_corr   >= 0.50   关节轨迹时间相关（同动作噪声观测实测 0.49~0.85，异动 -0.12）
      turn_corr   >= 0.50   归一化肩宽时序相关（抓转身/侧身；同动作实测 0.70，异动 -0.10，静止 0.21）
      pose_err    <= 0.30   逐桶姿态误差（单位=躯干长度；同动作实测 0.02~0.30，异动 0.43~0.56）
      orient_corr / dyn_corr 仅作参考不判定（前者在 2D 投影里对 yaw 不敏感，后者判别力弱）
    同时会把"时间错位"锚线（候选沿时间轴循环平移半程）一起算出来，作为机会水平对照。
    """
    An, Av = normalize_body(ref)
    Bn, Bv = normalize_body(cand)
    A, Av = resample(An, Av, samples)
    B, Bv = resample(Bn, Bv, samples)
    shift = samples // 2
    m_null = metrics(A, Av, np.roll(B, shift, axis=0), np.roll(Bv, shift, axis=0))
    m_cand = metrics(A, Av, B, Bv)
    m_self = metrics(A, Av, A, Av)

    checks = {}
    for k, (lim, op) in _THRESH.items():
        v = m_cand.get(k)
        if not np.isfinite(v):
            checks[k] = False
        elif op == ">=":
            checks[k] = v >= lim
        else:
            checks[k] = v <= lim
    enough = m_cand.get("joints_used", 0) >= 6
    return {"self": m_self, "null": m_null, "cand": m_cand,
            "checks": checks, "enough_joints": enough,
            "ref_frames": int(ref.shape[0]), "cand_frames": int(cand.shape[0]),
            "samples": samples}


# ---------------------------------------------------------------------------
# 自检：合成数据验证指标逻辑（不碰 GPU）
# ---------------------------------------------------------------------------
def _synth_template():
    """躯干长度=1 的基础骨架（OpenPose-18 布局，y 向下）。"""
    tm = np.zeros((N_BODY, 2), dtype=np.float64)
    tm[0] = (0.00, -0.20)   # nose
    tm[1] = (0.00, 0.00)    # neck
    tm[2] = (0.32, 0.03)    # R shoulder
    tm[3] = (0.62, 0.34)    # R elbow
    tm[4] = (0.78, 0.72)    # R wrist
    tm[5] = (-0.32, 0.03)   # L shoulder
    tm[6] = (-0.62, 0.34)   # L elbow
    tm[7] = (-0.78, 0.72)   # L wrist
    tm[8] = (0.22, 1.00)    # R hip
    tm[9] = (0.24, 1.62)    # R knee
    tm[10] = (0.22, 2.24)   # R ankle
    tm[11] = (-0.22, 1.00)  # L hip
    tm[12] = (-0.24, 1.62)  # L knee
    tm[13] = (-0.22, 2.24)  # L ankle
    tm[14] = (0.10, -0.20)  # R eye
    tm[15] = (-0.10, -0.20)  # L eye
    tm[16] = (0.18, -0.14)  # R ear
    tm[17] = (-0.18, -0.14)  # L ear
    return tm


def _rot(theta):
    c, s = np.cos(theta), np.sin(theta)
    return np.array([[c, -s], [s, c]])


def _synth_seq(T=140, seed=7, freq=1.0, phase=0.0, noise=0.02):
    """合成一段"转身+弹跳+摆臂"动作，返回 (T,18,3)。

    freq/phase 用来造"另一段动作"；noise 是观测噪声标准差（真实 DWPose 约 0.01~0.03）。
    """
    rng = np.random.default_rng(seed)
    tm = _synth_template()
    t = np.linspace(0.0, 2.0 * np.pi, T) * freq + phase
    prog = np.linspace(0.0, 1.0, T)
    yaw = 0.6 * np.sin(2.0 * t) + 0.30 * prog      # 转身（含单调漂移，使动作非周期）
    bounce = 12.0 * np.abs(np.sin(3.0 * t))
    sway = 6.0 * np.sin(2.0 * t) + 3.0 * prog
    arm = 0.35 * np.sin(4.0 * t) + 0.20 * prog    # 摆臂（关节角度）
    out = np.zeros((T, N_BODY, 3), dtype=np.float32)
    for i in range(T):
        p = tm.copy()
        p[3:5] += (arm[i], 0.0)                 # 右肘/腕摆动
        p[6:8] += (arm[i], 0.0)                 # 左肘/腕摆动
        p[9:11] += (0.25 * arm[i], 0.0)         # 右腿
        p[12:14] += (0.25 * arm[i], 0.0)        # 左腿
        # 绕 neck 做 yaw（用 2D 旋转近似转身时的水平投影变化）
        c = tm[NECK]
        p = (p - c) @ _rot(0.9 * yaw[i]).T + c
        p[:, 0] += sway[i]
        p[:, 1] += bounce[i]
        out[i, :, :2] = p
        out[i, :, 2] = 1.0
    out += rng.normal(0.0, noise, out.shape).astype(np.float32)
    return out


def self_test(samples=96):
    print("=== motion_fidelity_qa 自检（离线合成数据，不占 GPU）===")
    ref = _synth_seq(seed=7, noise=0.02)
    rng = np.random.default_rng(101)
    # "同动作的独立观测"：与 ref 同轨迹但噪声独立 —— 这才是真实可比的上限
    same = ref + rng.normal(0.0, 0.02, ref.shape).astype(np.float32)
    sc = ref.copy()
    sc[:, :, :2] = sc[:, :, :2] * 1.8 + np.array([300.0, 120.0], dtype=np.float32)
    other = _synth_seq(seed=99, freq=1.7, phase=1.1, noise=0.02)
    frozen = np.repeat(ref[:1], ref.shape[0], axis=0) \
        + rng.normal(0.0, 0.02, ref.shape).astype(np.float32)  # 产物几乎不动

    cases = [
        ("same-motion+noise", same, True, "同动作、独立观测噪声"),
        ("translate+scale  ", sc, True, "平移+缩放不变性"),
        ("different-motion ", other, False, "另一段动作"),
        ("frozen-pose      ", frozen, False, "产物几乎不动"),
    ]
    ok_all = True
    for name, cand, expect, desc in cases:
        r = evaluate(ref, cand, samples)
        got = bool(r["enough_joints"]) and all(r["checks"].values())
        ok = got == expect
        ok_all &= ok
        c = r["cand"]
        print("  [%s] %-18s %-16s traj=%6.3f orient=%6.3f err=%5.3f -> %s (期望 %s)"
              % ("OK" if ok else "FAIL", name, desc, c["traj_corr"], c["orient_corr"],
                 c["pose_err"], "PASS" if got else "FAIL", "PASS" if expect else "FAIL"))
    print("SELFTEST %s" % ("PASS" if ok_all else "FAIL"))
    return 0 if ok_all else 1


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def print_report(res, out_json=None):
    c, n, s = res["cand"], res["null"], res["self"]
    print("\n" + "=" * 72)
    print("动作保真客观比对（ref %d 帧 / cand %d 帧，重采样 %d 桶）"
          % (res["ref_frames"], res["cand_frames"], res["samples"]))
    print("-" * 72)
    print("  %-12s %10s %12s %12s %8s" % ("指标", "上限(同源)", "机会(错位)", "候选产物", "判定"))
    for k in _KEYS:
        lim, op = _THRESH.get(k, (float("nan"), " "))
        gate = ("%s %.2f" % (op, lim)) if k in _THRESH else "仅参考"
        print("  %-12s %10.3f %12.3f %12.3f %8s"
              % (k, s.get(k, float("nan")), n.get(k, float("nan")),
                 c.get(k, float("nan")), gate))
    print("-" * 72)
    print("  有效关节数 = %d" % c.get("joints_used", 0))
    for k in _THRESH:
        print("  %s: %s" % (k, "OK" if res["checks"].get(k) else "FAIL"))
    passed = bool(res["enough_joints"]) and all(res["checks"].values())
    print("  判定：%s" % ("PASS 动作复刻正常（轨迹/转身/姿态误差全部达标）"
                        if passed else "FAIL 动作未复刻（与源不同步）"))
    print("=" * 72)
    if out_json:
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2, default=str)
        print("  结果已写入: %s" % out_json)
    return passed


def main(argv=None):
    ap = argparse.ArgumentParser(description="动作保真客观验收（源视频 vs 产物 姿态轨迹比对）")
    ap.add_argument("--ref-kp", default=None, help="源视频的 keypoints.json")
    ap.add_argument("--cand-kp", default=None, help="产物视频的 keypoints.json")
    ap.add_argument("--ref-video", default=None, help="源视频（自动抽骨架）")
    ap.add_argument("--cand-video", default=None, help="产物视频（自动抽骨架）")
    ap.add_argument("--every", type=int, default=1, help="抽骨架跨步（每 N 帧取 1，默认 1）")
    ap.add_argument("--samples", type=int, default=96, help="时间重采样桶数（默认 96）")
    ap.add_argument("--json", default=None, help="把比对结果写入 JSON")
    ap.add_argument("--smooth", action="store_true",
                    help="对两侧骨架都套 pose_extract 的卡尔曼平滑，统一处理口径（推荐）")
    ap.add_argument("--ref-window", default=None,
                    help="只取参考骨架的某个帧窗，格式 START:LEN（产物只覆盖源视频一段时必填，否则时间轴对不上）")
    ap.add_argument("--ref-search", type=int, default=0,
                    help="在 START 附近 +/-N 帧搜最佳对齐（生成模型有时间膨胀，标称窗常有几帧偏移；默认 0=不搜）")
    ap.add_argument("--identity-ref", default=None,
                    help="参考图路径：加此项则额外做人脸身份一致性闸门（候选视频自带人脸检测）")
    ap.add_argument("--identity-every", type=int, default=5, help="身份闸门抽帧步长（默认 5）")
    ap.add_argument("--identity-thresh", type=float, default=0.50, help="身份闸门余弦阈值（默认 0.50）")
    ap.add_argument("--self-test", action="store_true", help="离线合成数据自检，不占 GPU")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test(samples=args.samples)

    ref_all = get_kp(args, "ref")
    cand = get_kp(args, "cand")
    if args.smooth:
        cand = smooth_body(cand)
        print("  已对候选骨架施加同参数卡尔曼平滑（口径对齐）")

    if args.ref_window:
        a, b = args.ref_window.split(":")
        s0, ln = int(a), int(b)
    else:
        s0, ln = 0, ref_all.shape[0]

    shifts = range(-args.ref_search, args.ref_search + 1) if args.ref_search > 0 else [0]
    rows = []
    for d in shifts:
        st = s0 + d
        if st < 0 or st + ln > ref_all.shape[0]:
            continue
        seg = ref_all[st:st + ln]
        if args.smooth:
            seg = smooth_body(seg)
        r = evaluate(seg, cand, args.samples)
        c = r["cand"]
        tr = c["traj_corr"] if np.isfinite(c["traj_corr"]) else -9.0
        tu = c["turn_corr"] if np.isfinite(c["turn_corr"]) else -9.0
        rows.append({"start": st, "off": d, "res": r, "key": tr + tu})
    if not rows:
        raise SystemExit("参考帧窗越界：START:LEN 超出参考骨架长度 %d" % ref_all.shape[0])
    rows.sort(key=lambda x: (-x["key"], abs(x["off"])))

    if len(rows) > 1:
        print("\n对齐搜索（起始 %d，+/-%d 帧）:" % (s0, args.ref_search))
        for i, x in enumerate(sorted(rows, key=lambda y: y["off"])):
            c = x["res"]["cand"]
            print("  start=%3d (%+d)  traj=%6.3f  turn=%6.3f  err=%5.3f%s"
                  % (x["start"], x["off"], c["traj_corr"], c["turn_corr"], c["pose_err"],
                     "  <== 采用" if x is rows[0] else ""))

    res = rows[0]["res"]
    print("\n采用对齐：参考窗起点 %d（相对标称 %+d 帧）" % (rows[0]["start"], rows[0]["off"]))
    passed = print_report(res)

    identity = None
    if args.identity_ref:
        if not getattr(args, "cand_video"):
            raise SystemExit("--identity-ref 需要同时提供 --cand-video 作为人脸来源")
        identity = identity_gate(args.identity_ref, args.cand_video,
                                 every=args.identity_every, thresh=args.identity_thresh)
        print("身份闸门：检出人脸帧 %d/%d，最大 cos=%.4f，均值 cos=%s，阈值 %.2f -> %s"
              % (identity["frames_with_face"], identity["total_frames"],
                 identity["max_cos"] if identity["max_cos"] is not None else float("nan"),
                 identity["mean_cos"], identity["thresh"],
                 "PASS" if identity["passed"] else "FAIL"))
        passed = passed and identity["passed"]

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"motion": res, "identity": identity, "passed": passed},
                      f, ensure_ascii=False, indent=2, default=str)
        print("  结果已写入: %s" % args.json)
    print("最终判定：%s" % ("PASS 产物动作与身份均正常" if passed else "FAIL 产物未达标"))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
