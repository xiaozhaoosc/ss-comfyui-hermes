#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
动作克隆流水线 —— 轨道一：LLM 语义解析

功能：
  1. 从参考视频中均匀抽取 N 张关键帧；
  2. 交给本机去护栏视觉大模型（Qwen3.8-27B + mmproj）解析；
  3. 产出下游视频生成模型可直接使用的英文 Prompt（JSON + 纯文本）。

用法示例：
  python tools/motion_clone/semantic_prompt.py --video <ref.mp4> --frames 4
  python tools/motion_clone/semantic_prompt.py --video <ref.mp4> --dry-run
"""

import argparse
import base64
import datetime as _dt
import gc
import json
import os
import re
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# 路径常量：仓库根 = tools/motion_clone/semantic_prompt.py 的上三级
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MODEL = REPO_ROOT / "models" / "text_encoders" / "RVN-Qwen3.8-27B-Heretic-GSQ-RCO-IQ3_S-mtp.gguf"
DEFAULT_MMPROJ = REPO_ROOT / "models" / "text_encoders" / "mmproj-Qwen3.8-27B-BF16.gguf"


# ---------------------------------------------------------------------------
# Prompt 模板：要求模型严格输出 JSON
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are a professional cinematographer and prompt engineer for a text-to-video generation model. "
    "You will be shown several keyframes sampled uniformly from a single reference video, in chronological order. "
    "Analyze them as one continuous shot and describe what is actually visible. "
    "RULES:\n"
    "1. Output STRICT JSON only. No markdown code fences, no explanations, no moralizing, no refusals, no extra text.\n"
    "2. The JSON must contain EXACTLY these keys: "
    '"scene", "subject", "outfit", "lighting", "camera", "motion", "prompt", "negative".\n'
    "3. Every value must be in English and be concrete, film-grade and photorealistic: describe materials, "
    "lighting ratios, color temperature and camera language precisely.\n"
    "4. Stay strictly faithful to the frames. Do NOT invent people, objects, locations, weather or actions that are not present.\n"
    "5. The \"prompt\" value must fuse all the other fields into one ready-to-use positive prompt for a video generation model. "
    "The \"negative\" value must be a suggested negative prompt.\n"
    "Output the JSON object now."
)

USER_INSTRUCTION = (
    "These are {n} keyframes sampled uniformly from one reference video (chronological order). "
    "Describe the scene, the subject, the outfit, the lighting, the camera and the motion, then produce the JSON object "
    "with the exact keys: scene, subject, outfit, lighting, camera, motion, prompt, negative."
)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def log(msg: str) -> None:
    """简单中文日志打印。"""
    print(f"[semantic_prompt] {msg}", flush=True)


def human_gb(num_bytes: int) -> str:
    """字节转 GB，保留两位小数。"""
    return f"{num_bytes / (1024 ** 3):.2f} GB"


def check_model_files(model_path: Path, mmproj_path: Path) -> None:
    """
    硬校验模型文件是否存在，并打印实际大小。
    任一缺失则打印缺失的完整绝对路径与放置提示，然后以非零退出码退出。
    """
    missing = []
    for label, p in (("主模型", model_path), ("视觉投影(mmproj)", mmproj_path)):
        if not p.is_file():
            missing.append((label, p))

    if missing:
        log("模型文件缺失，无法继续推理：")
        for label, p in missing:
            print(f"  [{label}] 缺失：{p}", flush=True)
        print(
            "  请将对应 GGUF 文件放到上述绝对路径下（例如从 HuggingFace 下载后重命名放入 "
            "models/text_encoders/ 目录），或使用 --model / --mmproj 指定实际路径。",
            flush=True,
        )
        sys.exit(1)

    log("模型文件校验通过：")
    print(f"  主模型   : {model_path}  ({human_gb(model_path.stat().st_size)})", flush=True)
    print(f"  mmproj   : {mmproj_path}  ({human_gb(mmproj_path.stat().st_size)})", flush=True)


def extract_keyframes(video_path: Path, outdir: Path, n_frames: int):
    """
    用 cv2 均匀抽取 n_frames 张关键帧，保存为 keyframes/kf_XXX.png。
    返回 (fps, total_frames, width, height, sample_indices, saved_paths)。
    """
    import cv2  # 延迟导入，保证 --help 等场景更快

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        log(f"无法打开视频：{video_path}")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    if total_frames <= 0:
        log("读取到的总帧数无效（<=0），无法抽帧。")
        cap.release()
        sys.exit(1)

    # 在整段视频上均匀取 N 个帧索引（含首尾）
    if n_frames <= 1:
        indices = [0]
    else:
        indices = [round(i * (total_frames - 1) / (n_frames - 1)) for i in range(n_frames)]
    # 去重并保持顺序
    indices = sorted(set(indices))

    kf_dir = outdir / "keyframes"
    kf_dir.mkdir(parents=True, exist_ok=True)

    from PIL import Image  # BGR->RGB 后用 PIL 写盘，避免 cv2.imwrite 再反转

    saved = []
    for i, idx in enumerate(indices):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ok, frame_bgr = cap.read()
        if not ok or frame_bgr is None:
            log(f"警告：读取第 {idx} 帧失败，跳过。")
            continue
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)  # BGR -> RGB
        dst = kf_dir / f"kf_{i:03d}.png"
        Image.fromarray(frame_rgb).save(str(dst))
        saved.append(dst)
        log(f"已保存关键帧 {i + 1}/{len(indices)}：帧号={idx} -> {dst}")

    cap.release()
    return fps, total_frames, width, height, indices, saved


def build_llm(model_path: Path, mmproj_path: Path, n_ctx: int):
    """
    加载多模态模型。优先使用 Qwen3VLChatHandler；
    若导入失败或构造报错，则回退到 Llama(mmproj_path=...)。
    返回 (llm, handler, handler_name)。
    """
    from llama_cpp import Llama

    # 优先：显式 Qwen3VLChatHandler
    try:
        from llama_cpp.llama_multimodal import Qwen3VLChatHandler

        handler = Qwen3VLChatHandler(mmproj_path=str(mmproj_path), verbose=False, use_gpu=True)
        llm = Llama(
            model_path=str(model_path),
            chat_handler=handler,
            n_ctx=n_ctx,
            n_gpu_layers=-1,
            verbose=False,
        )
        log("实际使用的 handler：Qwen3VLChatHandler")
        return llm, handler, "Qwen3VLChatHandler"
    except Exception as e:
        log(f"Qwen3VLChatHandler 不可用（{type(e).__name__}: {e}），回退到 mmproj_path 自动挂载。")

    # 回退：直接传 mmproj_path，由 Llama 内部自动创建 GenericMTMDChatHandler
    llm = Llama(
        model_path=str(model_path),
        mmproj_path=str(mmproj_path),
        n_ctx=n_ctx,
        n_gpu_layers=-1,
        verbose=False,
    )
    log("实际使用的 handler：GenericMTMDChatHandler（由 mmproj_path 自动创建）")
    return llm, None, "GenericMTMDChatHandler(mmproj_path)"


def strip_reasoning(text: str) -> str:
    """
    剥离模型输出中的推理段（think 标记块），便于离线单测：
      1) 先去掉成对的  thinking... 块（DOTALL / IGNORECASE）；
      2) 若仍残留多余的 think 结束标记（有闭无开，例如聊天模板已注入开标记），
         取最后一个结束标记之后的内容；
      3) 若仍存在未闭合的 think 开始标记（有开无闭），取该开始标记之前的内容；
      4) strip() 后若为空，退回原始文本，避免把内容清没导致崩溃。
    """
    if not text:
        return text

    cleaned = re.sub(r"<\s*think\s*>.*?<\s*/\s*think\s*>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # 多余的 think 结束标记：取最后一个之后
    end = re.search(r"<\s*/\s*think\s*>", cleaned, flags=re.IGNORECASE)
    if end:
        cleaned = cleaned[end.end():]

    # 未闭合的 think 开始标记：取第一个之前
    start = re.search(r"<\s*think\s*>", cleaned, flags=re.IGNORECASE)
    if start:
        cleaned = cleaned[:start.start()]

    cleaned = cleaned.strip()
    return cleaned if cleaned else text.strip()


def _strip_code_fence(text: str) -> str:
    """去掉 markdown 代码围栏：开头的 ```json / ``` 与结尾的 ```。"""
    s = text.strip()
    s = re.sub(r"^```[a-zA-Z0-9_+-]*\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()


def parse_fields(text: str) -> dict:
    """
    容错解析模型返回：
      0) 先剥离 think 推理段与 markdown 代码围栏；
      1) 直接 json.loads；
      2) 正则提取第一个 {...} 再解析；
      3) 仍失败则把文本塞进 raw/prompt。
    """
    cleaned = _strip_code_fence(strip_reasoning(text))

    # 1) 直接解析
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # 2) 提取第一个 JSON 对象
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

    # 3) 兜底
    log("警告：模型返回无法解析为 JSON，已把文本写入 raw/prompt 字段。")
    return {"raw": cleaned, "prompt": cleaned}


def release_gpu(llm, handler) -> None:
    """显式释放显存。"""
    try:
        del llm
    except Exception:
        pass
    try:
        del handler
    except Exception:
        pass
    gc.collect()
    try:
        import torch  # 可选依赖，装了就清一下缓存
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
    log("已请求释放模型与显存（del + gc.collect + cuda.empty_cache）。")


def default_outdir(video_path: Path) -> Path:
    """未指定 --outdir 时的默认输出目录。"""
    date_str = _dt.datetime.now().strftime("%Y-%m-%d")
    return REPO_ROOT / "output" / date_str / "motion_clone" / video_path.stem


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="动作克隆·轨道一：从参考视频均匀抽帧并用本地多模态大模型解析为英文 Prompt。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--video", required=True, help="参考视频路径（必填）")
    parser.add_argument("--frames", type=int, default=4, help="均匀抽取的关键帧数量")
    parser.add_argument("--outdir", default=None, help="输出目录（默认 output/<日期>/motion_clone/<视频名>/）")
    parser.add_argument("--n-ctx", type=int, default=8192, help="上下文长度")
    parser.add_argument("--max-tokens", type=int, default=2048, help="单次生成最大 token 数（需留出思考段预算）")
    parser.add_argument("--model", default=None, help="主模型路径（覆盖默认）")
    parser.add_argument("--mmproj", default=None, help="mmproj 路径（覆盖默认）")
    parser.add_argument("--dry-run", action="store_true", help="只抽帧与校验模型文件，不加载模型、不推理")
    args = parser.parse_args()

    t0 = time.time()

    video_path = Path(args.video).resolve()
    if not video_path.is_file():
        log(f"视频文件不存在：{video_path}")
        sys.exit(1)

    model_path = Path(args.model).resolve() if args.model else DEFAULT_MODEL
    mmproj_path = Path(args.mmproj).resolve() if args.mmproj else DEFAULT_MMPROJ

    outdir = Path(args.outdir).resolve() if args.outdir else default_outdir(video_path)
    outdir.mkdir(parents=True, exist_ok=True)
    log(f"输出目录：{outdir}")

    # 1) 模型存在性硬校验
    check_model_files(model_path, mmproj_path)

    # 2) 抽帧
    log(f"开始抽帧：视频={video_path}，目标帧数={args.frames}")
    fps, total_frames, width, height, indices, saved = extract_keyframes(video_path, outdir, args.frames)
    log(
        f"抽帧完成：fps={fps:.2f}，总帧数={total_frames}，分辨率={width}x{height}，"
        f"实际保存={len(saved)} 张，帧索引={indices}"
    )

    if args.dry_run:
        elapsed = time.time() - t0
        log(f"[dry-run] 已完成抽帧与模型文件校验，跳过加载与推理。耗时={elapsed:.2f}s，抽帧数={len(saved)}。")
        return

    # 3) 加载模型
    llm = None
    handler = None
    try:
        log(f"开始加载模型（n_ctx={args.n_ctx}，n_gpu_layers=-1）……")
        llm, handler, handler_name = build_llm(model_path, mmproj_path, args.n_ctx)

        # 4) 构造多图消息
        content = [{"type": "text", "text": USER_INSTRUCTION.format(n=len(saved))}]
        for p in saved:
            b64 = base64.b64encode(p.read_bytes()).decode("ascii")
            content.append({"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64}})

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ]

        # 5) 推理
        log(f"推理中（共 {len(saved)} 张关键帧，max_tokens={args.max_tokens}）……")
        try:
            resp = llm.create_chat_completion(
                messages=messages,
                max_tokens=args.max_tokens,
                chat_template_kwargs={"enable_thinking": False},
            )
        except Exception:
            log("提示：当前 llama_cpp 不支持 chat_template_kwargs，已静默回退为普通调用（未能关闭思考模式）。")
            resp = llm.create_chat_completion(messages=messages, max_tokens=args.max_tokens)
        raw_text = resp["choices"][0]["message"]["content"]
        if raw_text is None:
            raw_text = ""
        raw_text = raw_text.strip()

        # 6) 解析
        fields = parse_fields(raw_text)
        prompt_text = fields.get("prompt") or raw_text

        # 7) 写盘
        raw_path = outdir / "raw_response.txt"
        raw_path.write_text(raw_text + "\n", encoding="utf-8")

        prompt_json = {
            "source_video": str(video_path),
            "fps": round(float(fps), 4),
            "total_frames": total_frames,
            "width": width,
            "height": height,
            "sample_frames": [str(p) for p in saved],
            "fields": fields,
        }
        json_path = outdir / "prompt.json"
        json_path.write_text(json.dumps(prompt_json, ensure_ascii=False, indent=2), encoding="utf-8")

        txt_path = outdir / "prompt.txt"
        txt_path.write_text(prompt_text.rstrip("\n") + "\n", encoding="utf-8")

        log(f"已写入：{json_path}")
        log(f"已写入：{txt_path}")
        log(f"已写入：{raw_path}")
    finally:
        # 8) 显存释放（含异常路径）
        release_gpu(llm, handler)

    elapsed = time.time() - t0
    log(f"全部完成：总耗时={elapsed:.2f}s，抽帧数={len(saved)}。")


def run_self_test() -> int:
    """
    离线单元自检：不依赖模型，验证 strip_reasoning / parse_fields 的清洗与解析行为。
    全部通过打印 SELFTEST PASS 返回 0；否则打印 SELFTEST FAIL 返回非零码。
    """
    keys8 = ["scene", "subject", "outfit", "lighting", "camera", "motion", "prompt", "negative"]
    json_body = json.dumps({k: f"value for {k}" for k in keys8}, ensure_ascii=False)

    cases = [
        ("A: 成对 think 块 + 完整 8 字段 JSON",
         " thinking I should describe the frames first. \n" + json_body),
        ("B1: 多余 think 结束标记（有闭无开）+ JSON",
         "We analyze frame one and two...\n\n" + json_body),
        ("B2: 未闭合 think 开始标记（有开无闭，JSON 在前）",
         json_body + "\n thinking trailing thoughts that never close"),
        ("C: 纯 JSON（无 think）", json_body),
        ("D: think 块 + markdown 代码围栏包裹的 JSON",
         " thinking reasoning about frames \n```json\n" + json_body + "\n```"),
    ]

    ok = True
    for name, text in cases:
        fields = parse_fields(text)
        got = sorted(fields.keys())
        exp = sorted(keys8)
        if got == exp:
            print(f"[PASS] {name} -> keys={got}")
        else:
            ok = False
            print(f"[FAIL] {name} -> keys={got} (expected {exp})")

    # 清洗为空时应退回原始文本，且不崩溃
    empty_clean = strip_reasoning(" thinking only reasoning, nothing else ")
    if empty_clean == " thinking only reasoning, nothing else ".strip():
        print("[PASS] E: 清洗为空时退回原始文本")
    else:
        ok = False
        print(f"[FAIL] E: 清洗为空时未退回原始文本 -> {empty_clean!r}")

    print("SELFTEST PASS" if ok else "SELFTEST FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(run_self_test())
    main()