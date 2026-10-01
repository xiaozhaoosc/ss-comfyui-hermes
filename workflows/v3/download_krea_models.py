import os
import sys
import subprocess

sys.stdout.reconfigure(encoding='utf-8')

comfy_root = r"d:\ai_projects\ComfyUI"

models_to_download = [
    # 1. Text Encoder & VAE (ModelScope Comfy-Org/Krea-2)
    {
        "subfolder": "clip",
        "filename": "qwen3vl_4b_fp8_scaled.safetensors",
        "url": "https://modelscope.cn/api/v1/models/Comfy-Org/Krea-2/repo?Revision=master&FilePath=text_encoders/qwen3vl_4b_fp8_scaled.safetensors"
    },
    {
        "subfolder": "vae",
        "filename": "qwen_image_vae.safetensors",
        "url": "https://modelscope.cn/api/v1/models/Comfy-Org/Krea-2/repo?Revision=master&FilePath=vae/qwen_image_vae.safetensors"
    },
    # 2. Scheme A: Native FP8 UNet
    {
        "subfolder": "unet",
        "filename": "krea2_turbo_fp8_scaled.safetensors",
        "url": "https://modelscope.cn/api/v1/models/Comfy-Org/Krea-2/repo?Revision=master&FilePath=diffusion_models/krea2_turbo_fp8_scaled.safetensors"
    },
    # 3. Scheme B: GGUF UNet
    {
        "subfolder": "unet",
        "filename": "Krea-2-Turbo-Q8_0.gguf",
        "url": "https://modelscope.cn/api/v1/models/Abiray/Krea-2-Turbo-GGUF/repo?Revision=master&FilePath=Krea-2-Turbo-Q8_0.gguf"
    },
    # 4. Official Workflow JSON (stored in workflows/v3)
    {
        "custom_dir": os.path.join(comfy_root, "workflows", "v3"),
        "filename": "Rebels KREA-2-TURBO.json",
        "url": "https://modelscope.cn/api/v1/models/Abiray/Krea-2-Turbo-GGUF/repo?Revision=master&FilePath=Rebels%20KREA-2-TURBO.json"
    }
]

def print_log(msg):
    print(msg)
    sys.stdout.flush()

def download_item(item):
    filename = item["filename"]
    url = item["url"]
    
    if "custom_dir" in item:
        target_dir = item["custom_dir"]
    else:
        # We need to map directories to ComfyUI standard:
        # clip -> models/clip or models/text_encoders
        # unet -> models/unet or models/diffusion_models
        # Let's map dynamically:
        sub = item["subfolder"]
        if sub == "clip":
            target_dir = os.path.join(comfy_root, "models", "text_encoders")
        elif sub == "unet":
            target_dir = os.path.join(comfy_root, "models", "diffusion_models")
        else:
            target_dir = os.path.join(comfy_root, "models", sub)
        
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)
        
    target_path = os.path.join(target_dir, filename)
    
    # Check if exists and is valid
    min_valid_size = 10 * 1024 * 1024 if "custom_dir" not in item else 1024
    if os.path.exists(target_path):
        size = os.path.getsize(target_path)
        if size >= min_valid_size:
            print_log(f"🟢 [EXISTS] {filename} is already downloaded and valid ({size / (1024*1024):.2f} MB).")
            return True
        else:
            print_log(f"🧹 [CLEANUP] Removing invalid tiny file: {filename}")
            os.remove(target_path)
            
    print_log(f"\n⏳ Downloading {filename} to {target_dir}...")
    
    # Resume download with curl -C -
    cmd = [
        "curl.exe",
        "-C", "-",
        "-L",
        "--connect-timeout", "20",
        "--retry", "3",
        "-o", target_path,
        url
    ]
    
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')
        if res.returncode != 0:
            print_log(f"⚠️ [RESUME_FAILED] Resuming download failed for {filename}. Retrying with fresh download...")
            if os.path.exists(target_path):
                os.remove(target_path)
            
            cmd_fresh = [
                "curl.exe",
                "-L",
                "--connect-timeout", "20",
                "--retry", "3",
                "-o", target_path,
                url
            ]
            res_fresh = subprocess.run(cmd_fresh, capture_output=True, text=True, errors='ignore')
            if res_fresh.returncode != 0:
                print_log(f"❌ [FAILED] Fresh download failed for {filename}. Stderr: {res_fresh.stderr}")
                return False
                
        # Final validation
        if os.path.exists(target_path):
            size = os.path.getsize(target_path)
            if size < min_valid_size:
                with open(target_path, 'r', errors='ignore') as f:
                    content = f.read(200).strip()
                print_log(f"⚠️ [WARNING] Downloaded file is too small ({size} bytes). Removing. Content: {content}")
                os.remove(target_path)
                return False
            else:
                print_log(f"✅ [SUCCESS] Downloaded {filename} successfully ({size / (1024*1024):.2f} MB).")
                return True
        else:
            print_log(f"❌ [FAILED] File not found after curl exit for {filename}")
            return False
            
    except Exception as e:
        print_log(f"❌ [ERROR] Exception occurred during download of {filename}: {e}")
        if os.path.exists(target_path):
            os.remove(target_path)
        return False

def main():
    print_log("=== ComfyUI Krea-2 & Qwen3-VL Model Downloader (ModelScope Edition) ===")
    success_count = 0
    fail_count = 0
    
    for item in models_to_download:
        ok = download_item(item)
        if ok:
            success_count += 1
        else:
            fail_count += 1
            
    print_log(f"\n🎉 Download process finished! Success: {success_count}, Fail/Skipped: {fail_count}")

if __name__ == '__main__':
    main()
