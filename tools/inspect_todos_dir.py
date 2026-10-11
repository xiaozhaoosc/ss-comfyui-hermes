import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

p = r"d:\ai_projects\ComfyUI\todos\北宋杨家将"
print(f"Path: {p}")
for root, dirs, files in os.walk(p):
    rel = os.path.relpath(root, p)
    indent = "  " * (rel.count(os.sep) if rel != "." else 0)
    print(f"{indent}[DIR] {os.path.basename(root)}/")
    for f in files:
        print(f"{indent}  - {f}")
