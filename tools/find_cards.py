import asyncio
from playwright.async_api import async_playwright

async def find_cards():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        page = [pg for pg in b.contexts[0].pages if 'flow.google.com/project' in pg.url][0]

        items = await page.locator("[aria-label*='Generated video'], [aria-label*='video'], [aria-label*='Video'], div:has(> img[src*='asb'])").all()
        print(f"Total candidate elements: {len(items)}")
        for idx, it in enumerate(items):
            box = await it.bounding_box()
            aria = await it.get_attribute("aria-label")
            txt = (await it.inner_text()).strip().replace('\n', ' ')[:40]
            print(f"  [{idx}]: aria='{aria}', box={box}, text='{txt}'")

        await b.close()

if __name__ == '__main__':
    asyncio.run(find_cards())
