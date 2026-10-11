import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def inspect_models():
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

        debug_dir = os.path.abspath("output/2026-10-10/flow_debug")
        
        # 点击模型选择下拉框
        dropdown = flow_page.locator("button:has-text('Omni 1.1 Flash'), div:has-text('Omni 1.1 Flash')").last
        print("Clicking model dropdown...")
        await dropdown.click()
        await flow_page.wait_for_timeout(1500)
        
        await flow_page.screenshot(path=os.path.join(debug_dir, "live_flow_models_dropdown.png"))
        print("Screenshot saved: live_flow_models_dropdown.png")
        
        # 查找所有的菜单项
        items = await flow_page.locator("[role='menuitem'], [role='option'], .mat-mdc-menu-item, button").all()
        for i, it in enumerate(items):
            txt = (await it.inner_text()).strip()
            if any(k in txt.lower() for k in ['omni', 'veo', 'flash', 'pro', 'quality', 'fast', 'lite']):
                print(f"Model item [{i}]: {txt}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect_models())
