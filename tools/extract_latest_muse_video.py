import asyncio
import os
import sys
import base64
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def extract_latest_muse_video():
    save_path = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/comparison/muse_shot02_real.mp4")
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        
        muse_page = None
        for page in context.pages:
            if "muse.ai" in page.url:
                muse_page = page
                break
                
        if not muse_page:
            print("Muse page not found!")
            await browser.close()
            return
            
        videos = await muse_page.locator("video").all()
        print(f"Total video elements on Muse: {len(videos)}")
        for i, v in enumerate(videos):
            src = await v.get_attribute("src")
            print(f"  Video [{i}]: src='{src}'")

        if len(videos) > 0:
            # 最新生成的往往是最后一个 video
            latest_vid = videos[-1]
            latest_src = await latest_vid.get_attribute("src")
            print(f"Downloading latest video [-1]: {latest_src}...")
            
            b64_data = await muse_page.evaluate("""async (videoSrc) => {
                const resp = await fetch(videoSrc);
                const blob = await resp.blob();
                return new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result.split(',')[1]);
                    reader.onerror = reject;
                    reader.readAsDataURL(blob);
                });
            }""", latest_src)
            
            video_bytes = base64.b64decode(b64_data)
            with open(save_path, "wb") as f:
                f.write(video_bytes)
            print(f"[√] Saved to {save_path} ({len(video_bytes)} bytes)")
            
            # 同时覆盖 muse_shot02.mp4
            final_p = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/comparison/muse_shot02.mp4")
            with open(final_p, "wb") as f:
                f.write(video_bytes)
            print(f"[√] Updated {final_p}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(extract_latest_muse_video())
