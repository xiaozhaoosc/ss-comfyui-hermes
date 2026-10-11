import asyncio
import os
import base64
import time
from playwright.async_api import async_playwright

async def wait_and_download_shot02():
    save_path = os.path.abspath('output/2026-10-10/route_a/videos/shot_02_veo_8s.mp4')
    debug_dir = os.path.abspath('output/2026-10-10/route_a/debug')
    
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        page = [pg for pg in b.contexts[0].pages if 'flow.google.com/project' in pg.url][0]

        print("Monitoring Shot 02 video rendering...")
        # 等待最多 120 秒
        for tick in range(24): # 24 * 5s = 120s
            await page.wait_for_timeout(5000)
            videos = await page.locator("video").all()
            print(f"Tick {tick+1}: Total video elements on page = {len(videos)}")
            
            # 当有两个视频元素，或者最新的视频元素 src 不是旧的 shot 01 时
            if len(videos) >= 2:
                # 第二个或者最新的视频
                v_src = await videos[0].get_attribute("src")
                print(f"[✓] New video element detected: {v_src[:80]}...")
                
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

                print(f"[✓] Saved Shot 02 video to: {save_path} ({os.path.getsize(save_path)} bytes)")
                break
            else:
                # 检查是否还在百分比进度
                status_texts = await page.locator("text=/\\d+%/").all()
                if status_texts:
                    pct = (await status_texts[0].inner_text()).strip()
                    print(f"  ... Rendering progress: {pct}")

        await page.screenshot(path=os.path.join(debug_dir, "shot02_finished_canvas.png"))
        await b.close()

if __name__ == '__main__':
    asyncio.run(wait_and_download_shot02())
