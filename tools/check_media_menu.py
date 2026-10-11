import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def main():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        page = [pg for pg in b.contexts[0].pages if 'flow.google.com' in pg.url][0]
        
        await page.screenshot(path='output/2026-10-10/route_a/debug/menu_snap.png')
        print("Screenshot saved to output/2026-10-10/route_a/debug/menu_snap.png")

        # 检查当前页面上的所有 menu item
        items = await page.locator("[role='menuitem'], .mat-mdc-menu-item").all()
        print(f"Total menu items: {len(items)}")
        for idx, item in enumerate(items):
            txt = await item.inner_text()
            print(f"  Item #{idx}: '{txt}'")

        await b.close()

if __name__ == '__main__':
    asyncio.run(main())
