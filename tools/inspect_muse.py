import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def inspect_muse():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        
        muse_page = None
        for page in context.pages:
            if "muse.ai" in page.url:
                muse_page = page
                break
                
        if not muse_page:
            print("Muse page not found!")
            await browser.close()
            return
            
        print(f"Connected to Muse page: {muse_page.url}")
        
        # 探测输入框与按钮
        inputs = await muse_page.locator("textarea, input").all()
        print(f"Muse Inputs ({len(inputs)}):")
        for i, inp in enumerate(inputs):
            p = await inp.get_attribute("placeholder")
            t = await inp.evaluate("e => e.tagName")
            print(f"  [{i}] {t}: placeholder='{p}'")
            
        buttons = await muse_page.locator("button").all()
        print(f"Muse Buttons ({len(buttons)}):")
        for i, btn in enumerate(buttons[:20]):
            txt = (await btn.inner_text()).strip().replace('\n', ' ')
            aria = await btn.get_attribute("aria-label")
            if txt or aria:
                print(f"  [{i}] text='{txt[:25]}', aria='{aria}'")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect_muse())
