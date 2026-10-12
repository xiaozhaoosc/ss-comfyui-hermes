"""
Hitomi 放量驱动器：290 条分 3 个子目录、20 条/轮小循环。

策略（对应计划 §8.3/§8.4）：
  - 每轮先等 ComfyUI 队列排空（门控，防 poll 超时后叠加提交），
    再 --submit-only 提交 20 条（子目录内按 _face_priority 降序），
    随后 --poll-only 轮询终态并跑后处理（水印/语录/BGM）。
  - "输出已存在则跳过" + _done_map 账本保证任意时刻中断可原命令重入续跑。
  - 单条失败不碍整批：/history 终态判定，error 进失败清单。

用法：
  python tools/hitomi_scaleup.py                    # 全量（ayano → るーんちゃ → Jia）
  python tools/hitomi_scaleup.py --limit 20 --subdirs "ayano (insta_ayano.fj)"
  中断后重跑同一命令即可续跑（已产出自动跳过）。

日志：output/2026-10-12/hitomi_batch/_scaleup_driver.log（进度）
      output/2026-10-12/hitomi_batch/_scaleup_rounds.log（每轮完整输出尾部）
"""
import argparse
import json
import re
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
PY = ROOT / "venv" / "Scripts" / "python.exe"
BATCH = ROOT / "tools" / "batch_faceswap_overlay.py"
INPUT_ROOT = ROOT / "input" / "hitomi_insta_batch"
OUT_BASE = ROOT / "output" / "2026-10-12" / "hitomi_batch"
FACE = str(ROOT / "input" / "ken4" / "face" / "gpt" / "duo.png")
SUBDIRS = ["ayano (insta_ayano.fj)", "るーんちゃ！ (insta_runchaliveeee)", "Jia (insta_jia_to_jia)"]
DRIVER_LOG = OUT_BASE / "_scaleup_driver.log"
ROUNDS_LOG = OUT_BASE / "_scaleup_rounds.log"

# 本机 8188 会被系统代理劫持，队列查询一律绕开
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def log(msg):
    line = "[%s] %s" % (time.strftime("%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    with open(DRIVER_LOG, "a", encoding="utf-8") as fp:
        fp.write(line + "\n")


def queue_depth():
    q = json.loads(_opener.open("http://127.0.0.1:8188/queue", timeout=30).read())
    return len(q.get("queue_running", [])), len(q.get("queue_pending", []))


def wait_queue_empty(max_wait=6 * 3600):
    """门控：等队列排空再提交（poll-only 超时返回时的兜底，防止在跑任务上叠加）"""
    start = time.time()
    warned = False
    while True:
        try:
            running, pending = queue_depth()
        except Exception as e:
            if not warned:
                log("⚠️ 队列查询失败（%s），持续等待 ComfyUI 恢复" % e)
                warned = True
            time.sleep(60)
            continue
        if running == 0 and pending == 0:
            if warned:
                log("✅ ComfyUI 已恢复，队列空")
            return
        if time.time() - start > max_wait:
            log("⚠️ 队列等待超过 %dh 仍未空（running=%d pending=%d），仍继续提交（skip 逻辑保护）"
                % (max_wait // 3600, running, pending))
            return
        if not warned:
            log("⏳ 等待队列排空（running=%d pending=%d）..." % (running, pending))
            warned = True
        time.sleep(30)


def run_batch(args):
    cmd = [str(PY), "-u", str(BATCH)] + args
    log("RUN: " + " ".join(args))
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=str(ROOT))
    with open(ROUNDS_LOG, "a", encoding="utf-8") as fp:
        fp.write("\n===== %s =====\n$ %s\n%s\n" % (
            time.strftime("%m-%d %H:%M:%S"), " ".join(args), (p.stdout or "")[-4000:]))
    return p.returncode, p.stdout or ""


def round_args(in_dir, out_dir, order_file, limit, mode):
    return ["--input", str(in_dir), "--face", FACE,
            "--output", str(out_dir), "--original-dir", str(in_dir),
            "--limit", str(limit), "--order-file", str(order_file), mode]


def main():
    ap = argparse.ArgumentParser(description="Hitomi 放量驱动器（20条/轮小循环）")
    ap.add_argument("--limit", type=int, default=20, help="每轮提交条数（默认20）")
    ap.add_argument("--subdirs", default=",".join(SUBDIRS), help="逗号分隔的子目录列表")
    a = ap.parse_args()

    OUT_BASE.mkdir(parents=True, exist_ok=True)
    log("===== 放量驱动器启动｜limit=%d｜face=%s =====" % (a.limit, FACE))

    for subdir in a.subdirs.split(","):
        in_dir = INPUT_ROOT / subdir
        out_dir = OUT_BASE / subdir
        order_file = OUT_BASE / ("%s_order.txt" % subdir.replace("/", "_"))
        if not in_dir.is_dir():
            log("❌ 输入目录不存在，跳过: %s" % in_dir)
            continue
        if not order_file.exists():
            log("❌ 顺序清单不存在，跳过: %s" % order_file)
            continue
        log("—— 子目录开始：%s ——" % subdir)
        round_no = 0
        while True:
            round_no += 1
            wait_queue_empty()
            rc, out = run_batch(round_args(in_dir, out_dir, order_file, a.limit, "--submit-only"))
            if "无需提交" in out:
                log("✅ 子目录 %s 全部完成（第%d轮：无需提交）" % (subdir, round_no))
                break
            m = re.search(r"已提交 (\d+) 个任务", out)
            if not m:
                log("⚠️ submit-only 输出异常（rc=%d），60s 后重试" % rc)
                time.sleep(60)
                round_no -= 1
                continue
            n = int(m.group(1))
            if n == 0:
                # 0 条 ≠ 完成：若本轮有提交失败（❌），是 ComfyUI 故障，重试而非跳过
                if "❌" in out:
                    log("⚠️ 本轮 0 条提交成功且有失败记录（ComfyUI 异常？），60s 后重试")
                    time.sleep(60)
                    round_no -= 1
                    continue
                log("✅ 子目录 %s 全部完成（第%d轮：0 条待提交）" % (subdir, round_no))
                break
            log("📤 %s 第%d轮：提交 %d 条 → 轮询+后处理" % (subdir, round_no, n))
            rc, out = run_batch(round_args(in_dir, out_dir, order_file, a.limit, "--poll-only"))
            log("📥 %s 第%d轮 poll 结束（rc=%d）" % (subdir, round_no, rc))

    log("===== 全部子目录处理完毕，放量结束 =====")


if __name__ == "__main__":
    main()
