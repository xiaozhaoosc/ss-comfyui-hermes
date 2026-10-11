import asyncio
from playwright.async_api import async_playwright

async def inspect_video_card():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        page = [pg for pg in b.contexts[0].pages if 'flow.google.com/project' in pg.url][0]
        
        # 查找所有的 video 或 play 按钮或包含 play_arrow 的元素
        videos = await page.locator("video").all()
        print(f"Total <video> elements: {len(videos)}")
        for i, v in enumerate(videos):
            src = await v.get_attribute("src")
            print(f"  Video [{i}]: src='{src}'")

        # 查找包含 play 图标的卡片
        play_cards = await page.locator("button:has-text('play_arrow'), div:has-text('play_arrow'), [aria-label*='Play'], [aria-label*='video']").all()
        print(f"Play card elements: {len(play_cards)}")
        for j, pc in enumerate(play_cards[:5]):
            txt = (await pc.inner_text()).strip()
            aria = await pc.get_attribute("aria-label")
            print(f"  Play item [{j}]: text='{txt}', aria='{aria}'")

        await b.close()

if __name__ == '__main__':
    asyncio.run(inspect_video_card())
