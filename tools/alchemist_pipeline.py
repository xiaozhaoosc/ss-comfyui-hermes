# -*- coding: utf-8 -*-
"""无人值守炼丹流水线（Windows 任务计划 2026-09-09 02:00 触发）
流程: 防重入 → 等底模下载完成 → 释放ComfyUI显存 → 打标组装数据集 → 启动训练 → 验证 → 等完成 → 归档LoRA
日志: D:\ai_projects\ai-toolkit\pipeline_log.txt（训练日志: train_log.txt）
"""
import glob, json, os, shutil, subprocess, time, urllib.request

VENV_PY = r"D:\ai_projects\ComfyUI\venv\Scripts\python.exe"
TOOLKIT = r"D:\ai_projects\ai-toolkit"
COMFY = r"D:\ai_projects\ComfyUI"
COMFY_HOST = "http://127.0.0.1:8188"
HUB_MODEL_DIR = r"D:\AI_Cache\huggingface\hub\models--black-forest-labs--FLUX.1-dev"
TRAIN_OUT = os.path.join(TOOLKIT, "output", "my_flux_lora_v1")
DATASET = os.path.join(TOOLKIT, "my_dataset")
LOG = os.path.join(TOOLKIT, "pipeline_log.txt")
TRAIN_LOG = os.path.join(TOOLKIT, "train_log.txt")
DL_LOG = os.path.join(TOOLKIT, "download_log.txt")
COMFY_LORAS = os.path.join(COMFY, "models", "loras")
DL_SCRIPT = os.path.join(COMFY, "tools", "download_flux_dev.py")
ASSEMBLE = os.path.join(COMFY, "tools", "assemble_lora_dataset.py")

DETACHED = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP


def log(msg):
    line = "[%s] %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def model_ready():
    """Windows 无符号链接模式下 HF 缓存文件直存 snapshots/，而非 blobs/。
    校验关键组件: transformer(>=20GB) + text_encoder_2(>=8GB) + vae。"""
    import glob as _g
    snaps = _g.glob(os.path.join(HUB_MODEL_DIR, "snapshots", "*"))
    for snap in snaps:
        def dir_gb(sub):
            d = os.path.join(snap, sub)
            if not os.path.isdir(d):
                return 0.0
            return sum(os.path.getsize(os.path.join(d, f)) for f in os.listdir(d)
                        if not f.endswith((".incomplete", ".lock"))) / 1e9
        if dir_gb("transformer") >= 20 and dir_gb("text_encoder_2") >= 8 and dir_gb("vae") > 0.05:
            return dir_gb("transformer") + dir_gb("text_encoder_2") + dir_gb("text_encoder") + dir_gb("vae")
    return 0.0


def py_procs_running(keyword):
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\").CommandLine"],
            capture_output=True, text=True, timeout=30).stdout or ""
        return keyword in out
    except Exception:
        return False


def free_comfy_vram():
    try:
        req = urllib.request.Request(
            COMFY_HOST + "/free",
            data=json.dumps({"unload_models": True, "free_memory": True}).encode(),
            headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=20)
        log("ComfyUI VRAM released (/free)")
    except Exception as e:
        log(f"ComfyUI /free skipped (possibly not running): {e}")


def main():
    log("=== 炼丹流水线启动 ===")
    # 0) 防重入
    if glob.glob(os.path.join(TRAIN_OUT, "*.safetensors")):
        log("训练已完成过，直接退出")
        return
    if py_procs_running("run.py"):
        log("训练进程已在运行，直接退出")
        return

    # 1) 等待门控底模下载完成（最多再等3小时，下载挂了自动重启）
    t0 = time.time()
    restarts = 0
    while model_ready() <= 0:
        if time.time() - t0 > 3 * 3600:
            log(f"FATAL: 底模下载超时（未就绪），退出")
            return
        if not py_procs_running("download_flux_dev"):
            restarts += 1
            if restarts > 10:
                log("FATAL: 下载重启超过10次仍未就绪，退出")
                return
            log("下载进程不在运行，重启下载...")
            dlog = open(DL_LOG, "a", encoding="utf-8")
            subprocess.Popen([VENV_PY, DL_SCRIPT, "https://huggingface.co"],
                            creationflags=DETACHED, stdout=dlog,
                            stderr=subprocess.STDOUT, close_fds=True)
        time.sleep(60)
    log(f"底模就位: {model_ready():.1f}GB")

    # 2) 释放 ComfyUI 显存（否则16G卡训练必爆）
    free_comfy_vram()

    # 3) 打标 + 组装数据集
    try:
        r = subprocess.run([VENV_PY, ASSEMBLE], capture_output=True, text=True, timeout=600)
        log("assemble rc=%d | %s" % (r.returncode, (r.stdout or "").strip().replace("\n", " | ")[:500]))
    except Exception as e:
        log(f"FATAL: assemble 执行异常 {e}")
        return
    pngs = glob.glob(os.path.join(DATASET, "*.png"))
    txts = glob.glob(os.path.join(DATASET, "*.txt"))
    if len(pngs) < 40 or len(pngs) != len(txts):
        log(f"FATAL: 数据集配对异常 png={len(pngs)} txt={len(txts)}，退出")
        return
    log(f"数据集就绪: {len(pngs)} 对")

    # 4) 启动训练（独立进程，日志重定向）。早退自动重试（显存被 ComfyUI 挤占会导致 0xC0000005 崩溃, 重试前再 /free）
    env = os.environ.copy()
    env["HF_ENDPOINT"] = "https://huggingface.co"
    env["HF_HUB_DISABLE_XET"] = "1"
    env["PYTHONUNBUFFERED"] = "1"  # 关键: 否则 stdout 块缓冲, train_log 长时间不增长, 看门狗会误杀正常训练
    proc = None
    for attempt in range(1, 4):  # 最多 3 次
        free_comfy_vram()  # 每次(重)启动前都释放, 防止 ComfyUI 重新占了显存
        logf = open(TRAIN_LOG, "w", encoding="utf-8")
        proc = subprocess.Popen([VENV_PY, "run.py", os.path.join("config", "my_flux_lora.yaml")],
                                cwd=TOOLKIT, stdout=logf, stderr=subprocess.STDOUT,
                                env=env, creationflags=DETACHED)
        log(f"训练已启动 pid={proc.pid} (第{attempt}次)")

        # 5) 启动验证（4分钟后进程应存活）
        time.sleep(240)
        if proc.poll() is None:
            break  # 存活, 进入监控
        tail = ""
        try:
            tail = open(TRAIN_LOG, "r", encoding="utf-8", errors="replace").read()[-600:]
        except OSError:
            pass
        log(f"训练进程早退 rc={proc.returncode} (第{attempt}次)。日志末尾: {tail[:300]}")
        time.sleep(30)  # 给系统喘口气再重试
    else:
        log("FATAL: 训练 3 次尝试均早退，放弃。请检查 train_log.txt")
        return
    log("启动验证通过：进程存活（4分钟）")

    # 6) 等训练完成（2000步约2-3小时，上限6小时）
    t0 = time.time()
    last_log_size = -1
    last_progress_t = time.time()
    while time.time() - t0 < 6 * 3600:
        time.sleep(300)
        # 记录显存占用 (诊断用, 也作为看门狗辅助判活信号)
        vram_mib = 0
        try:
            vram_out = subprocess.run(
                ["C:\\Windows\\System32\\nvidia-smi.exe",
                 "--query-gpu=memory.used", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=15).stdout.strip()
            vram_mib = int("".join(ch for ch in vram_out if ch.isdigit()) or 0)
        except Exception:
            pass
        if proc.poll() is not None:
            break
        # 看门狗: 日志 40 分钟无增长 且 显存 <8GB 才判挂死。
        # (显存 >8GB 说明模型驻 GPU 正常训练, 可能只是缓冲没刷; 真正停驻 CPU 时显存会掉下来)
        try:
            size = os.path.getsize(TRAIN_LOG)
        except OSError:
            size = 0
        if size > last_log_size + 1024:
            last_log_size = size
            last_progress_t = time.time()
        elif time.time() - last_progress_t > 40 * 60:
            if vram_mib >= 8192:
                log(f"看门狗放行: 日志未增长但 VRAM={vram_mib}MiB (模型在GPU工作, 判定为缓冲未刷)")
                last_progress_t = time.time()  # 重置计时, 继续观察
            else:
                log(f"FATAL: train_log 40分钟无进展 且 VRAM={vram_mib}MiB，疑似模型停驻CPU，杀掉训练进程")
                proc.kill()
                return
        log(f"监控: 进程存活, VRAM={vram_mib}MiB, log={size/1e6:.1f}MB, 已等待{(time.time()-t0)/60:.0f}分钟")
    if proc.poll() is None:
        log("WARNING: 6小时未完成，停止等待（训练进程继续在后台跑）")
        return
    log(f"训练进程结束 rc={proc.returncode}")

    # 7) 归档 LoRA 到 ComfyUI
    cands = glob.glob(os.path.join(TRAIN_OUT, "*.safetensors"))
    if not cands:
        cands = glob.glob(os.path.join(TRAIN_OUT, "**", "*.safetensors"), recursive=True)
    if cands:
        src = max(cands, key=os.path.getmtime)
        dst = os.path.join(COMFY_LORAS, os.path.basename(src))
        try:
            shutil.copy2(src, dst)
            log(f"LoRA 已归档: {src} -> {dst} ({os.path.getsize(src)/1e6:.1f}MB)")
        except Exception as e:
            log(f"归档失败: {e}")
    else:
        log("WARNING: 训练结束但未找到 safetensors 产物")
    log("=== 炼丹流水线结束 ===")


if __name__ == "__main__":
    main()