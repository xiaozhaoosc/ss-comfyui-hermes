import asyncio
import os
import sys
import re
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def test_costs():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        flow_page = None
        for page in context.pages:
            if "flow.google.com/project" in page.url:
                flow_page = page
                break
                
        if not flow_page:
            print("Flow project page not found!")
            await browser.close()
            return

        # 确保设置弹窗开启
        settings_pane = flow_page.locator("div:has-text('Generating will use')").first
        if await settings_pane.count() == 0:
            trigger = flow_page.locator("button[aria-label='Settings trigger']").first
            await trigger.click()
            await flow_page.wait_for_timeout(1000)

        # 确保在 Video 标签页
        video_tab = flow_page.locator("button:has-text('Video'), div[role='button']:has-text('Video')").first
        await video_tab.click()
        await flow_page.wait_for_timeout(500)

        # 测试 x1 按钮
        x1_btn = flow_page.locator("button:has-text('x1'), div:has-text('x1')").last
        await x1_btn.click()
        await flow_page.wait_for_timeout(500)

        # 读取当前额度提示
        cost_text = await flow_page.locator("text=/Generating will use \\d+ credits/").inner_text()
        print(f"Current cost (x1): '{cost_text}'")

        # 检查 Veo 3.1 - Lite
        dropdown = flow_page.locator("button:has(i), div:has-text('Omni 1.1 Flash'), div:has-text('Veo 3.1')").last
        await dropdown.click()
        await flow_page.wait_for_timeout(500)
        
        lite_opt = flow_page.locator("button:has-text('Veo 3.1 - Lite')").first
        if await lite_opt.count() > 0:
            await lite_opt.click()
            await flow_page.wait_for_timeout(500)
            cost_lite = await flow_page.locator("text=/Generating will use \\d+ credits/").inner_text()
            print(f"Cost with Veo 3.1 - Lite (x1): '{cost_lite}'")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_costs())
