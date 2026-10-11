import asyncio
import os
import base64
import time
from playwright.async_api import async_playwright

async def wait_shot02():
    save_path = os.path.abspath('output/2026-10-10/route_a/videos/shot_02_veo_8s.mp4')
    debug_dir = os.path.abspath('output/2026-10-10/route_a/debug')
    
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        page = [pg for pg in b.contexts[0].pages if 'flow.google.com/project' in pg.url][0]

        print("Waiting for Shot 02 video to complete 100%...")
        for tick in range(20): # 20 * 4s = 80s
            await page.wait_for_timeout(4000)
            videos = await page.locator("video").all()
            print(f"Tick {tick+1}: Total videos = {len(videos)}")
            
            # 找到最新的非 aca8e9e4 的视频
            new_v = None
            for v in videos:
                src = await v.get_attribute("src")
                if src and "aca8e9e4" not in src:
                    new_v = v
                    break

            if new_v:
                src = await new_v.get_attribute("src")
                print(f"[✓] Completed! Found new video src: {src[:70]}...")
                b64 = await page.evaluate("""async (url) => {
                    const res = await fetch(url);
                    const blob = await res.blob();
                    return new Promise((r) => {
                        const rd = new FileReader();
                        rd.onloadend = () => r(rd.result.split(',')[1]);
                        rd.readAsDataURL(blob);
                    });
                }""", src)
                with open(save_path, "wb") as f:
                    f.write(base64.b64decode(b64))
                print(f"[✓] Saved Shot 02 video to: {save_path} ({os.path.getsize(save_path)} bytes)")
                break

        await page.screenshot(path=os.path.join(debug_dir, "shot02_completed_canvas.png"))
        await b.close()

if __name__ == '__main__':
    asyncio.run(wait_shot02())
