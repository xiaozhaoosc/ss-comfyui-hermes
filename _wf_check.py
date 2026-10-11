import os, json, re

OUT = r"D:/ai_projects/ComfyUI/_wf_check.txt"
baidu = r"D:\BaiduNetdiskDownload"
custom_nodes = r"D:\ai_projects\ComfyUI\custom_nodes"
models_root = r"D:\ai_projects\ComfyUI\models"
core_nodes = r"D:\ai_projects\ComfyUI\nodes.py"
core_extras = r"D:\ai_projects\ComfyUI\comfy_extras"

MODEL_EXT = (".safetensors",".ckpt",".pt",".pth",".bin",".gguf",".onnx",".vae",".sft",".ggml",".pkl",".civitai",".safetensors")
SKIP_NONWF = {
    r"D:\BaiduNetdiskDownload\lora训练器\lora-scripts-v1.10.0\assets\config.json",
    r"D:\BaiduNetdiskDownload\lora训练器\lora-scripts-v1.10.0\mikazuki\tsconfig.json",
}

def log(m):
    with open(OUT,"a",encoding="utf-8") as f: f.write(m+"\n")
open(OUT,"w",encoding="utf-8").close()

# ---- 1. discover candidate json files (depth<=3) ----
cands=[]
def walk(d,depth):
    if depth>3 or len(cands)>=2000: return
    try:
        for n in os.listdir(d):
            if len(cands)>=2000: break
            full=os.path.join(d,n)
            try:
                if os.path.isdir(full): walk(full,depth+1)
                elif n.lower().endswith(".json"): cands.append(full)
            except Exception: pass
    except Exception: pass
walk(baidu,0)

# ---- 2. parse each candidate, detect workflow, extract class_types + model refs ----
def is_model_str(s):
    if not isinstance(s,str): return False
    ls=s.lower()
    if ls.endswith(MODEL_EXT): return True
    return False

def collect(node, cts, mrefs):
    """recursively collect class_type/type and model-like strings"""
    if isinstance(node, dict):
        if "class_type" in node and isinstance(node["class_type"],str):
            cts.add(node["class_type"])
        if "type" in node and isinstance(node.get("widgets_values"),list) and isinstance(node["type"],str):
            cts.add(node["type"])
        for k,v in node.items():
            if k in ("widgets_values",):
                if isinstance(v,list):
                    for item in v:
                        if is_model_str(item): mrefs.add(item)
                elif is_model_str(v): mrefs.add(v)
            elif k=="ckpt_name" or k=="lora_name" or k=="unet_name" or k=="vae_name" or k=="clip_name" or k=="control_net_name" or k=="model_name" or k=="model_path" or k=="weight_path" or k=="file" or k=="name":
                if is_model_str(v): mrefs.add(v)
            collect(v,cts,mrefs)
    elif isinstance(node,list):
        for v in node: collect(v,cts,mrefs)

workflows=[]
for p in cands:
    if p in SKIP_NONWF: continue
    try:
        with open(p,"r",encoding="utf-8",errors="ignore") as f: data=json.load(f)
    except Exception as e:
        log(f"# PARSE FAIL {p}: {e}")
        continue
    cts=set(); mrefs=set()
    fmt="?"
    if isinstance(data,dict):
        if any(isinstance(v,dict) and "class_type" in v for v in data.values()):
            fmt="api"
            collect(data,cts,mrefs)
        elif isinstance(data.get("nodes"),list):
            fmt="ui"
            collect(data,cts,mrefs)
    if not cts:
        continue  # not a workflow
    # normalize model refs to basename
    mref_base=set()
    for m in mrefs:
        b=os.path.basename(m.strip())
        if b: mref_base.add(b)
    workflows.append({"path":p,"fmt":fmt,"nodes":len(cts),"cts":cts,"mrefs":mref_base})

# ---- 3. build class_type -> pack map by scanning custom_nodes + core ----
pack_text={}  # packdir(without .disabled) -> text
for name in os.listdir(custom_nodes):
    full=os.path.join(custom_nodes,name)
    if not os.path.isdir(full): continue
    pack=name[:-len(".disabled")] if name.endswith(".disabled") else name
    txt=[]
    if pack not in pack_text: pack_text[pack]=""
    for root,_,files in os.walk(full):
        for fn in files:
            if not fn.endswith(".py"): continue
            fp=os.path.join(root,fn)
            try:
                if os.path.getsize(fp)>3_000_000: continue
                with open(fp,"r",encoding="utf-8",errors="ignore") as f: c=f.read()
                pack_text[pack]+= "\n"+c
            except Exception: pass

core_text=""
try:
    with open(core_nodes,"r",encoding="utf-8",errors="ignore") as f: core_text+=f.read()
except Exception: pass
if os.path.isdir(core_extras):
    for root,_,files in os.walk(core_extras):
        for fn in files:
            if fn.endswith(".py"):
                try:
                    with open(os.path.join(root,fn),"r",encoding="utf-8",errors="ignore") as f: core_text+= "\n"+f.read()
                except Exception: pass

def provider(ct):
    # returns ("builtin",None) or ("pack",packname,"enabled":bool) or ("missing",None)
    if ct in ("","Node"): return ("missing",None)
    if ct in core_text: return ("builtin",None)
    for pack,txt in pack_text.items():
        if ct in txt:
            enabled = not pack.endswith(".disabled") and os.path.isdir(os.path.join(custom_nodes,pack)) and (not pack.endswith(".disabled"))
            # pack key already stripped; enabled = dir exists without .disabled -> we stored stripped name; check actual dir
            actual_disabled = any(d==pack+".disabled" for d in os.listdir(custom_nodes) if os.path.isdir(os.path.join(custom_nodes,d)))
            return ("pack",pack, not actual_disabled)
    return ("missing",None)

# ---- 4. model availability ----
model_files=set()
count=0
for root,_,files in os.walk(models_root):
    for fn in files:
        model_files.add(fn.lower())
        count+=1
        if count>60000: break
    if count>60000: break

# ---- 5. evaluate each workflow ----
def classify(cts):
    ok=set(); need_enable=set(); missing=set(); builtin=set()
    for ct in cts:
        pr=provider(ct)
        if pr[0]=="builtin": builtin.add(ct)
        elif pr[0]=="pack":
            if pr[2]: ok.add(pr[1])
            else: need_enable.add(pr[1])
        else: missing.add(ct)
    return ok,need_enable,missing,builtin

results=[]
for w in workflows:
    ok,need_enable,missing,builtin=classify(w["cts"])
    models_present=set(); models_missing=set()
    for m in w["mrefs"]:
        if m.lower() in model_files: models_present.add(m)
        else: models_missing.add(m)
    results.append({**w,"ok":ok,"need_enable":need_enable,"missing":missing,"mp":models_present,"mm":models_missing})

# ---- 6. output ----
log(f"WORKFLOWS PARSED: {len(results)}")
log(f"MODEL FILES ENUMERATED: {count}")
log("")
for w in sorted(results,key=lambda x:x["path"].lower()):
    p=w["path"]
    short=p.replace(baidu+"\\","")
    log("="*80)
    log(f"FILE: {short}")
    log(f"  format={w['fmt']}  nodes={w['nodes']}")
    if w["cts"]:
        log(f"  class_types({len(w['cts'])}): {', '.join(sorted(w['cts']))[:400]}")
    if w["ok"]: log(f"  [节点OK] 已启用: {', '.join(sorted(w['ok']))}")
    if w["need_enable"]: log(f"  [需启用] 已安装但禁用: {', '.join(sorted(w['need_enable']))}")
    if w["missing"]: log(f"  [缺节点] 未安装/未知: {', '.join(sorted(w['missing']))[:300]}")
    if w["mp"]: log(f"  [模型OK] {', '.join(sorted(w['mp']))[:300]}")
    if w["mm"]: log(f"  [缺模型] {', '.join(sorted(w['mm']))[:300]}")
    # verdict
    if w["missing"]: v="缺节点(未安装)"
    elif w["need_enable"]: v="需启用节点"
    elif w["mm"]: v="缺模型"
    else: v="本机可运行"
    log(f"  >>> 结论: {v}")
    log("")

# summary
log("")
log("#"*80)
log("# SUMMARY")
log("#"*80)
def grp(v): return [r for r in results if (r["missing"] and v=="缺节点(未安装)") or (not r["missing"] and r["need_enable"] and v=="需启用节点") or (not r["missing"] and not r["need_enable"] and r["mm"] and v=="缺模型") or (not r["missing"] and not r["need_enable"] and not r["mm"] and v=="本机可运行")]
for v in ["本机可运行","需启用节点","缺模型","缺节点(未安装)"]:
    items=grp(v)
    log(f"\n## {v}  ({len(items)})")
    for r in sorted(items,key=lambda x:x["path"].lower()):
        log(f"  - {r['path'].replace(baidu+'\\\\','')}")
print("DONE", len(results))
