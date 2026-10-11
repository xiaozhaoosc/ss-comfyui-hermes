import asyncio
import os
import sys
import time
import base64
import json
import re
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.append(os.path.dirname(__file__))

from flow_video_automation import FlowCreditLedger

SHOT_02_INFO = {
    "shot": 2,
    "title": "寇准殿前死谏",
    "aspect": "16:9",
    "duration": "8s",
    "image_prompt": "Traditional Chinese ink wash cut-paper animation style, Shanghai Animation Film Studio aesthetic. Medium low angle shot inside Kaifeng imperial court hall. Prime Minister Kou Zhun prostrating on golden tiles with folded hands, pleading earnestly before Emperor Taizong on the golden dragon throne. Crisp black ink lines, solemn atmosphere, shafts of dusty sunlight through palace lattice windows, 8k.",
    "video_prompt": "Smooth slow push in towards Prime Minister Kou Zhun prostrating on the floor, robes trembling with emotional breathing, dust motes drifting in shafts of sunlight, solemn court ambiance, dramatic cinematic historical lighting, 8s."
}

async def run_shot_02():
    today = "2026-10-10"
    base_dir = os.path.abspath(f"output/{today}/route_a")
    img_dir = os.path.join(base_dir, "images")
    video_dir = os.path.join(base_dir, "videos")
    debug_dir = os.path.join(base_dir, "debug")
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(video_dir, exist_ok=True)
    os.makedirs(debug_dir, exist_ok=True)

    ledger = FlowCreditLedger(target_date=today, max_daily_credits=100)
    
    # 确保账本包含 Shot 01 已扣减的 10 积分
    if ledger.data["total_credits_used"] == 0:
        ledger.record_usage(
            shot_id=1,
            model="Veo 3.1 - Lite",
            duration="8s",
            count="x1",
            cost=10,
            prompt="Grand Song imperial carriage procession marching north through freezing mountain pass...",
            artifact_path=os.path.join(video_dir, "shot_01_veo_8s.mp4")
        )

    # 检查 Shot 02 额度
    can_proceed, reason = ledger.can_afford(10)
    if not can_proceed:
        print("[!] 积分限额触发，停止执行:", reason)
        return

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        page = [pg for pg in browser.contexts[0].pages if "flow.google.com/project" in pg.url][0]

        # ---------------------------------------------------------
        # 阶段 1：使用 Nano Banana 2.1 生成 Shot 02 静态首帧 (0 积分)
        # ---------------------------------------------------------
        img_file = os.path.join(img_dir, "shot_02_frame.png")
        if not os.path.exists(img_file):
            print("\n[阶段 1: 0积分生图] 正在生成 Shot 02 高清首帧 (Nano Banana 2.1)...")
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(300)
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(400)

            trigger = page.locator("button[aria-label='Settings trigger']").first
            await trigger.click(force=True)
            await page.wait_for_timeout(800)

            img_tab = page.locator("div.cdk-overlay-pane button:has-text('Image')").first
            await img_tab.click(force=True)
            await page.wait_for_timeout(400)

            # 16:9 画幅
            asp_btn = page.locator("div.cdk-overlay-pane button:has-text('16:9')").first
            if await asp_btn.count() > 0:
                await asp_btn.click(force=True)

            await page.keyboard.press("Escape")
            await page.wait_for_timeout(400)

            # 填入提示词
            editor = page.locator(".ProseMirror").first
            await editor.click(force=True)
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await page.keyboard.type(SHOT_02_INFO["image_prompt"], delay=10)
            await page.wait_for_timeout(600)

            gen_btn = page.locator("button[aria-label='Start generation'], button:has-text('arrow_forward')").first
            await gen_btn.click(force=True)
            print("[+] 已提交 Nano Banana 2.1 生图，等待 12s 生成完成...")
            await page.wait_for_timeout(12000)

            # 下载最新图片
            imgs = await page.locator("img[src*='flow.google.com/asb/'], img[src*='googleusercontent.com']").all()
            imgs = [im for im in imgs if "ogw/AF2b" not in (await im.get_attribute("src") or "")]
            if imgs:
                src = await imgs[0].get_attribute("src")
                b64 = await page.evaluate("""async (url) => {
                    const res = await fetch(url);
                    const blob = await res.blob();
                    return new Promise((r) => {
                        const rd = new FileReader();
                        rd.onloadend = () => r(rd.result.split(',')[1]);
                        rd.readAsDataURL(blob);
                    });
                }""", src)
                with open(img_file, "wb") as f:
                    f.write(base64.b64decode(b64))
                print(f"[✓ 阶段 1完成] Shot 02 首帧已保存: {img_file} ({os.path.getsize(img_file)} 字节)")
        else:
            print(f"[阶段 1跳过] Shot 02 首帧已存在: {img_file}")

        # ---------------------------------------------------------
        # 阶段 2：使用 Veo 3.1 - Lite 生成 Shot 02 8s 视频 (10 积分)
        # ---------------------------------------------------------
        video_file = os.path.join(video_dir, "shot_02_veo_8s.mp4")
        if not os.path.exists(video_file):
            print("\n[阶段 2: 视频渲染] 正在配置 Veo 3.1 - Lite 8秒视频 (10 积分)...")
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(300)
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(400)

            trigger = page.locator("button[aria-label='Settings trigger']").first
            await trigger.click(force=True)
            await page.wait_for_timeout(800)

            vid_tab = page.locator("div.cdk-overlay-pane button:has-text('Video')").first
            await vid_tab.click(force=True)
            await page.wait_for_timeout(500)

            # x1 档位与 8s 时长
            await page.locator("div.cdk-overlay-pane button:has-text('x1')").first.click(force=True)
            dur_btn = page.locator("div.cdk-overlay-pane button:has-text('8s')").first
            if await dur_btn.count() > 0:
                await dur_btn.click(force=True)

            # 切换模型至 Veo 3.1 - Lite
            dropdown = page.locator("div.cdk-overlay-pane button:has-text('arrow_drop_down'), div.cdk-overlay-pane button:has-text('Flash'), div.cdk-overlay-pane button:has-text('Veo')").first
            if await dropdown.count() > 0:
                cur_txt = (await dropdown.inner_text()).strip()
                if "Veo 3.1 - Lite" not in cur_txt:
                    await dropdown.click(force=True)
                    await page.wait_for_timeout(600)
                    lite_opt = page.locator("[role='menu'] button:has-text('Veo 3.1 - Lite'), button:has-text('Veo 3.1 - Lite')").first
                    if await lite_opt.count() > 0:
                        await lite_opt.click(force=True)
                        await page.wait_for_timeout(600)

            # 抓取积分提示
            cost_elem = page.locator("div.cdk-overlay-pane").get_by_text(re.compile(r"Generating will use \d+ credits")).first
            cost_txt = await cost_elem.inner_text() if await cost_elem.count() > 0 else "10 credits"
            m = re.search(r"(\d+)\s*credits", cost_txt)
            cost_val = int(m.group(1)) if m else 10
            print(f"[+] 经 UI 确认，单次视频生成将消耗: {cost_val} 积分。")

            await page.keyboard.press("Escape")
            await page.wait_for_timeout(400)

            # 记录当前已有的 video 元素数量
            existing_videos = await page.locator("video").all()
            old_video_count = len(existing_videos)

            # 填入视频动作提示词
            editor = page.locator(".ProseMirror").first
            await editor.click(force=True)
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await page.keyboard.type(SHOT_02_INFO["video_prompt"], delay=10)
            await page.wait_for_timeout(600)

            gen_btn = page.locator("button[aria-label='Start generation'], button:has-text('arrow_forward')").first
            await gen_btn.click(force=True)
            print(f"[+] 已点击 Start generation 提交 Shot 02 视频渲染！")
            await page.wait_for_timeout(4000)

            # 截屏留存
            await page.screenshot(path=os.path.join(debug_dir, "shot02_submitted.png"))

            # 更新账本
            ledger.record_usage(
                shot_id=2,
                model="Veo 3.1 - Lite",
                duration="8s",
                count="x1",
                cost=cost_val,
                prompt=SHOT_02_INFO["video_prompt"],
                artifact_path=video_file
            )

            # 监控渲染并下载
            print("[+] 正在监控 Veo 3.1 渲染进程 (最长 180s)...")
            start_t = time.time()
            saved = False
            while time.time() - start_t < 180:
                await page.wait_for_timeout(6000)
                videos = await page.locator("video").all()
                if len(videos) > old_video_count or (len(videos) > 0 and old_video_count == 0):
                    newest_video = videos[0]
                    v_src = await newest_video.get_attribute("src")
                    if v_src and ("flow-content.google" in v_src or "blob:" in v_src or "http" in v_src):
                        print(f"[✓] 检测到 Shot 02 视频成片流: {v_src[:70]}...")
                        b64_vid = await page.evaluate("""async (url) => {
                            const res = await fetch(url);
                            const blob = await res.blob();
                            return new Promise((r) => {
                                const rd = new FileReader();
                                rd.onloadend = () => r(rd.result.split(',')[1]);
                                rd.readAsDataURL(blob);
                            });
                        }""", v_src)
                        with open(video_file, "wb") as vf:
                            vf.write(base64.b64decode(b64_vid))
                        print(f"[✓ 阶段 2完成] Shot 02 视频成片已下载: {video_file} ({os.path.getsize(video_file)} 字节)")
                        saved = True
                        break
                print(f"  ... Veo 渲染进行中 ({int(time.time() - start_t)}s)")

            if not saved:
                print("[-] 监控超时，截取当前界面排查...")
                await page.screenshot(path=os.path.join(debug_dir, "shot02_timeout.png"))
        else:
            print(f"[阶段 2跳过] Shot 02 视频成片已存在: {video_file}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_shot_02())
