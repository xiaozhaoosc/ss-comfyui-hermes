#!/usr/bin/env python3
"""OOTD 图文批量生成提交器（系列化 + 断点续跑）

读取系列配置 series.json（project / base / shots），复用
tools/ootd_study/workflows/v5/ootd_image_flux_api.json 模板，对每个 shot 完成
「注入占位符 -> base 参数落地 -> 逐节点校验 -> 提交 -> 等待 -> 图片验收（非黑 +
尺寸）」，并把结果增量写入 output/<date>/<project>/progress.json。

用法:
  # 干跑：只做加载/注入/参数落地/逐节点校验，不提交
  python tools/ootd_study/ootd_series_submit.py \
      --series tools/ootd_study/series/ootd_blue_shirt.json --dry-run

  # 真提交全部 shot
  python tools/ootd_study/ootd_series_submit.py \
      --series tools/ootd_study/series/ootd_blue_shirt.json

  # 只跑指定 shot / 断点续跑（两者可组合）
  python tools/ootd_study/ootd_series_submit.py \
      --series ... --only 01_classic,02_eyes_revealed --resume

  # 指定归档日期（默认今天）
  python tools/ootd_study/ootd_series_submit.py --series ... --date 2026-10-02

仅依赖标准库 + tools/h3_fast_submit.py + venv 内已装的 av。
"""
import argparse
import copy
import datetime
import json
import os
import sys
import time

# 让 tools/ 目录可被导入（复用 h3_fast_submit，其 main 有 __main__ 保护不会被触发）
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS_DIR = os.path.dirname(_THIS_DIR)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import h3_fast_submit as h3  # noqa: E402

# ROOT = 上三级目录（tools/ootd_study/ootd_series_submit.py -> ComfyUI）
_ROOT = os.path.dirname(_TOOLS_DIR)
if not os.path.isdir(os.path.join(_ROOT, "input")):
    _ROOT = h3.ROOT  # 兜底
ROOT = _ROOT
INPUT_ROOT = os.path.join(ROOT, "input")
OUTPUT_ROOT = os.path.join(ROOT, "output")
DEFAULT_TEMPLATE = os.path.join(_THIS_DIR, "workflows", "v5", "ootd_image_flux_api.json")
DEFAULT_POSE = "pose_stretched_natural.png"
MIN_BRIGHTNESS = 3.0

BASE_REQUIRED = ["width", "height", "steps", "guidance", "lora", "lora_strength", "controlnet"]
CN_REQUIRED = ["enabled", "type", "strength", "end_percent"]
SHOT_REQUIRED = ["id", "prompt", "seed"]


# ----------------------------- 加载与校验 -----------------------------

def load_series(path):
    if not os.path.exists(path):
        raise ValueError(f"系列配置不存在: {path}")
    with open(path, "r", encoding="utf-8-sig") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"系列配置 JSON 解析失败: {e}")


def check_series(series):
    """返回错误信息列表（空列表表示通过）。"""
    errors = []
    if not isinstance(series, dict):
        return ["系列配置根节点必须是 JSON 对象"]
    project = series.get("project")
    if not isinstance(project, str) or not project.strip():
        errors.append("project 缺失或为空（必须为非空字符串）")
    base = series.get("base")
    if not isinstance(base, dict):
        errors.append("base 缺失或不是对象")
        base = {}
    for k in BASE_REQUIRED:
        if k not in base:
            errors.append(f"base 缺少字段: {k}")
    cn = base.get("controlnet")
    if not isinstance(cn, dict):
        errors.append("base.controlnet 缺失或不是对象")
        cn = {}
    else:
        for k in CN_REQUIRED:
            if k not in cn:
                errors.append(f"base.controlnet 缺少字段: {k}")
    shots = series.get("shots")
    if not isinstance(shots, list) or not shots:
        errors.append("shots 缺失、不是数组或为空")
        shots = []
    seen = set()
    for i, s in enumerate(shots):
        if not isinstance(s, dict):
            errors.append(f"shots[{i}] 不是对象")
            continue
        for k in SHOT_REQUIRED:
            if k not in s:
                errors.append(f"shots[{i}] 缺少字段: {k}")
        sid = s.get("id")
        if isinstance(sid, str) and sid:
            if sid in seen:
                errors.append(f"shot id 重复: {sid}")
            seen.add(sid)
        elif "id" in s:
            errors.append(f"shots[{i}].id 必须为非空字符串")
    return errors


def select_shots(shots, only_ids):
    if only_ids:
        by_id = {s.get("id"): s for s in shots if isinstance(s, dict)}
        missing = [oid for oid in only_ids if oid not in by_id]
        if missing:
            raise ValueError(
                f"--only 指定的 shot 不存在: {', '.join(missing)}；"
                f"可选: {', '.join(k for k in by_id)}")
        return [by_id[oid] for oid in only_ids]
    return shots


# ----------------------------- 构图 -----------------------------

def apply_base(wf, base):
    """把 base 参数真正落到已注入的工作流 dict 上（不走占位符）。"""
    wf["7"]["inputs"]["steps"] = base["steps"]
    wf["10"]["inputs"]["guidance"] = base["guidance"]
    wf["11"]["inputs"]["guidance"] = 1.0
    wf["20"]["inputs"]["strength_model"] = base["lora_strength"]
    wf["20"]["inputs"]["strength_clip"] = base["lora_strength"]
    if base.get("lora") and wf["20"]["inputs"].get("lora_name") != base["lora"]:
        wf["20"]["inputs"]["lora_name"] = base["lora"]
    cn = base["controlnet"]
    wf["33"]["inputs"]["strength"] = cn["strength"]
    wf["33"]["inputs"]["end_percent"] = cn["end_percent"]
    if cn["enabled"]:
        wf["7"]["inputs"]["positive"] = ["33", 0]
        wf["7"]["inputs"]["negative"] = ["33", 1]
    else:
        # 旁路 ControlNet：FluxGuidance 仅 1 个输出(索引 0)，
        # 故 KSampler.negative 必须取 ["11",0]（模板默认的 ["11",1] 会越界报错）
        wf["7"]["inputs"]["positive"] = ["10", 0]
        wf["7"]["inputs"]["negative"] = ["11", 0]
    return wf


def compose(template, shot, base, project, date):
    """返回 (wf, output_prefix, pose)。"""
    pose = shot.get("pose") or DEFAULT_POSE
    shot_id = shot["id"]
    prefix = f"{date}/{project}/img/{shot_id}"
    values = {
        "prompt": shot["prompt"],
        "seed": shot["seed"],
        "width": base["width"],
        "height": base["height"],
        "output": prefix,
        "pose": pose,
    }
    wf = h3.inject_placeholders(copy.deepcopy(template), values)
    apply_base(wf, base)
    return wf, prefix, pose


# ----------------------------- 进度文件 -----------------------------

def progress_path(date, project):
    return os.path.join(OUTPUT_ROOT, date, project, "progress.json")


def load_progress(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            data.setdefault("completed", [])
            data.setdefault("results", {})
            return data
        except Exception:
            pass
    return {"completed": [], "results": {}, "updated": None}


def save_progress(path, prog):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    prog["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(prog, f, ensure_ascii=False, indent=2)


# ----------------------------- 验收 -----------------------------

def image_size(png):
    import av
    with av.open(png) as c:
        s = c.streams.video[0]
        return int(s.width), int(s.height)


def pick_png(files):
    pngs = [p for p in files if p.lower().endswith(".png") and os.path.exists(p)]
    return pngs[-1] if pngs else None


# ----------------------------- 主流程 -----------------------------

def main():
    ap = argparse.ArgumentParser(description="OOTD 图文批量生成提交器")
    ap.add_argument("--series", required=True, help="系列配置 series.json 路径")
    ap.add_argument("--template", default=DEFAULT_TEMPLATE, help="API 工作流模板 JSON")
    ap.add_argument("--dry-run", action="store_true", help="只校验不提交")
    ap.add_argument("--resume", action="store_true", help="跳过 progress.json 中已完成的 shot")
    ap.add_argument("--only", default=None, help="只跑指定 shot id，逗号分隔")
    ap.add_argument("--date", default=None, help="归档日期 YYYY-MM-DD（默认今天）")
    args = ap.parse_args()

    date = args.date or datetime.date.today().isoformat()
    only_ids = [x.strip() for x in args.only.split(",") if x.strip()] if args.only else None

    # 1. 加载与校验系列配置
    try:
        series = load_series(args.series)
    except ValueError as e:
        print(f"[失败] {e}")
        return 1
    errs = check_series(series)
    if errs:
        print(f"[失败] 系列配置校验未通过（{len(errs)} 项）:")
        for e in errs:
            print("  - " + e)
        return 1
    project = series["project"]
    base = series["base"]

    try:
        shots = select_shots(series["shots"], only_ids)
    except ValueError as e:
        print(f"[失败] {e}")
        return 1

    # 2. 加载模板
    if not os.path.exists(args.template):
        print(f"[失败] 工作流模板不存在: {args.template}")
        return 1
    with open(args.template, "r", encoding="utf-8-sig") as f:
        template = json.load(f)

    print(f"[系列] {project}  日期={date}  模板={os.path.basename(args.template)}")
    print(f"[base] {base['width']}x{base['height']} steps={base['steps']} "
          f"guidance={base['guidance']} lora={base['lora']}@{base['lora_strength']} "
          f"controlnet={base['controlnet']['enabled']}")
    print(f"[shots] 待处理 {len(shots)} 个: {', '.join(s['id'] for s in shots)}")

    # ----------------------------- dry-run -----------------------------
    if args.dry_run:
        print("\n=== dry-run：加载 -> 注入 -> 参数落地 -> 逐节点校验（不提交）===")
        all_ok = True
        for shot in shots:
            sid = shot["id"]
            wf, prefix, pose = compose(template, shot, base, project, date)
            print(f"\n[{sid}] output_prefix = {prefix}")
            print(f"[{sid}] pose = {pose}（存在={os.path.exists(os.path.join(INPUT_ROOT, pose))}）")
            errors, lines = h3.validate_workflow(wf)
            for ln in lines:
                print(ln)
            if not os.path.exists(os.path.join(INPUT_ROOT, pose)):
                errors.append(f"pose 参考图不存在于 input: {pose}")
            if errors:
                all_ok = False
                print(f"[{sid}] 校验失败（{len(errors)} 项）:")
                for e in errors:
                    print("  - " + e)
            else:
                print(f"[{sid}] 校验 OK（{len(wf)} 节点）")
        if all_ok:
            print(f"\n[通过] {len(shots)} 个 shot 全部校验通过（dry-run 结束，未提交）")
            return 0
        print("\n[失败] 存在校验问题（dry-run 结束，未提交）")
        return 1

    # ----------------------------- 真提交 -----------------------------
    ppath = progress_path(date, project)
    prog = load_progress(ppath)
    print(f"\n[进度] {ppath}（已完成 {len(prog['completed'])}）")

    summary = []
    n_done = n_fail = n_skip = 0

    for shot in shots:
        sid = shot["id"]
        if args.resume and sid in prog["completed"]:
            n_skip += 1
            prev = prog["results"].get(sid, {})
            print(f"\n[{sid}] --resume：已完成，跳过（file={prev.get('file')}）")
            summary.append((sid, "跳过", prev.get("file"), prev.get("brightness"),
                            prev.get("width"), prev.get("height"), 0.0))
            continue

        t0 = time.time()
        print(f"\n=== [{sid}] 构图 ===")
        try:
            wf, prefix, pose = compose(template, shot, base, project, date)
        except Exception as e:
            n_fail += 1
            print(f"[{sid}] 构图失败: {e}")
            summary.append((sid, "构图失败", None, None, None, None, time.time() - t0))
            continue
        print(f"  output_prefix = {prefix}  pose = {pose}")

        # 逐节点校验（失败：中止该 shot 并继续下一个）
        errors, lines = h3.validate_workflow(wf)
        if errors:
            n_fail += 1
            print(f"[{sid}] 校验失败（{len(errors)} 项），中止该 shot，继续下一个:")
            for e in errors:
                print("  - " + e)
            summary.append((sid, "校验失败", None, None, None, None, time.time() - t0))
            continue
        print(f"  校验 OK（{len(wf)} 节点）")

        # 提交
        try:
            r = h3._post_json("/prompt", {"prompt": wf})
        except Exception as e:
            n_fail += 1
            print(f"[{sid}] 提交异常: {e}")
            summary.append((sid, "提交异常", None, None, None, None, time.time() - t0))
            continue
        pid = r.get("prompt_id")
        node_errors = r.get("node_errors") or {}
        if node_errors:
            n_fail += 1
            print(f"[{sid}] node_errors 非空，提交失败:")
            print(json.dumps(node_errors, ensure_ascii=False)[:1500])
            summary.append((sid, "提交失败", None, None, None, None, time.time() - t0))
            continue
        print(f"  已提交 pid={pid}，等待完成…")

        # 等待
        rec = h3.wait_done(pid)
        if not rec:
            n_fail += 1
            print(f"[{sid}] 未正常完成（超时或执行错误），继续下一个")
            summary.append((sid, "执行失败", None, None, None, None, time.time() - t0))
            continue

        files = h3.find_output_files(rec)
        png = pick_png(files)
        if not png or not os.path.exists(png):
            n_fail += 1
            print(f"[{sid}] outputs 中未定位到 PNG（{files}）")
            summary.append((sid, "无产物", None, None, None, None, time.time() - t0))
            continue

        # 验收：非黑 + 尺寸
        bright = h3.mean_brightness(png)
        try:
            w, h = image_size(png)
        except Exception as e:
            w = h = None
            print(f"[{sid}] 读取尺寸失败: {e}")
        ok_bright = bright is not None and bright >= MIN_BRIGHTNESS
        ok_size = (w == base["width"] and h == base["height"])
        elapsed = time.time() - t0
        print(f"  产物: {png}")
        print(f"  亮度 = {bright:.2f}（阈值 >= {MIN_BRIGHTNESS}）-> {'通过' if ok_bright else '未通过'}")
        print(f"  尺寸 = {w}x{h}（期望 {base['width']}x{base['height']}）-> {'通过' if ok_size else '未通过'}")

        if ok_bright and ok_size:
            n_done += 1
            prog["results"][sid] = {"file": png, "brightness": round(float(bright), 3),
                                    "width": w, "height": h}
            if sid not in prog["completed"]:
                prog["completed"].append(sid)
            save_progress(ppath, prog)
            print(f"  [{sid}] 验收通过，已写入 progress.json")
            summary.append((sid, "完成", png, bright, w, h, elapsed))
        else:
            n_fail += 1
            print(f"  [{sid}] 验收未通过（亮度/尺寸），不计入 completed")
            summary.append((sid, "验收失败", png, bright, w, h, elapsed))

    # ----------------------------- 汇总 -----------------------------
    print("\n=== 汇总 ===")
    for sid, status, file, bright, w, h, elapsed in summary:
        fn = os.path.basename(file) if file else "-"
        b = f"{bright:.2f}" if isinstance(bright, (int, float)) else "-"
        size = f"{w}x{h}" if w and h else "-"
        print(f"  [{status}] {sid}: file={fn} 亮度={b} 尺寸={size} 耗时={elapsed:.1f}s")
    print(f"\n完成 {n_done} / 失败 {n_fail} / 跳过 {n_skip}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())