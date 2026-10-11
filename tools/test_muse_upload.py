import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def check_muse_upload():
    test_img = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/flow_pilot/shot01.jpg")
    print(f"Test image path: {test_img} (exists: {os.path.exists(test_img)})")

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

        file_input = muse_page.locator("input[type='file']").first
        if await file_input.count() > 0:
            print("Found file input on Muse, uploading test image...")
            await file_input.set_input_files(test_img)
            await muse_page.wait_for_timeout(3000)
            
            # 检查是否有缩略图或预览出现
            imgs = await muse_page.locator("img").all()
            print(f"Total img tags on Muse: {len(imgs)}")
            
            # 检查输入框内状态
            ta = muse_page.locator("textarea[placeholder='消息']").first
            val = await ta.input_value()
            print(f"Textarea current value: '{val}'")
        else:
            print("No file input found on Muse.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(check_muse_upload())
