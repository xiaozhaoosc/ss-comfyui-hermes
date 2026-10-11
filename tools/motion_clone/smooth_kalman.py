# -*- coding: utf-8 -*-
"""动作克隆 —— 人体关键点轨迹卡尔曼平滑模块。

背景：从参考视频逐帧提取 Pose 时，快速舞蹈、转身、遮挡会造成严重的逐帧抖动
（jittering）。本模块用常速（CV）卡尔曼滤波对每个关键点跨帧的 (x, y) 轨迹做平滑，
在保留运动趋势的同时显著抑制抖动。

坐标系约定：
    单个关键点 = (x, y, conf)；conf 为置信度。
    单条轨迹   = 长度等于帧数的序列，元素为 (x, y, conf) 或 None（该帧未检测到）。
    多帧序列   = List[frame]，frame = List[keypoint]；外层为帧（时间），内层为关键点序号。

依赖：仅 numpy 与 filterpy。
"""

import numpy as np
from filterpy.kalman import KalmanFilter


def _parse_point(item):
    """把输入元素解析为 (x, y, conf) 三元组，或返回 None。

    容错点：
        - None            -> None（该帧未检测到）
        - (x, y)          -> conf 视为 1.0
        - (x, y, conf)    -> 原样解析
        - list / np.ndarray 形式的上述结构同样接受
    """
    if item is None:
        return None
    try:
        arr = np.asarray(item, dtype=float).reshape(-1)
    except (ValueError, TypeError):
        # 无法转为数值（例如含非法字符），视为无效观测
        return None
    if arr.size == 2:
        return float(arr[0]), float(arr[1]), 1.0
    if arr.size >= 3:
        return float(arr[0]), float(arr[1]), float(arr[2])
    # 长度不足 2，视为无效
    return None


def _build_filter(process_noise, measurement_noise):
    """构造一个 dt=1 的常速（CV）卡尔曼滤波器。

    状态 x = [x, y, vx, vy]，观测 z = [x, y]。
    """
    kf = KalmanFilter(dim_x=4, dim_z=2)

    # F：匀速转移矩阵（dt = 1）
    kf.F = np.array([[1.0, 0.0, 1.0, 0.0],
                     [0.0, 1.0, 0.0, 1.0],
                     [0.0, 0.0, 1.0, 0.0],
                     [0.0, 0.0, 0.0, 1.0]])

    # H：仅观测位置（x, y）
    kf.H = np.array([[1.0, 0.0, 0.0, 0.0],
                     [0.0, 1.0, 0.0, 0.0]])

    # P：初始协方差（位置/速度都不确定，给较大的初始不确定性）
    kf.P = np.eye(4) * 1000.0

    # Q：过程噪声（process_noise 越大越信任观测、平滑越弱）
    kf.Q = np.eye(4) * float(process_noise)

    # R：观测噪声（measurement_noise 越大越信任预测、平滑越强）
    kf.R = np.eye(2) * float(measurement_noise)

    return kf


def smooth_track(track, conf_thresh=0.3, process_noise=1e-2, measurement_noise=1e-1):
    """对单个人体关键点跨帧的轨迹做卡尔曼平滑。

    track: 长度=帧数 的序列，元素为 (x, y, conf) 三元组 或 None（该帧未检测到）。
    返回: 等长的列表，元素为 (x, y, conf) 或 None。

    规则：
        - 首个有效观测（非 None 且 conf >= conf_thresh）用于初始化滤波器状态，
          位置取该观测值，速度置 0。
        - 置信度不足（conf < conf_thresh）或为 None 的帧：只做 predict() 不做 update()，
          且输出记 None（不输出）。
        - 若全程无有效观测，则整条轨迹返回全 None。
    """
    n = len(track)
    parsed = [_parse_point(item) for item in track]

    # 找到首个有效观测，用于初始化滤波器
    init_idx = None
    for i, p in enumerate(parsed):
        if p is not None and p[2] >= conf_thresh:
            init_idx = i
            break

    # 全程无有效观测 -> 全 None
    if init_idx is None:
        return [None] * n

    kf = _build_filter(process_noise, measurement_noise)

    # 用首个有效观测初始化状态：位置 = 观测，速度 = 0
    x0, y0, _ = parsed[init_idx]
    kf.x = np.zeros((4, 1))
    kf.x[:2] = np.array([[x0], [y0]])

    out = [None] * n
    for i in range(n):
        # 每一帧都先预测（即使该帧是无效观测，也维持运动状态继续推进）
        kf.predict()

        p = parsed[i]
        if i == init_idx:
            # 初始化帧：用该观测更新一次，随后输出滤波结果
            kf.update(np.array([[x0], [y0]]))
            out[i] = (float(kf.x[0, 0]), float(kf.x[1, 0]), p[2])
        elif p is not None and p[2] >= conf_thresh:
            # 有效观测：更新并输出平滑后的位置
            kf.update(np.array([[p[0]], [p[1]]]))
            out[i] = (float(kf.x[0, 0]), float(kf.x[1, 0]), p[2])
        else:
            # 低置信 / 缺失：不更新、不输出（保持“不输出”的语义）
            out[i] = None

    return out


def smooth_sequence(frames_keypoints, conf_thresh=0.3, process_noise=1e-2, measurement_noise=1e-1):
    """对多帧、多关键点的序列整体平滑。

    frames_keypoints: List[frame]，frame = List[keypoint]，keypoint = (x, y, conf) 或 None。
    形状约定：外层=帧（时间），内层=关键点序号。

    返回: 与输入结构完全相同（同样的帧数、同样的关键点个数、None 仍为 None 的位置对应保留），
          但坐标已被平滑。帧数必须保持不变。

    每个关键点序号独立维护一个卡尔曼滤波器，互不共享状态。
    """
    n_frames = len(frames_keypoints)
    if n_frames == 0:
        return []

    # 校验：所有帧的关键点个数必须一致
    n_kp = None
    for fi, frame in enumerate(frames_keypoints):
        if frame is None:
            raise ValueError(
                "第 %d 帧为 None，无法确定关键点个数；"
                "smooth_sequence 要求每一帧都是关键点序列（List[keypoint]）。" % fi
            )
        cnt = len(frame)
        if n_kp is None:
            n_kp = cnt
        elif cnt != n_kp:
            raise ValueError(
                "各帧关键点个数不一致：第 0 帧有 %d 个关键点，"
                "第 %d 帧有 %d 个。smooth_sequence 要求所有帧的关键点个数相同。" % (n_kp, fi, cnt)
            )

    # 转置：为每个关键点序号抽出一条跨帧轨迹（内层 -> 外层）
    smoothed_tracks = []
    for k in range(n_kp):
        track = [frames_keypoints[t][k] for t in range(n_frames)]
        smoothed_tracks.append(
            smooth_track(track, conf_thresh, process_noise, measurement_noise)
        )

    # 重新组装回与输入完全相同的结构（帧数不变、关键点个数不变）
    out = [[smoothed_tracks[k][t] for k in range(n_kp)] for t in range(n_frames)]
    return out


if __name__ == "__main__":
    np.random.seed(42)

    # ---------- 用例 1：200 帧合成轨迹，验证抖动下降 ----------
    print("=" * 60)
    print("用例 1：200 帧合成正弦轨迹 + 高斯噪声，验证帧间抖动下降")
    print("=" * 60)

    n_frames = 200
    frames_keypoints = []
    for t in range(n_frames):
        # 真实信号：平滑正弦 + 轻微线性漂移
        x_true = 300.0 + 100.0 * np.sin(2.0 * np.pi * t / 50.0) + 0.5 * t
        y_true = 200.0 + 80.0 * np.cos(2.0 * np.pi * t / 60.0) + 0.3 * t
        # 叠加较大高斯噪声，模拟逐帧抖动
        x_obs = x_true + np.random.normal(0.0, 15.0)
        y_obs = y_true + np.random.normal(0.0, 15.0)
        frames_keypoints.append([(x_obs, y_obs, 1.0)])

    def _jitter(xy_seq):
        """抖动度量：帧间差（一阶差分）的方差。"""
        arr = np.asarray(xy_seq, dtype=float)
        diff = np.diff(arr, axis=0)
        return float(np.var(diff))

    obs_xy = [(f[0][0], f[0][1]) for f in frames_keypoints]

    smoothed = smooth_sequence(frames_keypoints)

    # 结构保持不变
    assert len(smoothed) == n_frames, "平滑前后帧数必须一致！"
    assert all(len(f) == 1 for f in smoothed), "平滑前后关键点个数必须一致！"

    sm_xy = [(f[0][0], f[0][1]) for f in smoothed]

    var_before = _jitter(obs_xy)
    var_after = _jitter(sm_xy)
    ratio = var_after / var_before
    drop_pct = (1.0 - ratio) * 100.0

    print("原始轨迹帧间差方差 (jitter) : %.4f" % var_before)
    print("平滑后帧间差方差 (jitter)   : %.4f" % var_after)
    print("方差比值 (平滑后/原始)      : %.4f" % ratio)
    print("平滑后方差下降              : %.2f%%" % drop_pct)

    assert var_after < var_before, "平滑后方差未下降，平滑失败！"
    print("结论：平滑后方差显著下降，抖动被有效抑制。")

    # ---------- 用例 2：含 None 与低置信点，验证 None 位置 ----------
    print()
    print("=" * 60)
    print("用例 2：含 None 与低置信点，验证输出 None 的位置")
    print("=" * 60)

    none_frames = {3, 4, 10}      # 未检测到
    low_conf_frames = {7, 8}      # 置信度低于阈值
    frames2 = []
    for t in range(20):
        if t in none_frames:
            frames2.append([None])
        elif t in low_conf_frames:
            frames2.append([(100.0 + t, 100.0 + t, 0.1)])
        else:
            frames2.append([(100.0 + t, 100.0 + t, 0.9)])

    sm2 = smooth_sequence(frames2)
    none_positions = [i for i, f in enumerate(sm2) if f[0] is None]
    expected_none = sorted(none_frames | low_conf_frames)

    print("输入为 None 的帧位置        :", sorted(none_frames))
    print("输入为低置信点的帧位置      :", sorted(low_conf_frames))
    print("平滑后输出为 None 的帧位置  :", none_positions)
    print("期望输出为 None 的帧位置    :", expected_none)
    assert none_positions == expected_none, "输出 None 的位置与期望不符！"
    assert all(sm2[i][0] is not None for i in range(20) if i not in expected_none), \
        "有效观测帧不应输出 None！"
    print("结论：低置信点与缺失点既未参与更新也未输出，None 位置符合预期。")

    # ---------- 用例 3：边界与容错 ----------
    print()
    print("=" * 60)
    print("用例 3：边界与容错检查")
    print("=" * 60)

    # 3.1 全程无有效观测 -> 全 None
    all_none = smooth_track([None, (1.0, 2.0, 0.05), None, (3.0, 4.0, 0.2)])
    assert all(v is None for v in all_none), "全程无有效观测应返回全 None！"
    print("3.1 全程无有效观测 -> 全部返回 None：通过")

    # 3.2 (x, y) 两元组 / list / np.ndarray 容错
    mixed_track = [
        np.array([10.0, 20.0, 0.9]),   # ndarray 三元组
        [10.5, 20.5],                  # list 两元组，conf 视为 1.0
        (11.0, 21.0, 0.95),            # tuple 三元组
        None,
    ]
    sm3 = smooth_track(mixed_track)
    assert len(sm3) == 4
    assert sm3[3] is None
    assert all(sm3[i] is not None for i in range(3))
    print("3.2 混合输入形式 (tuple/list/ndarray, 二元/三元)：通过")

    # 3.3 关键点个数不一致 -> ValueError
    try:
        smooth_sequence([[(1.0, 2.0, 0.9)],
                         [(1.0, 2.0, 0.9), (3.0, 4.0, 0.9)]])
        raise AssertionError("关键点个数不一致时应当抛出 ValueError！")
    except ValueError as exc:
        print("3.3 关键点个数不一致已抛出 ValueError：", exc)

    # 3.4 多关键点独立滤波，结构保持一致
    frames4 = [[(float(i), float(i) * 2, 1.0), (float(i) * 3, float(i) * 4, 1.0)]
               for i in range(30)]
    sm4 = smooth_sequence(frames4)
    assert len(sm4) == 30 and all(len(f) == 2 for f in sm4)
    assert sm4[0][0] is not None and sm4[0][1] is not None
    print("3.4 多关键点独立滤波且结构保持一致：通过")

    print()
    print("SELFTEST PASS")