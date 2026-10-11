# -*- coding: utf-8 -*-
"""串行跑「同一组提示词 × 多模型」对比矩阵。

四个档位（同一套 _pc_prompts.SCENES 场景，仅换底模/采样参数）：
  z_image_turbo      Z-Image Turbo bf16      8步  / cfg 1.0 / 1024²
  flux_dev_fp8       Flux.1 Dev FP8         20步  / guidance 3.5 / 768²
  majicmix           SD1.5 majicmixRealistic 30步 / cfg 7.0 / 512×768
  sdxl_realvis       SDXL RealVisXL_V4.0     30步 / cfg 5.5 / 1024²

产物统一落 output/YYYY-MM-DD_wb/<model>/。
用法：python tools/_pc_run_matrix.py [--only zimage,flux] [--scenes s01_x,s02_y]
"""
import os, sys, time, subprocess, io

BASE = r"D:\ai_projects\ComfyUI"
PY = sys.executable
LOG = os.path.join(BASE, "_pc_matrix_log.txt")
DAY = time.strftime("%Y-%m-%d") + "_wb"

MATRIX = [
    ("z_image_turbo", ["tools/_pc_gen.py"]),
    ("flux_dev_fp8", ["tools/_pc_gen.py", "--backend", "flux", "fp8",
                      "--outdir", "output/%s/flux_dev_fp8" % DAY]),
    ("majicmix", ["tools/_pc_gen.py", "--backend", "sd15",
                  "majicmixRealistic_v7.safetensors", "majicmix",
                  "--outdir", "output/%s/majicmix" % DAY]),
    ("sdxl_realvis", ["tools/_pc_gen.py", "--backend", "sd15",
                      "RealVisXL_V4.0.safetensors", "sdxl_realvis",
                      "--outdir", "output/%s/sdxl_realvis" % DAY]),
]

LOGBUF = []


def log(m):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), m)
    LOGBUF.append(line)
    try:
        with io.open(LOG, "w", encoding="utf-8") as f:
            f.write("\n".join(LOGBUF))
    except Exception:
        pass


def main():
    only = None
    scenes = []
    a = sys.argv
    for i, tok in enumerate(a):
        if tok == "--only" and i + 1 < len(a):
            only = set(x.strip() for x in a[i + 1].split(",") if x.strip())
        if tok == "--scenes" and i + 1 < len(a):
            scenes = ["--scenes", a[i + 1]]

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"

    t_all = time.time()
    summary = []
    for name, cmd in MATRIX:
        if only and name not in only:
            log("SKIP %s" % name)
            continue
        full = [PY] + cmd + scenes
        log("=== START %s : %s" % (name, " ".join(cmd + scenes)))
        t0 = time.time()
        try:
            r = subprocess.run(full, cwd=BASE, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", env=env, timeout=7200)
            tail = (r.stdout or "").strip().splitlines()[-12:]
            for ln in tail:
                log("   | %s" % ln)
            if r.returncode != 0:
                err = (r.stderr or "").strip().splitlines()[-8:]
                for ln in err:
                    log("   ! %s" % ln)
        except subprocess.TimeoutExpired:
            log("   ! TIMEOUT after 2h")
        dt = time.time() - t0
        summary.append((name, dt))
        log("=== DONE %s in %.1f min" % (name, dt / 60.0))

    log("")
    log("=== 矩阵完成，总耗时 %.1f 分钟 ===" % ((time.time() - t_all) / 60.0))
    for n, d in summary:
        log("   %-16s %.1f min" % (n, d / 60.0))


if __name__ == "__main__":
    main()
