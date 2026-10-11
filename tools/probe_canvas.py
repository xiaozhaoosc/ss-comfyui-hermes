import asyncio
from playwright.async_api import async_playwright

async def probe():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        page = [pg for pg in b.contexts[0].pages if 'flow.google.com/project' in pg.url][0]
        imgs = await page.locator('img').all()
        print('Total imgs:', len(imgs))
        for i, img in enumerate(imgs):
            src = await img.get_attribute('src')
            print(f'  Img {i}: {src[:60] if src else None}')
        # 查看 canvas
        canvases = await page.locator('canvas').all()
        print('Total canvases:', len(canvases))
        await b.close()

if __name__ == '__main__':
    asyncio.run(probe())
