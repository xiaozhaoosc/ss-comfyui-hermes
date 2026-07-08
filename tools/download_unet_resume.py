import os, sys, time, signal

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

def handler(sig, frame):
    print("\n[!] Interrupted by user")
    sys.exit(1)
signal.signal(signal.SIGINT, handler)

MODEL_ID = "imaginairy/idm-vton-safetensors"
FILENAME = "unet/diffusion_pytorch_model.fp16.safetensors"
DEST = os.path.join("models", "IDM-VTON", "unet", "diffusion_pytorch_model.safetensors")

os.makedirs(os.path.dirname(DEST), exist_ok=True)

print(f"[*] Downloading {FILENAME} from {MODEL_ID}")
print(f"[*] Destination: {DEST}")
print(f"[*] Using hf-mirror.com with resume support")
print(f"[*] Press Ctrl+C to stop (resume later)")
print()

from huggingface_hub import hf_hub_download

try:
    path = hf_hub_download(
        repo_id=MODEL_ID,
        filename=FILENAME,
        local_dir="models/IDM-VTON",
        local_dir_use_symlinks=False,
        resume_download=True,
    )
    print(f"\n[OK] Downloaded to: {path}")
    # Rename to expected filename
    final = os.path.join("models", "IDM-VTON", "unet", "diffusion_pytorch_model.safetensors")
    if path != final:
        os.replace(path, final)
        print(f"[OK] Renamed to: {final}")
    
    # Verify size
    sz = os.path.getsize(final)
    print(f"[OK] File size: {sz/1e9:.2f} GB")
    print("[DONE] Ready for IDM-VTON inference!")
except KeyboardInterrupt:
    print("\n[!] Download interrupted. Resume by running this script again.")
    sys.exit(1)
except Exception as e:
    print(f"\n[ERR] {e}")
    sys.exit(1)
