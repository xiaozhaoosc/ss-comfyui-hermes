import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def inspect_sidebar():
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

        nav_items = await flow_page.locator("a, mat-list-item, [role='listitem'], .mat-mdc-list-item").all()
        print(f"Nav items count: {len(nav_items)}")
        for i, item in enumerate(nav_items):
            txt = (await item.inner_text()).strip().replace('\n', ' ')
            href = await item.get_attribute("href")
            print(f"  Nav [{i}]: '{txt}', href='{href}'")
            if "scene" in txt.lower():
                print(f"    -> Clicking Scene item {i}...")
                await item.click()
                await flow_page.wait_for_timeout(2000)
                shot_path = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/flow_debug/flow_scenes_clicked.png")
                await flow_page.screenshot(path=shot_path, timeout=5000)
                print(f"    -> Screenshot saved: {shot_path}")
                break

        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect_sidebar())
