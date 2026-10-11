import os

for root, dirs, files in os.walk(r'd:\ai_projects\ComfyUI'):
    if any(p in root for p in ['.git', 'models', 'output', 'venv', 'input']):
        continue
    for f in files:
        if f.endswith('.py'):
            p = os.path.join(root, f)
            try:
                with open(p, 'r', encoding='utf-8', errors='ignore') as fp:
                    content = fp.read()
                    if 'WanAnimateToVideo' in content:
                        print('Found in:', p)
            except Exception:
                pass
