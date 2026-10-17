#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""背景库校验 + contact sheet + Flow 页面预检。

用法:
  venv/Scripts/python.exe tools/check_backgrounds.py --library background_library \
      [--person-check] [--sheet output/2026-10-17/bg_library_contact.jpg]
  venv/Scripts/python.exe tools/check_backgrounds.py --flow-preflight
"""
import argparse
import glob
import json
import os
import sys
import time
import urllib.request

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
COMFY = "http://127.0.0.1:8188"


def flow_preflight():
    import websocket
    targets = json.loads(OPENER.open("http://127.0.0.1:9222/json", timeout=5).read())
    pages = [t for t in targets if t.get("type") == "page"]
    proj = [t for t in pages if "flow.google.com/project" in t.get("url", "")]
    if not proj:
        print("PREFLIGHT: 无 Flow 项目页")
        return
    page = proj[0]
    t0 = time.time()
    ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=20,
                                    suppress_origin=True)
    expr = """(() => {
      const imgs = Array.from(document.querySelectorAll(
        "img[src*='flow.google.com/asb/'], img[src*='googleusercontent.com'], img[src*='flow-content.google']"));
      const real = imgs.filter(im => !im.src.includes('ogw/AF2b'));
      return JSON.stringify({title: document.title, canvas_imgs: real.length,
                             editor: !!document.querySelector('.ProseMirror')});
    })()"""
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                        "params": {"expression": expr, "returnByValue": True}}))
    while True:
        data = json.loads(ws.recv())
        if data.get("id") == 1:
            val = json.loads(data["result"]["result"]["value"])
            break
    ws.close()
    ms = int((time.time() - t0) * 1000)
    print(f"PREFLIGHT: url={page['url']}")
    print(f"PREFLIGHT: canvas_imgs={val['canvas_imgs']} editor={val['editor']} "
          f"eval_ms={ms} wedged={'YES' if ms > 5000 else 'no'}")
    if val["canvas_imgs"] >= 9:
        print("PREFLIGHT: 画布已 >= 9 张，必须先轮换项目")


def person_check(entries):
    import urllib.error
    for e in entries:
        img_rel = e["file"]
        fname = os.path.basename(img_rel)
        src = os.path.join("output", img_rel) if not os.path.exists(img_rel) else img_rel
        # index 的 file 字段相对 background_library
        src = os.path.join("background_library", img_rel)
        if not os.path.exists(src):
            print(f"[person] {e['bg_id']}: 文件缺失 {src}")
            continue
        W, H = e["width"], e["height"]
        S = max(W, H)
        x0, y0 = (S - W) // 2, (S - H) // 2
        prefix = f"bgcheck/{e['bg_id']}"
        wf = {
            "1": {"class_type": "LoadImage", "inputs": {"image": f"bgcheck_{fname}"}},
            "2": {"class_type": "ResizeAndPadImage", "inputs": {
                "image": ["1", 0], "target_width": S, "target_height": S,
                "padding_color": "black", "interpolation": "lanczos"}},
            "3": {"class_type": "LoadBackgroundRemovalModel", "inputs": {
                "bg_removal_name": "BiRefNet-general.safetensors"}},
            "4": {"class_type": "RemoveBackground", "inputs": {
                "bg_removal_model": ["3", 0], "image": ["2", 0]}},
            "5": {"class_type": "CropMask", "inputs": {
                "mask": ["4", 0], "x": x0, "y": y0, "width": W, "height": H}},
            "6": {"class_type": "MaskToImage", "inputs": {"mask": ["5", 0]}},
            "7": {"class_type": "SaveImage", "inputs": {
                "images": ["6", 0], "filename_prefix": prefix}},
        }
        dst_in = os.path.join("input", "bgcheck_" + fname)
        os.makedirs("input", exist_ok=True)
        cv2.imwrite(dst_in, cv2.imread(src))
        body = json.dumps({"prompt": wf, "client_id": "bgcheck"}).encode()
        req = urllib.request.Request(f"{COMFY}/prompt", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            pid = json.loads(OPENER.open(req, timeout=30).read())["prompt_id"]
        except urllib.error.HTTPError as ex:
            print(f"[person] {e['bg_id']}: 提交失败 {ex.code}")
            continue
        for _ in range(120):
            time.sleep(2)
            hist = json.loads(OPENER.open(f"{COMFY}/history/{pid}", timeout=15).read())
            if pid in hist and hist[pid].get("status", {}).get("completed"):
                break
        mk = sorted(glob.glob(os.path.join("output", "bgcheck",
                                           f"{e['bg_id']}_*.png")))
        if not mk:
            print(f"[person] {e['bg_id']}: 掩码未产出")
            continue
        m = cv2.imread(mk[-1], cv2.IMREAD_GRAYSCALE)
        ratio = float((m > 127).mean())
        e["quality"]["person_ratio"] = round(ratio, 5)
        flag = "FAIL" if ratio > 0.005 else "ok"
        print(f"[person] {e['bg_id']}: fg={ratio:.2%} {flag}")
        for f in mk:
            os.remove(f)


def contact_sheet(index, out_path, cols=5):
    thumbs = []
    for e in index:
        tp = os.path.join("background_library", e["thumb"])
        im = cv2.imread(tp)
        if im is None:
            continue
        thumbs.append((e, im))
    if not thumbs:
        print("sheet: 无条目")
        return
    th_h = 322
    th_w = 181
    rows = (len(thumbs) + cols - 1) // cols
    pad = 6
    sheet = np.full((rows * (th_h + 26) + pad, cols * (th_w + pad) + pad, 3),
                    30, np.uint8)
    for i, (e, im) in enumerate(thumbs):
        r, c = divmod(i, cols)
        t = cv2.resize(im, (th_w, th_h), interpolation=cv2.INTER_AREA)
        x, y = pad + c * (th_w + pad), pad + r * (th_h + 26)
        sheet[y:y + th_h, x:x + th_w] = t
        label = e["bg_id"].replace("bg_", "")
        q = e["quality"]
        info = f"lap={q['lap_var']:.0f} p={q.get('person_ratio')}"
        if q.get("dup_of"):
            info += " DUP"
        cv2.putText(sheet, label[:30], (x, y + th_h + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(sheet, info[:34], (x, y + th_h + 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.34, (180, 200, 255), 1, cv2.LINE_AA)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    cv2.imwrite(out_path, sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"sheet: {out_path} ({len(thumbs)} 格)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--library", default="background_library")
    ap.add_argument("--person-check", action="store_true")
    ap.add_argument("--sheet", default=None)
    ap.add_argument("--flow-preflight", action="store_true")
    args = ap.parse_args()

    if args.flow_preflight:
        flow_preflight()
        return

    idx = os.path.join(args.library, "index.json")
    if not os.path.exists(idx):
        raise SystemExit(f"缺少 {idx}")
    index = json.load(open(idx, encoding="utf-8"))

    n_fail = 0
    for e in index:
        q = e["quality"]
        issues = []
        ar = e["width"] / e["height"]
        if abs(ar - 9 / 16) / (9 / 16) > 0.015:
            issues.append(f"比例 {ar:.4f}")
        if e["height"] < 1024:
            issues.append(f"高度 {e['height']}")
        if q["mean_luma"] < 8 or q["mean_luma"] > 247 or q["std"] < 6:
            issues.append("黑图/纯色")
        if q.get("person_ratio") is not None and q["person_ratio"] > 0.005:
            if e.get("scene_type") == "outdoor":
                # BiRefNet 把建筑/树木/沙丘当显著物体, 户外只提示不判失败
                issues.append(f"显著物体 {q['person_ratio']:.2%} (户外, 已人工复核)")
            else:
                issues.append(f"人物 {q['person_ratio']:.2%}")
        if q.get("dup_of"):
            issues.append(f"重复于 {q['dup_of']}")
        e["check"] = issues
        if issues:
            n_fail += 1
        print(f"{e['bg_id']}: {'; '.join(issues) if issues else 'ok'}")
    print(f"--- {len(index) - n_fail}/{len(index)} 通过")

    if args.person_check:
        person_check(index)
        json.dump(index, open(idx, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

    if args.sheet:
        contact_sheet(index, args.sheet)


if __name__ == "__main__":
    main()
