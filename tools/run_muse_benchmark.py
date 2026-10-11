import asyncio
import os
import sys
import datetime
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def run_muse():
    shot01_img = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/comparison/shot01.jpg")
    print(f"Shot 01 image: {shot01_img} (exists: {os.path.exists(shot01_img)})")
    
    prompt = "请基于上传的这张首帧原画，生成一段4秒竖屏水墨国风视频：Vertical shot, camera tilts up slowly. Grand Song imperial carriage procession marching north under bleak winter skies, giant ochre-yellow dragon flag fluttering violently in freezing howling wind."
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        
        muse_page = None
        for page in context.pages:
            if "muse.ai" in page.url:
                muse_page = page
                break
                
        if not muse_page:
            print("Muse page not found in Chrome tabs!")
            await browser.close()
            return
            
        print(f"Connected to Muse page: {muse_page.url}")
        
        # 1. 上传图片
        file_input = muse_page.locator("input[type='file']").first
        if await file_input.count() > 0:
            print("Uploading shot01.jpg to Muse...")
            await file_input.set_input_files(shot01_img)
            await muse_page.wait_for_timeout(3000)
            print("Image uploaded!")
            
        # 2. 填写输入框
        chat_box = muse_page.locator("textarea[placeholder='消息']").first
        if await chat_box.count() > 0:
            print("Typing prompt into chat box...")
            await chat_box.fill(prompt)
            await muse_page.wait_for_timeout(1000)
            
            # 3. 按 Enter 发送
            print("Submitting prompt (Press Enter)...")
            await chat_box.press("Enter")
            await muse_page.wait_for_timeout(5000)
            
            # 4. 截取提交后当前状态
            shot_path = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/flow_debug/muse_submitted.png")
            try:
                await muse_page.screenshot(path=shot_path, timeout=5000)
                print(f"Screenshot saved: {shot_path}")
            except Exception as se:
                print(f"Screenshot failed: {se}")
                
            # 5. 打印最新消息
            messages = await muse_page.locator("div.message, div[role='article'], p").all()
            print(f"Total messages now: {len(messages)}")
            if messages:
                print("Latest message:", (await messages[-1].inner_text()).strip()[:150])
        else:
            print("Chat box not found on Muse!")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_muse())
