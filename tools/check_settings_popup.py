import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def check_settings_popup():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        
        flow_page = None
        for page in context.pages:
            if "flow.google.com/project" in page.url:
                flow_page = page
                break
                
        if not flow_page:
            print("Flow page not found!")
            await browser.close()
            return
            
        settings_btn = flow_page.locator("button[aria-label='Settings trigger']").first
        await settings_btn.click()
        await flow_page.wait_for_timeout(1000)
        
        # 查找 cdk-overlay 里面的所有文本
        overlay = flow_page.locator(".cdk-overlay-container")
        if await overlay.count() > 0:
            text = await overlay.inner_text()
            print("Overlay content:\n", text)
        else:
            print("No cdk-overlay-container found.")
            
        await flow_page.keyboard.press("Escape")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(check_settings_popup())
