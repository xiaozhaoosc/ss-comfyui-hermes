# -*- coding: utf-8 -*-
"""手工查询出图任务进度（不轮询、不阻塞）。

用法：
  python tools/_pc_status.py                 # 队列 + 最近一次提交台账的完成情况
  python tools/_pc_status.py --ledger <path> # 指定台账 json
  python tools/_pc_status.py --files         # 额外列出已落盘的产物文件
"""
import os, io, sys, json, glob, time, urllib.request, urllib.error

BASE = r"D:\ai_projects\ComfyUI"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
HOST = "http://127.0.0.1:8188"
DEFAULT_LEDGER = os.path.join(BASE, "output", time.strftime("%Y-%m-%d") + "_wb",
                              "lora_ab", "_submit_log.json")


def api_get(ep, timeout=20):
    with OPENER.open(HOST + ep, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def main():
    ledger_path = DEFAULT_LEDGER
    show_files = "--files" in sys.argv
    if "--ledger" in sys.argv:
        i = sys.argv.index("--ledger")
        if i + 1 < len(sys.argv):
            ledger_path = sys.argv[i + 1]

    out = []
    out.append("=== ComfyUI 队列（%s）===" % time.strftime("%H:%M:%S"))
    try:
        q = api_get("/queue")
        run = q.get("queue_running", [])
        pend = q.get("queue_pending", [])
        out.append("  running=%d  pending=%d" % (len(run), len(pend)))
        for item in run[:5]:
            try:
                out.append("   [run] %s" % (item[1] if len(item) > 1 else item)[:70])
            except Exception:
                pass
    except Exception as e:
        out.append("  !! 连不上 ComfyUI: %s" % str(e)[:100])
        out.append("     （先确认 main.py 已启动；本机 8188 会被 HTTP_PROXY 劫持，本脚本已绕代理）")

    out.append("")
    out.append("=== 台账 %s ===" % ledger_path)
    if not os.path.exists(ledger_path):
        out.append("  (台账不存在 —— 还没跑过 _pc_lora_ab.py？)")
    else:
        with io.open(ledger_path, encoding="utf-8") as f:
            led = json.load(f)
        jobs = led.get("jobs", [])
        out.append("  创建于 %s ｜ 任务 %d 个 ｜ 模式 %s" % (
            led.get("created"), len(jobs),
            "只提交" if led.get("no_wait") else "提交并等待"))

        # 按组统计
        stats = {}
        pending = []
        done_list = []
        fail_list = []
        for j in jobs:
            g = j["group"]
            s = stats.setdefault(g, {"n": 0, "done": 0, "fail": 0, "unknown": 0, "files": []})
            s["n"] += 1
            pid = j.get("prompt_id")
            if not j.get("ok_submit"):
                s["fail"] += 1
                fail_list.append(j)
                continue
            has_file = bool(glob.glob(os.path.join(BASE, "output", "*_wb", g,
                                                   "pc_%s_%s_*.png" % (g, j["scene"]))))
            if has_file:
                s["done"] += 1
                s["files"].append(j["scene"])
                done_list.append(j)
                continue
            try:
                h = api_get("/history/" + pid, timeout=15)
                if pid in h:
                    s["done"] += 1
                    s["files"].append(j["scene"])
                    done_list.append(j)
                else:
                    s["unknown"] += 1
                    pending.append(j)
            except Exception:
                s["unknown"] += 1
                pending.append(j)

        out.append("")
        out.append("  %-16s %6s %6s %6s %8s" % ("组", "提交", "完成", "失败", "未完成"))
        for g, s in stats.items():
            out.append("  %-16s %6d %6d %6d %8d" % (g, s["n"], s["done"], s["fail"], s["unknown"]))

        if pending:
            out.append("")
            out.append("  未完成 %d 个：" % len(pending))
            for j in pending[:20]:
                out.append("    %-16s %-24s pid=%s" % (j["group"], j["scene"],
                                                       str(j.get("prompt_id"))[:36]))
        if fail_list:
            out.append("")
            out.append("  提交失败 %d 个：" % len(fail_list))
            for j in fail_list[:10]:
                out.append("    %-16s %-24s %s" % (j["group"], j["scene"],
                                                   str(j.get("err"))[:110]))

        if show_files:
            out.append("")
            out.append("  已落盘产物：")
            for j in done_list:
                hits = sorted(glob.glob(os.path.join(BASE, "output", "*_wb", j["group"],
                                                     "pc_%s_%s_*.png" % (j["group"], j["scene"]))))
                if hits:
                    out.append("    %-16s %-24s %s  %.2f MB" % (
                        j["group"], j["scene"], os.path.basename(hits[-1]),
                        os.path.getsize(hits[-1]) / 1024.0 ** 2))

    txt = "\n".join(out)
    print(txt)
    with io.open(os.path.join(BASE, "_pc_status.txt"), "w", encoding="utf-8") as f:
        f.write(txt)


if __name__ == "__main__":
    main()
