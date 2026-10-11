"""Download Flux Klein Face Swap models - fixed absolute paths."""
import os, sys
os.environ.pop('HF_ENDPOINT', None)

from huggingface_hub import hf_hub_download, login

token = open(os.path.expanduser('~/.cache/huggingface/token')).read().strip()
login(token=token)

BASE = r'D:\ai_projects\ComfyUI\models'

MODELS = [
    ('Comfy-Org/flux2-klein-9B', 'split_files/text_encoders/qwen_3_8b.safetensors', os.path.join(BASE, 'text_encoders')),
    ('Comfy-Org/flux2-dev', 'split_files/vae/flux2-vae.safetensors', os.path.join(BASE, 'vae')),
    ('unsloth/FLUX.2-klein-9B-GGUF', 'flux-2-klein-9b-Q4_K_M.gguf', os.path.join(BASE, 'diffusion_models')),
]

for repo, fname, ldir in MODELS:
    target = os.path.join(ldir, os.path.basename(fname))
    if os.path.exists(target):
        sz = os.path.getsize(target) / (1024**3)
        if sz > 0.1:
            print(f'[SKIP] {target} ({sz:.1f} GB)')
            continue

    print(f'\n=== {os.path.basename(fname)} from {repo} ===', flush=True)
    try:
        result = hf_hub_download(
            repo_id=repo,
            filename=fname,
            local_dir=ldir,
            token=token,
        )
        sz = os.path.getsize(result) / (1024**3)
        print(f'[OK] {result} ({sz:.1f} GB)')
    except Exception as e:
        print(f'[ERROR] {e}')

print('\nDone!')
