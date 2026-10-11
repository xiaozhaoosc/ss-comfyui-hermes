import asyncio
import os
import requests
import base64
from playwright.async_api import async_playwright

async def download_video():
    out_dir = os.path.abspath('output/2026-10-10/route_a/videos')
    os.makedirs(out_dir, exist_ok=True)
    save_path = os.path.join(out_dir, 'shot_01_veo_8s.mp4')
    
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        page = [pg for pg in b.contexts[0].pages if 'flow.google.com/project' in pg.url][0]
        
        video_elem = page.locator("video").first
        v_src = await video_elem.get_attribute("src")
        print("Found video src:", v_src[:80])

        b64 = await page.evaluate("""async (url) => {
            const res = await fetch(url);
            const blob = await res.blob();
            return new Promise((r) => {
                const rd = new FileReader();
                rd.onloadend = () => r(rd.result.split(',')[1]);
                rd.readAsDataURL(blob);
            });
        }""", v_src)

        with open(save_path, "wb") as f:
            f.write(base64.b64decode(b64))

        print(f"[✓] Saved video to: {save_path} ({os.path.getsize(save_path)} bytes)")
        await b.close()

if __name__ == '__main__':
    asyncio.run(download_video())
