import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def inspect():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        
        # 1. 检查 Flow
        flow_page = None
        for page in context.pages:
            if "flow.google.com/project" in page.url:
                flow_page = page
                break
                
        if flow_page:
            print("\n=== Google Flow Analysis ===")
            print(f"URL: {flow_page.url}")
            # 查找 file input
            file_inputs = await flow_page.locator("input[type='file']").all()
            print(f"File inputs in Flow: {len(file_inputs)}")
            for i, fi in enumerate(file_inputs):
                accept = await fi.get_attribute("accept")
                print(f"  File input [{i}]: accept='{accept}'")
                
            # 查找主 prompt textarea
            prompt_ta = flow_page.locator("textarea").first
            if await prompt_ta.count() > 0:
                print("Flow prompt textarea found!")
        else:
            print("Flow page not open!")

        # 2. 检查 Muse
        muse_page = None
        for page in context.pages:
            if "muse.ai" in page.url:
                muse_page = page
                break
                
        if muse_page:
            print("\n=== Muse.ai Analysis ===")
            print(f"URL: {muse_page.url}")
            file_inputs_muse = await muse_page.locator("input[type='file']").all()
            print(f"File inputs in Muse: {len(file_inputs_muse)}")
            for i, fi in enumerate(file_inputs_muse):
                accept = await fi.get_attribute("accept")
                print(f"  File input [{i}]: accept='{accept}'")
                
            # 查找输入框附近的按钮 (如上传图片、模式切换)
            chat_box = muse_page.locator("textarea[placeholder='消息']").first
            if await chat_box.count() > 0:
                parent = chat_box.locator("xpath=../..")
                btns = await parent.locator("button, svg").all()
                print(f"Buttons/icons around Muse chatbox: {len(btns)}")
                for i, b in enumerate(btns[:10]):
                    aria = await b.get_attribute("aria-label")
                    txt = (await b.inner_text()).strip()
                    print(f"  Muse bar item [{i}]: text='{txt}', aria='{aria}'")
                    
            # 查找最近一条聊天记录中的视频或图片
            videos = await muse_page.locator("video").all()
            print(f"Existing videos on Muse page: {len(videos)}")
        else:
            print("Muse page not open!")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect())
