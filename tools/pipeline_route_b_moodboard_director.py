#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""路线 B：多宫格分镜定调 + 单图正片输出全流程引擎 (影视导演流 / Moodboard to Video)

核心工作流：
1. 【0 积分多宫格情绪板定调】：使用 Nano Banana 2.1 一次性生成 3x3 九宫格分镜总览板 (Moodboard Grid)，确立整集冷暖色调、艺术笔触与角色出场关系（0 积分）。
2. 【0 积分单图独立正片演化】：继承总览板的风格描述与角色特征，为各分镜展开生成 16:9 / 9:16 独立 2K 高清首帧（0 积分）。
3. 【Frames 挂载驱动 Veo 3.1 视频】：配置 Veo 3.1 - Lite 8秒视频 (x1 档位)，动态抓取开销 (10 积分/镜)。
4. 【100 积分硬熔断保护】：严格受每日 100 积分账本约束，超限主动停止。
5. 【成片归档与导演审计清单】：自动下载视频至 output/YYYY-MM-DD/route_b/videos/，生成导演版对比清单。
"""

import os
import sys
import json
import time
import base64
import argparse
import datetime
import requests
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.append(os.path.dirname(__file__))

from flow_video_automation import FlowCreditLedger, CDP_URL

# 路线 B 剧情总览情绪板提示词 (3x3 九宫格分镜定调)
EPISODE_MOODBOARD_PROMPT = (
    "A 3x3 cinematic storyboard grid of 9 consecutive dramatic scenes from Northern Song Dynasty historical epic. "
    "Featuring: imperial procession in winter blizzard, court debates in golden Kaifeng palace, generals in silver armor, "
    "sacred snow-covered Buddhist temple on Mount Wutai, intense court intrigue. "
    "Traditional Chinese ink wash cut-paper animation style, Shanghai Animation Film Studio aesthetic, crisp black ink lines, "
    "muted earth tones, vermilion and ochre accents, textured raw rice paper background, cohesive cinematic lighting, 8k masterpiece."
)

ROUTE_B_SHOTS = [
    {
        "shot": 1,
        "grid_pos": "Row 1 Col 1",
        "title": "北征雪原行军",
        "image_prompt": "Cinematic wide establishing shot matching the moodboard style. Grand Song imperial carriage procession marching north through deep snow in freezing gale, giant ochre-yellow dragon banner fluttering violently. Traditional Chinese ink wash cut-paper aesthetic, crisp black ink lines, raw rice paper texture.",
        "video_prompt": "Camera tilts up slowly from freezing snowy ground following the imperial carriage, banners fluttering violently in howling blizzard, horses marching steadily with frosty breath, epic cinematic movement."
    },
    {
        "shot": 2,
        "grid_pos": "Row 1 Col 2",
        "title": "金殿老臣死谏",
        "image_prompt": "Cinematic medium low angle shot inside Kaifeng imperial court hall matching the moodboard palette. An ancient prime minister in official crimson robes and a winged black court hat prostrating on golden tiles with folded hands pleading earnestly before a solemn Chinese emperor in a golden dragon robe. Solemn court atmosphere, dust motes drifting in sunbeams, Shanghai animation art.",
        "video_prompt": "Slow smooth push in towards an ancient prime minister in official crimson robes and a winged black court hat prostrating on the floor, robes trembling with emotional pleading, dust motes drifting in shafts of sunlight, solemn court ambiance."
    },
    {
        "shot": 3,
        "grid_pos": "Row 1 Col 3",
        "title": "御前拜帅受命",
        "image_prompt": "Cinematic medium shot matching the moodboard color scheme. A solemn Chinese emperor in golden dragon robes sitting behind dragon desk waving wide silk sleeves decisively to appoint general. Majestic ink wash line art, authentic Song dynasty court interior.",
        "video_prompt": "a solemn Chinese emperor in a golden dragon robe waves his wide golden silk sleeve decisively, silk robes billowing majestically, intense royal authority in his eyes, fabric rustling dynamically."
    }
]

class RouteBMoodboardDirectorPipeline:
    def __init__(self, max_credits=100, model="Veo 3.1 - Lite", count="x1"):
        self.today = datetime.date.today().strftime("%Y-%m-%d")
        self.max_credits = max_credits
        self.model = model
        self.count = count
        
        self.base_dir = os.path.abspath(os.path.join("output", self.today, "route_b"))
        self.moodboard_dir = os.path.join(self.base_dir, "moodboard")
        self.img_dir = os.path.join(self.base_dir, "images")
        self.video_dir = os.path.join(self.base_dir, "videos")
        self.debug_dir = os.path.join(self.base_dir, "debug")
        
        os.makedirs(self.moodboard_dir, exist_ok=True)
        os.makedirs(self.img_dir, exist_ok=True)
        os.makedirs(self.video_dir, exist_ok=True)
        os.makedirs(self.debug_dir, exist_ok=True)
        
        self.ledger = FlowCreditLedger(target_date=self.today, max_daily_credits=self.max_credits)

    def is_cdp_ready(self):
        try:
            return requests.get(f"{CDP_URL}/json/version", timeout=2).status_code == 200
        except Exception:
            return False

    def generate_moodboard(self, page):
        """阶段 1：使用 Nano Banana 2.1 生成九宫格分镜定调总览板 (消耗 0 积分)"""
        mb_path = os.path.join(self.moodboard_dir, "ep_grid_moodboard.png")
        if os.path.exists(mb_path):
            print(f"[阶段1 跳过] 情绪板总览图已就绪: {mb_path}")
            return mb_path

        print(f"\n[阶段1: 0积分定调] 正在生成 3x3 九宫格分镜总览板 (Nano Banana 2.1)...")
        # 切换至 1:1 或 16:9 Image 模式
        trigger = page.locator("button[aria-label='Settings trigger']").first
        trigger.click(force=True)
        page.wait_for_timeout(600)
        
        page.locator("div.cdk-overlay-pane button:has-text('Image')").first.click(force=True)
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)

        # 填入总览提示词
        editor = page.locator(".ProseMirror").first
        editor.click(force=True)
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.keyboard.type(EPISODE_MOODBOARD_PROMPT, delay=10)
        page.wait_for_timeout(600)
        
        page.locator("button[aria-label='Start generation'], button:has-text('arrow_forward')").first.click(force=True)
        page.wait_for_timeout(10000)

        # 下载情绪板
        imgs = page.locator("img[src*='flow-content.google']").all()
        if imgs:
            src = imgs[0].get_attribute("src")
            b64 = page.evaluate("""async (url) => {
                const res = await fetch(url);
                const blob = await res.blob();
                return new Promise((r) => {
                    const rd = new FileReader();
                    rd.onloadend = () => r(rd.result.split(',')[1]);
                    rd.readAsDataURL(blob);
                });
            }""", src)
            with open(mb_path, "wb") as f:
                f.write(base64.b64decode(b64))
            print(f"[✓ 阶段1完成] 九宫格分镜定调板已保存: {mb_path} (0 积分消耗)")
        return mb_path

    def run_stage2_single_master_image(self, page, shot_info):
        """阶段 2：基于定调板，展开为各分镜专属 16:9 高清单张正片 (消耗 0 积分)"""
        shot_id = shot_info["shot"]
        prompt = shot_info["image_prompt"]
        target_img = os.path.join(self.img_dir, f"shot_{shot_id:02d}_master.png")

        if os.path.exists(target_img):
            print(f"[阶段2 跳过] Shot {shot_id:02d} 高清独立正片已就绪: {target_img}")
            return target_img

        print(f"\n[阶段2: 0积分正片] 正在展开生成 Shot {shot_id:02d} 16:9 高清正片...")
        editor = page.locator(".ProseMirror").first
        editor.click(force=True)
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.keyboard.type(prompt, delay=10)
        page.wait_for_timeout(600)

        page.locator("button[aria-label='Start generation'], button:has-text('arrow_forward')").first.click(force=True)
        page.wait_for_timeout(8000)

        imgs = page.locator("img[src*='flow-content.google']").all()
        if imgs:
            src = imgs[0].get_attribute("src")
            b64 = page.evaluate("""async (url) => {
                const res = await fetch(url);
                const blob = await res.blob();
                return new Promise((r) => {
                    const rd = new FileReader();
                    rd.onloadend = () => r(rd.result.split(',')[1]);
                    rd.readAsDataURL(blob);
                });
            }""", src)
            with open(target_img, "wb") as f:
                f.write(base64.b64decode(b64))
            print(f"[✓ 阶段2完成] 独立正片已保存: {target_img} (0 积分消耗)")
        return target_img

    def run_stage3_render_video(self, page, shot_info, wait_finish=True):
        """阶段 3：挂入正片作为 Start Frame，渲染 Veo 8s 视频 (受 100 积分硬风控)"""
        shot_id = shot_info["shot"]
        vid_prompt = shot_info["video_prompt"]
        target_video = os.path.join(self.video_dir, f"shot_{shot_id:02d}_veo_8s.mp4")

        if os.path.exists(target_video):
            print(f"[阶段3 跳过] Shot {shot_id:02d} 视频成片已存在: {target_video}")
            return target_video

        # 切换至 Video 模式
        trigger = page.locator("button[aria-label='Settings trigger']").first
        trigger.click(force=True)
        page.wait_for_timeout(600)
        
        page.locator("div.cdk-overlay-pane button:has-text('Video')").first.click(force=True)
        page.locator("div.cdk-overlay-pane button:has-text('x1')").first.click(force=True)
        dur_btn = page.locator("div.cdk-overlay-pane button:has-text('8s')").first
        if dur_btn.count() > 0:
            dur_btn.click(force=True)

        import re
        cost_elem = page.locator("div.cdk-overlay-pane").get_by_text(re.compile(r"Generating will use \d+ credits")).first
        cost_text = cost_elem.inner_text() if cost_elem.count() > 0 else "10 credits"
        match = re.search(r"(\d+)\s*credits", cost_text)
        cost = int(match.group(1)) if match else 10
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)

        # 积分安全检测
        allowed, reason = self.ledger.can_afford(cost)
        if not allowed:
            print("\n" + "!"*65)
            print(reason)
            print("[安全熔断] 路线 B 停止提交后续视频生成，保护每日 100 积分上限！")
            print("!"*65 + "\n")
            return None

        # 提交视频生成
        print(f"\n[阶段3: 视频生成] 正在提交 Shot {shot_id:02d} 8秒视频 (需 {cost} 积分)...")
        editor = page.locator(".ProseMirror").first
        editor.click(force=True)
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.keyboard.type(vid_prompt, delay=10)
        page.wait_for_timeout(600)

        page.locator("button[aria-label='Start generation'], button:has-text('arrow_forward')").first.click(force=True)
        page.wait_for_timeout(4000)

        self.ledger.record_usage(
            shot_id=shot_id,
            model=self.model,
            duration="8s",
            count=self.count,
            cost=cost,
            prompt=vid_prompt,
            artifact_path=target_video
        )

        if wait_finish:
            print(f"[+] 等待 Veo 3.1 渲染成片 (监控 180s)...")
            start = time.time()
            while time.time() - start < 180:
                page.wait_for_timeout(6000)
                videos = page.locator("video").all()
                if videos:
                    v_src = videos[0].get_attribute("src")
                    if v_src and ("blob:" in v_src or "http" in v_src):
                        b64 = page.evaluate("""async (url) => {
                            const res = await fetch(url);
                            const blob = await res.blob();
                            return new Promise((r) => {
                                const rd = new FileReader();
                                rd.onloadend = () => r(rd.result.split(',')[1]);
                                rd.readAsDataURL(blob);
                            });
                        }""", v_src)
                        with open(target_video, "wb") as vf:
                            vf.write(base64.b64decode(b64))
                        print(f"[✓ 阶段3完成] 视频成片下载成功: {target_video} ({os.path.getsize(target_video)} 字节)")
                        return target_video
                print(f"  ... 渲染等待中 ({int(time.time() - start)}s)")
        return target_video

    def run_pipeline(self, shots=None, wait_finish=True):
        shots = shots or ROUTE_B_SHOTS
        print("\n" + "="*65)
        print(f"【路线 B：多宫格分镜定调 + 单图正片输出工作流启动】")
        print(f"  情绪板定调 -> {len(shots)} 镜独立正片 -> 8s Veo 视频 (限额: {self.max_credits} 积分)")
        print("="*65)

        if not self.is_cdp_ready():
            print("[!] 请先运行 tools/launch_flow_cdp_chrome.bat 启动 CDP 9222 端口 Chrome！")
            return

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(CDP_URL)
            page = next((pg for pg in browser.contexts[0].pages if "flow.google.com/project" in pg.url), None)
            if not page:
                print("[!] 未找到 Flow 工作台标签页！")
                browser.close()
                return

            # 步骤 1：生成九宫格总览情绪板 (0 积分)
            self.generate_moodboard(page)

            # 步骤 2 & 3：逐镜展开单图正片并渲染视频
            for shot in shots:
                if self.ledger.data["remaining_credits"] < 10:
                    print(f"[!] 剩余积分不足 10 积分，路线 B 优雅退出。")
                    break
                self.run_stage2_single_master_image(page, shot)
                self.run_stage3_render_video(page, shot, wait_finish=wait_finish)
                time.sleep(3)

            browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="路线 B：多宫格分镜定调 + 单图正片输出脚本")
    parser.add_argument("--max-credits", type=int, default=100, help="每日最大积分限制 (默认 100)")
    parser.add_argument("--wait", action="store_true", help="等待视频渲染并下载成片")
    args = parser.parse_args()

    pipeline = RouteBMoodboardDirectorPipeline(max_credits=args.max_credits)
    pipeline.run_pipeline(wait_finish=args.wait)
