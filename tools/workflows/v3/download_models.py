import os
import sys
import subprocess

sys.stdout.reconfigure(encoding='utf-8')

comfy_root = r"d:\ai_projects\ComfyUI"

# List of models to download (fully verified working URLs)
models_to_download = [
    # 1. Checkpoint - DreamShaper 8
    {
        "subfolder": "checkpoints",
        "filename": "dreamshaper_8.safetensors",
        "url": "https://modelscope.cn/api/v1/models/sd_lora/dreamshaper_8/repo?Revision=master&FilePath=dreamshaper_8.safetensors"
    },
    # 2. ControlNets (ModelScope ControlNet-v1-1)
    {
        "subfolder": "controlnet",
        "filename": "control_v11p_sd15_canny.pth",
        "url": "https://modelscope.cn/api/v1/models/lllyasviel/ControlNet-v1-1/repo?Revision=master&FilePath=control_v11p_sd15_canny.pth"
    },
    {
        "subfolder": "controlnet",
        "filename": "control_sd15_depth.pth",
        "url": "https://modelscope.cn/api/v1/models/lllyasviel/ControlNet-v1-1/repo?Revision=master&FilePath=control_v11f1p_sd15_depth.pth"
    },
    {
        "subfolder": "controlnet",
        "filename": "control_sd15_random_color.pth",
        "url": "https://modelscope.cn/api/v1/models/lllyasviel/ControlNet-v1-1/repo?Revision=master&FilePath=control_v11p_sd15_scribble.pth"
    },
    # 3. IP-Adapter
    {
        "subfolder": "ipadapter",
        "filename": "ip-adapter-plus_sd15.bin",
        "url": "https://hf-mirror.com/h94/IP-Adapter/resolve/main/models/ip-adapter-plus_sd15.bin"
    },
    # 4. DWPose ONNX dependency
    {
        "subfolder": "onnx",
        "filename": "yolox_l.onnx",
        "url": "https://hf-mirror.com/yzd-v/DWPose/resolve/main/yolox_l.onnx"
    },
    {
        "subfolder": "onnx",
        "filename": "dw-ll_ucoco_384.onnx",
        "url": "https://hf-mirror.com/yzd-v/DWPose/resolve/main/dw-ll_ucoco_384.onnx"
    }
]

def print_log(msg):
    print(msg)
    sys.stdout.flush()

def download_model(item):
    subfolder = item["subfolder"]
    filename = item["filename"]
    url = item["url"]
    
    target_dir = os.path.join(comfy_root, "models", subfolder)
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)
        
    target_path = os.path.join(target_dir, filename)
    
    # Check if exists and is valid
    if os.path.exists(target_path):
        size = os.path.getsize(target_path)
        if size >= 1024 * 1024: # Must be larger than 1MB to be considered a model
            print_log(f"🟢 [EXISTS] {filename} is already downloaded and valid ({size / (1024*1024):.2f} MB).")
            return True
        else:
            print_log(f"🧹 [CLEANUP] Removing invalid tiny file: {filename}")
            os.remove(target_path)
            
    print_log(f"\n⏳ Downloading {filename} to {target_dir}...")
    
    # Try resume download first with curl -C -
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
        # Run curl synchronously for this item (downloading sequentially is safer for disk IO)
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
                print_log(f"❌ [FAILED] Curl failed for {filename}. Stderr: {res_fresh.stderr}")
                return False
            
        # Check size validation
        if os.path.exists(target_path):
            size = os.path.getsize(target_path)
            if size < 1024 * 1024:
                # Read content for debugging
                with open(target_path, 'r', errors='ignore') as f:
                    content = f.read(200).strip()
                print_log(f"⚠️ [WARNING] Downloaded file is too small ({size} bytes). Removing. Content snippet: {content}")
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
    print_log("=== ComfyUI FaceSwap Workflow Model Downloader ===")
    print_log("Notice: The three private LoRAs (FilmPortrait, fuqiface, add_detail) are skipped")
    print_log("because they require private HF auth. They are already bypassed in the v3 workflow fallback.")
    
    success_count = 0
    fail_count = 0
    
    for item in models_to_download:
        ok = download_model(item)
        if ok:
            success_count += 1
        else:
            fail_count += 1
            
    print_log(f"\n🎉 Download process finished! Success: {success_count}, Fail/Skipped: {fail_count}")

if __name__ == '__main__':
    main()
