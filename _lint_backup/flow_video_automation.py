#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Google Flow 视频自动化生成与每日积分风控引擎 (Veo 3.1 / Omni)

核心功能：
1. 模式纠偏：自动锁定 [Video] 视频模式，彻底杜绝默认生图模型 (Nano Banana) 导致的误生成图片。
2. 每日积分预算硬熔断 (Daily Credit Budget Guard)：
   - 默认每日积分上限：100 credits (支持参数 --max-credits 自定义)。
   - 提交前动态读取 UI 计算的 "Generating will use XX credits"。
   - 维护每日持久化账本 output/YYYY-MM-DD/flow_credit_ledger.json。
   - 严格预检：一旦累计消耗 + 本次消耗 > 每日上限，立即阻断提交并告警。
3. 自动化调度与下载：
   - 自动切换模型 (Veo 3.1 - Lite / Veo 3.1 - Fast / Omni 1.1 Flash)、时长 (8s/6s/4s) 与数量 (x1/x2)。
   - 自动填入提示词并触发 Start generation。
   - 监控视频渲染状态，自动下载保存至 output/YYYY-MM-DD/flow_videos/。
"""

import os
import sys
import re
import json
import time
import base64
import argparse
import datetime
import requests
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

CDP_URL = "http://127.0.0.1:9222"

# 第 3 集 Grid 01 候选镜头动作提示词 (聚焦纯视频运镜与历史质感)
DEFAULT_SHOTS = [
    {
        "shot": 1,
        "sec": "8s",
        "prompt": "Cinematic vertical epic, camera tilts up slowly from freezing snowy ground. Grand Song imperial carriage procession marching north under bleak winter skies, giant ochre-yellow dragon banner fluttering violently in freezing howling mountain wind. High dynamic motion, photorealistic historical epic, 8k resolution."
    },
    {
        "shot": 2,
        "sec": "8s",
        "prompt": "Cinematic medium low angle shot inside Kaifeng imperial court hall. Prime Minister Kou Zhun prostrating on the floor with folded hands, pleading earnestly before Emperor Taizong in golden dragon robes, solemn court atmosphere, subtle breathing motion, dust motes drifting in shafts of sunlight."
    },
    {
        "shot": 3,
        "sec": "8s",
        "prompt": "Cinematic medium shot of Emperor Taizong sitting behind the golden imperial desk, waving silk sleeve decisively to appoint Supreme Escort General, fabric waving dynamically, solemn expressions, cinematic lighting, 8k."
    },
    {
        "shot": 4,
        "sec": "8s",
        "prompt": "Medium shot, camera slowly pushes in smoothly. Eldest Son Yang Yanping in silver lamellar armor standing beside the Emperor's royal chariot, wind blowing helmet tassels, noble steadfast gaze, photorealistic armor metallic reflections."
    },
    {
        "shot": 5,
        "sec": "8s",
        "prompt": "Wide static cinematic shot of Mount Wutai in Northern Song Dynasty. Mist floating across pine ridges, snow falling gently on ancient temple roofs, solemn spiritual atmosphere, majestic mountain landscape."
    },
    {
        "shot": 6,
        "sec": "8s",
        "prompt": "Atmospheric medium shot inside Buddhist temple hall. Master of ceremonies raising golden incense burners, white smoke curling upwards in graceful motion, monks chanting in background, warm candlelight flickering."
    },
    {
        "shot": 7,
        "sec": "8s",
        "prompt": "High angle shot looking down. Emperor Taizong bowing down devoutly on both knees before the towering golden Buddha statue, golden robes draping over stone altar, solemn prayer."
    },
    {
        "shot": 8,
        "sec": "8s",
        "prompt": "Intense medium close-up shot on temple steps. Treacherous courtier leaning in whispering into the Emperor's ear with subtle sinister smile, wind rustling court garments, sharp tension."
    },
    {
        "shot": 9,
        "sec": "8s",
        "prompt": "Dynamic cinematic close shot. Prince the Eighth Zhao Defang rushing forward grabbing the Emperor's golden sleeve in desperate plea, carriage wheel turning, horse whinnying in cold breath."
    }
]

class FlowCreditLedger:
    """每日积分账本管理与安全熔断器"""
    def __init__(self, target_date=None, max_daily_credits=100):
        self.date_str = target_date or datetime.date.today().strftime("%Y-%m-%d")
        self.max_daily_credits = max_daily_credits
        self.ledger_dir = os.path.abspath(os.path.join("output", self.date_str))
        os.makedirs(self.ledger_dir, exist_ok=True)
        self.ledger_path = os.path.join(self.ledger_dir, "flow_credit_ledger.json")
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.ledger_path):
            try:
                with open(self.ledger_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("date") == self.date_str:
                        # 沿用当日已记录的上限或参数更新
                        if self.max_daily_credits:
                            data["max_daily_credits"] = self.max_daily_credits
                        return data
            except Exception as e:
                print(f"[!] 账本读取异常，重新初始化: {e}")

        # 初始化新账本
        init_data = {
            "date": self.date_str,
            "max_daily_credits": self.max_daily_credits,
            "total_credits_used": 0,
            "remaining_credits": self.max_daily_credits,
            "history": []
        }
        self._save(init_data)
        return init_data

    def _save(self, data=None):
        if data is None:
            data = self.data
        data["remaining_credits"] = max(0, data["max_daily_credits"] - data["total_credits_used"])
        with open(self.ledger_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def can_afford(self, cost: int):
        """检查本次开销是否超出今日配额"""
        current_used = self.data.get("total_credits_used", 0)
        max_allowed = self.data.get("max_daily_credits", 100)
        if current_used + cost > max_allowed:
            return False, (
                f"【每日积分熔断触发】今日已消耗 {current_used} 积分，本次任务需消耗 {cost} 积分，"
                f"总计 {current_used + cost} 积分，将超出每日最大上限 {max_allowed} 积分！"
            )
        return True, "允许生成"

    def record_usage(self, shot_id: int, model: str, duration: str, count: str, cost: int, prompt: str, artifact_path: str = ""):
        """记录已提交任务的积分开销"""
        record = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "shot_id": shot_id,
            "model": model,
            "duration": duration,
            "count": count,
            "cost": cost,
            "prompt_snippet": prompt[:80],
            "artifact_path": artifact_path
        }
        self.data["history"].append(record)
        self.data["total_credits_used"] += cost
        self._save()
        print(f"[✓ 账本更新] 已扣减 {cost} 积分 | 今日已用: {self.data['total_credits_used']}/{self.data['max_daily_credits']} 积分 | 剩余: {self.data['remaining_credits']} 积分")

class FlowVideoAutomator:
    """Google Flow CDP 自动化视频生成控制器"""
    def __init__(self, max_daily_credits=100, model="Veo 3.1 - Lite", count="x1", duration="8s", aspect="16:9"):
        self.max_daily_credits = max_daily_credits
        self.model = model
        self.count = count
        self.duration = duration
        self.aspect = aspect
        self.today = datetime.date.today().strftime("%Y-%m-%d")
        
        self.video_dir = os.path.abspath(os.path.join("output", self.today, "flow_videos"))
        self.debug_dir = os.path.abspath(os.path.join("output", self.today, "flow_debug"))
        os.makedirs(self.video_dir, exist_ok=True)
        os.makedirs(self.debug_dir, exist_ok=True)

        self.ledger = FlowCreditLedger(target_date=self.today, max_daily_credits=self.max_daily_credits)

    def is_cdp_ready(self):
        try:
            r = requests.get(f"{CDP_URL}/json/version", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    def print_status(self):
        print("\n" + "="*60)
        print("【Google Flow 今日视频积分状态】")
        print(f"  日期: {self.ledger.date_str}")
        print(f"  每日最大积分限制: {self.ledger.max_daily_credits} 积分")
        print(f"  今日已消耗: {self.ledger.data['total_credits_used']} 积分")
        print(f"  今日剩余可用: {self.ledger.data['remaining_credits']} 积分")
        print(f"  今日已提交任务数: {len(self.ledger.data['history'])} 镜")
        print("="*60 + "\n")

    def configure_video_mode(self, page):
        """核心配置：强制进入 [Video] 模式并选定模型与开销"""
        print(f"[+] 正在配置视频参数: 模型={self.model}, 数量={self.count}, 时长={self.duration}, 画幅={self.aspect}...")
        
        # 连续 Escape 关闭残留弹层
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)

        # 1. 打开 Settings Trigger
        trigger = page.locator("button[aria-label='Settings trigger']").first
        if trigger.count() == 0:
            raise RuntimeError("未在页面中找到 Settings Trigger 按钮，请确认是否处于 Flow Canvas 工作台。")
        trigger.click(force=True)
        page.wait_for_timeout(800)

        # 2. 切换到 [Video] 标签页
        video_tab = page.locator("div.cdk-overlay-pane button:has-text('Video')").first
        if video_tab.count() > 0:
            video_tab.click(force=True)
            page.wait_for_timeout(600)
        else:
            print("[!] 未在弹窗中找到 Video 按钮，尝试查找包含 videocam 的标签...")
            v_btn = page.locator("button:has-text('videocam')").first
            if v_btn.count() > 0:
                v_btn.click(force=True)
                page.wait_for_timeout(600)

        # 3. 设置数量 (默认 x1，最大化镜头数量以节省积分)
        cnt_btn = page.locator(f"div.cdk-overlay-pane button:has-text('{self.count}')").first
        if cnt_btn.count() > 0:
            cnt_btn.click(force=True)
            page.wait_for_timeout(400)

        # 4. 设置画幅 (16:9 / 9:16)
        aspect_btn = page.locator(f"div.cdk-overlay-pane button:has-text('{self.aspect}')").first
        if aspect_btn.count() > 0:
            aspect_btn.click(force=True)
            page.wait_for_timeout(400)

        # 5. 设置时长 (4s / 6s / 8s / 10s)
        dur_btn = page.locator(f"div.cdk-overlay-pane button:has-text('{self.duration}')").first
        if dur_btn.count() > 0:
            dur_btn.click(force=True)
            page.wait_for_timeout(400)

        # 6. 设置目标模型 (Veo 3.1 - Lite / Veo 3.1 - Fast / Omni 1.1 Flash)
        model_dropdown = page.locator("div.cdk-overlay-pane button:has-text('arrow_drop_down'), div.cdk-overlay-pane button:has-text('Flash'), div.cdk-overlay-pane button:has-text('Veo')").first
        if model_dropdown.count() > 0:
            curr_text = (model_dropdown.inner_text()).strip()
            if self.model not in curr_text:
                print(f"[+] 正在从当前模型切换至: {self.model}...")
                model_dropdown.click(force=True)
                page.wait_for_timeout(600)
                target_opt = page.locator(f"[role='menu'] button:has-text('{self.model}'), button:has-text('{self.model}')").first
                if target_opt.count() > 0:
                    target_opt.click(force=True)
                    page.wait_for_timeout(600)

        # 7. 动态读取 UI 实际计算的积分成本 "Generating will use XX credits"
        cost_elem = page.locator("div.cdk-overlay-pane").get_by_text(re.compile(r"Generating will use \d+ credits")).first
        if cost_elem.count() > 0:
            cost_text = cost_elem.inner_text()
            match = re.search(r"(\d+)\s*credits", cost_text)
            cost_val = int(match.group(1)) if match else 10
        else:
            cost_val = 10 # 兜底预估
            print("[!] 未能直接抓取到积分提示，使用 Lite 档默认估算 10 积分。")

        # 保存设置界面的审计截屏
        shot_audit = os.path.join(self.debug_dir, "last_settings_config.png")
        page.screenshot(path=shot_audit)

        # 8. 按 Escape 收起设置面板
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)

        print(f"[+] 视频模式配置完成！当前单次任务实际开销: {cost_val} 积分。")
        return cost_val

    def generate_shot(self, shot_data, wait_finish=True, timeout_sec=240):
        """执行单个镜头的生成全流程（含严格风控）"""
        shot_id = shot_data.get("shot", 1)
        prompt = shot_data.get("prompt", "")
        
        target_video_file = os.path.join(self.video_dir, f"flow_shot{shot_id:02d}_{self.model.replace(' ', '_').lower()}.mp4")
        if os.path.exists(target_video_file):
            print(f"[跳过] 镜头 Shot {shot_id:02d} 成片已存在: {target_video_file}")
            return True

        if not self.is_cdp_ready():
            print("[!] 调试端口 9222 未连通，请先运行: tools/launch_flow_cdp_chrome.bat")
            return False

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(CDP_URL)
            context = browser.contexts[0]
            
            flow_page = None
            for page in context.pages:
                if "flow.google.com/project" in page.url:
                    flow_page = page
                    break

            if not flow_page:
                print("[!] 未找到正在运行的 Flow 项目工作台标签页 (flow.google.com/project)！")
                browser.close()
                return False

            # 1. 预检配置并抓取确切积分消耗
            cost = self.configure_video_mode(flow_page)

            # 2. 积分熔断安全检测
            allowed, reason = self.ledger.can_afford(cost)
            if not allowed:
                print("\n" + "!"*65)
                print(reason)
                print(f"[安全保护] 脚本主动终止本次生成，坚决不透支积分！")
                print("!"*65 + "\n")
                browser.close()
                return False

            # 3. 记录当前已有媒体数量
            existing_cards = flow_page.locator("img[src*='flow-content.google'], video").count()

            # 4. 定位并填充提示词输入框
            print(f"[+] 正在填入 Shot {shot_id:02d} 提示词 ({len(prompt)} 字符)...")
            editor = flow_page.locator(".ProseMirror").first
            if editor.count() == 0:
                # 尝试点击输入栏中部聚焦
                prompt_bar = flow_page.locator(".prompt-box, div:has(> button[aria-label='Settings trigger'])").first
                prompt_bar.click(force=True)
                flow_page.wait_for_timeout(300)
                editor = flow_page.locator(".ProseMirror").first

            editor.click(force=True)
            flow_page.wait_for_timeout(300)
            flow_page.keyboard.press("Control+A")
            flow_page.keyboard.press("Backspace")
            flow_page.wait_for_timeout(200)
            flow_page.keyboard.type(prompt, delay=10)
            flow_page.wait_for_timeout(800)

            # 5. 点击 Start generation 提交
            gen_btn = flow_page.locator("button[aria-label='Start generation'], button:has-text('arrow_forward')").first
            if gen_btn.count() == 0:
                print("[!] 未找到生成箭头按钮！")
                browser.close()
                return False

            print(f"[+] 点击 'Start generation' 提交视频渲染 (单次消耗 {cost} 积分)...")
            gen_btn.click(force=True)
            flow_page.wait_for_timeout(4000)

            # 6. 保存触发截屏
            submit_shot = os.path.join(self.debug_dir, f"shot{shot_id:02d}_triggered.png")
            flow_page.screenshot(path=submit_shot)

            # 7. 立即记录账本 (扣除积分)
            self.ledger.record_usage(
                shot_id=shot_id,
                model=self.model,
                duration=self.duration,
                count=self.count,
                cost=cost,
                prompt=prompt,
                artifact_path=target_video_file
            )

            # 8. 如果不等待直接返回 (长任务提交不轮询模式)
            if not wait_finish:
                print(f"[✓ 已提交后台] Shot {shot_id:02d} 视频生成已触发！按纪律返回，不阻塞长轮询。")
                browser.close()
                return True

            # 9. 监控渲染并下载视频成片
            print(f"[+] 正在监控 Shot {shot_id:02d} 视频生成状态 (最长等待 {timeout_sec}s)...")
            start_time = time.time()
            video_saved = False

            while time.time() - start_time < timeout_sec:
                flow_page.wait_for_timeout(6000)
                # 探测是否有新生成的卡片
                curr_cards = flow_page.locator("img[src*='flow-content.google'], video").all()
                if len(curr_cards) > existing_cards:
                    # 检查是否有就绪的 video 元素或下载按钮
                    videos = flow_page.locator("video").all()
                    if videos:
                        newest_video = videos[0]
                        v_src = newest_video.get_attribute("src")
                        if v_src and ("blob:" in v_src or "google" in v_src or "http" in v_src):
                            print(f"[√] 捕获到视频渲染产物 URL: {v_src[:60]}...")
                            b64 = flow_page.evaluate("""async (url) => {
                                const res = await fetch(url);
                                const blob = await res.blob();
                                return new Promise((r) => {
                                    const rd = new FileReader();
                                    rd.onloadend = () => r(rd.result.split(',')[1]);
                                    rd.readAsDataURL(blob);
                                });
                            }""", v_src)
                            with open(target_video_file, "wb") as vf:
                                vf.write(base64.b64decode(b64))
                            print(f"[√ 视频归档成功] 已下载成片: {target_video_file} ({os.path.getsize(target_video_file)} 字节)")
                            video_saved = True
                            break
                print(f"  ... 渲染进行中 ({int(time.time() - start_time)}s)")

            if not video_saved:
                print(f"[-] 等待超时或未直接提取到视频流。截取当前工作台留存，可在稍后通过批量下载提取。")
                flow_page.screenshot(path=os.path.join(self.debug_dir, f"shot{shot_id:02d}_timeout.png"))

            browser.close()
            return True

    def run_batch(self, shots=None, wait_each=False):
        """批量运行镜头，受每日积分硬上限 100 严格保护"""
        shots = shots or DEFAULT_SHOTS
        print("\n" + "="*65)
        print(f"【Google Flow 批量生片任务启动】")
        print(f"  总计划镜头: {len(shots)} 镜 | 每日硬限额: {self.max_daily_credits} 积分")
        print(f"  今日已消耗: {self.ledger.data['total_credits_used']} 积分 | 剩余额度: {self.ledger.data['remaining_credits']} 积分")
        print("="*65 + "\n")

        for idx, shot in enumerate(shots, 1):
            if self.ledger.data['remaining_credits'] <= 0:
                print(f"[!] 今日积分预算已全部耗尽 (已用 {self.ledger.data['total_credits_used']} 积分)！安全停止批处理。")
                break

            print(f"\n--- [任务进度 {idx}/{len(shots)}] 处理 Shot {shot['shot']:02d} ---")
            success = self.generate_shot(shot, wait_finish=wait_each)
            if not success:
                # 若因积分不足而失败，直接退出循环
                if self.ledger.data['remaining_credits'] < 10:
                    print("[!] 剩余积分不足以继续生成后续视频，自动终止本轮批处理。")
                    break

            # 任务之间微歇防风控
            time.sleep(3)

        self.print_status()

def main():
    parser = argparse.ArgumentParser(description="Google Flow 视频自动化与 100 积分风控引擎")
    parser.add_argument("--max-credits", type=int, default=100, help="每日最大积分限制 (默认 100)")
    parser.add_argument("--shot", type=int, default=None, help="仅运行指定编号的镜头 (1-9)")
    parser.add_argument("--batch", action="store_true", help="按顺序批量跑完队列中所有镜头")
    parser.add_argument("--model", type=str, default="Veo 3.1 - Lite", choices=["Veo 3.1 - Lite", "Veo 3.1 - Fast", "Omni 1.1 Flash", "Veo 3.1 - Quality"], help="视频大模型档位")
    parser.add_argument("--count", type=str, default="x1", choices=["x1", "x2"], help="单次生成视频数量 (x1 节省积分)")
    parser.add_argument("--duration", type=str, default="8s", choices=["4s", "6s", "8s", "10s"], help="视频时长")
    parser.add_argument("--aspect", type=str, default="16:9", choices=["16:9", "9:16"], help="画幅比例")
    parser.add_argument("--wait", action="store_true", help="生成后在当前进程等待视频下载完成 (默认只提交不阻塞)")
    parser.add_argument("--status", action="store_true", help="查询今日积分账本与消耗统计")
    args = parser.parse_args()

    automator = FlowVideoAutomator(
        max_daily_credits=args.max_credits,
        model=args.model,
        count=args.count,
        duration=args.duration,
        aspect=args.aspect
    )

    if args.status:
        automator.print_status()
        return

    if args.shot:
        target_shot = next((s for s in DEFAULT_SHOTS if s["shot"] == args.shot), None)
        if not target_shot:
            print(f"[!] 未找到 Shot {args.shot} 的预设配置，自动使用基础模板。")
            target_shot = {"shot": args.shot, "prompt": "Cinematic historical epic video, photorealistic dynamic motion.", "sec": args.duration}
        automator.generate_shot(target_shot, wait_finish=args.wait)
    elif args.batch:
        automator.run_batch(DEFAULT_SHOTS, wait_each=args.wait)
    else:
        # 默认打印状态并提示
        automator.print_status()
        print("提示：请使用以下命令启动生片：")
        print("  1. 生成单镜 (例如 Shot 01): python tools/flow_video_automation.py --shot 1 --wait")
        print("  2. 批量跑片 (严格限制 100 积分): python tools/flow_video_automation.py --batch")
        print("  3. 查询今日积分账本: python tools/flow_video_automation.py --status")

if __name__ == "__main__":
    main()
