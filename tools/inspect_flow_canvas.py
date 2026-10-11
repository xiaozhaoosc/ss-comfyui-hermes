import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def inspect():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        
        flow_page = None
        for page in context.pages:
            if "flow.google.com/project" in page.url:
                flow_page = page
                break
        if not flow_page:
            for page in context.pages:
                if "flow.google.com" in page.url:
                    flow_page = page
                    break
                    
        if not flow_page:
            print("Flow page not found!")
            await browser.close()
            return
            
        print(f"Connected to Flow page: {flow_page.url}")
        
        # 探测输入框、文本域
        print("\n--- TEXT INPUTS ---")
        locators = flow_page.locator("textarea, input, [contenteditable='true']")
        count = await locators.count()
        print(f"Total input count: {count}")
        for i in range(min(count, 15)):
            loc = locators.nth(i)
            tag = await loc.evaluate("e => e.tagName")
            type_attr = await loc.get_attribute("type")
            placeholder = await loc.get_attribute("placeholder")
            aria = await loc.get_attribute("aria-label")
            print(f"  [{i}] Tag={tag}, type={type_attr}, placeholder='{placeholder}', aria-label='{aria}'")

        # 探测底部/核心生成按钮
        print("\n--- BUTTONS ---")
        btn_locs = flow_page.locator("button")
        btn_count = await btn_locs.count()
        print(f"Total button count: {btn_count}")
        for i in range(min(btn_count, 35)):
            btn = btn_locs.nth(i)
            text = (await btn.inner_text()).strip().replace('\n', ' ')
            aria = await btn.get_attribute("aria-label")
            classes = await btn.get_attribute("class")
            if text or aria:
                print(f"  Btn [{i}]: text='{text[:30]}', aria='{aria}', class='{classes[:40] if classes else ''}'")

        # 尝试截图 (加 5000ms 超时限制)
        try:
            shot_path = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/flow_debug/flow_canvas_clean.png")
            await flow_page.screenshot(path=shot_path, timeout=5000)
            print(f"\nScreenshot saved: {shot_path}")
        except Exception as e:
            print(f"\nScreenshot skipped due to timeout: {e}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect())
