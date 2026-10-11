import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def open_scenes():
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

        print("Clicking 'Scenes' on sidebar...")
        scenes_tab = flow_page.locator("button:has-text('Scenes'), div:has-text('Scenes')").first
        if await scenes_tab.count() > 0:
            await scenes_tab.click()
            await flow_page.wait_for_timeout(2000)
            
            shot_path = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/flow_debug/flow_scenes_view.png")
            await flow_page.screenshot(path=shot_path, timeout=5000)
            print(f"Screenshot saved: {shot_path}")
            
            # 探测当前页面按钮与模型标识
            text_items = await flow_page.locator(".sidebar, .content, mat-chip, button").all()
            print(f"Items found in Scenes view: {len(text_items)}")
            for i in range(min(len(text_items), 15)):
                t = text_items[i]
                txt = (await t.inner_text()).strip().replace('\n', ' ')
                if txt:
                    print(f"  [{i}]: {txt[:35]}")
        else:
            print("'Scenes' tab not found!")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(open_scenes())
