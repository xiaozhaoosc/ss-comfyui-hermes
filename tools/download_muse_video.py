import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def download_video():
    save_path = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/comparison/muse_shot01.mp4")
    print(f"Target save path: {save_path}")
    
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

        print("Locating video and download button...")
        # 方式 1: 直接在浏览器页面内将 blob URL 转成 base64 传回 Python，100% 成功且不依赖浏览器默认下载弹窗
        video = muse_page.locator("video").first
        video_src = await video.get_attribute("src")
        print(f"Video element src: {video_src}")
        
        try:
            print("Fetching video blob from page context...")
            b64_data = await muse_page.evaluate("""async (src) => {
                const resp = await fetch(src);
                const blob = await resp.blob();
                return new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result.split(',')[1]);
                    reader.onerror = reject;
                    reader.readAsDataURL(blob);
                });
            }""", video_src)
            
            import base64
            video_bytes = base64.b64decode(b64_data)
            with open(save_path, "wb") as f:
                f.write(video_bytes)
            print(f"SUCCESS! Video downloaded and saved: {save_path} ({len(video_bytes)} bytes)")
        except Exception as e:
            print(f"Blob fetch error: {e}, falling back to expect_download...")
            dl_btn = muse_page.locator("button[aria-label='下载视频']").first
            async with muse_page.expect_download() as dl_info:
                await dl_btn.click()
            download = await dl_info.value
            await download.save_as(save_path)
            print(f"Downloaded via expect_download: {save_path}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(download_video())
