# -*- coding: utf-8 -*-
"""
把本次排查过程产生的临时脚本/日志收进 tools/_scratch_h3/（**只移动，不删除**）。
保留：正式脚本、可复用工具、以及 _pc_* 一族的既有复用脚本。
"""
import io, os, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
DST = os.path.join(HERE, "_scratch_h3")
OUT = os.path.join(HERE, "_tidy_out.txt")

KEEP_EXACT = {
    "h3_rope_common.py",      # 共享库 + 质检引擎（正式）
    "run_h3_guard_v5.py",     # 主脚本（正式）
    "_cmd.py",                # 通用命令执行器（可复用）
    "_checkv.py",             # 验帧工具（可复用，MEMORY.md 里点名要留）
    "_tidy.py",               # 本脚本自身
}
KEEP_PREFIX = ("_pc_",)       # 上次任务的复用脚本族
IMG_EXT = (".png", ".jpg", ".jpeg")


def reap():
    os.makedirs(DST, exist_ok=True)
    moved, kept = [], []
    for n in sorted(os.listdir(HERE)):
        p = os.path.join(HERE, n)
        if os.path.isdir(p):
            continue
        if not n.startswith("_"):
            continue
        if n in KEEP_EXACT or n.startswith(KEEP_PREFIX):
            kept.append(n)
            continue
        shutil.move(p, os.path.join(DST, n))
        moved.append(n)
    return moved, kept


moved, kept = reap()

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("移入 %s ：%d 个\n" % (DST, len(moved)))
    for n in moved:
        f.write("   %s\n" % n)
    f.write("\n保留在 tools/ ：%d 个\n" % len(kept))
    for n in kept:
        f.write("   %s\n" % n)
