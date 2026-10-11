#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""北宋杨家将 · 通用「九宫格分镜生成 + 切片」器（Nano Banana，0 积分）

由 EP04 试点脚本 `yangjiajiang_ep04_flow_pilot.py` 参数化而来，支持任意集数。
驱动层：原生 CDP WebSocket（tools/_flow_cdp.py）——Playwright 1.61 对 Chrome 154 的
connect_over_cdp 会卡死（<ws connected> 后 180s 超时），故弃用。

提示词来源：`tools/yangjiajiang_flow_grid_prompts.py` 的 `EP_GRID_PROMPTS[ep][grid]`。

用法：
  python tools/yangjiajiang_flow_grids.py --ep 1 --grid 1              # 生成 EP01 第 1 组
  python tools/yangjiajiang_flow_grids.py --ep 1 --all                  # 生成 EP01 全部 6 组
  python tools/yangjiajiang_flow_grids.py --ep 1 --grid 1 --dry         # 只打印提示词
  python tools/yangjiajiang_flow_grids.py --ep 1 --slice-all            # 切片全部已下载九宫格

纪律（源自项目记忆，勿改）：
  - Flow 须在 Settings 切 Image + 9:16（默认 16:9 会输出横屏导致切片拉伸）；
  - 提示词须声明 full-bleed / no numbering（见 prompts 模块），否则模型自动加 1-9 编号污染首帧；
  - 切片内缩默认 3%（去掉格框线又不伤构图）；
  - CDP WebSocket 卡死 → 杀 flow_chrome_profile 的 chrome 进程重开 bat；Chrome 重启可能掉登录且只绑 ::1。
"""

import os
import sys
import time
import base64
import argparse
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _flow_cdp import resolve_base, attach_flow_page

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = r"d:\ai_projects\ComfyUI"

# 成品图域名有三类：flow-content.google（画布视图）/ flow.google.com/asb（画廊缩略图）/ lh3.googleusercontent
JS_LIST_IMGS = (
    "Array.from(document.querySelectorAll("
    "\"img[src*='flow-content.google'], img[src*='/asb/'], img[src*='googleusercontent']\"))"
    ".map(e => e.currentSrc || e.src)"
    ".filter(s => s && !s.includes('ogw/') && !s.includes('pr_32px'))"
)
JS_SETTINGS_TEXT = (
    "(document.querySelector(\"button[aria-label='Settings trigger']\")||{}).innerText||''"
)


def log(m):
    print(m, flush=True)


def ep_tag(ep):
    return f"ep{int(ep):02d}"


def today_dir(ep):
    d = datetime.date.today().strftime("%Y-%m-%d")
    base = os.path.join(ROOT, "output", d, f"yangjiajiang_{ep_tag(ep)}")
    grids = os.path.join(base, "grids")
    frames = os.path.join(base, "frames")
    debug = os.path.join(base, "flow_debug")
    for p in (base, grids, frames, debug):
        os.makedirs(p, exist_ok=True)
    return base, grids, frames, debug


def load_prompts(ep):
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from yangjiajiang_flow_grid_prompts import EP_GRID_PROMPTS
    ep = int(ep)
    if ep not in EP_GRID_PROMPTS:
        raise SystemExit(f"[!] prompts 模块没有第 {ep} 集（可用: {sorted(EP_GRID_PROMPTS)}）")
    return EP_GRID_PROMPTS[ep]


SEL_SETTINGS = "document.querySelector(\"button[aria-label='Settings trigger']\")"
SEL_GENERATE = ("[...document.querySelectorAll(\"button[aria-label='Start generation']\")]"
                ".find(b => !b.disabled) || null")


def configure_generation(pg, mode="Image", ratio="9:16"):
    """Settings 面板：切 Image 模式 + 9:16（按钮文本按换行末行匹配）。真实鼠标点击。"""
    try:
        raw = (pg.eval(JS_SETTINGS_TEXT) or "").strip()
        lines = [x.strip() for x in raw.split("\n") if x.strip()]
        cur = " / ".join(lines)
        log(f"  [配置] 当前档位: {cur}")
        # 触发器文本形如 'Nano Banana 2.1\ncrop_9_16\n9:16'——必须按末行==目标比例判断，
        # 不能用子串匹配（'crop_9_16' 含 '9_16' 会误判，实际选中的可能是 16:9）
        if lines and lines[-1] == ratio:
            log(f"  [配置] 已是目标比例 {ratio}，跳过")
            return

        # 打开面板
        for attempt in (1, 2, 3):
            if not pg.click_selector(SEL_SETTINGS):
                log("  [配置] 未找到 Settings trigger")
                return
            time.sleep(2.5)
            if pg.eval("!!document.querySelector('.cdk-overlay-pane')"):
                break
            log(f"  [配置] 第 {attempt} 次未打开面板，重试...")
        else:
            log("  [配置] 设置面板始终未打开（忽略，沿用当前设置）")
            return

        # 1) 模式：Image / Video（文本形如 'image | Image'）
        js_mode = """
(() => {
  const pane = document.querySelector('.cdk-overlay-pane');
  if (!pane) return null;
  const needle = MODE.lower();
  for (const b of pane.querySelectorAll('button')) {
    const t = (b.innerText||'').trim().replace(/\\n/g,' ').toLowerCase();
    if (t.includes('| ' + needle) || t.endsWith(needle)) {
      const r = b.getBoundingClientRect();
      return JSON.stringify({x: r.x + r.width/2, y: r.y + r.height/2, label: t});
    }
  }
  return null;
})()""".replace("MODE.lower()", repr(mode.lower()))
        hit = pg.eval(js_mode)
        if hit:
            import json as _json
            pos = _json.loads(hit)
            pg.click_at(pos["x"], pos["y"])
            log(f"  [配置] 模式 -> {mode} ({pos['label'][:40]})")
        else:
            log("  [配置] 未找到模式按钮")
        time.sleep(0.8)

        # 2) 比例：按钮文本形如 'crop_9_16\n9:16'，取末行标签精确匹配
        js_ratio = """
(() => {
  const pane = document.querySelector('.cdk-overlay-pane');
  if (!pane) return null;
  const want = RATIO;
  for (const b of pane.querySelectorAll('button')) {
    const lines = (b.innerText||'').trim().split('\\n');
    if (lines[lines.length-1].trim() === want) {
      const r = b.getBoundingClientRect();
      return JSON.stringify({x: r.x + r.width/2, y: r.y + r.height/2});
    }
  }
  return null;
})()""".replace("RATIO", repr(ratio))
        hit = pg.eval(js_ratio)
        if hit:
            import json as _json
            pos = _json.loads(hit)
            pg.click_at(pos["x"], pos["y"])
            log(f"  [配置] 比例 -> {ratio}")
        else:
            log("  [配置] 未找到比例按钮")
        time.sleep(1.0)

        pg.key("Escape", code="Escape", key_code=27)
        time.sleep(0.8)
    except Exception as e:
        log(f"  [配置] 异常（忽略）: {e}")


def fill_prompt_and_generate(pg, prompt, debug, g):
    """清空编辑器 → 注入提示词 → 点生成。"""
    # 聚焦编辑器并全选清空（CDP 按键为受信输入，ProseMirror 可识别）
    pg.eval(
        "(document.querySelector('.ProseMirror')||{focus:()=>0}).focus();"
        "document.querySelector('.ProseMirror') ? 'focused' : 'no-editor'"
    )
    time.sleep(0.5)
    pg.key("a", code="KeyA", key_code=65, modifiers=2)  # Ctrl+A
    time.sleep(0.2)
    pg.key("Backspace", code="Backspace", key_code=8)
    time.sleep(0.4)
    pg.insert_text(prompt)
    time.sleep(1.2)

    got = pg.eval("(document.querySelector('.ProseMirror')||{innerText:''}).innerText.length")
    log(f"  [注入] 编辑器当前 {got} 字符（目标约 {len(prompt)}）")

    if not pg.click_selector(SEL_GENERATE, scroll=False):
        pg.screenshot(os.path.join(debug, f"grid{g}_no_genbtn.png"))
        log("[!] 找不到生成按钮，已截图 debug 目录。")
        return False
    return True


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


def generate_grid(ep, g, prompts, wait_s=100, dry=False):
    prompt = prompts[g]
    base, grids, frames, debug = today_dir(ep)
    out_path = os.path.join(grids, f"{ep_tag(ep)}_grid{g:02d}.png")

    log("=" * 68)
    log(f"[EP{int(ep):02d} Grid {g}] 目标: {out_path}")
    log("-" * 68)
    log(prompt)
    log("-" * 68 + f" ({len(prompt.split())} words)")

    if dry:
        log("[--dry] 仅打印提示词，未操作浏览器。")
        return None
    if os.path.exists(out_path):
        bak = os.path.join(grids, f"{ep_tag(ep)}_grid{g:02d}.prev_{int(time.time())}.png")
        os.replace(out_path, bak)
        log(f"[备份] 同名旧图已改名: {os.path.basename(bak)}")

    cdp = resolve_base()
    if not cdp:
        log("[!] CDP 9222 不可用（已探 127.0.0.1 / localhost / [::1]），请先运行 tools\\launch_flow_cdp_chrome.bat")
        return None
    log(f"[+] CDP 端点: {cdp}")

    pg = attach_flow_page(cdp)
    log(f"[+] 已接管页面: {pg.eval('location.href')}")
    try:
        before = set(pg.eval(JS_LIST_IMGS) or [])
        log(f"[+] 生成前页面图片数: {len(before)}")

        configure_generation(pg, mode="Image", ratio="9:16")

        if not fill_prompt_and_generate(pg, prompt, debug, g):
            return None
        log(f"[+] 已提交生成，等待出图（最多 {wait_s}s）...")

        new_src = None
        deadline = time.time() + wait_s
        while time.time() < deadline:
            time.sleep(5)
            now = pg.eval(JS_LIST_IMGS) or []
            fresh = [s for s in now if s not in before]
            if fresh:
                new_src = fresh[-1]
                log(f"  [√] 检测到新图: {new_src[:80]}...")
                break
            log("  ... 尚未出图")

        if not new_src:
            pg.screenshot(os.path.join(debug, f"grid{g}_timeout.png"))
            log(f"[!] 超时未捕获新图，已截图: grid{g}_timeout.png")
            return None

        time.sleep(3)
        srcs = pg.eval(JS_LIST_IMGS) or []
        pick = new_src
        for s in srcs:
            if s not in before and "=s" not in s:
                pick = s
        size = download_by_url(pg, pick, out_path)
        pg.screenshot(os.path.join(debug, f"grid{g}_after.png"))

        if size < 20000:
            log(f"[!] 下载文件过小({size}B)，可能非有效图片，请检查 {out_path}")
            return None
        log(f"[✓ EP{int(ep):02d} Grid {g} 完成] {out_path}  ({size/1024:.1f} KB)  0 积分")
        return out_path
    finally:
        pg.close()


def slice_grid(ep, g, pad=0.03, target=(544, 960)):
    """把第 g 组九宫格按 3x3 切为 9 张单镜首帧（544x960）。"""
    from PIL import Image
    base, grids, frames, debug = today_dir(ep)
    src = os.path.join(grids, f"{ep_tag(ep)}_grid{g:02d}.png")
    if not os.path.exists(src):
        log(f"[!] 找不到九宫格: {src}（请先 --grid {g} 生成）")
        return []
    img = Image.open(src).convert("RGB")
    W, H = img.size
    cw, ch = W / 3.0, H / 3.0
    log(f"[切片] EP{int(ep):02d} Grid {g} 源图 {W}x{H} -> 3x3，每格 {cw:.0f}x{ch:.0f}，内缩 {pad*100:.0f}%")
    outs = []
    for r in range(3):
        for c in range(3):
            shot = (g - 1) * 9 + r * 3 + c + 1
            cl = int(c * cw + cw * pad)
            ct = int(r * ch + ch * pad)
            cr = int((c + 1) * cw - cw * pad)
            cb = int((r + 1) * ch - ch * pad)
            crop = img.crop((cl, ct, cr, cb)).resize(target, Image.LANCZOS)
            p1 = os.path.join(frames, f"yang_{ep_tag(ep)}_shot{shot:02d}.jpg")
            crop.save(p1, quality=95)
            outs.append(p1)
    log(f"[✓ 切片完成] EP{int(ep):02d} Grid {g}: Shot {(g-1)*9+1:02d} ~ Shot {g*9:02d} 已输出到 {frames}")
    return outs


def make_contact_sheet(ep, g):
    from PIL import Image
    base, grids, frames, debug = today_dir(ep)
    imgs = []
    for i in range(9):
        shot = (g - 1) * 9 + i + 1
        p = os.path.join(frames, f"yang_{ep_tag(ep)}_shot{shot:02d}.jpg")
        if os.path.exists(p):
            imgs.append(Image.open(p))
    if len(imgs) != 9:
        log(f"[!] contact sheet 需要 9 张，当前 {len(imgs)} 张")
        return None
    w, h = imgs[0].size
    sheet = Image.new("RGB", (w * 3, h * 3), (20, 20, 20))
    for i, im in enumerate(imgs):
        sheet.paste(im, ((i % 3) * w, (i // 3) * h))
    out = os.path.join(debug, f"{ep_tag(ep)}_grid{g:02d}_contact_sheet.jpg")
    sheet.save(out, quality=92)
    log(f"[✓ 速览图] {out}")
    return out


def main():
    ap = argparse.ArgumentParser(description="北宋杨家将 通用九宫格生成 / 切片器")
    ap.add_argument("--ep", type=int, required=True, help="集数（如 1 / 5）")
    ap.add_argument("--grid", type=int, choices=[1, 2, 3, 4, 5, 6], help="生成指定组")
    ap.add_argument("--all", action="store_true", help="依次生成全部 6 组")
    ap.add_argument("--dry", action="store_true", help="只打印提示词，不操作浏览器")
    ap.add_argument("--slice", type=int, dest="slice_g", choices=[1, 2, 3, 4, 5, 6], help="切片指定组")
    ap.add_argument("--slice-all", action="store_true", help="切片全部已存在的九宫格")
    ap.add_argument("--pad", type=float, default=0.03, help="切片内缩比例（默认 0.03）")
    ap.add_argument("--wait", type=int, default=100, help="出图最长等待秒数（默认 100）")
    args = ap.parse_args()

    if args.slice_g or args.slice_all:
        targets = [args.slice_g] if args.slice_g else [1, 2, 3, 4, 5, 6]
        for g in targets:
            outs = slice_grid(args.ep, g, pad=args.pad)
            if outs:
                make_contact_sheet(args.ep, g)
        return

    prompts = load_prompts(args.ep)
    targets = [1, 2, 3, 4, 5, 6] if args.all else ([args.grid] if args.grid else [])
    if not targets:
        ap.print_help()
        return
    for g in targets:
        generate_grid(args.ep, g, prompts, wait_s=args.wait, dry=args.dry)
        if not args.dry and targets.index(g) < len(targets) - 1:
            time.sleep(3)


if __name__ == "__main__":
    main()
