#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""路线 A：Flow 原生单图高清直出全流程引擎 (Native Single-Frame to Video)

核心工作流：
1. 【0 积分关键帧抽卡】：使用 Nano Banana 2.1 直接为每个分镜生成 16:9 / 9:16 原生高清首帧（消耗 0 积分）。
2. 【Frames 挂载驱动】：将生成的基准首帧挂载为起始关键帧 (Start Frame)。
3. 【Veo 3.1 视频渲染】：配置 Veo 3.1 - Lite 8秒视频 (x1 档位)，动态抓取开销 (10 积分/镜)。
4. 【100 积分预算熔断】：每镜提交前严格校验当日累计账本，超 100 积分自动熔断。
5. 【本地自动归档】：自动下载视频至 output/YYYY-MM-DD/route_a/videos/，保存调试截屏与元数据清单。
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
from prompt_safety_linter import lint_prompt
from flow_frame_lock import attach_start_frame, verify_frame_lock, clear_ingredients

# 示范剧情分镜列表 (北宋杨家将 8秒/段)
ROUTE_A_SHOTS = [
    {
        "shot": 1,
        "title": "大军开拔北征",
        "aspect": "16:9",
        "duration": "8s",
        "image_prompt": "Cinematic historical epic wide shot. Grand Song imperial carriage procession marching north through freezing mountain pass under heavy blizzard, giant ochre-yellow dragon banner fluttering violently. Traditional Chinese ink wash cut-paper animation style, Shanghai Animation Film Studio aesthetic, crisp black ink lines, raw rice paper texture, 8k.",
        "video_prompt": "Camera tilts up slowly from freezing snowy ground following the imperial carriage, banners fluttering violently in blizzard, horses marching steadily with frosty breath, epic cinematic movement."
    },
    {
        "shot": 2,
        "title": "寇准殿前死谏",
        "aspect": "16:9",
        "duration": "8s",
        "image_prompt": "Cinematic medium low angle shot inside Kaifeng imperial court hall. An ancient prime minister in official crimson robes and a winged black court hat prostrating on golden tiles with folded hands, pleading earnestly before the golden throne. Traditional Chinese ink wash cut-paper aesthetic, crisp black ink lines, solemn atmosphere, shafts of dusty sunlight.",
        "video_prompt": "Slow smooth push in towards an ancient prime minister in official crimson robes and a winged black court hat prostrating on the floor, subtle robes trembling with emotional breathing, dust motes drifting in shafts of sunlight, solemn court ambiance."
    },
    {
        "shot": 3,
        "title": "太宗挥袂拜将",
        "aspect": "16:9",
        "duration": "8s",
        "image_prompt": "Cinematic medium shot. A solemn Chinese emperor in golden dragon robes sitting behind imperial dragon desk, waving wide silk sleeves decisively to appoint general. Traditional Chinese ink wash style, Shanghai Animation Film Studio art, crisp black line art, majestic lighting.",
        "video_prompt": "a solemn Chinese emperor in a golden dragon robe waves his wide golden silk sleeve decisively, silk robes billowing majestically, intense royal authority in his eyes, fabric rustling dynamically."
    },
    {
        "shot": 4,
        "title": "杨延平银甲受命",
        "aspect": "16:9",
        "duration": "8s",
        "image_prompt": "Cinematic medium shot. A young valiant commander in silver lamellar armor with red helmet tassels standing beside the imperial chariot, fierce loyal gaze, red helmet tassels blowing in northern wind. Traditional ink wash animation aesthetic, exquisite armor details.",
        "video_prompt": "Camera smoothly circles around a young valiant commander in silver lamellar armor with red helmet tassels, red helmet tassels blowing sharply in icy wind, hand firmly gripping long spear, valiant resolute expression."
    }
]

class RouteAFlowNativePipeline:
    def __init__(self, max_credits=100, model="Veo 3.1 - Lite", count="x1"):
        self.today = datetime.date.today().strftime("%Y-%m-%d")
        self.max_credits = max_credits
        self.model = model
        self.count = count
        
        self.base_dir = os.path.abspath(os.path.join("output", self.today, "route_a"))
        self.img_dir = os.path.join(self.base_dir, "images")
        self.video_dir = os.path.join(self.base_dir, "videos")
        self.debug_dir = os.path.join(self.base_dir, "debug")
        
        os.makedirs(self.img_dir, exist_ok=True)
        os.makedirs(self.video_dir, exist_ok=True)
        os.makedirs(self.debug_dir, exist_ok=True)
        
        self.ledger = FlowCreditLedger(target_date=self.today, max_daily_credits=self.max_credits)

    def is_cdp_ready(self):
        try:
            return requests.get(f"{CDP_URL}/json/version", timeout=2).status_code == 200
        except Exception:
            return False

    def run_stage1_generate_image(self, page, shot_info):
        """阶段 1：使用 Nano Banana 2.1 生成高清单帧参考图 (消耗 0 积分)"""
        shot_id = shot_info["shot"]
        # 前置合规审查：去名化，规避 Google Prominent People Policy 硬阻断
        img_prompt, _chg, _risk = lint_prompt(shot_info["image_prompt"])
        if _chg:
            print(f"[合规审查] Shot {shot_id:02d} 首帧提示词已去名化 {len(_chg)} 处")
        for _r in _risk:
            print(f"[合规警告] Shot {shot_id:02d} 残留风险: {_r['match']} — {_r['reason']}")
        aspect = shot_info.get("aspect", "16:9")
        target_img = os.path.join(self.img_dir, f"shot_{shot_id:02d}_frame.png")
        
        if os.path.exists(target_img):
            print(f"[阶段1 跳过] Shot {shot_id:02d} 高清基准图已就绪: {target_img}")
            return target_img

        print(f"\n[阶段1: 0积分生图] 正在生成 Shot {shot_id:02d} 高清首帧 (Nano Banana 2.1)...")
        # 1. 确保弹窗为 Image 模式
        trigger = page.locator("button[aria-label='Settings trigger']").first
        trigger.click(force=True)
        page.wait_for_timeout(600)
        
        img_tab = page.locator("div.cdk-overlay-pane button:has-text('Image')").first
        if img_tab.count() > 0:
            img_tab.click(force=True)
            page.wait_for_timeout(400)
            
        # 设置画幅
        asp_btn = page.locator(f"div.cdk-overlay-pane button:has-text('{aspect}')").first
        if asp_btn.count() > 0:
            asp_btn.click(force=True)
            
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)

        # 2. 填入 Image Prompt 并触发生成
        editor = page.locator(".ProseMirror").first
        editor.click(force=True)
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.keyboard.type(img_prompt, delay=10)
        page.wait_for_timeout(600)
        
        gen_btn = page.locator("button[aria-label='Start generation'], button:has-text('arrow_forward')").first
        gen_btn.click(force=True)
        page.wait_for_timeout(5000)

        # 3. 等待完成并下载最新生成的静态图片
        print(f"[+] 等待 Nano Banana 2.1 首帧生成完毕...")
        page.wait_for_timeout(8000)
        imgs = page.locator("img[src*='flow.google.com/asb/'], img[src*='googleusercontent.com']").all()
        # 排除用户头像
        imgs = [im for im in imgs if "ogw/AF2b" not in (im.get_attribute("src") or "")]
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
            print(f"[✓ 阶段1完成] 首帧参考图已保存: {target_img} (0 积分消耗)")
        return target_img

    def run_stage2_render_video(self, page, shot_info, wait_finish=True):
        """阶段 2：挂入首帧，驱动 Veo 3.1 渲染 8s 视频 (扣减 10 积分，受 100 积分硬风控)"""
        shot_id = shot_info["shot"]
        # 前置合规审查：去名化，规避 Google Prominent People Policy 硬阻断
        vid_prompt, _chg, _risk = lint_prompt(shot_info["video_prompt"])
        if _chg:
            print(f"[合规审查] Shot {shot_id:02d} 视频提示词已去名化 {len(_chg)} 处")
        for _r in _risk:
            print(f"[合规警告] Shot {shot_id:02d} 残留风险: {_r['match']} — {_r['reason']}")
        duration = shot_info.get("duration", "8s")
        target_video = os.path.join(self.video_dir, f"shot_{shot_id:02d}_veo_{duration}.mp4")

        if os.path.exists(target_video):
            print(f"[阶段2 跳过] Shot {shot_id:02d} 视频成片已存在: {target_video}")
            return target_video

        # 1. 切换至 Video 模式并设定模型
        trigger = page.locator("button[aria-label='Settings trigger']").first
        trigger.click(force=True)
        page.wait_for_timeout(600)
        
        vid_tab = page.locator("div.cdk-overlay-pane button:has-text('Video')").first
        vid_tab.click(force=True)
        page.wait_for_timeout(400)

        # 设置 x1 与时长
        page.locator("div.cdk-overlay-pane button:has-text('x1')").first.click(force=True)
        dur_btn = page.locator(f"div.cdk-overlay-pane button:has-text('{duration}')").first
        if dur_btn.count() > 0:
            dur_btn.click(force=True)

        # 确保选中 Veo 3.1 - Lite 模型
        model_dropdown = page.locator("div.cdk-overlay-pane button:has-text('arrow_drop_down'), div.cdk-overlay-pane button:has-text('Flash'), div.cdk-overlay-pane button:has-text('Veo')").first
        if model_dropdown.count() > 0:
            curr_text = (model_dropdown.inner_text()).strip()
            if self.model not in curr_text:
                print(f"[+] 正在切换模型至: {self.model}...")
                model_dropdown.click(force=True)
                page.wait_for_timeout(600)
                target_opt = page.locator(f"[role='menu'] button:has-text('{self.model}'), button:has-text('{self.model}')").first
                if target_opt.count() > 0:
                    target_opt.click(force=True)
                    page.wait_for_timeout(600)

        # 检查积分开销
        import re
        cost_elem = page.locator("div.cdk-overlay-pane").get_by_text(re.compile(r"Generating will use \d+ credits")).first
        cost_text = cost_elem.inner_text() if cost_elem.count() > 0 else "10 credits"
        match = re.search(r"(\d+)\s*credits", cost_text)
        cost = int(match.group(1)) if match else 10
        
        # 2. 积分熔断安全检测
        allowed, reason = self.ledger.can_afford(cost)
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)

        if not allowed:
            print("\n" + "!"*65)
            print(reason)
            print("[安全熔断] 路线 A 停止提交后续视频生成，保护每日 100 积分上限！")
            print("!"*65 + "\n")
            return None

        # 3. 挂载首帧 —— 不挂载就等于没用首帧，Veo 会自由发挥导致画风漂移
        frame_path = os.path.join(self.img_dir, f"shot_{shot_id:02d}_frame.png")
        has_frame = os.path.exists(frame_path)
        if has_frame:
            print(f"[首帧锁定] 挂载 Start Frame: {frame_path}")
            clear_ingredients(page)
            ok, detail = attach_start_frame(page, frame_path, debug_dir=self.debug_dir)
            if not ok:
                print("\n" + "!" * 65)
                print(f"[!] 首帧挂载失败: {detail.get('error') or detail.get('signal')}")
                print("[安全中止] 不提交本镜，避免把积分花在没锁住首帧的视频上")
                print("!" * 65 + "\n")
                return None
            print(f"[✓ 首帧已挂载] {detail.get('signal')}")
        else:
            print(f"[警告] 未找到首帧 {frame_path}，将退化为纯文生视频，画风无法锁定")

        # 4. 填入 Video 动作运镜提示词
        print(f"\n[阶段2: 视频生成] 正在提交 Shot {shot_id:02d} 8秒视频 (需 {cost} 积分)...")
        editor = page.locator(".ProseMirror").first
        editor.click(force=True)
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.keyboard.type(vid_prompt, delay=10)
        page.wait_for_timeout(600)

        # 4. 提交生成
        gen_btn = page.locator("button[aria-label='Start generation'], button:has-text('arrow_forward')").first
        gen_btn.click(force=True)
        page.wait_for_timeout(4000)

        # 5. 扣减账本
        self.ledger.record_usage(
            shot_id=shot_id,
            model=self.model,
            duration=duration,
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
                        print(f"[✓ 阶段2完成] 视频成片下载成功: {target_video} ({os.path.getsize(target_video)} 字节)")

                        # 首帧一致性校验：确认 Veo 真的用了我们给的首帧
                        if has_frame:
                            passed, rep = verify_frame_lock(frame_path, target_video)
                            qa_path = os.path.join(self.debug_dir, f"frame_lock_shot_{shot_id:02d}.json")
                            with open(qa_path, "w", encoding="utf-8") as qf:
                                json.dump(rep, qf, ensure_ascii=False, indent=2)
                            m = rep.get("metrics", {})
                            if passed:
                                print(f"[✓ 首帧锁定校验] PASS  汉明={m.get('phash_hamming')} "
                                      f"直方图={m.get('hist_corr')} 结构={m.get('gray_corr')}")
                            else:
                                print("\n" + "!" * 65)
                                print(f"[!] 首帧锁定校验 FAIL —— 成片与提交的首帧不一致")
                                print(f"    汉明={m.get('phash_hamming')} 直方图={m.get('hist_corr')} "
                                      f"结构={m.get('gray_corr')}")
                                for r in rep.get("reasons", []):
                                    print(f"    - {r}")
                                print("    （不自动重跑，重跑会再扣积分；请人工确认后再决定）")
                                print("!" * 65 + "\n")
                        return target_video
                print(f"  ... 渲染等待中 ({int(time.time() - start)}s)")
        return target_video

    def run_pipeline(self, shots=None, wait_finish=True):
        shots = shots or ROUTE_A_SHOTS
        print("\n" + "="*65)
        print(f"【路线 A：Flow 原生单图高清直出工作流启动】")
        print(f"  计划段落: {len(shots)} 镜 | 每镜 8 秒 | 每日限额: {self.max_credits} 积分")
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

            for shot in shots:
                if self.ledger.data["remaining_credits"] < 10:
                    print(f"[!] 剩余积分已不足 10 积分，路线 A 优雅退出。")
                    break
                # 步骤 1：生成 0 积分首帧
                img_path = self.run_stage1_generate_image(page, shot)
                # 步骤 2：生成视频并扣减积分
                vid_path = self.run_stage2_render_video(page, shot, wait_finish=wait_finish)
                time.sleep(3)

            browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="路线 A：Flow 原生单图高清直出脚本")
    parser.add_argument("--max-credits", type=int, default=100, help="每日最大积分限制 (默认 100)")
    parser.add_argument("--wait", action="store_true", help="等待视频渲染并下载成片")
    parser.add_argument("--shots", type=str, default="1,2", help="指定运行的镜头列表 (例如 1,2)")
    args = parser.parse_args()

    pipeline = RouteAFlowNativePipeline(max_credits=args.max_credits)
    
    target_ids = [int(x.strip()) for x in args.shots.split(",") if x.strip().isdigit()]
    selected_shots = [s for s in ROUTE_A_SHOTS if s["shot"] in target_ids]
    if not selected_shots:
        selected_shots = ROUTE_A_SHOTS[:2]

    pipeline.run_pipeline(shots=selected_shots, wait_finish=args.wait)
