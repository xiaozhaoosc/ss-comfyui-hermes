#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""北宋杨家将 · 第 4 集《邠阳城·血》Google Flow 九宫格生成器（Nano Banana，0 积分）

用途：
1. 通过 CDP(127.0.0.1:9222) 接管已登录的 Flow 页面，用 Nano Banana 生成 6 组 3x3 九宫格分镜总览板。
2. 每组九宫格对应 9 镜（共 54 镜），下载后按 3x3 切分为单镜首帧（另由 slice 子命令完成）。

美术纪律（与元数据表一致）：
- 新白描 = 上美影手绘动画风：白描为骨 + 宣纸底 + 淡彩平涂
- 本集不启用朱砂红；战场不给血
- 竖屏 9:16 成片，九宫格内每格即一镜的首帧构图

用法：
  python tools/yangjiajiang_ep04_flow_pilot.py --grid 1        # 生成第 1 组九宫格（试点）
  python tools/yangjiajiang_ep04_flow_pilot.py --grid 1 --dry  # 只打印提示词，不操作浏览器
  python tools/yangjiajiang_ep04_flow_pilot.py --slice 1       # 把已下载的 grid1 切成 9 张首帧
"""

import os
import sys
import time
import base64
import argparse
import datetime

import requests
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

CDP_URL = "http://127.0.0.1:9222"
ROOT = r"d:\ai_projects\ComfyUI"

# 统一样式基座（正向描述，不使用否定句——Flow 无负向词字段）
STYLE_BASE = (
    "Traditional Chinese ink-wash cut-paper animation style, vintage Shanghai Animation Film Studio aesthetic, "
    "crisp black ink brush outlines, flat solid blocks of mineral pigment colour, raw rice paper texture, "
    "palette of ink black, moon white, celadon green, ochre and pale gold, flat cel-shaded light, film grain."
)

GRID_HEAD = (
    "A 3x3 nine-panel cinematic storyboard grid, panels read left to right top to bottom, "
    "nine consecutive scenes from a Northern Song Dynasty historical epic. "
    "Each panel is full-bleed artwork filling its own cell edge to edge, "
    "clean illustration only with no panel numbers, no captions and no text of any kind. "
)

# 6 组九宫格提示词（每组 9 个 panel，对应 EP04_METADATA 的 9 镜）
EP04_GRID_PROMPTS = {
    1: GRID_HEAD + (
        "Panel 1: a lone walled city ringed by countless enemy campfires under a heavy moon. "
        "Panel 2: a young armored general kneels in a candlelit hall, pledging his life. "
        "Panel 3: an old general holds up a candle and studies the young man's face closely. "
        "Panel 4: the emperor sits alone behind his desk, knuckles tapping, undecided. "
        "Panel 5: a city map spread on the desk, a finger tracing toward the west gate. "
        "Panel 6: a dust-covered soldier bursts through the door with urgent news. "
        "Panel 7: the young general bows and points at the emperor's golden dragon robe. "
        "Panel 8: the golden dragon robe lowered onto the young general's shoulders. "
        "Panel 9: four armored young men follow him out through a dark doorway. "
    ) + STYLE_BASE,
    2: GRID_HEAD + (
        "Panel 1: inside an enemy tent at night, a chieftain reads a surrender letter by a brazier. "
        "Panel 2: an enemy general in armor advises acceptance, hand on his sword. "
        "Panel 3: enemy cavalry parted to open a long empty surrender corridor toward a city gate. "
        "Panel 4: a white surrender flag rising slowly on a city wall at dawn. "
        "Panel 5: the east gate barely ajar, a small group of riders slipping out, the emperor in plain cloth looking back. "
        "Panel 6: the west gate wide open, an imperial dragon carriage rolling out with curtain lowered. "
        "Panel 7: close on the swinging carriage curtain, a corner of golden robe showing within. "
        "Panel 8: an enemy chieftain on horseback towering over the carriage, whip raised in arrogance. "
        "Panel 9: the dragon carriage alone amid thousands of enemy riders, dead silence, dust hanging in air. "
    ) + STYLE_BASE,
    3: GRID_HEAD + (
        "Panel 1: inside the carriage a young man lifts his head, eyes flashing, hand raised to signal. "
        "Panel 2: the carriage curtain flung open, blinding daylight bursting in, a figure standing up. "
        "Panel 3: the young man draws a bow to full crescent, arrow aimed off-screen. "
        "Panel 4: an arrow flying across open ground toward an enemy chieftain on horseback. "
        "Panel 5: the chieftain's horse rearing, the saddle empty, enemy riders recoiling. "
        "Panel 6: three young armored riders bursting from both sides of the carriage, blades sweeping. "
        "Panel 7: an enemy formation collapsing into dust and falling banners, riders colliding. "
        "Panel 8: the young man leaping down from the carriage taking a long spear from a guard. "
        "Panel 9: close on his empty sword-clasp and plain battle robe, only a spear in hand. "
    ) + STYLE_BASE,
}

EP04_GRID_PROMPTS.update({
    4: GRID_HEAD + (
        "Panel 1: an enemy general on horseback thrusting a spear down at a foot soldier below. "
        "Panel 2: a burst of armor scale plates scattering and a spear spinning loose from a hand, no blood shown. "
        "Panel 3: the foot soldier thrusting his spear into an enemy horse's flank, the rider thrown to dust. "
        "Panel 4: shot from behind a shoulder, a young man falling toward off-screen, his fall unseen. "
        "Panel 5: a second young rider charging in, driving the enemy back, vaulting off his horse. "
        "Panel 6: the lone rider surrounded and attacked by two enemy generals on an open plain. "
        "Panel 7: the young man rising once more, spear driven into an enemy's armor, then bowing slowly to the earth, spear planted in frozen ground. "
        "Panel 8: a third young horseman in a reed marsh, horse toppling over hidden trip ropes, dust and lance-ends only, no blood. "
        "Panel 9: wide high-angle still of a battlefield, three banners tilted into frozen soil beneath settling dust. "
    ) + STYLE_BASE,
    5: GRID_HEAD + (
        "Panel 1: a young soldier retreating behind a broken earthen wall, dust and shouts rising outside. "
        "Panel 2: close overhead of his hands drawing a worn small wooden box from his robe. "
        "Panel 3: the box open, a razor and an ordination certificate lying inside under a shaft of light. "
        "Panel 4: the young man seated with hair loosed, a razor drawn down from his brow, black hair falling. "
        "Panel 5: broken breastplate and iron helmet hung on a bare tree, swaying in wind. "
        "Panel 6: the young man in a plain grey monk's robe, looking back once at the armor on the tree. "
        "Panel 7: two enemy soldiers blocking a path with spears, the monk showing his certificate, palms together. "
        "Panel 8: a fourth young horseman half-kneeling amid enemy spears, his horse down, back unbowed. "
        "Panel 9: two riders crossing in opposite directions on a dusty road, never looking back at each other. "
    ) + STYLE_BASE,
    6: GRID_HEAD + (
        "Panel 1: dusk on an empty battlefield, enemy riders searching among cold embers, one general reining in. "
        "Panel 2: an emperor in plain cloth turning his horse to look back across open fields, anxious. "
        "Panel 3: close on an old general bowing his head, hands clasped, beard trembling in the wind. "
        "Panel 4: the old general standing in a low sun, looking back once as dust veils the distant hills. "
        "Panel 5: a lone young rider blocking a road with his spear, coaches receding behind him. "
        "Panel 6: enemy cavalry turning back at sunset, gold gong struck three times, dust falling. "
        "Panel 7: a column of enemy riders escorting a bound captive northward, hoofprints in the dust road. "
        "Panel 8: three empty saddles set side by side on bare ground, reins loose and stirring in the wind. "
        "Panel 9: sunrise, a short column of riders heading east, sunlight spreading along the horizon. "
    ) + STYLE_BASE,
})

def log(m):
    print(m, flush=True)


def today_dir():
    d = datetime.date.today().strftime("%Y-%m-%d")
    base = os.path.join(ROOT, "output", d, "yangjiajiang_ep04")
    grids = os.path.join(base, "grids")
    frames = os.path.join(base, "frames")
    debug = os.path.join(base, "flow_debug")
    for p in (base, grids, frames, debug):
        os.makedirs(p, exist_ok=True)
    return base, grids, frames, debug


def is_cdp_ready():
    try:
        return requests.get(f"{CDP_URL}/json/version", timeout=3).status_code == 200
    except Exception:
        return False


def find_flow_page(ctx):
    for pg in ctx.pages:
        try:
            if "flow.google.com" in pg.url:
                return pg
        except Exception:
            continue
    return None


def configure_generation(page, mode="Image", ratio="9:16"):
    """配置生成模式与画幅比例。EP04 需要 Image 模式 + 9:16 竖屏（九宫格整体 9:16，单格也是 9:16）。

    实测面板按钮文本形如：'image | Image'、'crop_9_16 | 9:16'（图标名 | 标签）。
    """
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(600)
        trigger = page.locator("button[aria-label='Settings trigger']").first
        if trigger.count() == 0:
            log("  [配置] 未找到 Settings trigger，沿用当前设置")
            return
        t0 = (trigger.inner_text() or "").replace("\n", " ")
        log(f"  [配置] 当前档位: {t0}")
        if ratio.replace(":", "_") in t0:
            log(f"  [配置] 已是目标比例 {ratio}，跳过")
            return

        pane = None
        for attempt in (1, 2, 3):
            trigger.click(force=True)
            page.wait_for_timeout(2500)
            p = page.locator(".cdk-overlay-pane").first
            if p.count() > 0:
                pane = p
                break
            log(f"  [配置] 第 {attempt} 次未打开面板，重试...")
        if pane is None:
            log("  [配置] 设置面板始终未打开")
            page.keyboard.press("Escape")
            return

        # 1) 模式：Image / Video（按钮文本含图标名前缀）
        for b in pane.locator("button").all():
            try:
                t = (b.inner_text() or "").strip().replace("\n", " ")
                if ("| " + mode.lower()) in t.lower() or t.lower().endswith(mode.lower()):
                    b.click(force=True)
                    page.wait_for_timeout(500)
                    log(f"  [配置] 模式 -> {mode}")
                    break
            except Exception:
                continue

        # 2) 比例：按钮文本形如 'crop_9_16\n9:16'，取末行标签精确匹配
        for b in pane.locator("button").all():
            try:
                raw = (b.inner_text() or "").strip()
                label = raw.split("\n")[-1].strip()
                if label == ratio:
                    b.click(force=True)
                    page.wait_for_timeout(600)
                    log(f"  [配置] 比例 -> {ratio}")
                    break
            except Exception:
                continue

        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
    except Exception as e:
        log(f"  [配置] 异常（忽略）: {e}")


def get_img_srcs(page):
    try:
        return page.eval_on_selector_all(
            "img[src*='flow-content.google']",
            "els => els.map(e => e.currentSrc || e.src)")
    except Exception:
        return []


def download_by_src(page, src, path):
    b64 = page.evaluate("""async (url) => {
        const res = await fetch(url);
        const blob = await res.blob();
        return await new Promise((r) => {
            const rd = new FileReader();
            rd.onloadend = () => r(rd.result.split(',')[1]);
            rd.readAsDataURL(blob);
        });
    }""", src)
    with open(path, "wb") as f:
        f.write(base64.b64decode(b64))
    return os.path.getsize(path)


def generate_grid(g, wait_s=100, dry=False):
    prompt = EP04_GRID_PROMPTS[g]
    base, grids, frames, debug = today_dir()
    out_path = os.path.join(grids, f"ep04_grid{g:02d}.png")

    log("=" * 68)
    log(f"[Grid {g}] 目标: {out_path}")
    log("-" * 68)
    log(prompt)
    log("-" * 68 + f" ({len(prompt.split())} words)")

    if dry:
        log("[--dry] 仅打印提示词，未操作浏览器。")
        return None
    if os.path.exists(out_path):
        bak = os.path.join(grids, f"ep04_grid{g:02d}.prev_{int(time.time())}.png")
        os.replace(out_path, bak)
        log(f"[备份] 同名旧图已改名: {os.path.basename(bak)}")
    if not is_cdp_ready():
        log("[!] CDP 9222 不可用，请先运行 tools\\launch_flow_cdp_chrome.bat")
        return None

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0]
        page = find_flow_page(ctx)
        if page is None:
            log("[!] 未找到已打开的 flow.google.com 页面，请先在 CDP Chrome 中打开 Flow 项目。")
            return None
        log(f"[+] 已接管页面: {page.url}")
        page.bring_to_front()

        before = set(get_img_srcs(page))
        log(f"[+] 生成前页面图片数: {len(before)}")

        configure_generation(page, mode="Image", ratio="9:16")

        editor = page.locator(".ProseMirror").first
        if editor.count() == 0:
            page.screenshot(path=os.path.join(debug, f"grid{g}_no_editor.png"))
            log("[!] 找不到 .ProseMirror 提示词输入框，已截图 debug 目录。")
            return None
        editor.click(force=True)
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.wait_for_timeout(300)
        page.keyboard.type(prompt, delay=6)
        page.wait_for_timeout(800)

        gen = page.locator("button[aria-label='Start generation'], button:has-text('arrow_forward')").first
        if gen.count() == 0:
            page.screenshot(path=os.path.join(debug, f"grid{g}_no_genbtn.png"))
            log("[!] 找不到生成按钮，已截图 debug 目录。")
            return None
        gen.click(force=True)
        log(f"[+] 已提交生成，等待出图（最多 {wait_s}s）...")

        # 等待新图出现（有限次检查，非任务轮询）
        new_src = None
        deadline = time.time() + wait_s
        while time.time() < deadline:
            page.wait_for_timeout(5000)
            now = get_img_srcs(page)
            fresh = [s for s in now if s not in before]
            if fresh:
                new_src = fresh[-1]
                log(f"  [√] 检测到新图: {new_src[:80]}...")
                break
            log("  ... 尚未出图")

        if not new_src:
            page.screenshot(path=os.path.join(debug, f"grid{g}_timeout.png"), full_page=True)
            log(f"[!] 超时未捕获新图，已截图: grid{g}_timeout.png")
            return None

        # 给浏览器一点时间完成大图渲染，再取最高分辨率源
        page.wait_for_timeout(3000)
        srcs = get_img_srcs(page)
        pick = new_src
        for s in srcs:
            if s not in before and "=s" not in s:
                pick = s
        size = download_by_src(page, pick, out_path)
        page.screenshot(path=os.path.join(debug, f"grid{g}_after.png"))

        if size < 20000:
            log(f"[!] 下载文件过小({size}B)，可能非有效图片，请检查 {out_path}")
            return None
        log(f"[✓ Grid {g} 完成] {out_path}  ({size/1024:.1f} KB)  0 积分")
        return out_path

def slice_grid(g, pad=0.02, target=(544, 960)):
    """把第 g 组九宫格按 3x3 切为 9 张单镜首帧（544x960）。"""
    from PIL import Image
    base, grids, frames, debug = today_dir()
    src = os.path.join(grids, f"ep04_grid{g:02d}.png")
    if not os.path.exists(src):
        log(f"[!] 找不到九宫格: {src}（请先 --grid {g} 生成）")
        return []
    img = Image.open(src).convert("RGB")
    W, H = img.size
    cw, ch = W / 3.0, H / 3.0
    log(f"[切片] Grid {g} 源图 {W}x{H} -> 3x3，每格 {cw:.0f}x{ch:.0f}，内缩 {pad*100:.0f}%")
    outs = []
    for r in range(3):
        for c in range(3):
            shot = (g - 1) * 9 + r * 3 + c + 1
            cl = int(c * cw + cw * pad)
            ct = int(r * ch + ch * pad)
            cr = int((c + 1) * cw - cw * pad)
            cb = int((r + 1) * ch - ch * pad)
            crop = img.crop((cl, ct, cr, cb)).resize(target, Image.LANCZOS)
            p1 = os.path.join(frames, f"yang_ep04_shot{shot:02d}.jpg")
            crop.save(p1, quality=95)
            outs.append(p1)
    log(f"[✓ 切片完成] Grid {g}: Shot {(g-1)*9+1:02d} ~ Shot {g*9:02d} 已输出到 {frames}")
    return outs


def make_contact_sheet(g, cols=3):
    """把已切好的 9 张首帧拼成一张速览图，便于人工验收。"""
    from PIL import Image
    base, grids, frames, debug = today_dir()
    imgs = []
    for i in range(9):
        shot = (g - 1) * 9 + i + 1
        p = os.path.join(frames, f"yang_ep04_shot{shot:02d}.jpg")
        if os.path.exists(p):
            imgs.append(Image.open(p))
    if len(imgs) != 9:
        log(f"[!] contact sheet 需要 9 张，当前 {len(imgs)} 张")
        return None
    w, h = imgs[0].size
    sheet = Image.new("RGB", (w * 3, h * 3), (20, 20, 20))
    for i, im in enumerate(imgs):
        sheet.paste(im, ((i % 3) * w, (i // 3) * h))
    out = os.path.join(debug, f"ep04_grid{g:02d}_contact_sheet.jpg")
    sheet.save(out, quality=92)
    log(f"[✓ 速览图] {out}")
    return out


def main():
    ap = argparse.ArgumentParser(description="EP04 Flow 九宫格生成 / 切片")
    ap.add_argument("--grid", type=int, choices=[1, 2, 3, 4, 5, 6], help="生成指定组九宫格")
    ap.add_argument("--all", action="store_true", help="依次生成全部 6 组")
    ap.add_argument("--dry", action="store_true", help="只打印提示词，不操作浏览器")
    ap.add_argument("--slice", type=int, dest="slice_g", choices=[1, 2, 3, 4, 5, 6], help="切片指定组")
    ap.add_argument("--pad", type=float, default=0.02, help="切片内缩比例（默认 0.02）")
    ap.add_argument("--wait", type=int, default=100, help="出图最长等待秒数（默认 100）")
    args = ap.parse_args()

    if args.slice_g:
        outs = slice_grid(args.slice_g, pad=args.pad)
        if outs:
            make_contact_sheet(args.slice_g)
        return

    targets = [1, 2, 3, 4, 5, 6] if args.all else ([args.grid] if args.grid else [])
    if not targets:
        ap.print_help()
        return
    for g in targets:
        generate_grid(g, wait_s=args.wait, dry=args.dry)
        if not args.dry and targets.index(g) < len(targets) - 1:
            time.sleep(3)


if __name__ == "__main__":
    main()

