import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def inspect_muse_history():
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

        print(f"Connected to Muse page: {muse_page.url}")
        
        # 提取消息气泡文本
        messages = await muse_page.locator("div.message, div[role='article'], p, .chat-message").all()
        print(f"Messages/paragraphs found: {len(messages)}")
        for i, m in enumerate(messages[:15]):
            txt = (await m.inner_text()).strip()
            if txt and len(txt) > 5:
                print(f"  [{i}]: {txt[:100]}...")

        # 检查 video 元素与下载按钮
        videos = await muse_page.locator("video").all()
        print(f"\nVideos found: {len(videos)}")
        for i, v in enumerate(videos):
            src = await v.get_attribute("src")
            print(f"  Video [{i}]: src='{src}'")

        download_btns = await muse_page.locator("button[aria-label='下载视频'], button:has-text('下载')").all()
        print(f"\nDownload buttons found: {len(download_btns)}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect_muse_history())
