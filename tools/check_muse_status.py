import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def check_muse():
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
        
        # 截屏看当前状态
        shot_path = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/flow_debug/muse_current_status.png")
        try:
            await muse_page.screenshot(path=shot_path, timeout=5000)
            print(f"Screenshot saved: {shot_path}")
        except Exception as e:
            print(f"Screenshot failed: {e}")
            
        # 检查最新消息
        messages = await muse_page.locator("div.message, div[role='article'], p, .chat-message").all()
        print(f"Total messages: {len(messages)}")
        for i, m in enumerate(messages[-5:]):
            txt = (await m.inner_text()).strip()
            print(f"  Recent [{i}]: {txt[:120]}")

        # 检查最新生成的 video 标签
        videos = await muse_page.locator("video").all()
        print(f"Videos present on page: {len(videos)}")
        for i, v in enumerate(videos):
            src = await v.get_attribute("src")
            print(f"  Video [{i}]: {src}")

        # 检查下载按钮
        dl_btns = await muse_page.locator("button[aria-label='下载视频']").all()
        print(f"Download video buttons: {len(dl_btns)}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(check_muse())
