#!/usr/bin/env python3
"""50写真 6批×50张 后台编排器：等 idle → 提交下一批 → ... → 全部完成

batch 1 由 cron 触发轮直接提交；本脚本从 batch 2 开始。
防重复：提交前检查 output 目录是否已有该批次输出子目录。
日志写到 tools/batch_run.log，最终状态写 tools/batch_run_status.json。
"""
import json, urllib.request, subprocess, sys, os, time

COMFY = "http://127.0.0.1:8188"
COMFY_DIR = r"D:\ai_projects\ComfyUI"
OUTPUT_DIR = os.path.join(COMFY_DIR, "output")
LOG_PATH = os.path.join(COMFY_DIR, "tools", "batch_run.log")
STATUS_PATH = os.path.join(COMFY_DIR, "tools", "batch_run_status.json")

BATCH_FOLDERS = {
    1: "50xiezhen_batch01_泳装_basic",
    2: "50xiezhen_batch02_睡裙_basic",
    3: "50xiezhen_batch03_内衣秀_basic",
    4: "50xiezhen_batch04_泳装_skill",
    5: "50xiezhen_batch05_睡裙_skill",
    6: "50xiezhen_batch06_内衣秀_skill",
}

CRON_JOB_ID = "a03fc445e512"
REPORT_PATH = r"D:\obsidian\obsidian\ComfyUI\50写真批次prompts\BATCH_RUN_REPORT.md"
HERMES = r"C:\Users\kenzhao\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe"

def log(msg):
    line = time.strftime("%H:%M:%S") + " " + msg
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def queue_len():
    try:
        with urllib.request.urlopen(f"{COMFY}/queue", timeout=10) as r:
            q = json.load(r)
        return len(q.get("queue_running", [])), len(q.get("queue_pending", []))
    except Exception as e:
        log(f"queue check error: {e}")
        return -1, -1

def wait_idle(timeout_min=100, label=""):
    deadline = time.time() + timeout_min * 60
    last_state = None
    while time.time() < deadline:
        r, p = queue_len()
        state = (r, p)
        if state != last_state:
            log(f"  [{label}] queue running={r} pending={p}")
            last_state = state
        if r == 0 and p == 0:
            return True
        time.sleep(30)
    return False

def batch_done(bid):
    folder = BATCH_FOLDERS.get(bid)
    if not folder:
        return False
    d = os.path.join(OUTPUT_DIR, folder)
    if not os.path.isdir(d):
        return False
    pngs = [f for f in os.listdir(d) if f.lower().endswith(".png")]
    return len(pngs) >= 50

def submit(bid):
    r = subprocess.run(
        [sys.executable, "tools/submit_batches_50xiezhen.py", str(bid)],
        cwd=COMFY_DIR, capture_output=True, text=True, timeout=300)
    tail = (r.stdout or "")[-1500:] + (r.stderr or "")[-1500:]
    return r.returncode == 0, tail

def main():
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    log("=== orchestrator start ===")
    results = {}
    # batch 1 由 cron 触发轮提交，先等它跑完
    if not wait_idle(110, "wait batch1"):
        results["batch1_wait"] = "TIMEOUT"
        log("ERROR: batch 1 等待超时，退出")
        write_status(results)
        sys.exit(2)

    for bid in range(2, 7):
        if batch_done(bid):
            log(f"batch {bid}: 输出已存在(≥50 PNG)，跳过防重复")
            results[f"batch{bid}"] = "SKIP(done)"
            continue
        ok, tail = submit(bid)
        if not ok:
            log(f"ERROR batch {bid} 提交失败: {tail}")
            results[f"batch{bid}"] = f"SUBMIT_FAIL: {tail}"
            continue  # 任务要求：记录错误继续跑下一批
        log(f"batch {bid}: 提交成功，等跑完")
        results[f"batch{bid}"] = "submitted"
        if bid < 6:
            if not wait_idle(110, f"wait batch{bid}"):
                log(f"ERROR: batch {bid} 等待超时，继续下一批")
                results[f"batch{bid}_wait"] = "TIMEOUT"

    # 最终等全部跑完（剩余 3 批约 2.3h，给 200 分钟上限）
    final = wait_idle(200, "final wait")
    results["final_idle"] = "OK" if final else "TIMEOUT"
    log("=== orchestrator done, final_idle=" + ("OK" if final else "TIMEOUT") + " ===")
    write_status(results)

    # ---- 收尾阶段：统计输出、写报告、pause cron ----
    finish = finalize()
    results["finish"] = finish
    write_status(results)
    log("=== finalize: " + str(finish) + " ===")

def finalize():
    """统计各批产物、写报告、暂停本 cron。返回结果 dict。"""
    out = {}
    rows = []
    total_png = 0
    total_bytes = 0
    for bid in range(1, 7):
        folder = BATCH_FOLDERS[bid]
        d = os.path.join(OUTPUT_DIR, folder)
        pngs, size = [], 0
        latest = 0
        if os.path.isdir(d):
            for f in os.listdir(d):
                fp = os.path.join(d, f)
                if f.lower().endswith(".png") and os.path.isfile(fp):
                    st = os.stat(fp)
                    pngs.append(f)
                    size += st.st_size
                    latest = max(latest, st.st_mtime)
        n = len(pngs)
        total_png += n
        total_bytes += size
        done_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(latest)) if latest else "-"
        avg = size / n / 1024 if n else 0
        rows.append((bid, folder, n, size / 1024 / 1024, avg, done_at))
        out[f"batch{bid}"] = {"png_count": n, "size_mb": round(size / 1024 / 1024, 1),
                              "avg_kb": round(avg, 0), "done_at": done_at}

    lines = [
        "# BATCH_RUN_REPORT — 50 写真 6 批 × 50 张",
        "",
        f"- 报告生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 批次来源：`tools/submit_batches_50xiezhen.py`（8 步 euler_simple, 768×1280, T8-flux.1-dev-abliterated-V2-GGUF-Q4_K_M）",
        f"- 总计：{total_png} PNG / {total_bytes / 1024 / 1024:.0f} MB",
        "",
        "| 批次 | 目录 | PNG 数 | 总大小(MB) | 单张均值(KB) | 完成时间 |",
        "|---|---|---|---|---|---|",
    ]
    for bid, folder, n, mb, avg, done_at in rows:
        ok = "✅" if n >= 50 else "❌"
        lines.append(f"| {bid:02d} | {folder} | {n} {ok} | {mb:.1f} | {avg:.0f} | {done_at} |")
    lines.append("")
    fails = [f"batch{bid:02d}({n}张)" for bid, folder, n, mb, avg, done_at in rows if n < 50]
    if fails:
        lines.append(f"## ⚠️ 失败/缺失批次：{', '.join(fails)}")
    else:
        lines.append("## ✅ 全部 6 批 × 50 张 = 300 张 完成，无失败")
    lines.append("")
    lines.append("## 备注")
    lines.append("- batch01 提交时发现脚本 bug（batch_id 字符串未转 int 导致 'batch not configured'），已修复为 `int(a)` 后重提。")
    lines.append("- 批次间按序执行：等上一批队列 idle 再提下一批。")

    try:
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        out["report_written"] = REPORT_PATH
    except Exception as e:
        out["report_error"] = str(e)

    # pause cron
    try:
        r = subprocess.run([HERMES, "cron", "pause", CRON_JOB_ID],
                           capture_output=True, text=True, timeout=60)
        out["cron_paused"] = (r.returncode == 0)
        out["cron_output"] = (r.stdout + r.stderr)[-500:]
    except Exception as e:
        out["cron_pause_error"] = str(e)
    return out

def write_status(results):
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump({"ts": time.time(), "results": results}, f, ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
