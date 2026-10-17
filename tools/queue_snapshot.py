#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ComfyUI 队列快照 / 一键重投。

背景：本机 ComfyUI 一旦重启，pending 队列和 /history 会一起没掉，排队几十小时的任务
就白排了。这里把队列里每条任务的完整 API 图落盘，随时可以原样重投。

用法:
    # 1) 快照（默认写到 output/<今天>/queue_snapshot_<HHMM>.json）
    python tools/queue_snapshot.py snapshot
    python tools/queue_snapshot.py snapshot --out D:/tmp/q.json

    # 2) 重投（按原顺序；--dry-run 只看不打）
    python tools/queue_snapshot.py restore --in <快照文件>
    python tools/queue_snapshot.py restore --in <快照文件> --include-prefix v6_fix
    python tools/queue_snapshot.py restore --in <快照文件> --only 272,273
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime

BASE = "http://127.0.0.1:8188"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# os.environ 里的代理会劫持 127.0.0.1:8188，必须显式绕开
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get(path, timeout=60):
    with OPENER.open(urllib.request.Request(BASE + path), timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def post(path, payload, timeout=300):
    # 注意：POST /queue 的 clear/delete 返回空 body（204），不能按 JSON 解
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with OPENER.open(req, timeout=timeout) as r:
        body = r.read().decode("utf-8")
    return json.loads(body) if body.strip() else {"ok": True, "status": r.status}


def label_of(graph):
    """给任务起个人能认的名字：优先看 VHS 输出前缀 / LoadVideo / LoadImage。"""
    for nid, nd in graph.items():
        if nd.get("class_type") == "VHS_VideoCombine":
            p = nd.get("inputs", {}).get("filename_prefix")
            if p and isinstance(p, str) and p not in ("AnimateDiff", ""):
                return p
    for nid, nd in graph.items():
        if nd.get("class_type") == "VHS_LoadVideo":
            v = nd.get("inputs", {}).get("video")
            if v:
                return os.path.splitext(os.path.basename(v))[0]
    for nid, nd in graph.items():
        if nd.get("class_type") == "LoadImage":
            v = nd.get("inputs", {}).get("image")
            if v:
                return os.path.splitext(os.path.basename(v))[0]
    types = sorted({nd.get("class_type") for nd in graph.values()})
    return "graph:" + ",".join(types[:3])


def cmd_snapshot(args):
    q = get("/queue")
    running, pending = q.get("queue_running") or [], q.get("queue_pending") or []
    items = []
    for pos, it in enumerate(running):
        num, pid, graph = it[0], it[1], it[2]
        items.append({"number": num, "prompt_id": pid, "state": "running",
                      "position": -1, "label": label_of(graph), "prompt": graph})
    for pos, it in enumerate(pending):
        num, pid, graph = it[0], it[1], it[2]
        items.append({"number": num, "prompt_id": pid, "state": "pending",
                      "position": pos, "label": label_of(graph), "prompt": graph})
    out = args.out or os.path.join(
        ROOT, "output", datetime.now().strftime("%Y-%m-%d"),
        "queue_snapshot_%s.json" % datetime.now().strftime("%H%M"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    snap = {"captured_at": datetime.now().isoformat(timespec="seconds"),
            "server": BASE, "running": len(running), "pending": len(pending),
            "items": items}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False)
    print("快照已写出: %s" % out)
    print("  running=%d pending=%d 共 %d 条" % (len(running), len(pending), len(items)))
    labels = {}
    for it in items:
        labels[it["label"]] = labels.get(it["label"], 0) + 1
    for k, v in sorted(labels.items(), key=lambda x: -x[1])[:10]:
        print("    %4d x %s" % (v, k))
    return 0


def cmd_restore(args):
    snap = json.load(open(args.in_, encoding="utf-8"))
    items = snap["items"]
    only = set(int(x) for x in args.only.split(",")) if args.only else None
    kept = []
    for it in items:
        if only is not None and it["number"] not in only:
            continue
        if args.include_prefix and not str(it["label"]).startswith(args.include_prefix):
            continue
        if args.exclude_prefix and str(it["label"]).startswith(args.exclude_prefix):
            continue
        kept.append(it)
    print("待重投 %d / %d 条" % (len(kept), len(items)))
    if args.dry_run:
        for it in kept:
            print("  #%s %s" % (it["number"], it["label"]))
        return 0
    ok = fail = 0
    for it in kept:
        try:
            res = post("/prompt", {"prompt": it["prompt"], "client_id": "queue-restore"})
        except urllib.error.HTTPError as e:
            try:
                err = json.loads(e.read().decode("utf-8"))
                msg = json.dumps(err.get("node_errors") or err, ensure_ascii=False)[:200]
            except Exception:
                msg = "HTTP %s" % e.code
            print("  #%s FAIL %s" % (it["number"], msg))
            fail += 1
            continue
        print("  #%s -> new #%s %s" % (it["number"], res.get("number"), it["label"]))
        ok += 1
    print("完成: ok=%d fail=%d" % (ok, fail))
    return 0 if fail == 0 else 1


def cmd_clear(args):
    if not args.yes:
        print("这会清空整个队列（含正在跑的任务）。确认请加 --yes")
        return 1
    res = post("/queue", {"clear": True}, timeout=120)
    print("clear ->", json.dumps(res, ensure_ascii=False)[:200])
    q = get("/queue")
    print("剩余 running=%d pending=%d" % (len(q["queue_running"]), len(q["queue_pending"])))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("snapshot")
    p1.add_argument("--out", default=None)
    p1.set_defaults(func=cmd_snapshot)

    p2 = sub.add_parser("restore")
    p2.add_argument("--in", dest="in_", required=True)
    p2.add_argument("--only", default=None, help="只重投这些原编号，逗号分隔")
    p2.add_argument("--include-prefix", default=None)
    p2.add_argument("--exclude-prefix", default=None)
    p2.add_argument("--dry-run", action="store_true")
    p2.set_defaults(func=cmd_restore)

    p3 = sub.add_parser("clear")
    p3.add_argument("--yes", action="store_true")
    p3.set_defaults(func=cmd_clear)

    if len(sys.argv) == 1:
        ap.print_help()
        return 0
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
