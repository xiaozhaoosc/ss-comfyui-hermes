import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        page = [pg for pg in b.contexts[0].pages if 'flow.google.com' in pg.url][0]
        done_btn = page.locator("button:has-text('Done'), button[aria-label*='Done']").first
        if await done_btn.count() > 0:
            await done_btn.click()
            await page.wait_for_timeout(2000)
            print("Successfully clicked Done and returned to canvas.")
        await b.close()

if __name__ == '__main__':
    asyncio.run(main())
