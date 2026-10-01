#!/usr/bin/env python3
"""用智谱 GLM-4V-Flash 批量分析 OOTD 参考图（免费不限次，并发10）。
用法: python tools/analyze_refs.py [子目录]
输出: 每张图 -> 发型/服装/是否干净单人/是否三视图/正面像位置
"""
import base64, json, os, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

API = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
KEY = "f2649c2b4bef47b099bf63a63ce135e4.kpn7Es4gyg3dawQk"
MODEL = "glm-4v-flash"

BASE = "input/ootd/face"
SUBDIRS = sys.argv[1:] if len(sys.argv) > 1 else ["gpt", "gemini"]

QUESTION = (
    "这是人物参考图。请用一行简洁中文回答，按以下4点："
    "1)发型(丸子头/披肩/马尾/低马尾/盘发/其他)；"
    "2)服装(上衣+下装)；"
    "3)是否【单人单视角全身照】(是/否)；"
    "4)是否【三视图/character sheet】(含正面+侧面+背面多视角、或FRONT/SIDE/BACK文字标注)(是/否)；"
    "5)若为三视图，正面单人像大致在图的哪个位置(左/中/右/上/下)。"
)

def b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def ask(img_path):
    body = {
        "model": MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64(img_path)}},
                {"type": "text", "text": QUESTION},
            ],
        }],
        "temperature": 0.2,
    }
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + KEY})
    r = json.loads(urllib.request.urlopen(req, timeout=120).read())
    return r["choices"][0]["message"]["content"]

def collect():
    jobs = []
    for sub in SUBDIRS:
        d = os.path.join(BASE, sub)
        if not os.path.isdir(d):
            print(f"目录不存在: {d}"); continue
        for fn in sorted(os.listdir(d)):
            if fn.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                jobs.append((sub, os.path.join(d, fn)))
    return jobs

def main():
    jobs = collect()
    print(f"共 {len(jobs)} 张图待分析\n")
    results = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        fut = {}
        for sub, p in jobs:
            fut[ex.submit(ask, p)] = (sub, os.path.basename(p))
        for i, f in enumerate(as_completed(fut), 1):
            sub, fn = fut[f]
            try:
                txt = f.result().strip().replace("\n", " ")
            except Exception as e:
                txt = f"[错误] {e}"
            results[(sub, fn)] = txt
            print(f"[{i}/{len(jobs)}] {sub}/{fn}\n    {txt}\n", flush=True)
    out = "input/ootd/refs_analysis.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({f"{s}/{n}": t for (s, n), t in results.items()}, fh, ensure_ascii=False, indent=2)
    print(f"结果已存 {out}")

if __name__ == "__main__":
    main()
