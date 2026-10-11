import os, json, sys

OUT = r"D:/ai_projects/ComfyUI/_wf_scan.txt"
baidu = r"D:\BaiduNetdiskDownload"
cn = r"D:\ai_projects\ComfyUI\custom_nodes"
models_root = r"D:\ai_projects\ComfyUI\models"  # junction -> D:\OLLAMA_MODELS\models

def log(msg):
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

# fresh file
open(OUT, "w", encoding="utf-8").close()

# 1) top-level listing of BaiduNetdiskDownload
log("=== BaiduNetdiskDownload TOP LEVEL ===")
try:
    items = sorted(os.listdir(baidu))
    log(f"(total entries at top: {len(items)})")
    for n in items[:600]:
        full = os.path.join(baidu, n)
        try:
            isdir = os.path.isdir(full)
            sz = os.path.getsize(full) if not isdir else 0
            log(f"{'D' if isdir else 'F'}  {n}  {sz}")
        except Exception as e:
            log(f"?  {n}  {e}")
except Exception as e:
    log(f"ERR listing baidu: {e}")

# 2) bounded JSON discovery (ComfyUI workflows are .json)
log("")
log("=== JSON files found (depth<=3, cap 1500) ===")
found = []
def walk(d, depth):
    if depth > 3 or len(found) >= 1500:
        return
    try:
        for n in os.listdir(d):
            if len(found) >= 1500:
                break
            full = os.path.join(d, n)
            try:
                if os.path.isdir(full):
                    walk(full, depth + 1)
                elif n.lower().endswith(".json"):
                    found.append(full)
            except Exception:
                pass
    except Exception:
        pass
walk(baidu, 0)
log(f"(json files found: {len(found)})")
for p in found:
    try:
        sz = os.path.getsize(p)
    except Exception:
        sz = -1
    log(f"{sz}  {p}")

# 3) custom_nodes enabled/disabled
log("")
log("=== custom_nodes (enabled vs .disabled) ===")
try:
    for n in sorted(os.listdir(cn)):
        full = os.path.join(cn, n)
        if not os.path.isdir(full):
            continue
        disabled = n.endswith(".disabled")
        log(f"{'OFF' if disabled else 'ON '}  {n}")
except Exception as e:
    log(f"ERR listing custom_nodes: {e}")

# 4) model type dirs (top-level under models junction)
log("")
log("=== models top-level dirs ===")
try:
    for n in sorted(os.listdir(models_root)):
        full = os.path.join(models_root, n)
        try:
            isdir = os.path.isdir(full)
            log(f"{'D' if isdir else 'F'}  {n}")
        except Exception as e:
            log(f"?  {n}  {e}")
except Exception as e:
    log(f"ERR listing models: {e}")

log("")
log("=== DONE ===")
print("OK wrote", OUT)
