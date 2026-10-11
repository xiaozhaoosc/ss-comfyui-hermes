import asyncio
import os
import re
from playwright.async_api import async_playwright

async def submit_shot02_video():
    prompt = "Cinematic medium low angle shot inside Kaifeng imperial court hall. An ancient prime minister in crimson robes prostrating on the floor with folded hands, robes trembling with emotional breathing, pleading earnestly before the imperial throne, dust motes drifting in shafts of sunlight, solemn court ambiance, dramatic historical lighting, 8s."
    
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        page = [pg for pg in b.contexts[0].pages if 'flow.google.com/project' in pg.url][0]

        # 1. 确保弹窗干净
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(300)
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(500)

        # 2. 点击设置触发按钮 (pill 胶囊)
        pill = page.locator("button[aria-label='Settings trigger']").first
        print("Clicking settings trigger pill...")
        await pill.click(force=True)
        await page.wait_for_timeout(1000)

        # 3. 点击 [Video] 标签页
        # 兼容文本或 videocam 图标
        vid_btn = page.locator("button:has-text('Video'), [role='tab']:has-text('Video'), button:has-text('videocam')").first
        print("Clicking Video tab...")
        await vid_btn.click(force=True)
        await page.wait_for_timeout(800)

        # 4. 选择 x1
        x1_btn = page.locator(".cdk-overlay-pane button:has-text('x1'), div:has-text('x1')").last
        if await x1_btn.count() > 0:
            await x1_btn.click(force=True)
            await page.wait_for_timeout(400)

        # 5. 选择 8s
        dur_btn = page.locator(".cdk-overlay-pane button:has-text('8s')").first
        if await dur_btn.count() > 0:
            await dur_btn.click(force=True)
            await page.wait_for_timeout(400)

        # 6. 选择 Veo 3.1 - Lite
        dropdown = page.locator(".cdk-overlay-pane button:has-text('Flash'), .cdk-overlay-pane button:has-text('Veo'), .cdk-overlay-pane button:has-text('arrow_drop_down')").first
        if await dropdown.count() > 0:
            txt = (await dropdown.inner_text()).strip()
            if "Veo 3.1 - Lite" not in txt:
                print("Switching model to Veo 3.1 - Lite...")
                await dropdown.click(force=True)
                await page.wait_for_timeout(600)
                opt = page.locator("[role='menu'] button:has-text('Veo 3.1 - Lite'), button:has-text('Veo 3.1 - Lite')").first
                if await opt.count() > 0:
                    await opt.click(force=True)
                    await page.wait_for_timeout(600)

        # 7. 读取积分
        cost_el = page.locator(".cdk-overlay-pane").get_by_text(re.compile(r"Generating will use \d+ credits")).first
        cost_txt = await cost_el.inner_text() if await cost_el.count() > 0 else "10 credits"
        print(f"Credit cost: {cost_txt}")

        await page.keyboard.press("Escape")
        await page.wait_for_timeout(400)

        # 8. 填入视频提示词
        print("Typing Shot 02 video prompt...")
        editor = page.locator(".ProseMirror").first
        await editor.click(force=True)
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        await page.keyboard.type(prompt, delay=10)
        await page.wait_for_timeout(800)

        # 9. 点击生成
        gen_btn = page.locator("button[aria-label='Start generation'], button:has-text('arrow_forward')").first
        print("Clicking Start generation for Shot 02 video...")
        await gen_btn.click(force=True)
        await page.wait_for_timeout(5000)

        await page.screenshot(path="output/2026-10-10/route_a/debug/shot02_video_triggered.png")
        print("Shot 02 video submitted successfully!")
        await b.close()

if __name__ == '__main__':
    asyncio.run(submit_shot02_video())
