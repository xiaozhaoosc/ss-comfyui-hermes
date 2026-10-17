#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Flow 虚拟角色资产工作流：本地 CPU 选最佳基准脸 + Flow 生成多视图。

两个子命令：
  select  从账号源目录的图片/视频里挑「最佳真人基准脸」（insightface CPU，检测分 × 人脸面积）
  gen     用 Flow（CDP 9222）围绕基准脸生成多视图
          ├─ 路线 A（默认）：上传基准脸作参考图 → 锁身份生成
          └─ 路线 B（--prompt-only）：不加参考图，纯提示词合成（仅作对比/兜底）

纪律（务守）：
  - 全程不碰 ComfyUI 8188 / 队列（本工具只读源目录 + 写 output/<日期>/hitomi_char_assets/）。
  - 非 ASCII 路径（如 "るーんちゃ！"）：读图用 np.fromfile + cv2.imdecode，写图用 imencode + tofile，
    cv2.imread/imwrite 对非 ASCII 路径会失败（项目历史踩过）。
  - Flow 侧沿用 tools/yangjiajiang_flow_grids.py 的选择器：Settings 切 Image + 比例
    （比例按钮按文本末行精确匹配，禁止子串：crop_9_16 含 9_16 会误判）；提示词注入 .ProseMirror；
    生成按钮取未 disabled 的，真实鼠标点击（JS .click() 对 Angular Material 无效）。
  - 找不到生成按钮 / 超时都要截图到 flow_debug/ 并返回非零，不死循环。

用法（python 用 C:\\Users\\kenzhao\\anaconda3\\python.exe）：
  python tools/flow_character_assets.py select --account "ayano (insta_ayano.fj)"
  python tools/flow_character_assets.py gen --account "ayano (insta_ayano.fj)" --dry
  python tools/flow_character_assets.py gen --account "ayano (insta_ayano.fj)" \\
      --project https://flow.google.com/project/<id> --views front,left45,right45,smile --wait 120
  python tools/flow_character_assets.py gen --account "ayano (insta_ayano.fj)" --prompt-only \\
      --views front,left45,right45,smile
"""

import os

# insightface→albumentations 会联网查版本（本机代理下会卡 ~30s），提前禁掉
os.environ.setdefault("NO_ALBUMENTATIONS_UPDATE", "1")

import argparse
import base64
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _flow_cdp import resolve_base, attach_flow_via_browser
from char_lib_add import _insightface_dir
from flow_character_prompts import VIEWS, build_prompt

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
DEFAULT_SOURCE = r"D:\Program Files\hitomi_downloader_GUI\hitomi_downloaded_insta"
DEFAULT_OUT = ROOT / "output" / "2026-10-12" / "hitomi_char_assets"
FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VID_EXT = {".mp4", ".mov", ".webm"}

JS_LIST_IMGS = (
    "Array.from(document.querySelectorAll("
    "\"img[src*='flow.google.com/asb/'], img[src*='flow-content.google'], img[src*='googleusercontent']\"))"
    ".map(e => e.currentSrc || e.src)"
    ".filter(s => s && !s.includes('ogw/') && !s.includes('pr_32px'))"
)
JS_SETTINGS_TEXT = "(document.querySelector(\"button[aria-label='Settings trigger']\")||{}).innerText||''"
JS_UNUSUAL_ACTIVITY = (
    "[...document.querySelectorAll('*')].some(e => e.children.length===0 "
    "&& /unusual activity/i.test(e.textContent||''))"
)
SEL_SETTINGS = "document.querySelector(\"button[aria-label='Settings trigger']\")"
SEL_GENERATE = ("[...document.querySelectorAll(\"button[aria-label='Start generation']\")]"
                ".find(b => !b.disabled) || null")


def log(m):
    print(m, flush=True)


# ---------------------------------------------------------------- 选脸（CPU）

def _safe_imread(path):
    """读图，兼容非 ASCII 路径（cv2.imread 对中文/日文路径返回 None）。"""
    import cv2
    img = cv2.imread(str(path))
    if img is None:
        img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    return img


def _safe_imwrite(path, img):
    """写图，兼容非 ASCII 路径（cv2.imwrite 对中文/日文路径写不出）。"""
    import cv2
    ok, buf = cv2.imencode(Path(path).suffix or ".jpg", img)
    if not ok:
        raise RuntimeError("编码失败: %s" % path)
    buf.tofile(str(path))


class FaceScorer:
    """insightface CPU 检测+识别；模型只加载一次（算法与 char_lib_add.detect_and_embed 一致）。"""

    def __init__(self):
        from insightface.model_zoo import get_model
        md = _insightface_dir()
        self.det = get_model(str(md / "det_10g.onnx"), providers=["CPUExecutionProvider"])
        self.det.prepare(ctx_id=-1, input_size=(640, 640), det_thresh=0.5)
        self.rec = get_model(str(md / "w600k_r50.onnx"), providers=["CPUExecutionProvider"])
        self.rec.prepare(ctx_id=-1)

    def score(self, img):
        """返回最大脸 {bbox, det_score, area, feat}；无脸返回 None。"""
        from types import SimpleNamespace
        bboxes, kpss = self.det.detect(img, input_size=(640, 640), max_num=0)
        if bboxes is None or len(bboxes) == 0:
            return None
        flat = np.asarray(bboxes, dtype=np.float32).reshape(-1)
        bb = flat.reshape(-1, 5)[:, :4] if flat.size % 5 == 0 else flat.reshape(-1, 4)[:, :4]
        kp = np.asarray(kpss, dtype=np.float32).reshape(-1, 5, 2)
        area = (bb[:, 2] - bb[:, 0]) * (bb[:, 3] - bb[:, 1])
        i = int(np.argmax(area))
        feat = np.asarray(self.rec.get(img, SimpleNamespace(kps=kp[i])), dtype=np.float32).reshape(-1)
        feat = feat / np.linalg.norm(feat)
        return {"bbox": [float(x) for x in bb[i]],
                "det_score": float(np.asarray(bboxes).reshape(-1, 5)[i, 4]),
                "area": float(area[i]), "feat": feat}


def _extract_frames(video, dst_dir, every):
    """用 ffmpeg 每 `every` 秒均匀抽一帧到 dst_dir；极短视频兜底取首帧。"""
    dst_dir.mkdir(parents=True, exist_ok=True)
    for f in dst_dir.glob("f_*.jpg"):
        f.unlink()
    pat = str(dst_dir / "f_%04d.jpg")
    subprocess.run([FFMPEG, "-y", "-i", str(video), "-vf", f"fps=1/{every}", "-q:v", "2", pat],
                   capture_output=True)
    frames = sorted(dst_dir.glob("f_*.jpg"))
    if not frames:
        subprocess.run([FFMPEG, "-y", "-ss", "0", "-i", str(video), "-frames:v", "1", "-q:v", "2", pat],
                       capture_output=True)
        frames = sorted(dst_dir.glob("f_*.jpg"))
    return frames


def cmd_select(a):
    src = Path(a.source) / a.account
    if not src.is_dir():
        sys.exit(f"[!] 源目录不存在: {src}")
    base = Path(a.out) / a.account / "base"
    base.mkdir(parents=True, exist_ok=True)
    tmp = Path(a.out) / a.account / "_frames"
    every = (1.0 / a.fps) if a.fps else a.every

    imgs = [p for p in sorted(src.iterdir()) if p.suffix.lower() in IMG_EXT]
    vids = [p for p in sorted(src.iterdir()) if p.suffix.lower() in VID_EXT]
    log(f"[select] 账号={a.account}｜图片={len(imgs)} 视频={len(vids)}｜抽帧间隔={every}s")

    candidates = [(p, f"image:{p.name}") for p in imgs]
    for v in vids:
        for i, f in enumerate(_extract_frames(v, tmp / v.stem[:40], every)):
            candidates.append((f, f"video:{v.name}#{i}"))
    log(f"[select] 候选总数={len(candidates)}，开始 CPU 打分（这是一次性成本）...")

    scorer = FaceScorer()
    results = []
    for n, (p, origin) in enumerate(candidates, 1):
        img = _safe_imread(p)
        if img is None:
            continue
        try:
            info = scorer.score(img)
        except Exception as e:
            log(f"  [{n}/{len(candidates)}] 跳过 {origin}（{e}）")
            continue
        if not info:
            continue
        results.append({"file": str(p), "origin": origin, "det_score": round(info["det_score"], 4),
                        "bbox": [round(x, 1) for x in info["bbox"]], "area": round(info["area"], 1),
                        "pick_score": round(info["det_score"] * info["area"], 1), "_feat": info["feat"]})
        if n % 20 == 0:
            log(f"  [{n}/{len(candidates)}] 已检出 {len(results)} 张脸")
    if not results:
        sys.exit("[!] 未在任何候选里检测到人脸")

    results.sort(key=lambda r: r["pick_score"], reverse=True)
    best = results[0]
    _safe_imwrite(base / "base_face.jpg", _safe_imread(best["file"]))
    np.save(base / "embedding.npy", best["_feat"])
    for r in results:
        r.pop("_feat")
    (base / "candidates.json").write_text(
        json.dumps({"account": a.account, "src": str(src), "count": len(results),
                    "ranked": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"[✓ select] 基准脸 -> {base / 'base_face.jpg'}")
    log(f"          det_score={best['det_score']} area={best['area']} pick={best['pick_score']}｜来源 {best['origin']}")
    log(f"          候选清单 -> {base / 'candidates.json'}（共 {len(results)} 张脸）")


# ---------------------------------------------------------------- Flow 生成

def configure_generation(pg, ratio):
    """Settings 面板：切 Image 模式 + 目标比例（末行精确匹配）。真实鼠标点击。"""
    try:
        lines = [x.strip() for x in (pg.eval(JS_SETTINGS_TEXT) or "").split("\n") if x.strip()]
        log(f"  [配置] 当前档位: {' / '.join(lines)}")
        if lines and lines[-1] == ratio:
            log(f"  [配置] 已是目标比例 {ratio}，跳过")
            return
        for attempt in (1, 2, 3):
            pg.click_selector(SEL_SETTINGS)
            time.sleep(2.5)
            if pg.eval("!!document.querySelector('.cdk-overlay-pane')"):
                break
            log(f"  [配置] 第 {attempt} 次未打开面板，重试...")
        else:
            log("  [配置] 设置面板始终未打开（沿用当前设置）")
            return

        js_mode = """
(() => {
  const pane = document.querySelector('.cdk-overlay-pane');
  if (!pane) return null;
  const needle = 'image';
  for (const b of pane.querySelectorAll('button')) {
    const t = (b.innerText||'').trim().replace(/\\n/g,' ').toLowerCase();
    if (t.includes('| ' + needle) || t.endsWith(needle)) {
      const r = b.getBoundingClientRect();
      return JSON.stringify({x: r.x + r.width/2, y: r.y + r.height/2, label: t});
    }
  }
  return null;
})()"""
        hit = pg.eval(js_mode)
        if hit:
            pos = json.loads(hit)
            pg.click_at(pos["x"], pos["y"])
            log(f"  [配置] 模式 -> Image ({pos['label'][:40]})")
        else:
            log("  [配置] 未找到模式按钮")
        time.sleep(0.8)

        js_ratio = """
(() => {
  const pane = document.querySelector('.cdk-overlay-pane');
  if (!pane) return null;
  const want = RATIO;
  for (const b of pane.querySelectorAll('button')) {
    const l = (b.innerText||'').trim().split('\\n');
    if (l[l.length-1].trim() === want) {
      const r = b.getBoundingClientRect();
      return JSON.stringify({x: r.x + r.width/2, y: r.y + r.height/2});
    }
  }
  return null;
})()""".replace("RATIO", repr(ratio))
        hit = pg.eval(js_ratio)
        if hit:
            pos = json.loads(hit)
            pg.click_at(pos["x"], pos["y"])
            log(f"  [配置] 比例 -> {ratio}")
        else:
            log(f"  [配置] 未找到比例按钮 {ratio}（沿用当前）")
        time.sleep(1.0)
        pg.key("Escape", code="Escape", key_code=27)
        time.sleep(0.8)
    except Exception as e:
        log(f"  [配置] 异常（忽略）: {e}")


def fill_prompt(pg, prompt):
    """清空 .ProseMirror → 注入提示词。"""
    pg.eval("(document.querySelector('.ProseMirror')||{focus:()=>0}).focus();"
            "document.querySelector('.ProseMirror') ? 'focused' : 'no-editor'")
    time.sleep(0.5)
    pg.key("a", code="KeyA", key_code=65, modifiers=2)  # Ctrl+A
    time.sleep(0.2)
    pg.key("Backspace", code="Backspace", key_code=8)
    time.sleep(0.4)
    pg.insert_text(prompt)
    time.sleep(1.2)
    return pg.eval("(document.querySelector('.ProseMirror')||{innerText:''}).innerText.length")


def download_by_url(pg, src, path):
    js_fetch = """
(async (url) => {
  const res = await fetch(url);
  const blob = await res.blob();
  return await new Promise((r) => {
    const rd = new FileReader();
    rd.onloadend = () => r(rd.result.split(',')[1]);
    rd.readAsDataURL(blob);
  });
})"""
    b64 = pg.eval(f"({js_fetch})({src!r})", await_promise=True, timeout=90)
    with open(path, "wb") as f:
        f.write(base64.b64decode(b64))
    return os.path.getsize(path)


def _attach_reference(pg, filename, debug):
    """把已上传到项目库的基准脸作为「参考图」加入提示框（成分选择器 → Add to prompt）。"""
    stem = Path(filename).stem
    for attempt in range(3):
        pg.click_selector("document.querySelector(\"button[aria-label='Add ingredients to the prompt box']\")")
        time.sleep(3)
        tile_js = (
            "(() => { const els=[...document.querySelectorAll('*')].filter(e=>e.children.length===0"
            " && (e.textContent||'').includes(%r)); if(!els.length) return null; let el=els[0];"
            " for(let i=0;i<8&&el;i++){ if(el.getBoundingClientRect().width>40) break; el=el.parentElement;}"
            " return el; })()" % stem)
        if pg.click_selector(tile_js):
            time.sleep(2)
            if pg.click_selector("[...document.querySelectorAll('button')]"
                                 ".find(b => /Add to prompt/.test(b.innerText||'')) || null"):
                time.sleep(2)
                pg.key("Escape", code="Escape", key_code=27)
                log(f"  [A] 已把参考脸 {filename} 加入提示框")
                return
        pg.key("Escape", code="Escape", key_code=27)
        time.sleep(1)
        log(f"  [A] 第 {attempt + 1} 次未加入参考图，重试...")
    pg.screenshot(str(debug / "attach_ref_fail.png"))
    raise RuntimeError("未能把参考图加入提示框（成分选择器未出现目标媒体）")


def generate_view(pg, view, prompt, vdir, debug, wait_s):
    """注入提示词 → 点生成 → 轮询新图 → 下载到 vdir/<view>.png。"""
    out_path = vdir / f"{view}.png"
    log("-" * 60)
    log(f"[{view}] 目标: {out_path}")
    log(prompt)

    before = set(pg.eval(JS_LIST_IMGS) or [])
    got = fill_prompt(pg, prompt)
    log(f"  [注入] 编辑器 {got} 字符（目标约 {len(prompt)}）")
    if not pg.click_selector(SEL_GENERATE, scroll=False):
        pg.screenshot(str(debug / f"{view}_no_genbtn.png"))
        log(f"[!] 找不到可用的生成按钮，已截图 {view}_no_genbtn.png")
        return None
    log(f"  [+] 已提交，等待出图（最多 {wait_s}s）...")

    new_src, deadline = None, time.time() + wait_s
    while time.time() < deadline:
        time.sleep(5)
        try:
            now = pg.eval(JS_LIST_IMGS) or []
        except Exception as e:
            pg.screenshot(str(debug / f"{view}_ws_dead.png"))
            log(f"[!] CDP 会话中断（{e}），已截图 {view}_ws_dead.png")
            return None
        if pg.eval(JS_UNUSUAL_ACTIVITY):
            pg.screenshot(str(debug / f"{view}_flow_failed.png"))
            log(f"[!] Flow 判定异常活动，生成失败（已截图 {view}_flow_failed.png）；跳过该视图")
            return None
        fresh = [s for s in now if s not in before]
        if fresh:
            new_src = fresh[-1]
            log(f"  [√] 检测到新图: {new_src[:78]}...")
            break
        log("  ... 尚未出图")
    if not new_src:
        pg.screenshot(str(debug / f"{view}_timeout.png"))
        log(f"[!] 超时未捕获新图，已截图 {view}_timeout.png")
        return None

    time.sleep(3)
    srcs = pg.eval(JS_LIST_IMGS) or []
    pick = new_src
    for s in srcs:
        if s not in before and "=s" not in s:
            pick = s
    size = download_by_url(pg, pick, out_path)
    pg.screenshot(str(debug / f"{view}_after.png"))
    if size < 20000:
        log(f"[!] 下载文件过小({size}B)，可能非有效图: {out_path}")
        return None
    log(f"[✓ {view}] {out_path}  ({size / 1024:.1f} KB)")
    return out_path


def _attach_flow(cdp, url):
    """接管 Flow 页。用浏览器级 CDP + attachToTarget 会话：
    实测 Chrome 154 的页面级 ws 会在生成过程中偶发卡死（Runtime 不再响应），
    而浏览器级会话稳定，故直接用后者。"""
    return attach_flow_via_browser(cdp, navigate_url=url)


def _wait_composer(pg, timeout_s=60):
    """等生成输入框出现（项目页加载较慢）。"""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if pg.eval("!!document.querySelector('.ProseMirror')"):
            return True
        time.sleep(3)
    return False


def cmd_gen(a):
    out = Path(a.out) / a.account
    base = out / "base"
    face = Path(a.face) if a.face else (base / "base_face.jpg")
    views = [v.strip() for v in a.views.split(",") if v.strip()]
    for v in views:
        if v not in VIEWS:
            sys.exit(f"[!] 未知视图键 {v!r}（可用: {', '.join(VIEWS)}）")

    subdir = "views_promptonly" if a.prompt_only else "views"
    vdir = out / subdir
    debug = out / "flow_debug"
    vdir.mkdir(parents=True, exist_ok=True)
    debug.mkdir(parents=True, exist_ok=True)
    hint = a.char_hint or ""
    prompts = {v: build_prompt(v, hint) for v in views}

    route = "B（纯提示词）" if a.prompt_only else "A（参考图）"
    log(f"===== Flow 角色多视图生成｜账号={a.account}｜路线 {route} =====")
    log(f"视图: {', '.join(views)}｜比例: {a.ratio}｜产物目录: {vdir}")
    log(f"参考脸: {'—' if a.prompt_only else face}")

    if a.dry:
        for v in views:
            log("=" * 60)
            log(f"[{v}] -> {vdir / (v + '.png')}")
            log(prompts[v])
        log("[--dry] 仅打印提示词与目标路径，未连浏览器。")
        return 0

    if not a.prompt_only and not face.exists():
        sys.exit(f"[!] 找不到基准脸 {face}，请先跑 select 或 --face 指定")

    cdp = resolve_base()
    if not cdp:
        sys.exit("[!] CDP 9222 不可用（已探 127.0.0.1 / localhost / [::1]），请先运行 tools\\launch_flow_cdp_chrome.bat")
    log(f"[+] CDP 端点: {cdp}")
    pg = _attach_flow(cdp, a.project)
    log(f"[+] 已接管页面: {pg.eval('location.href')}")
    if not _wait_composer(pg):
        pg.screenshot(str(debug / "no_composer.png"))
        pg.close()
        sys.exit("[!] 当前页面没有生成输入框（可能未登录 / 不在项目页）。已截图 flow_debug/no_composer.png；"
                 "请用 --project 指定项目 URL，或人工重登 Google 后重试。")

    rc = 0
    try:
        if not a.prompt_only:
            try:
                pg.upload_file(str(face))
                log(f"[A] 已上传参考脸到 Flow 项目库: {face.name}")
                time.sleep(6)  # 等 Flow 侧把文件入库，成分选择器才能列出
            except Exception as e:
                pg.screenshot(str(debug / "upload_fail.png"))
                log(f"[!] 参考图上传失败（{e}）→ 降级路线 B 或人工检查。已截图 flow_debug/upload_fail.png")
                pg.close()
                return 3

        configure_generation(pg, a.ratio)

        ok = 0
        for v in views:
            if not a.prompt_only:
                # Flow 每次出图后会清掉提示框里的参考图，故每张前都重新挂载，否则会漂移
                try:
                    _attach_reference(pg, face.name, debug)
                except Exception as e:
                    log(f"[!] {v} 参考图挂载失败（{e}），该视图可能漂移")
            try:
                r = generate_view(pg, v, prompts[v], vdir, debug, a.wait)
            except Exception as e:
                pg.screenshot(str(debug / f"{v}_error.png"))
                log(f"[!] {v} 生成异常（{e}），已截图 {v}_error.png")
                r = None
            ok += 1 if r else 0
        log(f"[完成] {ok}/{len(views)} 张成功 → {vdir}")
        rc = 0 if ok == len(views) else 1
    finally:
        pg.close()
    return rc


def main():
    ap = argparse.ArgumentParser(description="Flow 虚拟角色资产：选脸 + 多视图生成")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("select", help="本地 CPU 从账号目录选最佳基准脸")
    sp.add_argument("--account", required=True, help="账号目录名（如 'ayano (insta_ayano.fj)'）")
    sp.add_argument("--source", default=DEFAULT_SOURCE, help="源目录根（默认 hitomi_downloaded_insta）")
    sp.add_argument("--out", default=str(DEFAULT_OUT), help="输出根目录")
    sp.add_argument("--every", type=float, default=2.0, help="视频抽帧间隔秒（默认 2）")
    sp.add_argument("--fps", type=float, help="按 fps 抽帧（覆盖 --every）")
    sp.set_defaults(func=cmd_select)

    gp = sub.add_parser("gen", help="Flow 生成多视图")
    gp.add_argument("--account", required=True)
    gp.add_argument("--source", default=DEFAULT_SOURCE)
    gp.add_argument("--face", help="基准脸路径（缺省用 select 产物 <out>/<账号>/base/base_face.jpg）")
    gp.add_argument("--views", default=",".join(VIEWS), help="逗号分隔视图键（默认全部）")
    gp.add_argument("--ratio", default="1:1", help="生成比例（默认 1:1）")
    gp.add_argument("--out", default=str(DEFAULT_OUT))
    gp.add_argument("--wait", type=int, default=120, help="单张最长等待秒（默认 120）")
    gp.add_argument("--dry", action="store_true", help="只打印提示词与目标路径，不连浏览器")
    gp.add_argument("--prompt-only", action="store_true", help="路线 B：不加参考图，产物落 views_promptonly/")
    gp.add_argument("--char-hint", help="路线 B 的外貌描述（夹带进提示词）")
    gp.add_argument("--project", help="Flow 项目页 URL（页面不在 /project/ 下时导航过去）")
    gp.set_defaults(func=cmd_gen)

    a = ap.parse_args()
    sys.exit(a.func(a) or 0)


if __name__ == "__main__":
    main()