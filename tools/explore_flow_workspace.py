import asyncio
import os
import sys
import datetime
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def open_flow_project():
    today = datetime.date.today().strftime("%Y-%m-%d")
    debug_dir = os.path.abspath(f"output/{today}/yangjiajiang_ep03/flow_debug")
    os.makedirs(debug_dir, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        
        flow_page = None
        for page in context.pages:
            if "flow.google.com" in page.url:
                flow_page = page
                break
                
        if not flow_page:
            print("Flow page not found!")
            await browser.close()
            return
            
        print(f"Found Flow page: {flow_page.url}")
        
        # 1. 按 Escape 关闭遮罩层 / profile 浮层
        await flow_page.keyboard.press("Escape")
        await flow_page.wait_for_timeout(1000)
        
        # 2. 点击 New project
        new_proj_btn = flow_page.locator("button.new-project-button, button:has-text('New project')").first
        print("Clicking New project (with force=True)...")
        await new_proj_btn.click(force=True)
        await flow_page.wait_for_timeout(5000)
        
        print(f"Current URL after click: {flow_page.url}")
        shot_path = os.path.join(debug_dir, "flow_workspace_active.png")
        await flow_page.screenshot(path=shot_path)
        print(f"Screenshot saved: {shot_path}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(open_flow_project())
