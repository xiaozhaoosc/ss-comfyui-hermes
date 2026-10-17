# -*- coding: utf-8 -*-
"""公众号草稿发布端到端实测脚本。

用法：
    venv/Scripts/python.exe tools/asset_manager/_e2e_publish_test.py --mode images
    venv/Scripts/python.exe tools/asset_manager/_e2e_publish_test.py --mode article
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# 本机代理会劫持 127.0.0.1，必须清空后再访问本机服务
for k in list(os.environ):
    if k.lower().endswith("_proxy"):
        os.environ.pop(k)

BASE = "http://127.0.0.1:8090"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
DIR = "2026-10-16/flow_images"

FIVE = [
    "char_cen_youqing_2204_01_01_front_9_16_220706_1.png",
    "char_cen_youqing_2204_01_02_three_quarter_9_16_220904_1.png",
    "char_cen_youqing_2204_01_03_side_profile_9_16_221103_1.png",
    "char_cen_youqing_2204_01_07_portrait_face_9_16_221805_1.png",
    "char_cen_youqing_2204_01_08_portrait_45deg_9_16_221920_1.png",
]
FOUR = [
    "char_cen_youqing_2204_01_01_front_9_16_220706_1.png",
    "char_cen_youqing_2204_01_02_three_quarter_9_16_220904_1.png",
    "char_cen_youqing_2204_01_07_portrait_face_9_16_221805_1.png",
    "char_cen_youqing_2204_01_08_portrait_45deg_9_16_221920_1.png",
]


def api(method, path, payload=None, timeout=30):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    return json.loads(OPENER.open(req, timeout=timeout).read().decode("utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["images", "article"], required=True)
    ap.add_argument("--timeout", type=int, default=420)
    args = ap.parse_args()

    names = FIVE if args.mode == "images" else FOUR
    rels = [f"{DIR}/{n}" for n in names]
    label = "贴图（createType=8，合集 OOTD）" if args.mode == "images" else "文章（标准编辑器，合集 #阿ken）"

    # 僵尸标签页会让 build_driver 建会话无限挂起，跑之前先自动清理
    import _cdp_probe
    for port in (9527, 9528):
        kept, closed = _cdp_probe.close_unresponsive_tabs(port, verbose=True)
        print(f"端口 {port} 标签页清理：保留 {kept}，关闭 {closed}")

    print(f"模式：{label}")
    print(f"图片：{len(rels)} 张，首图 {names[0]}")

    resp = api("POST", "/api/publish/jobs", {
        "file_rel_path": rels[0],
        "file_rel_paths": rels,
        "platforms": ["wechat_mp"],
        "title": "",          # 留空以走自动标题生成
        "content": "",        # 留空以走自动正文生成
        "tags": None,
        "publish_mode": "draft",
        "media_type": args.mode,
    })
    job = resp["jobs"][0]
    job_id = job["job_id"]
    print(f"任务已创建：{job_id}")
    print(f"自动标题：{job['title']}")
    print(f"自动标签：{job['tags']}")

    deadline = time.time() + args.timeout
    shown = 0
    last_status = None
    while time.time() < deadline:
        cur = api("GET", f"/api/publish/jobs/{job_id}")
        status = cur.get("status")
        if status != last_status:
            print(f"\n[状态] {last_status} -> {status}")
            last_status = status
        logs = cur.get("logs", [])
        for line in logs[shown:]:
            print(f"    {line}")
        shown = len(logs)
        if status in ("success", "failed", "need_login", "cancelled"):
            print(f"\n最终状态：{status}")
            return 0 if status == "success" else 2
        time.sleep(5)

    print("\n等待超时，任务仍在进行中，最后状态：", last_status)
    return 3


if __name__ == "__main__":
    sys.exit(main())
