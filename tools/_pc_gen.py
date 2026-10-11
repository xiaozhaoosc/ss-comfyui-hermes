# -*- coding: utf-8 -*-
"""统一出图入口。默认后端 = zimage（Z-Image Turbo）。

Usage:
  python tools/_pc_gen.py                                  # 默认档：Z-Image，跑全部场景
  python tools/_pc_gen.py --scenes s01_camisole_touch_hair # 只跑指定场景
  python tools/_pc_gen.py --steps 8 --wh 1024x1024          # 覆盖采样参数
  python tools/_pc_gen.py --dry                             # 只校验图，不提交
  python tools/_pc_gen.py --backend flux fp8               # 切到 Flux.1 Dev fp8
  python tools/_pc_gen.py --backend sd15 majicmixRealistic_v7.safetensors pc_sd15
  python tools/_pc_gen.py --list                            # 列出所有后端

各后端的专属参数（--variant / ckpt 名 / 输出子目录）原样透传给对应脚本。
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _pc_common import DEFAULT_BACKEND, BACKENDS

DEFAULT_ARGS = {
    # backend: 未显式提供位置参数时使用的默认位置参数
    "flux": ["fp8"],
    "sd15": ["Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors", "juggernaut"],
    "qwen21": [],
}

# 带值的选项（必须成对解析，值不能当成位置参数）
VALUE_OPTS = {"--scenes", "--steps", "--size", "--wh", "--guidance", "--lora",
              "--seed", "--outdir", "--cfg", "--sampler", "--scheduler"}
# 无值开关
FLAG_OPTS = {"--dry", "--no-wait", "--wait"}


def main():
    argv = sys.argv[1:]

    if "--list" in argv or "-l" in argv:
        print("可用后端（默认 = %s）：\n" % DEFAULT_BACKEND)
        for k in BACKENDS:
            mark = "  ★" if k == DEFAULT_BACKEND else "   "
            print("%s %-8s %s" % (mark, k, BACKENDS.get(k, "")))
        print("\n★ = 默认档，不带 --backend 时使用")
        return

    # 解析 argv：区分「带值的选项」「无值开关」「位置参数」。
    # 不能简单用 startswith("-") 判断 —— 否则 --outdir <路径> 的值会被误当成位置参数。
    backend = DEFAULT_BACKEND
    pos_args, opts = [], []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--backend":
            if i + 1 >= len(argv):
                print("!! --backend 后面要跟后端名，可选：%s" % " / ".join(BACKENDS))
                return
            backend = argv[i + 1]
            i += 2
            continue
        if a in VALUE_OPTS and i + 1 < len(argv):
            opts.append((a, argv[i + 1]))
            i += 2
            continue
        if a in FLAG_OPTS:
            opts.append((a, None))
            i += 1
            continue
        pos_args.append(a)
        i += 1

    if backend not in BACKENDS:
        print("!! 未知后端 %r，可选：%s" % (backend, " / ".join(BACKENDS)))
        return

    if backend == "zimage":
        import _pc_gen_zimage as m
    elif backend == "flux":
        import _pc_gen_flux as m
    elif backend == "sd15":
        import _pc_gen_sd15 as m
    elif backend == "qwen21":
        import _pc_gen_qwen21 as m
    else:
        print("!! 后端 %r 已在登记表里但尚未接入脚本" % backend)
        return

    # 位置参数（variant / ckpt / 输出子目录名）缺省时补该后端默认值
    if not pos_args:
        pos_args = list(DEFAULT_ARGS.get(backend, []))
    flat_opts = []
    for o, v in opts:
        flat_opts.append(o)
        if v is not None:
            flat_opts.append(v)
    rest = pos_args + flat_opts

    sys.argv = [os.path.basename(m.__file__)] + rest
    print("[backend] %s — %s" % (backend, BACKENDS[backend]), flush=True)
    m.main()


if __name__ == "__main__":
    main()
