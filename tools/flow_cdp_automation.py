#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""北宋杨家将 · Google Flow CDP 自动化接管与批量生片引擎

功能：
1. 通过 Chrome DevTools Protocol (CDP: 127.0.0.1:9222) 接管已登录的真实 Chrome 浏览器。
2. 自动检测 Google Flow 登录状态与工作台 (Workspace / Canvas) 界面。
3. 批量加载第 3 集 Grid 01（Shot 01 ~ Shot 09）首帧切片图片与英文动作提示词。
4. 支持低算力 / Lite / 快速预览档位（360P/720P 极速生成试点）。
5. 监控生成状态并自动下载视频到当日输出目录 output/YYYY-MM-DD/flow_raw/。
"""

import os
import sys
import time
import requests
from playwright.sync_api import sync_playwright

# 导入第3集元数据
sys.path.append(os.path.dirname(__file__))
try:
    from yangjiajiang_ep03_metadata import EP03_METADATA
except ImportError:
    EP03_METADATA = []

CDP_URL = "http://127.0.0.1:9222"
PILOT_IMG_DIR = r"d:\ai_projects\ComfyUI\output\2026-10-08\yangjiajiang_ep03\flow_pilot"
OUTPUT_DIR = r"d:\ai_projects\ComfyUI\output\2026-10-08\yangjiajiang_ep03\flow_raw"
SCREENSHOT_DIR = r"d:\ai_projects\ComfyUI\output\2026-10-08\yangjiajiang_ep03\flow_debug"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Grid 01 对应的 9 组精简英文运镜提示词（适配 Flow Lite 档，去除画风负向词，聚焦动势）
GRID01_FLOW_PROMPTS = [
    {
        "shot": 1,
        "sec": 4, # 映射至 Flow 4s 档
        "prompt": "Vertical shot, camera tilts up slowly. Grand Song imperial carriage procession marching north under bleak winter skies, giant ochre-yellow dragon flag fluttering violently in freezing howling wind. SFX: howling winter wind, flapping banners."
    },
    {
        "shot": 2,
        "sec": 4,
        "prompt": "Medium low angle shot in ancient imperial court hall. An ancient prime minister in official crimson robes and a winged black court hat prostrating on the floor with folded hands, pleading earnestly. SFX: rustling robes, solemn court murmur."
    },
    {
        "shot": 3,
        "sec": 4,
        "prompt": "Medium shot of a solemn Chinese emperor in golden dragon robes sitting behind imperial desk, waving sleeve decisively to appoint Supreme Escort General. SFX: fabric rustle, heavy bell strike."
    },
    {
        "shot": 4,
        "sec": 4,
        "prompt": "Medium shot, camera slowly pushes in. A young valiant commander in silver lamellar armor with red helmet tassels standing beside the Emperor's royal chariot, both figures sharing striking facial resemblances in profile. SFX: armor clinking."
    },
    {
        "shot": 5,
        "sec": 4,
        "prompt": "Static wide minimalist vertical shot. Mount Wutai shrouded in pale moon-white mist, hundred-foot ink pine trees and bamboo groves swaying gently in mountain breeze. SFX: distant temple chime, faint wind."
    },
    {
        "shot": 6,
        "sec": 4,
        "prompt": "Medium shot inside solemn Buddhist temple hall. Master of ceremonies raising golden incense and silk banners before the altar, curling incense smoke rising gracefully. SFX: deep wooden fish knock, low chanting."
    },
    {
        "shot": 7,
        "sec": 4,
        "prompt": "High angle shot looking down. A solemn Chinese emperor in a golden dragon robe bowing down on both knees before the towering Sakyamuni Buddha statue, head lowered in solemn prayer. SFX: resonant temple bell strike."
    },
    {
        "shot": 8,
        "sec": 4,
        "prompt": "Medium close shot on temple stone steps. Treacherous courtier leaning in whispering into the Emperor's ear with subtle sinister expression. SFX: whispered words, distant wind."
    },
    {
        "shot": 9,
        "sec": 4,
        "prompt": "Dynamic close shot. Prince the Eighth Zhao Defang rushing forward grabbing the Emperor's golden silk sleeve in urgent pleading alarm, chariot wheel turning away. SFX: fabric tearing strain, sudden horse neigh."
    }
]

def check_cdp_available():
    """检测 127.0.0.1:9222 是否存活"""
    try:
        r = requests.get(f"{CDP_URL}/json/version", timeout=2)
        return r.status_code == 200, r.json()
    except Exception:
        return False, None

def inspect_and_operate_flow():
    is_live, version_info = check_cdp_available()
    if not is_live:
        print("[!] 端口 9222 未开启或尚未启动调试模式 Chrome！")
        print("    请先双击运行: tools/launch_flow_cdp_chrome.bat")
        print("    或在命令行执行: start chrome.exe --remote-debugging-port=9222 --user-data-dir=\"d:\\ai_projects\\ComfyUI\\flow_chrome_profile\" https://flow.google.com/")
        return False

    print(f"[+] 成功检测到 CDP 调试端口 9222！浏览器版本: {version_info.get('Browser')}")

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        context = browser.contexts[0]
        pages = context.pages
        print(f"[+] 当前已打开标签页数量: {len(pages)}")

        target_page = None
        for pg in pages:
            url = pg.url
            title = pg.title()
            print(f"    - 页面: '{title}' ({url})")
            if "flow.google.com" in url or "accounts.google.com" in url:
                target_page = pg
                break

        if not target_page:
            print("[+] 未发现 Flow 页面，自动在新标签页打开 https://flow.google.com/ ...")
            target_page = context.new_page()
            target_page.goto("https://flow.google.com/", wait_until="domcontentloaded", timeout=60000)

        target_page.wait_for_timeout(3000)
        curr_url = target_page.url
        curr_title = target_page.title()
        print(f"[+] 当前活动页面: {curr_title} ({curr_url})")

        # 检查是否还在登录页面
        if "accounts.google.com" in curr_url:
            print("\n" + "="*65)
            print("【提示】浏览器当前停留在 Google 账号登录页面！")
            print("请直接在桌面上弹出的 Chrome 窗口中输入您的 Google 账号密码完成登录。")
            print("登录完成后，再次运行本脚本即可全自动接管生片工作台！")
            print("="*65 + "\n")
            
            # 保存当前截图供排查
            shot_file = os.path.join(SCREENSHOT_DIR, "login_status.png")
            target_page.screenshot(path=shot_file)
            print(f"[截图保存] 状态已截屏: {shot_file}")
            return False

        elif "flow.google.com/about" in curr_url:
            print("[+] 页面处于 Landing Page，正在尝试点击进入工作台...")
            btn = target_page.locator("text=使用 Google Flow 创建").first
            if btn.count() > 0:
                btn.click()
                target_page.wait_for_timeout(4000)
                print(f"[+] 跳转后 URL: {target_page.url}")
            else:
                target_page.goto("https://flow.google.com/", wait_until="domcontentloaded")

        # 捕获工作台截图
        ws_shot = os.path.join(SCREENSHOT_DIR, "flow_workspace_current.png")
        target_page.screenshot(path=ws_shot)
        print(f"[截图保存] 工作台现状截屏已留存: {ws_shot}")

        print("\n" + "="*65)
        print("【试点准备完毕】第 3 集 Grid 01（前 9 镜）切片素材与提示词状态：")
        for item in GRID01_FLOW_PROMPTS:
            s_id = item["shot"]
            img_file = os.path.join(PILOT_IMG_DIR, f"shot0{s_id}.jpg")
            exists = "已就绪" if os.path.exists(img_file) else "缺失"
            print(f"  Shot {s_id:02d} [{item['sec']}s] | 首帧切片: {exists} | 动作: {item['prompt'][:55]}...")
        print("="*65 + "\n")

        return True

if __name__ == "__main__":
    ready = inspect_and_operate_flow()
    if ready:
        try:
            from flow_video_automation import FlowVideoAutomator, DEFAULT_SHOTS
            automator = FlowVideoAutomator(max_daily_credits=100)
            automator.print_status()
            print("若需启动 100 积分自动化生片，请执行:")
            print("  python tools/flow_video_automation.py --batch (批量生片，受 100 积分硬风控)")
            print("  python tools/flow_video_automation.py --shot 1 --wait (单镜生片并下载)")
        except ImportError:
            pass
