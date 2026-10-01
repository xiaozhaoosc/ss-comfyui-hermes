#!/usr/bin/env python3
"""H3 4-step turbo 快线（i2v 9:16 竖屏）独立提交器

把已验证的 4 步快线（UNET fused refdelta turbo8 + ChunkFFN + SLA 0.9/64 +
SigmaShift 12/3 + res_multistep/simple/4）从 UI 工作流转成 API 工作流后提交。

用法:
  # 干跑（只校验，不提交）
  python tools/h3_fast_submit.py --dry-run --prompt-file p.txt \
      --first-frame "Gemini_Generated_Image_8tttsy8tttsy8ttt (1).jpg"

  # 真提交
  python tools/h3_fast_submit.py --prompt-file p.txt \
      --first-frame "xxx.jpg" --width 736 --height 1088 --length 124 --seed 20260906

仅依赖标准库 + venv 内已装的 av/numpy（验收用）。
"""
import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8188"
ROOT = r"D:\ai_projects\ComfyUI"
INPUT_ROOT = os.path.join(ROOT, "input")
OUTPUT_ROOT = os.path.join(ROOT, "output")
DEFAULT_WORKFLOW = os.path.join(ROOT, "workflows", "v5", "h3_fast_i2v_9x16_api.json")
FFMPEG_ABS = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"

SLA_NODES = ["H3SLAAttention", "MiniMaxChunkFeedForward", "MiniMaxH3SigmaShift",
             "MiniMaxH3ImageToVideo"]
SLA_PKGS = ["comfy-kitchen", "triton-windows"]
FP16_VIDEO_VAE = "minimax_h3_video_vae_fp16"

SAMPLE_PROMPT = (
    "The camera slowly pushes in as the young woman turns her head toward the lens "
    "with a soft smile, subtle hair movement, gentle breathing; ambient room tone, "
    "light upbeat instrumental music."
)


# ----------------------------- HTTP -----------------------------

def _get_json(path, timeout=30):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=timeout) as r:
        return json.loads(r.read())


def _post_json(path, payload, timeout=60):
    req = urllib.request.Request(
        f"{BASE}{path}", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code} on POST {path}: {body[:1000]}")


_INFO_CACHE = {}


def object_info(class_type):
    if class_type not in _INFO_CACHE:
        try:
            data = _get_json(f"/object_info/{class_type}")
        except Exception as e:
            _INFO_CACHE[class_type] = None
            return None
        _INFO_CACHE[class_type] = data.get(class_type)
    return _INFO_CACHE[class_type]


# ----------------------------- 预检 -----------------------------

def align_length(n):
    n = max(5, int(n))
    if n % 17 != 5:
        n = n + ((5 - n % 17) % 17)
    return n


def _powershell_exe():
    p = shutil.which("powershell") or shutil.which("powershell.exe")
    if p:
        return p
    cand = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                        "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    return cand if os.path.exists(cand) else "powershell"


def check_single_instance():
    ps = (
        "$pids = @(Get-NetTCPConnection -LocalPort 8188 -State Listen "
        "-ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique);"
        'Write-Output ("COUNT=" + $pids.Count);'
        "foreach ($p in $pids) {"
        '  $cl = (Get-CimInstance Win32_Process -Filter "ProcessId=$p" '
        "-ErrorAction SilentlyContinue).CommandLine;"
        '  Write-Output ("PID=" + $p + " CMD=" + $cl) }'
    )
    try:
        r = subprocess.run([_powershell_exe(), "-NoProfile", "-NonInteractive",
                            "-Command", ps],
                           capture_output=True, text=True, timeout=60)
    except Exception as e:
        return False, f"无法执行 powershell 查询端口: {e}"
    out = r.stdout or ""
    count = None
    pids = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("COUNT="):
            try:
                count = int(line.split("=", 1)[1])
            except ValueError:
                pass
        elif line.startswith("PID="):
            pids.append(line)
    if count is None:
        return False, f"端口 8188 查询无结果（ComfyUI 未运行？）\n{out[-400:]}"
    if count == 0:
        return False, "端口 8188 无监听进程（ComfyUI 未运行）"
    if count != 1:
        return False, f"端口 8188 有 {count} 个监听进程（疑似双实例）"
    if "main.py" not in pids[0]:
        return False, f"端口 8188 持有者命令行不含 main.py: {pids[0]}"
    return True, f"单实例 OK（{pids[0]}）"


def check_sla_deps():
    import importlib.metadata as md
    missing = []
    for pkg in SLA_PKGS:
        try:
            v = md.version(pkg)
        except Exception:
            missing.append(pkg)
            continue
        if not v:
            missing.append(pkg)
    if missing:
        return False, f"缺少 pip 包: {', '.join(missing)}"
    missing_nodes = [n for n in SLA_NODES if object_info(n) is None]
    if missing_nodes:
        return False, f"/object_info 缺少节点: {', '.join(missing_nodes)}"
    return True, f"依赖 OK（comfy-kitchen/triton-windows + {len(SLA_NODES)} 个 SLA 节点）"


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def check_memory(min_gb=8.0):
    st = _MEMORYSTATUSEX()
    st.dwLength = ctypes.sizeof(st)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
        return False, "GlobalMemoryStatusEx 调用失败"
    avail_gb = st.ullAvailPhys / (1024 ** 3)
    ok = avail_gb >= min_gb
    msg = f"可用物理内存 {avail_gb:.1f} GB（阈值 {min_gb:.0f} GB）"
    return ok, msg


def check_video_vae(wf):
    found = []
    for nid, node in wf.items():
        if node.get("class_type") == "VAELoader":
            v = node.get("inputs", {}).get("vae_name", "")
            if isinstance(v, str):
                found.append(v)
    if not any(FP16_VIDEO_VAE in v for v in found):
        return False, f"未找到 fp16 视频 VAE（当前 VAELoader 取值: {found}）"
    return True, f"视频 VAE = {[v for v in found if FP16_VIDEO_VAE in v][0]}"


# ----------------------------- 注入 -----------------------------

def inject_placeholders(wf, values):
    """把 [inject:key] 字符串占位替换为各自类型的真实值。"""

    def walk(o):
        if isinstance(o, str):
            if o.startswith("[inject:") and o.endswith("]"):
                key = o[len("[inject:"):-1]
                if key not in values:
                    raise KeyError(f"未知占位符 {o}")
                return values[key]
            return o
        if isinstance(o, list):
            return [walk(x) for x in o]
        if isinstance(o, dict):
            return {k: walk(v) for k, v in o.items()}
        return o

    return walk(wf)


# ----------------------------- 校验 -----------------------------

def _enum_options(spec):
    if isinstance(spec, dict):
        v = spec.get("value")
        return v if isinstance(v, list) else None
    if isinstance(spec, list) and spec:
        head = spec[0]
        if isinstance(head, list):
            return head
        if isinstance(head, dict):
            if isinstance(head.get("value"), list):
                return head["value"]
            opts = head.get("options")
            if isinstance(opts, list):
                if opts and isinstance(opts[0], dict) and "key" in opts[0]:
                    return [o["key"] for o in opts]
                return opts
    return None


def _numeric_bounds(spec):
    if (isinstance(spec, list) and len(spec) >= 2 and isinstance(spec[0], str)
            and spec[0] in ("INT", "FLOAT") and isinstance(spec[1], dict)):
        return spec[0], spec[1].get("min"), spec[1].get("max")
    return None


def validate_workflow(wf):
    """逐节点用 /object_info 校验。返回 (errors, lines)。"""
    errors = []
    lines = []
    for nid in sorted(wf.keys(), key=lambda x: (len(str(x)), str(x))):
        node = wf[nid]
        ct = node.get("class_type")
        inputs = node.get("inputs", {}) or {}
        info = object_info(ct)
        if info is None:
            errors.append(f"[{nid}] class_type 不存在: {ct}")
            lines.append(f"  x [{nid}] {ct}: 节点不存在")
            continue
        required = (info.get("input", {}) or {}).get("required", {}) or {}
        node_msgs = []
        for name, spec in required.items():
            if name not in inputs:
                errors.append(f"[{nid}] {ct}: 缺少必填输入 {name}")
                node_msgs.append(f"缺少必填 {name}")
                continue
            val = inputs[name]
            if isinstance(val, list):
                continue  # link
            opts = _enum_options(spec)
            if opts is not None and val not in opts:
                errors.append(f"[{nid}] {ct}.{name}={val!r} 不在合法枚举内")
                node_msgs.append(f"{name}={val!r} 非法枚举")
                continue
            nb = _numeric_bounds(spec)
            if nb and isinstance(val, (int, float)) and not isinstance(val, bool):
                _, lo, hi = nb
                if lo is not None and val < lo or hi is not None and val > hi:
                    errors.append(f"[{nid}] {ct}.{name}={val} 超出范围 [{lo},{hi}]")
                    node_msgs.append(f"{name}={val} 越界")
                    continue
            opts_lbl = "枚举内" if opts is not None else "ok"
            node_msgs.append(f"{name}={val!r}({opts_lbl})")
        tag = "OK" if not node_msgs or all("ok" in m or "枚举内" in m for m in node_msgs) else "FAIL"
        lines.append(f"  [{tag}] {nid} {ct}: " + "; ".join(node_msgs))
    return errors, lines


# ----------------------------- 提交 / 等待 -----------------------------

def wait_done(pid, timeout=7200, poll=30):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            h = _get_json(f"/history/{pid}", timeout=20)
        except Exception as e:
            print(f"  查询 history 异常: {e}")
            time.sleep(poll)
            continue
        rec = h.get(pid)
        if rec:
            st = rec.get("status", {}) or {}
            if st.get("status_str") == "error" or "exec_err" in st:
                print("  执行出错:", json.dumps(st, ensure_ascii=False)[:800])
                return None
            if st.get("completed") or rec.get("outputs"):
                return rec
        time.sleep(poll)
    print("  等待超时")
    return None


def exec_seconds(status):
    t0 = t1 = None
    for m in (status or {}).get("messages", []) or []:
        if not isinstance(m, list) or len(m) < 2 or not isinstance(m[1], dict):
            continue
        ev, data = m[0], m[1]
        ts = data.get("timestamp")
        if ts is None:
            continue
        if ev == "execution_start":
            t0 = ts
        elif ev == "execution_success":
            t1 = ts
    if t0 is not None and t1 is not None and t1 >= t0:
        return (t1 - t0) / 1000.0
    return None


def find_output_files(rec):
    """从 outputs 里定位成片（键可能是 images/videos/gif 等）。"""
    cands = []
    for _nid, out in (rec.get("outputs") or {}).items():
        if not isinstance(out, dict):
            continue
        for _key, val in out.items():
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict) and item.get("filename"):
                        cands.append(item)
    resolved = []
    for it in cands:
        p = os.path.join(OUTPUT_ROOT, it.get("subfolder", "") or "", it["filename"])
        if os.path.exists(p):
            resolved.append(p)
    if not resolved and cands:
        # 文件可能尚未 flush，用拼接路径兜底
        it = cands[-1]
        resolved.append(os.path.join(OUTPUT_ROOT, it.get("subfolder", "") or "", it["filename"]))
    return resolved


# ----------------------------- 验收 -----------------------------

def resolve_ffmpeg():
    if os.path.exists(FFMPEG_ABS):
        return FFMPEG_ABS
    return shutil.which("ffmpeg")


def mean_brightness(png):
    try:
        import av
        import numpy as np
        with av.open(png) as c:
            for frame in c.decode(video=0):
                return float(frame.to_ndarray(format="rgb24").mean())
    except Exception:
        pass
    try:
        from PIL import Image
        import numpy as np
        return float(np.asarray(Image.open(png).convert("RGB")).mean())
    except Exception:
        return None


def acceptance(mp4, n_frames, fps, threshold=3.0):
    ff = resolve_ffmpeg()
    if not ff:
        print("  ! 未找到 ffmpeg，跳过抽帧验收")
        return None
    print(f"  抽帧用 ffmpeg: {ff}")
    dur = n_frames / float(fps)
    picks = [("首帧", 0.0), ("中帧", dur / 2.0), ("尾帧", max(0.0, dur - 1.0 / fps))]
    tmp = tempfile.mkdtemp(prefix="h3_fast_verify_")
    means = []
    for label, t in picks:
        out = os.path.join(tmp, f"{label}.png")
        r = subprocess.run([ff, "-y", "-ss", f"{t:.3f}", "-i", mp4,
                            "-frames:v", "1", out], capture_output=True)
        if r.returncode != 0 or not os.path.exists(out):
            print(f"  ! {label} 抽帧失败（t={t:.2f}s）")
            continue
        b = mean_brightness(out)
        if b is None:
            print(f"  ! {label} 亮度无法计算（缺 av/PIL）")
            continue
        means.append(b)
        print(f"  {label} t={t:.2f}s 平均亮度 = {b:.2f}")
    if not means:
        print("  ! 无法完成亮度验收")
        return None
    avg = sum(means) / len(means)
    ok = avg > threshold
    print(f"  三帧平均亮度 = {avg:.2f}（阈值 >{threshold}） -> {'通过' if ok else '未通过'}")
    shutil.rmtree(tmp, ignore_errors=True)
    return ok


# ----------------------------- main -----------------------------

def main():
    ap = argparse.ArgumentParser(description="H3 4-step turbo 快线 i2v 提交器")
    ap.add_argument("--workflow", default=DEFAULT_WORKFLOW, help="API 格式工作流 JSON")
    ap.add_argument("--prompt-file", help="提示词文本文件")
    ap.add_argument("--first-frame", help="input 目录下相对路径（如 xxx.jpg）")
    ap.add_argument("--width", type=int, default=736)
    ap.add_argument("--height", type=int, default=1088)
    ap.add_argument("--length", type=int, default=124)
    ap.add_argument("--seed", type=int, default=20260906)
    ap.add_argument("--prefix", default="2026-10-01/xinniang_cosplay_v1/fastseg")
    ap.add_argument("--dry-run", action="store_true", help="只校验不提交")
    ap.add_argument("--no-wait", action="store_true", help="提交后不等待")
    args = ap.parse_args()

    # 1. 帧长/尺寸对齐
    raw_len = args.length
    args.length = align_length(raw_len)
    if args.length != raw_len:
        print(f"[对齐] length {raw_len} -> {args.length}（向上取整到 17k+5）")
    else:
        print(f"[对齐] length {args.length} 已是 17k+5")
    for nm, v in (("width", args.width), ("height", args.height)):
        if v % 32 != 0:
            print(f"[警告] {nm}={v} 不是 32 的倍数，模型会自行吸附，建议改 32 倍数")

    # 2. 读取输入
    if not os.path.exists(args.workflow):
        print(f"[失败] 工作流不存在: {args.workflow}")
        return 1
    with open(args.workflow, "r", encoding="utf-8") as f:
        wf = json.load(f)

    if args.prompt_file:
        if not os.path.exists(args.prompt_file):
            print(f"[失败] 提示词文件不存在: {args.prompt_file}")
            return 1
        with open(args.prompt_file, "r", encoding="utf-8-sig") as f:
            prompt = f.read().strip()
    else:
        if not args.dry_run:
            print("[失败] 真提交必须提供 --prompt-file")
            return 1
        prompt = SAMPLE_PROMPT
        print("[提示] 未提供 --prompt-file，dry-run 使用内置示例提示词")

    first_frame = args.first_frame
    if not first_frame:
        if not args.dry_run:
            print("[失败] 真提交必须提供 --first-frame")
            return 1
        first_frame = "first_frame.png"
        print("[提示] 未提供 --first-frame，dry-run 使用示例 first_frame.png")
    if not os.path.exists(os.path.join(INPUT_ROOT, first_frame)):
        print(f"[警告] input 目录下未找到首帧文件: {first_frame}")

    # 3. 注入
    values = {
        "first_frame": first_frame,
        "prompt": prompt,
        "width": args.width,
        "height": args.height,
        "length": args.length,
        "seed": args.seed,
        "filename_prefix": args.prefix,
    }
    try:
        wf = inject_placeholders(wf, values)
    except KeyError as e:
        print(f"[失败] 注入失败: {e}")
        return 1

    # 4. 预检
    print("\n=== 预检 ===")
    checks = [
        ("单实例", check_single_instance),
        ("SLA 依赖", check_sla_deps),
        ("可用内存", check_memory),
        ("视频 VAE fp16", lambda: check_video_vae(wf)),
    ]
    # 可用内存随 ComfyUI 正在跑的任务波动；dry-run 只做校验不占显存/内存，
    # 故 dry-run 下内存不足仅告警，真提交时仍为硬门槛。
    soft = {"可用内存"} if args.dry_run else set()
    failed = False
    for name, fn in checks:
        ok, msg = fn()
        if ok:
            tag = "通过"
        elif name in soft:
            tag = "警告"
            print(f"  [警告] {name}: {msg} —— dry-run 不拦截，真提交时会硬失败")
            continue
        else:
            tag = "失败"
            failed = True
        print(f"  [{tag}] {name}: {msg}")
    if failed:
        print("\n[失败] 预检未通过，终止。")
        return 1

    # 5. dry-run 校验
    if args.dry_run:
        print("\n=== dry-run 逐节点校验（不会 POST /prompt）===")
        print(f"  注入: width={args.width} height={args.height} length={args.length} "
              f"seed={args.seed}")
        print(f"  prompt[:60]={prompt[:60]!r}  first_frame={first_frame!r}")
        print(f"  prefix={args.prefix!r}")
        errors, lines = validate_workflow(wf)
        for ln in lines:
            print(ln)
        if errors:
            print(f"\n[失败] 校验发现 {len(errors)} 个问题:")
            for e in errors:
                print("  - " + e)
            return 1
        print("\n[通过] 全部校验通过（dry-run 结束，未提交）")
        return 0

    # 6. 提交
    print("\n=== 提交 ===")
    payload = {"prompt": wf, "client_id": str(uuid.uuid4())}
    t_submit = time.time()
    try:
        r = _post_json("/prompt", payload)
    except Exception as e:
        print(f"[失败] 提交异常: {e}")
        return 1
    pid = r.get("prompt_id")
    node_errors = r.get("node_errors") or {}
    if node_errors:
        print(f"[失败] node_errors 非空:")
        print(json.dumps(node_errors, ensure_ascii=False)[:2000])
        return 1
    print(f"  已提交 pid={pid}")

    if args.no_wait:
        print("  --no-wait：不等待，退出。")
        return 0

    # 7. 等待
    print("\n=== 等待完成（每 30s 轮询）===")
    rec = wait_done(pid)
    if not rec:
        print("[失败] 未正常完成")
        return 1
    total = time.time() - t_submit
    secs = exec_seconds(rec.get("status", {}))
    files = find_output_files(rec)
    print("\n=== 结果 ===")
    print(f"  prompt_id: {pid}")
    print(f"  提交->落盘总耗时: {total:.1f}s")
    if secs is not None:
        print(f"  执行耗时(execution_start->success): {secs:.1f}s")
    else:
        print("  执行耗时: 无法从 status.messages 解析")
    if not files:
        print("[失败] outputs 中未定位到成片文件")
        return 1
    mp4 = files[-1]
    print(f"  成片: {mp4}（存在={os.path.exists(mp4)}）")

    # 8. 验收
    print("\n=== 验收（抽首/中/尾帧算亮度）===")
    ok = acceptance(mp4, args.length, 24.0)
    if ok is None:
        print("[警告] 验收未能完成（工具缺失），请人工复核")
        return 0
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mai