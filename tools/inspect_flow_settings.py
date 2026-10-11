import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def inspect_flow_settings():
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
            
        print("Clicking Settings trigger...")
        settings_btn = flow_page.locator("button[aria-label='Settings trigger']").first
        if await settings_btn.count() > 0:
            await settings_btn.click()
            await flow_page.wait_for_timeout(1500)
            
            # 探测弹出的菜单选项
            menu_items = await flow_page.locator("[role='menuitem'], [role='option'], .mat-mdc-menu-item, mat-radio-button, mat-select").all()
            print(f"Found {len(menu_items)} menu items / settings:")
            for i, mi in enumerate(menu_items):
                txt = (await mi.inner_text()).strip().replace('\n', ' | ')
                print(f"  [{i}]: {txt}")
                
            # 按 Escape 关闭菜单
            await flow_page.keyboard.press("Escape")
        else:
            print("Settings trigger button not found!")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect_flow_settings())
