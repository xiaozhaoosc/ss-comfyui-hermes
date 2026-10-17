"""把修复版(UI 格式)工作流转成 API prompt 并提交，用于真实校验/出片。"""
import json, urllib.request, urllib.error, collections, sys

BASE = "http://127.0.0.1:8188"
SRC = r'D:\ai_projects\ComfyUI\workflows\v6\1-Aiden-动作迁移升级版本！法线参考！！_本地修复版.json'

wf = json.load(open(SRC, encoding='utf-8'))
nodes = {n['id']: n for n in wf['nodes']}
links = {l[0]: l for l in wf['links']}

# ---- 结构自检 ----
ids = [n['id'] for n in wf['nodes']]
assert len(ids) == len(set(ids)), "节点 id 重复"
bad = [l for l in wf['links'] if l[1] not in nodes or l[3] not in nodes]
assert not bad, f"悬空连线 {bad[:5]}"
print(f"结构自检 OK: {len(ids)} 节点 / {len(wf['links'])} 连线")

oi = json.loads(urllib.request.urlopen(BASE + "/object_info", timeout=180).read().decode())

WIDGET_TYPES = ("INT", "FLOAT", "STRING", "BOOLEAN")
def widget_names(t):
    info = oi.get(t)
    if not info:
        return []
    names = []
    for sect in ("required", "optional"):
        for k, v in ((info.get("input") or {}).get(sect) or {}).items():
            t0 = v[0]
            if isinstance(t0, list) or t0 in WIDGET_TYPES:
                names.append(k)
    return names

# ---- bypass 重路（mode 4）----
for b in [n for n in nodes.values() if n.get('mode', 0) == 4]:
    bins = [i for i in b.get('inputs', []) if i.get('link') is not None]
    for out in b.get('outputs') or []:
        for lid in (out.get('links') or []):
            pick = next((i for i in bins if i.get('type') == out.get('type')), None)
            if pick is None and len(bins) == 1:
                pick = bins[0]
            if pick and pick['link'] in links:
                s = links[pick['link']]
                links[lid] = [lid, s[1], s[2], links[lid][3], links[lid][4], links[lid][5]]

def put(dst, key, val):
    if '.' in key:
        parent, child = key.split('.', 1)
        dst.setdefault(parent, {})
        if isinstance(dst[parent], dict):
            dst[parent][child] = val
            return
    dst[key] = val

prompt = {}
unknown = collections.Counter()
for nid, n in nodes.items():
    if n.get('mode', 0) != 0 or n['type'] in ('Note', 'MarkdownNote'):
        continue
    t = n['type']
    if t not in oi:
        unknown[t] += 1
    entry = {"class_type": t, "inputs": {}}
    for inp in n.get('inputs') or []:
        lid = inp.get('link')
        if lid is not None and lid in links:
            l = links[lid]
            put(entry['inputs'], inp['name'], [str(l[1]), l[2]])
    wv = n.get('widgets_values')
    names = widget_names(t)
    if wv is not None and names:
        if isinstance(wv, dict):
            for k in names:
                if k in wv:
                    entry['inputs'][k] = wv[k]
        else:
            linked = set(entry['inputs'].keys())
            for i, k in enumerate(names):
                if k in linked or i >= len(wv):
                    continue
                entry['inputs'][k] = wv[i]
    prompt[str(nid)] = entry

print("API 节点数:", len(prompt))
print("未注册的活动节点类型:", dict(unknown) if unknown else "(无)")
json.dump(prompt, open(r'D:\ai_projects\ComfyUI\_wf_api.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

body = json.dumps({"prompt": prompt, "client_id": "v6repair"}).encode()
req = urllib.request.Request(BASE + "/prompt", data=body, headers={"Content-Type": "application/json"})
try:
    r = json.loads(urllib.request.urlopen(req, timeout=300).read().decode())
    print("\n>>> 提交成功, prompt_id =", r.get("prompt_id"), " number =", r.get("number"))
except urllib.error.HTTPError as e:
    print("\n>>> 提交失败 HTTP", e.code)
    try:
        err = json.loads(e.read().decode())
        print("error:", json.dumps(err.get("error", {}), ensure_ascii=False))
        for k, v in (err.get("node_errors") or {}).items():
            print(f"  节点 {k} ({nodes.get(int(k),{}).get('type')}):")
            for e2 in v.get("errors", []):
                print(f"     - {e2.get('type')}: {e2.get('message')} | {str(e2.get('details'))[:220]}")
    except Exception as ex:
        print("raw:", ex)
