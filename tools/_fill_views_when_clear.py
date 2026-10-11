# -*- coding: utf-8 -*-
"""等 GPU 队列真正清空时，自动补跑角色资产表里缺失的视图。

背景：用户自己的批处理会频繁 /queue clear，把排队的任务整批清掉，
导致 _drama_char_sheet.py 后提交的视图（如 face/height）永远排不到。
本脚本轮询 /queue，抓「0 在跑 + 0 待跑」的空闲窗口，立刻调断点续跑版补缺失视图；
不齐就等下一个空档，自动重试，直到 5 视图齐全或超时。

用法:
  python tools/_fill_views_when_clear.py char_ref.demo.json --date 2026-10-11 --proj demo
"""
import sys, os, time, subprocess, glob, json, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _pc_common as C

VIEWS = ["front", "side", "back", "face", "height"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("char_json")
    ap.add_argument("--date", required=True)
    ap.add_argument("--proj", default="default")
    ap.add_argument("--poll", type=int, default=15, help="探队列间隔(秒)")
    ap.add_argument("--max-wait", type=int, default=3600, help="最长等待(秒)")
    a = ap.parse_args()

    with open(a.char_json, encoding="utf-8") as f:
        name = json.load(f)["name"]
    outdir = os.path.join(C.BASE, "output", a.date, a.proj, "01_assets", "char_" + name)
    main_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_drama_char_sheet.py")
    cmd = [sys.executable, main_script, a.char_json, "--date", a.date, "--proj", a.proj]

    def missing():
        m = []
        for v in VIEWS:
            if not glob.glob(os.path.join(outdir, "sheet_%s_%s_*.png" % (name, v))):
                m.append(v)
        return m

    t0 = time.time()
    while time.time() - t0 < a.max_wait:
        miss = missing()
        if not miss:
            print("[%s] DONE 5/5 视图齐全" % time.strftime("%H:%M:%S"))
            return
        try:
            q = C.api_get("/queue")
            running = len(q.get("queue_running", []))
            pending = len(q.get("queue_pending", []))
        except Exception:
            running, pending = 1, 0
        if running == 0 and pending == 0:
            print("[%s] 队列空闲，触发续跑补: %s" % (time.strftime("%H:%M:%S"), miss))
            env = dict(os.environ)
            env["DRAM_WAIT_TIMEOUT"] = "180"  # 失败视图快速重试
            try:
                subprocess.run(cmd, timeout=1800, env=env)
            except Exception as e:
                print("  run err:", e)
            # 继续循环复查
        else:
            print("[%s] 队列忙 R%d/P%d，缺 %s，等 %ds" % (
                time.strftime("%H:%M:%S"), running, pending, miss, a.poll))
            time.sleep(a.poll)
    print("[TIMEOUT] %ds 内未补齐，停止等待" % (time.time() - t0))


if __name__ == "__main__":
    main()
