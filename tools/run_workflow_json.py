#!/usr/bin/env python3
"""把 ComfyUI 的 UI 格式 workflow.json 转成 API prompt 并执行（用于验证导入即可用）。

基于节点 schemas(/object_info) 按输入顺序填充：
  - 已连线输入 → 用 link 的源节点输出值
  - 未连线输入 → 依序消费 widgets_values
用法:
  python tools/run_workflow_json.py <workflow.json>            # 只打印 API prompt
  python tools/run_workflow_json.py <workflow.json> --run      # 提交并等待出片
"""
import json, sys, urllib.request, uuid, time, argparse, os

BASE = "http://127.0.0.1:8188"
_schema_cache = {}

def schema(cn):
    if cn not in _schema_cache:
        r = json.loads(urllib.request.urlopen(f"{BASE}/object_info/{cn}", timeout=30).read())
        _schema_cache[cn] = r[cn]["input"]
    return _schema_cache[cn]

def build_api(wf):
    nodes = {n["id"]: n for n in wf["nodes"]}
    linkmap = {}
    for l in wf["links"]:
        linkmap[l[0]] = {"src": l[1], "src_slot": l[2], "dst": l[3], "dst_slot": l[4], "type": l[5]}
    # 每 node：已连线输入 name -> link_id
    linked = {}
    for n in wf["nodes"]:
        m = {}
        for inp in n.get("inputs", []):
            if inp.get("link") is not None:
                m[inp["name"]] = inp["link"]
        linked[n["id"]] = m
    widgets = {n["id"]: list(n.get("widgets_values", [])) for n in wf["nodes"]}

    prompt = {}
    for nid, node in nodes.items():
        cn = node["type"]
        sch = schema(cn)
        required = list(sch.get("required", {}).keys())
        optional = list(sch.get("optional", {}).keys())
        order = required + optional
        inp = {}
        wq = list(widgets[nid])
        lm = linked[nid]
        for name in order:
            if name in lm:                       # 已连线
                lk = linkmap[lm[name]]
                inp[name] = [str(lk["src"]), lk["src_slot"]]
            else:                                # widget 值（逐项消费）
                if name == "image" and cn == "LoadImage":
                    inp[name] = widgets[nid][-1] if widgets[nid] else ""
                    continue
                if not wq:
                    continue
                inp[name] = wq.pop(0)
        prompt[str(nid)] = {"class_type": cn, "inputs": inp}
    return prompt

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wf", help="workflow.json 路径")
    ap.add_argument("--run", action="store_true", help="提交并等待完成")
    ap.add_argument("--timeout", type=int, default=3600)
    args = ap.parse_args()

    with open(args.wf, encoding="utf-8") as f:
        wf = json.load(f)
    api = build_api(wf)
    print("=== API prompt ===")
    print(json.dumps(api, ensure_ascii=False, indent=2))
    if not args.run:
        return

    payload = {"prompt": api, "client_id": str(uuid.uuid4())}
    req = urllib.request.Request(f"{BASE}/prompt", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode(errors="replace")[:1000]); sys.exit(1)
    pid = resp.get("prompt_id")
    print(f"\n已提交 pid={pid}，等待出片...")
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        try:
            h = json.loads(urllib.request.urlopen(f"{BASE}/history/{pid}", timeout=15).read())
            rec = h.get(pid)
            if rec and rec.get("status", {}).get("completed"):
                print("✓ 执行完成")
                print("输出:", json.dumps(rec.get("outputs", {}), ensure_ascii=False)[:600])
                return
        except Exception as ex:
            print("查询异常:", ex)
        time.sleep(15)
    print("超时")

if __name__ == "__main__":
    main()