import json
import os

with open('user/default/workflows/motion_transfer_wan_animate_multichunk_full_ui.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

print("=== Nodes in motion_transfer_wan_animate_multichunk_full_ui.json ===")
for n in d['nodes']:
    print(f"ID {n['id']:3d} | {n['type']:25s} | {n.get('title')}")
    if n['id'] in [10, 12, 13, 14, 22, 23, 24, 25, 101, 201, 301, 401, 510]:
        print(f"       inputs: {n.get('inputs')}")
        print(f"       widgets: {n.get('widgets_values')}")

# Also check latest files in output/2026-10-09
out_dir = 'output/2026-10-09'
print(f"\n=== Files in {out_dir} ===")
for root, dirs, files in os.walk(out_dir):
    for f in files:
        if f.endswith('.mp4'):
            p = os.path.join(root, f)
            print(f"  {p} ({os.path.getsize(p)/1024/1024:.2f}MB, modified {os.path.getmtime(p)})")
