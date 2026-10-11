import asyncio
import os
import base64
from playwright.async_api import async_playwright

async def extract():
    save_path = os.path.abspath('output/2026-10-10/route_a/videos/shot_02_veo_8s.mp4')
    
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        page = [pg for pg in b.contexts[0].pages if 'flow.google.com/project' in pg.url][0]

        # 查找所有的 video 标签
        videos = await page.locator("video").all()
        print(f"Total <video> elements: {len(videos)}")
        for idx, v in enumerate(videos):
            src = await v.get_attribute("src")
            print(f"  Video [{idx}]: {src[:80] if src else 'None'}")

        # 如果只有 1 个 video，或者没有找到第二个，我们点击第一张卡片 (x=430, y=180) 来激活并加载 video
        top_left_card = page.locator("button:has-text('play_arrow'), [aria-label*='video'], [aria-label*='Video']").first
        if await top_left_card.count() > 0:
            print("Clicking top-left card to inspect/activate...")
            await top_left_card.click()
            await page.wait_for_timeout(1500)

        # 再次查找 video
        videos_after = await page.locator("video").all()
        print(f"Total <video> elements after click: {len(videos_after)}")
        target_src = None
        for v in videos_after:
            src = await v.get_attribute("src")
            print(f"  After click video: {src[:80] if src else 'None'}")
            if src and "aca8e9e4" not in src: # 排除 Shot 01 的旧视频
                target_src = src
                break

        if not target_src and videos_after:
            target_src = await videos_after[0].get_attribute("src")

        if target_src:
            print(f"[+] Found target video URL: {target_src[:80]}...")
            b64 = await page.evaluate("""async (url) => {
                const res = await fetch(url);
                const blob = await res.blob();
                return new Promise((r) => {
                    const rd = new FileReader();
                    rd.onloadend = () => r(rd.result.split(',')[1]);
                    rd.readAsDataURL(blob);
                });
            }""", target_src)

            with open(save_path, "wb") as f:
                f.write(base64.b64decode(b64))
            print(f"[✓] Saved Shot 02 video to: {save_path} ({os.path.getsize(save_path)} bytes)")

        await page.screenshot(path="output/2026-10-10/route_a/debug/shot02_extracted.png")
        await b.close()

if __name__ == '__main__':
    asyncio.run(extract())
