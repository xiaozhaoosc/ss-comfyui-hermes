import asyncio
import os
import base64
from playwright.async_api import async_playwright

async def download_newest_img():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        page = [pg for pg in b.contexts[0].pages if 'flow.google.com/project' in pg.url][0]
        
        imgs = await page.locator("img[src*='flow.google.com/asb/']").all()
        target_img = imgs[-1] # 最新的图片在最后
        src = await target_img.get_attribute("src")
        print("Newest image src:", src)

        b64 = await page.evaluate("""async (url) => {
            const res = await fetch(url);
            const blob = await res.blob();
            return new Promise((r) => {
                const rd = new FileReader();
                rd.onloadend = () => r(rd.result.split(',')[1]);
                rd.readAsDataURL(blob);
            });
        }""", src)

        save_path = os.path.abspath('output/2026-10-10/route_a/images/shot_02_frame.png')
        with open(save_path, "wb") as f:
            f.write(base64.b64decode(b64))

        print(f"Saved newest image to: {save_path} ({os.path.getsize(save_path)} bytes)")
        await b.close()

if __name__ == '__main__':
    asyncio.run(download_newest_img())
