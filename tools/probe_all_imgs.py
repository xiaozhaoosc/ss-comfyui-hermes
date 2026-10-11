import asyncio
from playwright.async_api import async_playwright

async def probe_all_imgs():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        page = [pg for pg in b.contexts[0].pages if 'flow.google.com/project' in pg.url][0]
        
        imgs = await page.locator("img[src*='flow.google.com/asb/']").all()
        print(f"Total flow asb images: {len(imgs)}")
        for i, img in enumerate(imgs):
            src = await img.get_attribute("src")
            box = await img.bounding_box()
            print(f"  Img [{i}]: src='{src[:60]}', box={box}")

        await b.close()

if __name__ == '__main__':
    asyncio.run(probe_all_imgs())
