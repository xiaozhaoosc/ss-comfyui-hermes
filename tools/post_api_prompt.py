# -*- coding: utf-8 -*-
"""把 API 格式工作流提交到本机 ComfyUI(127.0.0.1:8188)。

    python tools/post_api_prompt.py <api.json>
    python tools/post_api_prompt.py <api.json> --set 31.video=白模1.mp4 --set 20.seed=123
    python tools/post_api_prompt.py <api.json> --wait      # 提交后轮询直到出队

--set 用 <节点号>.<输入名>=<值>，值按 JSON 解析失败时当字符串。
"""
import argparse
import json
import time
import urllib.error
import urllib.request

HOST = "http://127.0.0.1:8188"
# 本机 HTTP_PROXY 会劫持 127.0.0.1:8188，必须绕代理
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(ep, payload=None, timeout=60):
    if payload is None:
        r = _OPENER.open(HOST + ep, timeout=timeout)
        return json.loads(r.read().decode("utf-8", "replace"))
    req = urllib.request.Request(HOST + ep, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        r = _OPENER.open(req, timeout=timeout)
        return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode("utf-8", "replace"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("api_json")
    ap.add_argument("--set", action="append", default=[], help="<节点号>.<输入名>=<值>")
    ap.add_argument("--wait", action="store_true")
    args = ap.parse_args()

    with open(args.api_json, encoding="utf-8") as f:
        prompt = json.load(f)

    for pair in args.set:
        path, _, raw = pair.partition("=")
        nid, _, key = path.partition(".")
        try:
            val = json.loads(raw)
        except ValueError:
            val = raw
        if nid not in prompt:
            raise SystemExit("没有节点 #%s" % nid)
        prompt[nid]["inputs"][key] = val

    res = call("/prompt", {"prompt": prompt})
    if "prompt_id" not in res:
        print("提交失败：")
        print(json.dumps(res, ensure_ascii=False, indent=2)[:4000])
        return
    pid = res["prompt_id"]
    print("已入队 prompt_id =", pid, "节点错误:", res.get("node_errors") or "无")

    if not args.wait:
        return
    while True:
        hist = call("/history/" + pid).get(pid)
        if hist:
            print("完成，产物：", json.dumps(hist.get("outputs"), ensure_ascii=False)[:2000])
            return
        time.sleep(5)


if __name__ == "__main__":
    main()
