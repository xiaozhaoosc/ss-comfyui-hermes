#!/usr/bin/env python3
"""H3 快线成片后期增强（RIFE 补帧 + RealESRGAN 超分）独立提交器

链路:
  LoadVideo -> GetVideoComponents ->(IMAGE) RIFEInterpolation ->
  ImageUpscaleWithModel -> ImageScale ->(AUDIO 直连) CreateVideo -> SaveVideo

把源 mp4 复制进 input 目录（LoadVideo 的 file 是 COMBO，只枚举 input 根目录），
轮询 /object_info 直到新文件出现在枚举里再提交。

用法:
  python tools/h3_enhance_submit.py --source <低清源 mp4>
  python tools/h3_enhance_submit.py --source <mp4> --dry-run
  可选: --target-fps 48 --out-width 1080 --out-height 1920 --rife-batch-size 4
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import h3_fast_submit as base  # 复用 HTTP/预检/校验/等待/验收工具函数

ROOT = base.ROOT
INPUT_ROOT = base.INPUT_ROOT
OUTPUT_ROOT = base.OUTPUT_ROOT
DEFAULT_WORKFLOW = os.path.join(ROOT, "workflows", "v5", "h3_enhance_v5_api.json")
FFPROBE_ABS = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffprobe.exe"

REQUIRED_NODES = ["LoadVideo", "GetVideoComponents", "RIFEInterpolation",
                  "UpscaleModelLoader", "ImageUpscaleWithModel", "ImageScale",
                  "CreateVideo", "SaveVideo"]
UPSCALE_MODEL = "RealESRGAN_x4plus.pth"
RIFE_MODEL = "flownet.pkl"
# 增强只载入小模型（RIFE + ESRGAN），RAM 门槛比快线的 8GB 宽松
MIN_FREE_RAM_GB = 6.0


# ----------------------------- 预检 -----------------------------

def check_queue_idle():
    try:
        q = base._get_json("/queue", timeout=20)
    except Exception as e:
        return False, f"查询 /queue 失败: {e}"
    run = len(q.get("queue_running") or [])
    pend = len(q.get("queue_pending") or [])
    return (run == 0 and pend == 0), f"/queue running={run} pending={pend}"


def check_nodes_and_models():
    missing = [n for n in REQUIRED_NODES if base.object_info(n) is None]
    if missing:
        return False, f"/object_info 缺少节点: {', '.join(missing)}"
    up = base.object_info("UpscaleModelLoader")
    opts = base._enum_options(up["input"]["required"]["model_name"])
    if not opts or UPSCALE_MODEL not in opts:
        return False, f"缺少超分模型 {UPSCALE_MODEL}（本机可选: {opts}）"
    rife = base.object_info("RIFEInterpolation")
    ropts = base._enum_options(rife["input"].get("optional", {}).get("model_name"))
    if not ropts or RIFE_MODEL not in ropts:
        return False, f"缺少 RIFE 模型 {RIFE_MODEL}（本机可选: {ropts}）"
    return True, f"节点齐全 + 模型存在（{UPSCALE_MODEL} / {RIFE_MODEL}）"


# ----------------------------- 输入准备 -----------------------------

def copy_source(src):
    """把源 mp4 复制进 input 目录，返回 (input 下文件名, 目标绝对路径)。"""
    stamp = time.strftime("%Y%m%d_%H%M%S")
    name = f"h3_enh_src_{stamp}.mp4"
    dst = os.path.join(INPUT_ROOT, name)
    if os.path.exists(dst):
        name = f"h3_enh_src_{stamp}_{uuid.uuid4().hex[:6]}.mp4"
        dst = os.path.join(INPUT_ROOT, name)
    shutil.copy2(src, dst)
    return name, dst


def wait_for_enum(fname, timeout=60, poll=3):
    """轮询 /object_info/LoadVideo 直到 file 枚举包含 fname。"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            data = base._get_json("/object_info/LoadVideo", timeout=20)
            spec = data["LoadVideo"]["input"]["required"]["file"]
            opts = base._enum_options(spec)
            if opts and fname in opts:
                return True
        except Exception:
            pass
        time.sleep(poll)
    return False


# ----------------------------- 验收 -----------------------------

def resolve_ffprobe():
    if os.path.exists(FFPROBE_ABS):
        return FFPROBE_ABS
    return shutil.which("ffprobe")


def probe(path):
    ff = resolve_ffprobe()
    if not ff:
        return {}
    r = subprocess.run(
        [ff, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate,nb_frames",
         "-show_entries", "format=duration", "-of", "json", path],
        capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {}


def _rate(s):
    try:
        if "/" in str(s):
            a, b = str(s).split("/")
            return float(a) / float(b)
        return float(s)
    except Exception:
        return None


def verify(mp4, src_probe, out_w, out_h, target_fps, tol=0.2):
    p = probe(mp4)
    st = (p.get("streams") or [{}])[0]
    w, h = st.get("width"), st.get("height")
    fps = _rate(st.get("r_frame_rate"))
    dur = float((p.get("format") or {}).get("duration") or 0)
    src_dur = float((src_probe.get("format") or {}).get("duration") or 0)
    nb = st.get("nb_frames")
    n_frames = int(nb) if nb and str(nb).isdigit() else int(round(dur * (fps or 1)))
    bad = []
    if w != out_w or h != out_h:
        bad.append(f"分辨率 {w}x{h} != {out_w}x{out_h}")
    if fps is None or abs(fps - target_fps) > 0.05:
        bad.append(f"帧率 {fps} != {target_fps}")
    if src_dur and abs(dur - src_dur) > tol:
        bad.append(f"时长 {dur:.3f}s 与源 {src_dur:.3f}s 差 {abs(dur-src_dur):.3f}s > {tol}s")
    print(f"  规格: {w}x{h} @ {fps}fps, {n_frames} 帧, {dur:.3f}s（源 {src_dur:.3f}s）")
    return (not bad), bad, n_frames, (fps or target_fps)


# ----------------------------- main -----------------------------

def main():
    ap = argparse.ArgumentParser(description="H3 快线成片后期增强提交器")
    ap.add_argument("--workflow", default=DEFAULT_WORKFLOW)
    ap.add_argument("--source", required=True, help="源 mp4 路径（必需）")
    ap.add_argument("--prefix", default="2026-10-01/xinniang_cosplay_v1/fast_hd")
    ap.add_argument("--target-fps", type=float, default=48.0)
    ap.add_argument("--out-width", type=int, default=1080)
    ap.add_argument("--out-height", type=int, default=1920)
    ap.add_argument("--rife-batch-size", type=int, default=4,
                    help="RIFE 并行帧数，OOM 时可降到 2")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-wait", action="store_true")
    args = ap.parse_args()

    if not os.path.isfile(args.source):
        print(f"[失败] 源文件不存在: {args.source}")
        return 1
    if not os.path.exists(args.workflow):
        print(f"[失败] 工作流不存在: {args.workflow}")
        return 1
    with open(args.workflow, "r", encoding="utf-8") as f:
        wf = json.load(f)

    src_probe = probe(args.source)
    print(f"源: {args.source}")
    src_st = (src_probe.get("streams") or [{}])[0]
    print(f"     {src_st.get('width')}x{src_st.get('height')} @ "
          f"{_rate(src_st.get('r_frame_rate'))}fps, "
          f"{(src_probe.get('format') or {}).get('duration')}s")

    # 预检
    print("\n=== 预检 ===")
    checks = [
        ("队列空闲", check_queue_idle),
        ("单实例", base.check_single_instance),
        ("可用内存", lambda: base.check_memory(MIN_FREE_RAM_GB)),
        ("节点/模型", check_nodes_and_models),
    ]
    # dry-run 只做校验、不提交也不占 GPU/显存，故队列与内存不足仅告警
    soft = {"可用内存", "队列空闲"} if args.dry_run else set()
    failed = False
    for name, fn in checks:
        ok, msg = fn()
        if ok:
            print(f"  [通过] {name}: {msg}")
        elif name in soft:
            print(f"  [警告] {name}: {msg} —— dry-run 不拦截，真提交时会硬失败")
        else:
            print(f"  [失败] {name}: {msg}")
            failed = True
    if failed:
        print("\n[失败] 预检未通过，终止。")
        return 1

    # 复制源到 input + 等枚举
    fname, dst = copy_source(args.source)
    print(f"\n[输入] 已复制到 input: {fname}")
    if not wait_for_enum(fname):
        print(f"[失败] 60s 内 LoadVideo 枚举未出现 {fname}")
        return 1
    print(f"[输入] LoadVideo 枚举已包含 {fname}")
    base._INFO_CACHE.pop("LoadVideo", None)  # 清缓存，让校验重新拉取新枚举

    # 注入
    values = {
        "source_file": fname,
        "prefix": args.prefix,
        "target_fps": float(args.target_fps),
        "out_width": args.out_width,
        "out_height": args.out_height,
    }
    try:
        wf = base.inject_placeholders(wf, values)
    except KeyError as e:
        print(f"[失败] 注入失败: {e}")
        return 1
    wf["3"]["inputs"]["batch_size"] = args.rife_batch_size

    if args.dry_run:
        print("\n=== dry-run 逐节点校验（不会 POST /prompt）===")
        print(f"  注入: source_file={fname!r} target_fps={args.target_fps} "
              f"out={args.out_width}x{args.out_height} prefix={args.prefix!r} "
              f"rife_batch={args.rife_batch_size}")
        errors, lines = base.validate_workflow(wf)
        for ln in lines:
            print(ln)
        if errors:
            print(f"\n[失败] 校验发现 {len(errors)} 个问题:")
            for e in errors:
                print("  - " + e)
            return 1
        try:
            os.remove(dst)  # dry-run 不留下 input 副本
            print(f"[清理] 已删除 dry-run 临时输入 {fname}")
        except OSError:
            pass
        print("\n[通过] 全部校验通过（dry-run 结束，未提交）")
        return 0

    # 提交
    print("\n=== 提交 ===")
    t_submit = time.time()
    try:
        r = base._post_json("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
    except Exception as e:
        print(f"[失败] 提交异常: {e}")
        return 1
    pid = r.get("prompt_id")
    node_errors = r.get("node_errors") or {}
    if node_errors:
        print("[失败] node_errors 非空:")
        print(json.dumps(node_errors, ensure_ascii=False)[:2000])
        return 1
    print(f"  已提交 pid={pid}")

    if args.no_wait:
        print("  --no-wait：不等待，退出。")
        return 0

    # 等待
    print("\n=== 等待完成（每 30s 轮询）===")
    rec = base.wait_done(pid)
    if not rec:
        print("[失败] 未正常完成")
        return 1
    total = time.time() - t_submit
    secs = base.exec_seconds(rec.get("status", {}))
    files = base.find_output_files(rec)
    print("\n=== 结果 ===")
    print(f"  prompt_id: {pid}")
    print(f"  提交->落盘总耗时: {total:.1f}s")
    if secs is not None:
        print(f"  执行耗时(execution_start->success): {secs:.1f}s")
    if not files:
        print("[失败] outputs 中未定位到成片文件")
        return 1
    mp4 = files[-1]
    print(f"  成片: {mp4}（存在={os.path.exists(mp4)}）")

    # 验收：规格 + 亮度
    print("\n=== 验收 ===")
    ok, bad, n_frames, fps = verify(mp4, src_probe, args.out_width, args.out_height,
                                    args.target_fps)
    if not ok:
        print("  [失败] 规格不符:")
        for b in bad:
            print("    - " + b)
        return 1
    print("  [通过] 规格符合")
    bright = base.acceptance(mp4, n_frames, fps)
    if bright is None:
        print("[警告] 亮度验收未能完成（工具缺失），请人工复核")
        return 0
    return 0 if bright else 1


if __name__ == "__main__":
    sys.exit(main())