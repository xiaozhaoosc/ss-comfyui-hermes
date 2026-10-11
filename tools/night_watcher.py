#!/usr/bin/env python3
"""全自动批量执行器：处理目录及续传工作流

现在禁用出错的前端功能.py no longer needs symlinks!-
成功运行基于你下面调用，
但必选退出码（`--`或`-`模式）保留后续所有操作可执行
每个任务都是独立的独立通用操作.
单文件版本：使用 windows 转换器，适用于任何情况（UTF-8、PNG 或 GIF 插件）
"""
import json, urllib.request, uuid, time, os, sys, shutil, subprocess, tempfile, logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("night_watcher")

BASE = "http://127.0.0.1:8188"
WORKDIR = r"D:\ai_projects\ComfyUI"
OUT_DIR = os.path.join(WORKDIR, "output")
INPUT_DIR = os.path.join(WORKDIR, "input")

def safe_path(p):
    return str(Path(p.replace('/', os.sep)).abs())

class SafeExecutor:
    def __init__(self, mode="safe"):
        self.mode = mode
        self.pending_results = []

    def submit_task(self, wf, name):
        payload = {"prompt": wf, "client_id": str(uuid.uuid4())}
        req = urllib.request.Request(f"{BASE}/prompt", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=60).read())
            log.info(f"✓ {name} submitted PID={r['prompt_id'][:13]}")
            return True
        except Exception as e:
            log.error(f"✗ {name} 提交失败: {e}")
            return False

    def process_batch_data(data, name_prefix, opt_flag=False):
        pass

    def _build_seg2_workflow(self):
        return {
            "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
            "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors", "type": "minimax"}},
            "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
            "4": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["1", 0], "shift_video": 12.0, "shift_audio": 3.0}},
            "9": {"class_type": "LoadImage", "inputs": {"image": "seg1_lastframe.png"}},
            "5": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
                "clip": ["2", 0], "vae": ["3", 0], "prompt": SEG2_EN,
                "width": 960, "height": 544, "length": 124, "first_frame": ["9", 0]}},
            "6": {"class_type": "KSampler", "inputs": {
                "model": ["4", 0], "seed": 20260831, "steps": 28, "cfg": 1.0,
                "sampler_name": "euler", "scheduler": "simple",
                "positive": ["5", 0], "negative": ["5", 0], "latent_image": ["5", 1], "denoise": 1.0}},
            "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["3", 0]}},
            "8": {"class_type": "VHS_VideoCombine", "inputs": {
                "images": ["7", 0], "frame_rate": 24.0, "loop_count": 0,
                "filename_prefix": "gufeng_2segs/seg2", "format": "video/h264-mp4"}}}

def main():
    now = time.strftime("%H:%M:%S")
    print(f"🌙 Night Watcher Active ({now})")

    if len(sys.argv) < 2:
        print("Usage: python tools/night_watcher.py --again|--live|--then")
        sys.exit(1)

    action = sys.argv[1]
    executor = SafeExecutor()

    # Check current state
    current_state = None
    try:
        q = json.loads(urllib.request.urlopen(f"{BASE}/queue", timeout=5).read())
        current_state = "running" if q.get("queue_running") else "idle"
    except Exception:
        current_state = "started"

    log.info(f"Current state: {current_state}")

    if action in ["--again", "reset"]:
        print("\n=== 第 1 层：继续已提交的任务 ===")
        # Re-submit seg2 temporarily if PID was confirmed working
        if action == "--again":
            executor.submit_task(executor._build_seg2_workflow(), "seg2")
    else:
        print("\n=== 第 2 层：等待翻译完成 ===")
        start = time.time()
        while not check_translation_done() and time.time() - start < 3600:
            # Only runs when queue is empty AND ops needed
            time.sleep(120)
        if check_translation_done():
            print("\n✅ 翻译完成，开始英文写真批量...")
            executor.submit_task(executor._build_seg2_workflow(), "seg2")
            # Loop continues...
        else:
            print("❌ 翻译超时")

def check_translation_done():
    """检查：翻译目录下所有 6 个 _en.json 合共 ≥ 80 条"""
    d = r"D:\obsidian\obsidian\ComfyUI\50写真批次prompts\en"
    total = 0
    if not os.path.exists(d): return False
    for f in os.listdir(d):
        if f.endswith("_en.json"):
            data = json.load(open(os.path.join(d, f), encoding='utf-8'))
            total += len(data)
    return total >= 250

def merge_videos(segs, output):
    try:
        output_dir = os.path.dirname(output)
        real_out = output if output.endswith(".mp4") else f"{safe_path(output)}_out.mp4"
        tmp = tempfile.mkdtemp(prefix="vm_")
        file_list = []
        for seg in segs:
            file_list.append(f"file '{seg.replace(os.sep, '/')}'")
        listfile = os.path.join(tmp, "list.txt")
        with open(listfile, 'w') as f:
            f.write("\n".join(file_list))
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile, "-c", "copy", real_out]
        r = subprocess.run(cmd, capture_output=True, text=True)
        shutil.rmtree(tmp, ignore_errors=True)
        if os.path.exists(real_out):
            log.info(f"✓ 合并完成: {real_out}")
            return True
        else:
            log.error(f"✗ Merge Failed: {r.stderr[-200:]}")
            return False
    except Exception as e:
        log.error(f"✗ Merging failed: {e}")
        return False

SEG2_EN = ("Close-up medium shot, young East Asian woman, twin braids, dancing, "
           "purple strapless brocade dress, purple gauze robe, black lace thigh-high socks, "
           "elegant flowing movements, hands making graceful gestures, turning, smiling. "
           "Classical Chinese courtyard, wooden lattice windows, purple wisteria flowers, "
           "soft bright light, high saturation, real photography, ultra detail")

if __name__ == '__main__':
    main()