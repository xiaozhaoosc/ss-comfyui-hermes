# -*- coding: utf-8 -*-
"""tools/face_expression_qa.py
表情复刻闸门：把「产物视频」的面部关键点构型序列与「源视频」逐帧比对。

为什么需要它：
    身体动作已有 motion_fidelity_qa.py 的三项闸门，但**表情一直是盲区**。
    本项目已确认：微表情无法塞进法线/白模（MoGe 会平滑掉毫米级起伏），
    表情只能走独立面捕通道（DWPose face70）+ 音频。要证明"表情复刻"，
    必须比对**面部构型随时间的演化**，而不是只看身份相似度。

指标（全部基于 face70 关键点的构型序列，与具体点位语义无关，稳健）：
    face_traj_corr  全脸 70 点构型的时间相关（均值）——抓"表情/头部整体是否同步"
    active_corr     活动区（源片中方差最大的 20 个点）相关——抓"嘴/眼/眉这些真正在动的地方"
    face_err        逐帧归一化构型误差（单位=脸尺度）——越小越像
    判定：face_traj_corr >= 0.50 且 active_corr >= 0.50 且 face_err <= 0.35

用法：
    python tools/face_expression_qa.py --self-test
    python tools/face_expression_qa.py --ref-video <源.mp4> --cand-video <产物.mp4> [--every 2] [--json out.json]
    python tools/face_expression_qa.py --ref-kp <源keypoints.json> --ref-window START:LEN \
        --cand-video <产物.mp4>   # 产物只覆盖源一段时必填；LEN = 产物帧数/产物fps*源fps
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

N_FACE = 70
_ACTIVE_K = 20
_THRESH = {"face_traj_corr": (0.50, ">="), "active_corr": (0.50, ">="), "face_err": (0.35, "<=")}


# ---------------------------------------------------------------------------
# 提取
# ---------------------------------------------------------------------------
def _face_rows(parts):
    """从 DWPose normalize 结果里取 face70 -> (70,3) 数组（缺测填 0）。"""
    row = np.zeros((N_FACE, 3), dtype=np.float32)
    face = parts[3] if parts is not None else None
    if face is not None:
        for j in range(min(N_FACE, len(face))):
            p = face[j]
            if p is not None:
                row[j] = (float(p[0]), float(p[1]), float(p[2]))
    return row


def face_from_video(path, every=1):
    """GPU DWPose 逐帧（可跨步）抽 face70，返回 (T,70,3)。"""
    from pose_extract import load_dwpose_backend, normalize_dwpose_frame  # noqa: E402

    infer = load_dwpose_backend()
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError("无法打开视频：%s" % path)
    out, idx = [], 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if every > 1 and idx % every != 0:
            idx += 1
            continue
        parts, _n = normalize_dwpose_frame(infer(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
        out.append(_face_rows(parts))
        idx += 1
    cap.release()
    if not out:
        raise RuntimeError("未读到帧：%s" % path)
    return np.stack(out, axis=0)


def face_from_json(path):
    """从 keypoints.json 取 face70。"""
    obj = json.load(open(path, encoding="utf-8"))
    frames = obj.get("frames") or []
    arr = np.zeros((len(frames), N_FACE, 3), dtype=np.float32)
    for i, fr in enumerate(frames):
        people = fr.get("people") or []
        if not people:
            continue
        face = people[0].get("face")
        if not face:
            continue
        for j in range(min(N_FACE, len(face))):
            p = face[j]
            if p is None:
                continue
            arr[i, j] = (float(p[0]), float(p[1]), float(p[2]))
    return arr


# ---------------------------------------------------------------------------
# 归一化：消平移与尺度（不做旋转对齐，以保留头部朝向这类表演信息）
# ---------------------------------------------------------------------------
def normalize_face(arr):
    """逐帧：原点=70点质心、尺度=RMS距质心。返回 (norm (T,70,2), valid (T,70))。"""
    T = arr.shape[0]
    norm = np.zeros((T, N_FACE, 2), dtype=np.float64)
    valid = np.zeros((T, N_FACE), dtype=bool)
    for t in range(T):
        conf = arr[t, :, 2]
        xy = arr[t, :, :2]
        v = (conf > 0) & ~((xy[:, 0] == 0) & (xy[:, 1] == 0))
        valid[t] = v
        if v.sum() < 10:          # 脸点太少，整帧作废
            valid[t] = False
            continue
        c = xy[v].mean(axis=0)
        scale = float(np.sqrt(((xy[v] - c) ** 2).sum(axis=1).mean()))
        if scale < 1e-3:
            valid[t] = False
            continue
        norm[t] = (xy - c) / scale
    return norm, valid


def resample(norm, valid, samples):
    T = norm.shape[0]
    R = np.full((samples, N_FACE, 2), np.nan)
    V = np.zeros((samples, N_FACE), dtype=bool)
    if T < 2:
        return R, V
    t_src = np.linspace(0.0, 1.0, T)
    u = np.linspace(0.0, 1.0, samples)
    for j in range(N_FACE):
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


def _corr(a, b):
    if a.size < 3 or a.std() < 1e-8 or b.std() < 1e-8:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def metrics(A, Av, B, Bv, active_idx=None):
    rs = []
    for j in range(N_FACE):
        m = Av[:, j] & Bv[:, j]
        if m.sum() < 8:
            continue
        for ax in (0, 1):
            rs.append(_corr(A[m, j, ax], B[m, j, ax]))
    traj = float(np.nanmean(rs)) if rs else float("nan")

    idxs = range(N_FACE) if active_idx is None else active_idx
    rs2 = []
    for j in idxs:
        m = Av[:, j] & Bv[:, j]
        if m.sum() < 8:
            continue
        for ax in (0, 1):
            rs2.append(_corr(A[m, j, ax], B[m, j, ax]))
    active = float(np.nanmean(rs2)) if rs2 else float("nan")

    errs = []
    for i in range(A.shape[0]):
        m = Av[i] & Bv[i]
        if m.sum() < 10:
            continue
        errs.append(float(np.mean(np.linalg.norm(A[i, m] - B[i, m], axis=1))))
    err = float(np.mean(errs)) if errs else float("nan")
    return {"face_traj_corr": traj, "active_corr": active, "face_err": err}


def _active_index(R, V):
    """源片中构型方差最大的 K 个点（真正在动的区域：嘴/眼/眉）。"""
    var = np.zeros(N_FACE)
    for j in range(N_FACE):
        m = V[:, j]
        if m.sum() < 8:
            continue
        var[j] = np.nanvar(R[m, j, 0]) + np.nanvar(R[m, j, 1])
    return list(np.argsort(-var)[:_ACTIVE_K])


def evaluate(ref, cand, samples=96):
    An, Av = normalize_face(ref)
    Bn, Bv = normalize_face(cand)
    A, Av = resample(An, Av, samples)
    B, Bv = resample(Bn, Bv, samples)
    act = _active_index(A, Av)
    m_cand = metrics(A, Av, B, Bv, act)
    m_null = metrics(A, Av, np.roll(B, samples // 2, 0), np.roll(Bv, samples // 2, 0), act)
    checks = {}
    for k, (lim, op) in _THRESH.items():
        v = m_cand.get(k)
        checks[k] = bool(np.isfinite(v)) and (v >= lim if op == ">=" else v <= lim)
    return {"cand": m_cand, "null": m_null, "checks": checks,
            "ref_frames": int(ref.shape[0]), "cand_frames": int(cand.shape[0]),
            "ref_faces": int(Av.any(axis=1).sum()), "cand_faces": int(Bv.any(axis=1).sum()),
            "samples": samples}


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------
def _synth_face(T=120, seed=3, noise=0.010, vary=True):
    """合成一张 70 点脸：眼/眉/嘴三组，可控开合。"""
    rng = np.random.default_rng(seed)
    base = np.zeros((N_FACE, 2))
    for i in range(70):
        ang = 2 * np.pi * i / 70.0
        base[i] = (0.9 * np.cos(ang), 0.7 * np.sin(ang))
    out = np.zeros((T, N_FACE, 3), dtype=np.float32)
    t = np.linspace(0, 2 * np.pi, T)
    for i in range(T):
        p = base.copy()
        if vary:
            mouth = 0.40 * (0.5 + 0.5 * np.sin(3.0 * t[i]))     # 说话开合
            p[48:68, 1] *= (1.0 - 0.9 * mouth)                  # 下半圈 = 嘴
            brow = 0.05 * np.sin(5.0 * t[i])
            p[17:27, 1] -= brow                                 # 眉
        p += rng.normal(0, noise, p.shape)
        out[i, :, :2] = p
        out[i, :, 2] = 1.0
    return out


def self_test(samples=96):
    print("=== face_expression_qa 自检（离线合成数据）===")
    ref = _synth_face(seed=3)
    rng = np.random.default_rng(11)
    same = ref + rng.normal(0, 0.010, ref.shape).astype(np.float32)
    flat = np.repeat(ref[:1], ref.shape[0], axis=0) + rng.normal(0, 0.010, ref.shape).astype(np.float32)
    other = _synth_face(seed=99, vary=False)      # 不动的脸
    cases = [("same-face+noise", same, True), ("frozen-face", flat, False),
             ("static-face-vs-moving", other, False)]
    ok_all = True
    for name, cand, expect in cases:
        r = evaluate(ref, cand, samples)
        got = all(r["checks"].values())
        ok = got == expect
        ok_all &= ok
        c = r["cand"]
        print("  [%s] %-22s traj=%6.3f active=%6.3f err=%5.3f -> %s (期望 %s)"
              % ("OK" if ok else "FAIL", name, c["face_traj_corr"], c["active_corr"],
                 c["face_err"], "PASS" if got else "FAIL", "PASS" if expect else "FAIL"))
    print("SELFTEST %s" % ("PASS" if ok_all else "FAIL"))
    return 0 if ok_all else 1


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="表情复刻闸门（face70 构型序列比对）")
    ap.add_argument("--ref-video", required=False)
    ap.add_argument("--cand-video", required=False)
    ap.add_argument("--ref-kp", default=None, help="可选：直接给源 keypoints.json（含 face）")
    ap.add_argument("--ref-window", default=None,
                    help="只取源脸关键点的某个帧窗，格式 START:LEN（产物只覆盖源视频一段时必填，"
                         "LEN 按源帧率换算：产物帧数/产物fps*源fps；否则重采样时间轴对不上）")
    ap.add_argument("--every", type=int, default=1, help="抽帧跨步（默认 1）")
    ap.add_argument("--samples", type=int, default=96)
    ap.add_argument("--json", default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test(args.samples)
    if not (args.cand_video and (args.ref_video or args.ref_kp)):
        raise SystemExit("需要 --cand-video 以及 --ref-video 或 --ref-kp")

    ref = face_from_json(args.ref_kp) if args.ref_kp else face_from_video(args.ref_video, args.every)
    if args.ref_window:
        a, b = args.ref_window.split(":")
        s0, ln = int(a), int(b)
        if s0 < 0 or ln <= 0 or s0 + ln > ref.shape[0]:
            raise SystemExit("ref-window 越界：源脸共 %d 帧" % ref.shape[0])
        ref = ref[s0:s0 + ln]
    print("  源脸帧数=%d" % ref.shape[0], flush=True)
    cand = face_from_video(args.cand_video, args.every)
    print("  产物脸帧数=%d" % cand.shape[0], flush=True)

    r = evaluate(ref, cand, args.samples)
    c, n = r["cand"], r["null"]
    print("\n" + "=" * 66)
    print("表情复刻闸门（源脸 %d 帧 / 产物脸 %d 帧，重采样 %d 桶）"
          % (r["ref_faces"], r["cand_faces"], r["samples"]))
    print("-" * 66)
    print("  %-18s %12s %12s %8s" % ("指标", "机会(错位)", "候选产物", "判定"))
    for k in _THRESH:
        lim, op = _THRESH[k]
        print("  %-18s %12.3f %12.3f %8s" % (k, n.get(k, float("nan")), c.get(k, float("nan")),
                                             "%s %.2f" % (op, lim)))
    print("-" * 66)
    passed = all(r["checks"].values())
    print("  判定：%s" % ("PASS 表情构型同步（嘴/眼/眉随源演化）" if passed
                        else "FAIL 表情未跟随"))
    print("=" * 66)
    if args.json:
        json.dump({"result": r, "passed": passed}, open(args.json, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2, default=str)
        print("  已写入: %s" % args.json)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
