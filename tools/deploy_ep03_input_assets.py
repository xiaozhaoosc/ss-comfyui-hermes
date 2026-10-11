import os
import shutil

def deploy():
    src_dir = os.path.abspath("input/yang_ep03")
    target_dir = os.path.abspath("input")
    
    files = [f for f in os.listdir(src_dir) if f.startswith("yang_ep03_shot") and f.endswith(".jpg")]
    print(f"Deploying {len(files)} shots to root input/ directory...")
    for f in sorted(files):
        src = os.path.join(src_dir, f)
        dst = os.path.join(target_dir, f)
        shutil.copy2(src, dst)
        
    print(f"[√] Successfully deployed all 54 shots to {target_dir}!")

if __name__ == "__main__":
    deploy()
