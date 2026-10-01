#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Qwen-Image 工作流参数注入 + 提交执行。

模板 (workflows/v4/qwen_image_2_1_*_v4.json 或 *_v5.json) 里所有可调节点都在 _meta.title
中带 [inject:xxx] 标记，本脚本按标记定位节点并覆盖参数，不依赖节点 id，
因此在 ComfyUI 界面里改过图再导出也不会失效。

版本映射：restore 用 v5（两遍扩散：结构修复 → 超分 → 最终分辨率细节重建），
t2i / i2i / edit 仍用 v4；--json 可强制指定任意工作流文件。

可注入标记:
  unet / clip / vae   模型文件名
  shift               ModelSamplingAuraFlow 的 shift
  prompt / negative   Pass1 正/负向提示词
  prompt2 / negative2 Pass2 正/负向提示词 (v5 restore)
  size                EmptySD3LatentImage 的 width/height (t2i)
  resize              ImageScaleToTotalPixels 的 megapixels/resolution_steps
                      (i2i/edit/restore 输入归一；v5 中即 Pass1 工作分辨率 R1)
  resize2             v5 Pass2 的 ImageScaleToTotalPixels.megapixels（R2，即最终输出尺寸）；
                      缺省 R2 = min(2.5, 2×R1)。v4 无此标记，自动走旧的 final_mp 收口
  image               LoadImage 的输入图
  sampler             Pass1 KSampler 的 seed/steps/cfg/sampler_name/scheduler/denoise
  sampler2            Pass2 KSampler 的同名参数外，denoise 由 --denoise2 控制 (v5)
  presr               前置超分 UpscaleModelLoader.model_name (v5；仅源图 <0.5MP 时保留)
  upscaler            主超分 UpscaleModelLoader.model_name (restore)
  final_mp            末级收口 ImageScaleToTotalPixels.megapixels (v4 restore)
  face                ReActorRestoreFace 的 codeformer_weight/visibility (v5)
  output              SaveImage 的 filename_prefix (默认自动带当日日期)

v5 restore（高清修复）默认值：Pass1 denoise 0.65、Pass2 denoise 0.35、
Pass1 工作分辨率 R1 = 1.0MP、Pass2 = 最终输出 R2 = 2×R1 (上限 2.5MP)、
主超分 realesr-general-x4v3.pth、末级 CodeFormer 人像修脸；源图 <0.5MP 时自动前置超分。

用法示例:
  python tools/qwen_v4_submit.py t2i  --prompt "a cat on the moon"                 # 只打印
  python tools/qwen_v4_submit.py t2i  --prompt "..." --run                         # 提交并等待
  python tools/qwen_v4_submit.py t2i  --width 1664 --height 928 --steps 30 --run
  python tools/qwen_v4_submit.py edit --image in.png --prompt "把背景换成海边" --run
  python tools/qwen_v4_submit.py i2i  --image in.png --denoise 0.6 --lightning 4 --run
  python tools/qwen_v4_submit.py restore --image old.png --run                     # v5 两遍修复
  python tools/qwen_v4_submit.py restore --image old.png --denoise 0.8 --denoise2 0.4 --run
  python tools/qwen_v4_submit.py restore --image old.png --no-presr --no-face --run
"""
import argparse
import json
import random
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # ComfyUI 根目录
WF_DIR = ROOT / "workflows" / "v4"
DEFAULT_SERVER = "http://127.0.0.1:8188"
# kind → 工作流版本（restore 用 v5 两遍扩散，其余仍 v4）
VERSION_BY_KIND = {"restore": "v5"}

# 复用 tools/restore_qa.py 的块状度检测（只 import，无副作用；缺失也不阻断）。
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from restore_qa import blockiness_ratio
except Exception:
    blockiness_ratio = None
# 按工作流类型选对应 Lightning LoRA（一个要改，一个不用改）
LIGHTNING_LORA = {
    4: {"t2i": "Qwen-Image-Lightning-4steps-V1.0.safetensors",
        "i2i": "Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors",
        "edit": "Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors",
        "restore": "Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors"},
    8: {"t2i": "Qwen-Image-Lightning-8steps-V1.0.safetensors",
        "i2i": "Qwen-Image-Edit-Lightning-8steps-V1.0-bf16.safetensors",
        "edit": "Qwen-Image-Edit-Lightning-8steps-V1.0-bf16.safetensors",
        "restore": "Qwen-Image-Edit-Lightning-8steps-V1.0-bf16.safetensors"},
}

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# ---------------------------------------------------------------- 模板操作

def find(nodes, key):
    """按 [inject:key] 标记定位唯一节点 id。"""
    hits = [nid for nid, n in nodes.items() if f"[inject:{key}]" in n.get("_meta", {}).get("title", "")]
    if not hits:
        raise SystemExit(f"✗ 模板里找不到 [inject:{key}] 节点，请检查工作流文件")
    if len(hits) > 1:
        raise SystemExit(f"✗ [inject:{key}] 匹配到多个节点: {hits}")
    return hits[0]


def patch(nodes, key, **fields):
    """按标记注入字段；全部为 None 时视为不注入（该标记可以不存在）。"""
    vals = {k: v for k, v in fields.items() if v is not None}
    if not vals:
        return None
    node = nodes[find(nodes, key)]
    node["inputs"].update(vals)
    return node


def has_marker(nodes, key):
    return any(f"[inject:{key}]" in n.get("_meta", {}).get("title", "") for n in nodes.values())


def prompt_input_name(nodes, key):
    """CLIPTextEncode 的文本输入叫 text，Qwen 系的编码器叫 prompt。"""
    node = nodes[find(nodes, key)]
    return "text" if node["class_type"] == "CLIPTextEncode" else "prompt"


def inject_lightning(nodes, ks, steps, lora_name):
    """把 Lightning LoRA 插到 AuraFlow 之后，并把 cfg 压到 1.0（官方加速配置）。

    同时压 [inject:sampler] 与（存在时）[inject:sampler2] 两个 KSampler 的
    steps/cfg；v4（只有 sampler）行为与改造前完全一致。
    """
    aura = find(nodes, "shift")
    consumers = [(nid, n) for nid, n in nodes.items()
                 if any(v == [aura, 0] for v in n["inputs"].values())]
    if not consumers:
        raise SystemExit("✗ 没找到 AuraFlow 的下游节点，无法插入 Lightning LoRA")

    new_id = str(max(int(k) for k in nodes) + 1)
    nodes[new_id] = {
        "inputs": {"model": [aura, 0], "lora_name": lora_name, "strength_model": 1.0},
        "class_type": "LoraLoaderModelOnly",
        "_meta": {"title": f"Lightning {steps}步 LoRA (脚本注入)"},
    }
    for _, n in consumers:
        for k, v in n["inputs"].items():
            if v == [aura, 0]:
                n["inputs"][k] = [new_id, 0]

    ks["inputs"]["steps"] = steps
    ks["inputs"]["cfg"] = 1.0
    if has_marker(nodes, "sampler2"):
        ks2 = nodes[find(nodes, "sampler2")]
        ks2["inputs"]["steps"] = steps
        ks2["inputs"]["cfg"] = 1.0
    return [nid for nid, _ in consumers]


def _consumers_of(nodes, src_id):
    """返回所有把 src_id 输出 0 当作输入的下游节点 id。"""
    return [nid for nid, n in nodes.items()
            if any(v == [src_id, 0] for v in n["inputs"].values())]


def cut_presr(nodes, presr_id, image_id):
    """剪掉前置超分链路：把超分节点的下游输入改接到 LoadImage，再删除两节点。

    按标记定位、改写连线，不依赖硬编码 id。
    """
    for up in _consumers_of(nodes, presr_id):
        for _, n in nodes.items():
            for k, v in n["inputs"].items():
                if v == [up, 0]:
                    n["inputs"][k] = [image_id, 0]
        nodes.pop(up, None)
    nodes.pop(presr_id, None)


def cut_face(nodes, face_id):
    """剪掉修脸节点：把它的下游输入改接到修脸节点原本的 image 输入。"""
    img_in = nodes[face_id]["inputs"].get("image")
    if img_in is None:
        raise SystemExit("✗ 修脸节点没有 image 输入，无法剪枝")
    for _, n in nodes.items():
        for k, v in n["inputs"].items():
            if v == [face_id, 0]:
                n["inputs"][k] = img_in
    nodes.pop(face_id, None)


def cut_pass2(nodes):
    """剪掉 Pass2（第二遍扩散），把成品改接到 Pass1 的超分收口输出。

    实测结论（2026-10-01）：Pass2 的第二次 VAE 编解码往返会把照片的自然微纹理
    抹掉——高频占比从 v4 的 1.73x（≈真实照片 1.75x）掉到 0.83x，肉眼表现为
    "AI 插画感 / 瓷娃娃皮肤"。而 [inject:resize2] 节点输出的"已收到 R2 的超分图"
    本身就已经是一张无压缩块、且保留照片质感的成品，可直接出图。

    做法：先把成品接线改到 [inject:resize2]，再从保存节点反向遍历，
    删掉所有不再可达的节点（正好就是整条 Pass2 链）。不依赖硬编码 id。
    """
    if not (has_marker(nodes, "resize2") and has_marker(nodes, "sampler2")):
        return False
    src = find(nodes, "resize2")
    sink = find(nodes, "output")

    # 1) 成品来源：有修脸节点就改它的 image 输入（保留修脸），否则直接改保存节点
    if has_marker(nodes, "face"):
        nodes[find(nodes, "face")]["inputs"]["image"] = [src, 0]
    else:
        nodes[sink]["inputs"]["images"] = [src, 0]

    # 2) 从保存节点反向遍历求可达集合，其余全删（= Pass2 那一串）
    keep, stack = set(), [sink]
    while stack:
        nid = stack.pop()
        if nid in keep or nid not in nodes:
            continue
        keep.add(nid)
        for v in nodes[nid]["inputs"].values():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str):
                stack.append(v[0])
    for nid in list(nodes):
        if nid not in keep:
            nodes.pop(nid, None)
    return True


def ensure_input_image(path):
    """把参考图放进 ComfyUI/input，返回 LoadImage 需要的文件名。"""
    src = Path(path).expanduser().resolve()
    if not src.exists():
        raise SystemExit(f"✗ 输入图不存在: {src}")
    input_dir = ROOT / "input"
    input_dir.mkdir(exist_ok=True)
    if src.parent == input_dir:
        return src.name
    dst = input_dir / f"{src.stem}_qwen{src.suffix}"
    if not dst.exists() or dst.stat().st_size != src.stat().st_size:
        shutil.copy2(src, dst)
    return dst.name


def image_megapixels(path):
    """读输入图的像素规模（MP）；读不出来返回 None（不阻断流程）。"""
    try:
        from PIL import Image
        with Image.open(path) as im:
            w, h = im.size
        return w * h / 1048576.0
    except Exception:
        return None


# ---------------------------------------------------------------- 提交与验证

def post_prompt(api, server):
    payload = {"prompt": api, "client_id": str(uuid.uuid4())}
    req = urllib.request.Request(f"{server}/prompt", data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=60).read())
    except urllib.error.HTTPError as e:
        raise SystemExit("✗ 提交失败 HTTP %s\n%s" % (e.code, e.read().decode(errors="replace")[:2000]))


def wait_and_verify(pid, server, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            rec = json.loads(urllib.request.urlopen(f"{server}/history/{pid}", timeout=20).read()).get(pid)
        except Exception as ex:
            print("  查询异常:", ex)
            rec = None
        if rec and rec.get("status", {}).get("completed"):
            files = []
            for out in rec.get("outputs", {}).values():
                for item in out.get("images", []) + out.get("gifs", []):
                    files.append(Path(item.get("subfolder", "")) / item["filename"])
            print("✓ 执行完成")
            for f in files:
                p = ROOT / "output" / f
                print(("  ✓ " if p.exists() else "  ? ") + str(p))
            if not files:
                print("  (history 无输出记录)")
            return True
        time.sleep(10)
    print("✗ 等待超时，最后状态:", json.dumps(rec.get("status", {}), ensure_ascii=False) if rec else "未知")
    return False


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(description="Qwen-Image v4 工作流参数注入 + 提交")
    ap.add_argument("kind", nargs="?", choices=["t2i", "i2i", "edit", "restore"], help="工作流类型")
    ap.add_argument("--json", help="直接指定工作流 JSON 路径（覆盖 kind）")
    ap.add_argument("--prompt", help="正向提示词")
    ap.add_argument("--prompt-file", help="从文本文件读取正向提示词")
    ap.add_argument("--negative", help="负向提示词")
    ap.add_argument("--image", help="输入图（i2i / edit / restore）")
    ap.add_argument("--width", type=int, help="t2i 宽度")
    ap.add_argument("--height", type=int, help="t2i 高度")
    ap.add_argument("--megapixels", type=float,
                    help="i2i/edit 输入图归一 MP；restore(v5) 为 Pass1 工作分辨率 R1"
                         "（缺省 min(1.25, max(1.0, 源图MP))）")
    ap.add_argument("--resolution-steps", type=int, help="尺寸对齐步长（默认 8）")
    ap.add_argument("--upscaler", help="主超分模型文件名（restore；v5 默认 realesr-general-x4v3.pth）")
    ap.add_argument("--presr-model",
                    help="前置超分模型文件名（v5；缺省与 --upscaler 相同，仅源图 <0.5MP 时接线）")
    ap.add_argument("--no-presr", action="store_true", help="强制不使用前置超分（即使源图很小）")
    ap.add_argument("--final-mp", type=float,
                    help="最终输出总像素 MP；restore(v5) 即 R2（缺省 min(2.5, 2×R1)）；"
                         "v4 restore 为末级收口（缺省 源图MP×16，上限 8MP）")
    ap.add_argument("--denoise", type=float,
                    help="重绘幅度（v5 restore Pass1 默认 0.65，越小越保脸、越大越清晰；"
                         "i2i 常用 0.5-0.8，edit 官方 1.0）")
    ap.add_argument("--denoise2", type=float,
                    help="v5 restore Pass2(细节重建)重绘幅度，默认 0.35")
    ap.add_argument("--face-weight", type=float,
                    help="v5 restore CodeFormer codeformer_weight（默认 0.5，越小越保脸）")
    ap.add_argument("--no-face", action="store_true", help="剪掉末级人像修脸节点 (v5)")
    ap.add_argument("--no-pass2", action="store_true",
                    help="剪掉 Pass2 第二遍扩散，直接出「Pass1 超分收口」的图 (v5)；"
                         "实测 Pass2 会抹掉照片自然纹理导致「AI 插画感」，保照片感时用它")
    ap.add_argument("--steps", type=int, help="采样步数")
    ap.add_argument("--cfg", type=float, help="CFG（必须 >1 负向提示词才生效）")
    ap.add_argument("--shift", type=float, help="ModelSamplingAuraFlow shift（官方 3.0/3.1）")
    ap.add_argument("--seed", type=int, default=None, help="随机种子，-1 表示随机")
    ap.add_argument("--sampler", help="采样器，默认 euler")
    ap.add_argument("--scheduler", help="调度器，默认 simple")
    ap.add_argument("--lightning", type=int, choices=[4, 8], help="插入 Lightning LoRA 并压到 cfg 1.0")
    ap.add_argument("--lora-name", help="覆盖 Lightning LoRA 文件名（默认按类型自动选）")
    ap.add_argument("--out-prefix", help="输出前缀，默认 <当日日期>/qwen_<kind>")
    ap.add_argument("--out-date", help="输出日期目录，默认今天")
    ap.add_argument("--save-json", help="把注入后的 API JSON 另存一份")
    ap.add_argument("--server", default=DEFAULT_SERVER)
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--run", action="store_true", help="提交到 ComfyUI 并等待出图（缺省只打印）")
    args = ap.parse_args()

    if not args.json and not args.kind:
        ap.error("需要给出 kind (t2i/i2i/edit/restore) 或 --json")
    if args.json:
        wf_path = Path(args.json)
    else:
        ver = VERSION_BY_KIND.get(args.kind, "v4")
        wf_path = WF_DIR / f"qwen_image_2_1_{args.kind}_{ver}.json"
    kind = args.kind or re.sub(r"_v\d+$", "", wf_path.stem.replace("qwen_image_2_1_", ""))
    if not wf_path.exists():
        raise SystemExit(f"✗ 工作流不存在: {wf_path}")

    nodes = json.loads(wf_path.read_text(encoding="utf-8"))
    notes = []

    # 源图像素规模（尺寸口径 / 超分剪枝 / 块状度体检都要用）
    in_mp = image_megapixels(args.image) if (args.image and kind != "t2i") else None

    # 源图块状度体检（仅提示，不阻断；restore_qa 缺失则静默跳过）
    if kind == "restore" and args.image and blockiness_ratio is not None:
        try:
            col, row = blockiness_ratio(args.image)
            if max(col, row) > 1.4:
                notes.append("源图有 8×8 压缩块（实测 col=%.3f row=%.3f），"
                             "建议 --denoise 0.75 以上" % (col, row))
        except Exception as ex:
            notes.append("源图块状度检测失败（已跳过）: %s" % ex)

    # 提示词（Pass1，以及 v5 的 Pass2；无对应标记时静默跳过）
    prompt = args.prompt
    if args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8").strip()
    patch(nodes, "prompt", **{prompt_input_name(nodes, "prompt"): prompt})
    if has_marker(nodes, "negative"):
        patch(nodes, "negative", **{prompt_input_name(nodes, "negative"): args.negative})
    elif args.negative:
        notes.append("该工作流无负向提示词节点（DMD 蒸馏不走 CFG），--negative 已忽略")
    if has_marker(nodes, "prompt2"):
        patch(nodes, "prompt2", **{prompt_input_name(nodes, "prompt2"): prompt})
    if has_marker(nodes, "negative2"):
        patch(nodes, "negative2", **{prompt_input_name(nodes, "negative2"): args.negative})

    # 模型与位移
    patch(nodes, "shift", shift=args.shift)

    # 尺寸
    work_mp = 1.0
    if kind == "t2i":
        patch(nodes, "size", width=args.width, height=args.height)
    elif has_marker(nodes, "resize"):
        if has_marker(nodes, "resize2"):
            # v5 两遍：R1 = Pass1 工作分辨率；R2 = Pass2 = 最终输出分辨率（无末级收口）
            r1 = args.megapixels if args.megapixels is not None else (
                min(1.25, max(1.0, in_mp)) if in_mp else 1.0)
            r2 = args.final_mp if args.final_mp is not None else min(2.5, 2.0 * r1)
            patch(nodes, "resize", megapixels=r1, resolution_steps=args.resolution_steps)
            patch(nodes, "resize2", megapixels=r2, resolution_steps=args.resolution_steps)
            work_mp = r1
            notes.append("R1(Pass1 工作分辨率) = %.2fMP；R2(Pass2 = 最终输出) = %.2fMP；"
                         "输出 = Pass2 分辨率，无末级收口节点" % (r1, r2))
            if r2 > 2.5:
                notes.append("R2 %.2fMP 超出建议上限 2.5MP，16GB 卡可能 OOM（未阻断）" % r2)
            if in_mp:
                if r2 / in_mp > 16:
                    notes.append("输出倍率已达 %.1f 倍，可信细节主要来自模型合成" % (r2 / in_mp))
                if r1 < in_mp:
                    notes.append("输入图 %.2fMP 会被先降到 %.2fMP 再修复，真实细节会丢；"
                                 "若原图已足够清晰，请加 --megapixels %.1f 跟随原图" % (in_mp, r1, in_mp))
        else:
            patch(nodes, "resize", megapixels=args.megapixels, resolution_steps=args.resolution_steps)
            work_mp = nodes[find(nodes, "resize")]["inputs"]["megapixels"]
            if in_mp and in_mp > work_mp * 1.5:
                notes.append("输入图 %.2fMP 会被先降到 %.2fMP 再修复，真实细节会丢；"
                             "若原图已足够清晰，请加 --megapixels %.1f 跟随原图" % (in_mp, work_mp, in_mp))
    elif args.megapixels or args.resolution_steps:
        notes.append("该工作流用 FluxKontextImageScale 自动定尺，--megapixels/--resolution-steps 已忽略")

    # 前置超分（v5）：源图 <0.5MP 才保留；>=0.5MP 或 --no-presr 时剪掉；读不出 mp 时保守保留。
    if has_marker(nodes, "presr"):
        drop_presr = args.no_presr or (in_mp is not None and in_mp >= 0.5)
        if drop_presr:
            cut_presr(nodes, find(nodes, "presr"), find(nodes, "image"))
            notes.append("已剪掉前置超分链路（%s）"
                         % ("--no-presr" if args.no_presr else "源图 %.2fMP ≥ 0.5MP" % in_mp))
        else:
            patch(nodes, "presr", model_name=args.presr_model or args.upscaler)
    elif args.presr_model:
        notes.append("该工作流无前置超分节点，--presr-model 已忽略")

    # 放大模型与输出尺寸收口 (restore)
    if has_marker(nodes, "upscaler"):
        patch(nodes, "upscaler", model_name=args.upscaler)
        up_name = nodes[find(nodes, "upscaler")]["inputs"]["model_name"]
        up_path = ROOT / "models" / "upscale_models" / up_name
        if not up_path.exists():
            raise SystemExit(f"✗ 放大模型不存在: {up_path}")
    elif args.upscaler:
        notes.append("该工作流无放大节点，--upscaler 已忽略")
    if has_marker(nodes, "final_mp"):
        final_mp = args.final_mp
        if final_mp is None and in_mp:
            # 放大幅度上限：源图像素 ×16（边长 4 倍）；下限不低于 Qwen 的工作分辨率，
            # 避免把 0.05MP 的图硬拉到 4MP —— 那只是把合成细节摊薄，看起来更糊。
            final_mp = round(min(8.0, max(work_mp, in_mp * 16)), 2)
            notes.append("输出尺寸按源图 %.2fMP 自动定为 %.2fMP（源图像素×16，上限 8MP）；"
                         "--final-mp 可覆盖" % (in_mp, final_mp))
        patch(nodes, "final_mp", megapixels=final_mp)
    elif args.final_mp is not None and not has_marker(nodes, "resize2"):
        notes.append("该工作流无输出尺寸收口节点，--final-mp 已忽略")

    # 人像修脸（v5）：--no-face 剪掉；否则注入 CodeFormer 权重
    if has_marker(nodes, "face"):
        if args.no_face:
            cut_face(nodes, find(nodes, "face"))
            notes.append("已剪掉人像修脸节点 (--no-face)")
        else:
            patch(nodes, "face", codeformer_weight=args.face_weight)
    elif args.face_weight is not None or args.no_face:
        notes.append("该工作流无人像修脸节点，--face-weight/--no-face 已忽略")

    # Pass2 剪枝（v5）：实测第二次 VAE 往返会抹掉照片自然纹理 → "AI 插画感"
    if args.no_pass2:
        if cut_pass2(nodes):
            notes.append("已剪掉 Pass2 第二遍扩散：直接输出「Pass1 超分收口」的图；"
                         "--denoise2 已忽略（不再有第二遍）")
        else:
            notes.append("该工作流无 Pass2（无 resize2/sampler2 标记），--no-pass2 已忽略")

    # 输入图
    if args.image:
        if kind == "t2i":
            notes.append("t2i 不需要输入图，--image 已忽略")
        else:
            patch(nodes, "image", image=ensure_input_image(args.image))

    # 采样
    seed = args.seed
    if seed is not None and seed < 0:
        seed = random.randint(0, 2**31 - 1)
    ks = None
    if has_marker(nodes, "sampler"):
        ks = patch(nodes, "sampler", seed=seed, steps=args.steps, cfg=args.cfg,
                   sampler_name=args.sampler, scheduler=args.scheduler, denoise=args.denoise) \
            or nodes[find(nodes, "sampler")]
        # v5 Pass2：denoise 由 --denoise2 控制，其余参数与 Pass1 共用
        if has_marker(nodes, "sampler2"):
            patch(nodes, "sampler2", seed=seed, steps=args.steps, cfg=args.cfg,
                  sampler_name=args.sampler, scheduler=args.scheduler, denoise=args.denoise2)
    else:
        # 少步蒸馏类工作流（如 Viggle Turbo）用自定义 sigma 表，只有 RandomNoise 需要注入种子
        patch(nodes, "noise", noise_seed=seed)
        if any(v is not None for v in (args.steps, args.cfg, args.sampler, args.scheduler, args.denoise)):
            notes.append("该工作流用自定义 sigma 表采样，--steps/--cfg/--sampler/--scheduler/--denoise 已忽略")

    # Lightning 加速
    if args.lightning:
        lora_name = args.lora_name or LIGHTNING_LORA[args.lightning].get(kind)
        if lora_name is None:
            raise SystemExit(f"✗ {kind} 没有预置的 Lightning LoRA，请用 --lora-name 指定")
        lora_path = ROOT / "models" / "loras" / lora_name
        if not lora_path.exists():
            raise SystemExit(f"✗ LoRA 不存在: {lora_path}\n  请先下载，或用 --lora-name 指定其它文件")
        touched = inject_lightning(nodes, ks, args.lightning, lora_name)
        notes.append(f"已插入 Lightning {args.lightning} 步 LoRA ({lora_name}) 到节点 {touched}，cfg 固定 1.0")
        if nodes[find(nodes, "negative")]["inputs"].get(prompt_input_name(nodes, "negative")):
            notes.append("cfg=1.0 时负向提示词不参与计算，可留空")

    # 输出前缀（项目规则：按日期归档）
    day = args.out_date or date.today().isoformat()
    patch(nodes, "output", filename_prefix=args.out_prefix or f"{day}/qwen_{kind}")

    for n in notes:
        print("提示:", n)
    print(f"工作流: {wf_path}")
    print(f"输出前缀: {nodes[find(nodes, 'output')]['inputs']['filename_prefix']}")

    if args.save_json:
        Path(args.save_json).write_text(json.dumps(nodes, ensure_ascii=False, indent=2), encoding="utf-8")
        print("已写出注入后的 JSON:", args.save_json)

    print("=== API prompt ===")
    print(json.dumps(nodes, ensure_ascii=False, indent=2))
    if not args.run:
        print("\n(未加 --run，仅打印；确认无误后加 --run 提交)")
        return

    resp = post_prompt(nodes, args.server)
    pid = resp.get("prompt_id")
    print(f"\n已提交 pid={pid}，等待出图...")
    if not wait_and_verify(pid, args.server, args.timeout):
        sys.exit(1)


if __name__ == "__main__":
    main()