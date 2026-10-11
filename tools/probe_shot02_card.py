import asyncio
from playwright.async_api import async_playwright

async def probe_card():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        page = [pg for pg in b.contexts[0].pages if 'flow.google.com/project' in pg.url][0]

        # 查找包含 0% 或 progress 或 card 的所有元素
        cards = await page.locator("div.media-card, div[role='article'], div:has(> video), div:has(> img)").all()
        print(f"Total card containers: {len(cards)}")
        
        # 查找所有文本
        texts = await page.locator(".cdk-overlay-pane, .card-content, .media-item, [aria-label*='video'], [aria-label*='Video']").all()
        for i, t in enumerate(texts[:10]):
            txt = (await t.inner_text()).strip().replace('\n', ' ')
            aria = await t.get_attribute("aria-label")
            print(f"Item [{i}]: text='{txt}', aria='{aria}'")

        # 检查是否有错误提示 toast 或 notification
        toasts = await page.locator(".mat-mdc-snack-bar-container, .error-message, [role='alert'], .toast").all()
        print(f"Toasts/Alerts: {len(toasts)}")
        for j, ts in enumerate(toasts):
            print(f"Toast [{j}]: {await ts.inner_text()}")

        # 检查所有 video 元素
        videos = await page.locator("video").all()
        print(f"Total video elements: {len(videos)}")
        for k, v in enumerate(videos):
            src = await v.get_attribute("src")
            print(f"Video [{k}]: {src[:80] if src else 'No src'}")

        await b.close()

if __name__ == '__main__':
    asyncio.run(probe_card())
