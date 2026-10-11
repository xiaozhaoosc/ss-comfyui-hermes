import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        page = [pg for pg in b.contexts[0].pages if 'flow.google.com' in pg.url][0]
        
        # 寻找 delete_forever 按钮
        btn = page.locator("button:has-text('delete_forever'), [aria-label*='delete'], [aria-label*='Delete']").first
        if await btn.count() > 0:
            await btn.click()
            await page.wait_for_timeout(1500)
            print("Successfully clicked delete_forever on failed card.")
        else:
            print("No delete button found.")
            
        await page.screenshot(path="output/2026-10-10/route_a/debug/canvas_after_cleanup.png")
        await b.close()

if __name__ == '__main__':
    asyncio.run(main())
