#!/usr/bin/env python3
"""Qwen-Image-2.1 关键帧生成器（API 格式）独立提交器

输入「参考人物图 + 关键帧描述」-> 输出保身份的关键帧图（比例跟随参考图, 9:16 竖屏即得竖构图）。
这些关键帧作为 H3 视频流水线的首/尾帧。

复用 tools/h3_fast_submit.py 的 HTTP/注入/校验/等待/验收工具函数。

用法:
  # 干跑（只校验，不提交）
  python tools/qwen_keyframe_submit.py --dry-run \
      --ref-image "qwen_test_source.png" \
      --prompt "a portrait of the same person standing on a city street at sunset, medium shot"

  # 真提交
  python tools/qwen_keyframe_submit.py --ref-image "qwen_test_source.png" \
      --prompt-file kf.txt --seed 42 --output-prefix "2026-10-02/keyframe/kf"

仅依赖标准库 + venv 内已装的 av/numpy（亮度验收用）。
"""
import argparse
import json
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from h3_fast_submit import (  # noqa: E402
    INPUT_ROOT,
    _post_json,
    inject_placeholders,
    validate_workflow,
    wait_done,
    find_output_files,
    mean_brightness,
)

ROOT = r"D:\ai_projects\ComfyUI"
DEFAULT_WORKFLOW = os.path.join(ROOT, "workflows", "v5", "qwen_image_2_1_keyframe_api.json")
SD_PY = os.path.join(ROOT, "comfy", "sd.py")
DEFAULT_OUTPUT = "2026-10-02/keyframe/kf"

SAMPLE_PROMPT = (
    "a portrait of the same person standing on a city street at sunset, "
    "medium shot, cinematic lighting"
)


# ----------------------------- 预检 -----------------------------

def check_vision_patch():
    """硬检查 comfy/sd.py 内 QWEN3VL_8B 视觉塔键名前缀补丁（model.visual. -> visual.）。

    该补丁位于 CLIPType.QWEN_IMAGE + TEModel.QWEN3VL_8B 分支；缺失时编辑路径
    视觉塔权重为空，编辑/关键帧生成会失败。ComfyUI 升级覆盖 sd.py 后需重新打补丁。
    """
    if not os.path.exists(SD_PY):
        return False, f"未找到 {SD_PY}"
    with open(SD_PY, "r", encoding="utf-8", errors="replace") as f:
        src = f.read()
    marker = "CLIPType.QWEN_IMAGE and te_model == TEModel.QWEN3VL_8B"
    idx = src.find(marker)
    if idx < 0:
        return False, (
            "comfy/sd.py 缺少 QWEN_IMAGE + QWEN3VL_8B 分支（视觉塔键名前缀补丁）。"
            "ComfyUI 升级后请重新打补丁：在该分支内加入 "
            "state_dict_prefix_replace(..., {\"model.visual.\": \"visual.\"})，"
            "否则编辑路径视觉塔权重为空。"
        )
    block = src[idx:idx + 900]
    if ('"model.visual."' in block and '"visual."' in block
            and "state_dict_prefix_replace" in block):
        return True, "sd.py 视觉塔前缀补丁存在（QWEN_IMAGE 分支 model.visual. -> visual.）"
    return False, (
        "QWEN_IMAGE 分支存在但未见 model.visual. -> visual. 前缀替换。"
        "请在该分支补 patch，否则编辑路径视觉塔权重为空。"
    )


def check_clip_loader(wf):
    """硬检查文本编码器：必须为官方 safetensors（非 GGUF）且 type=qwen_image。"""
    found = []
    for _nid, node in wf.items():
        if node.get("class_type") != "CLIPLoader":
            continue
        ins = node.get("inputs", {}) or {}
        found.append((ins.get("clip_name"), ins.get("type")))
    if not found:
        return False, "工作流中未找到 CLIPLoader 节点"
    for clip_name, ctype in found:
        if isinstance(clip_name, str) and clip_name.lower().endswith(".gguf"):
            return False, (
                f"CLIPLoader.clip_name={clip_name!r} 是 GGUF；编辑需视觉塔，"
                "GGUF 文本编码器形状不匹配，必须使用官方 int8 safetensors。"
            )
        if ctype != "qwen_image":
            return False, (
                f"CLIPLoader.type={ctype!r} 必须为 'qwen_image'（当前取值非法）。"
            )
    return True, f"CLIPLoader.clip_name={found[0][0]!r}, type={found[0][1]!r}"


def precheck(workflow_path):
    """可复用预检：读取工作流并做硬检查（视觉塔前缀补丁 + CLIPLoader 非 GGUF/type=qwen_image）。

    供 h3_fl2v_pipeline.py 等编排器复用。返回 (ok, lines)，lines 为可直接打印的中文说明行。
    """
    if not os.path.exists(workflow_path):
        return False, [f"[失败] 工作流不存在: {workflow_path}"]
    try:
        with open(workflow_path, "r", encoding="utf-8") as f:
            wf = json.load(f)
    except Exception as e:
        return False, [f"[失败] 工作流解析失败: {e}"]
    vok, vmsg = check_vision_patch()
    cok, cmsg = check_clip_loader(wf)
    lines = [
        f"[{'通过' if vok else '失败'}] 视觉塔前缀补丁: {vmsg}",
        f"[{'通过' if cok else '失败'}] CLIPLoader 文本编码器: {cmsg}",
    ]
    return (vok and cok), lines


# ----------------------------- main -----------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Qwen-Image-2.1 关键帧生成器（参考人物 + 描述 -> 保身份关键帧）")
    ap.add_argument("--workflow", default=DEFAULT_WORKFLOW, help="API 格式工作流 JSON")
    ap.add_argument("--ref-image", help="input 目录下的参考人物图相对路径")
    ap.add_argument("--prompt", help="关键帧描述")
    ap.add_argument("--prompt-file", help="关键帧描述文本文件")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--output-prefix", default=DEFAULT_OUTPUT,
                    help="SaveImage.filename_prefix（日期归档）")
    ap.add_argument("--dry-run", action="store_true", help="只校验不提交")
    ap.add_argument("--no-wait", action="store_true", help="提交后不等待")
    args = ap.parse_args()

    # 1. 读取工作流
    if not os.path.exists(args.workflow):
        print(f"[失败] 工作流不存在: {args.workflow}")
        return 1
    with open(args.workflow, "r", encoding="utf-8") as f:
        wf = json.load(f)

    # 2. 提示词
    if args.prompt_file:
        if not os.path.exists(args.prompt_file):
            print(f"[失败] 提示词文件不存在: {args.prompt_file}")
            return 1
        with open(args.prompt_file, "r", encoding="utf-8-sig") as f:
            prompt = f.read().strip()
    elif args.prompt:
        prompt = args.prompt
    else:
        if not args.dry_run:
            print("[失败] 真提交必须提供 --prompt 或 --prompt-file")
            return 1
        prompt = SAMPLE_PROMPT
        print("[提示] 未提供 --prompt/--prompt-file，dry-run 使用内置示例描述")

    # 3. 参考人物图
    ref = args.ref_image
    if not ref:
        if not args.dry_run:
            print("[失败] 真提交必须提供 --ref-image")
            return 1
        ref = "qwen_test_source.png"
        print(f"[提示] 未提供 --ref-image，dry-run 使用示例 {ref!r}")
    if not os.path.exists(os.path.join(INPUT_ROOT, ref)):
        if not args.dry_run:
            print(f"[失败] input 目录下未找到参考人物图: {ref}")
            return 1
        print(f"[警告] input 目录下未找到参考人物图: {ref}")

    # 4. 预检（注入前，对字面量做硬检查；复用 precheck() 保证 CLI 与编排器同一套逻辑）
    print("\n=== 预检 ===")
    pok, plines = precheck(args.workflow)
    for ln in plines:
        print("  " + ln)
    if not pok:
        print("\n[失败] 预检未通过，终止（未提交）。")
        return 1

    # 5. 注入
    values = {
        "image": ref,
        "prompt": prompt,
        "seed": args.seed,
        "output": args.output_prefix,
    }
    try:
        wf = inject_placeholders(wf, values)
    except KeyError as e:
        print(f"[失败] 注入失败: {e}")
        return 1

    # 6. dry-run 校验
    if args.dry_run:
        print("\n=== dry-run 逐节点校验（不会 POST /prompt）===")
        print(f"  注入: image={ref!r} seed={args.seed} output={args.output_prefix!r}")
        print(f"  prompt[:60]={prompt[:60]!r}")
        errors, lines = validate_workflow(wf)
        for ln in lines:
            print(ln)
        if errors:
            print(f"\n[失败] 校验发现 {len(errors)} 个问题:")
            for e in errors:
                print("  - " + e)
            return 1
        print("\n[通过] 全部校验通过（dry-run 结束，未提交）")
        return 0

    # 7. 提交
    print("\n=== 提交 ===")
    payload = {"prompt": wf, "client_id": str(uuid.uuid4())}
    t_submit = time.time()
    try:
        r = _post_json("/prompt", payload)
    except Exception as e:
        print(f"[失败] 提交异常: {e}")
        return 1
    pid = r.get("prompt_id")
    node_errors = r.get("node_errors") or {}
    if node_errors:
        print("[失败] node_errors 非空:")
        print(json.dumps(node_errors, ensure_ascii=False)[:2000])
        return 1
    print(f"  已提交 pid={pid}")

    if args.no_wait:
        print("  --no-wait：不等待，退出。")
        return 0

    # 8. 等待
    print("\n=== 等待完成（每 30s 轮询）===")
    rec = wait_done(pid)
    if not rec:
        print("[失败] 未正常完成")
        return 1
    total = time.time() - t_submit
    files = find_output_files(rec)
    print("\n=== 结果 ===")
    print(f"  prompt_id: {pid}")
    print(f"  提交->落盘总耗时: {total:.1f}s")
    if not files:
        print("[失败] outputs 中未定位到关键帧文件")
        return 1
    png = files[-1]
    print(f"  关键帧: {png}（存在={os.path.exists(png)}）")

    # 9. 验收（非纯黑）
    b = mean_brightness(png)
    if b is None:
        print("[警告] 无法计算亮度（缺 av/PIL），请人工复核")
        return 0
    ok = b > 3.0
    print(f"  平均亮度 = {b:.2f}（阈值 >3.0） -> {'通过' if ok else '未通过'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
