import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def upload_to_flow():
    test_img = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/comparison/shot01_input.jpg")
    print(f"Target upload image: {test_img} (exists: {os.path.exists(test_img)})")
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        
        flow_page = None
        for page in context.pages:
            if "flow.google.com/project" in page.url:
                flow_page = page
                break
                
        if not flow_page:
            print("Flow page not found!")
            await browser.close()
            return

        print("Clicking Add media menu...")
        media_btn = flow_page.locator("button[aria-label='Add media menu']").first
        await media_btn.click()
        await flow_page.wait_for_timeout(1000)

        upload_opt = flow_page.locator("text='Upload', button:has-text('Upload')").first
        print(f"Upload option count: {await upload_opt.count()}")

        try:
            async with flow_page.expect_file_chooser(timeout=5000) as fc_info:
                await upload_opt.click()
            file_chooser = await fc_info.value
            print("File chooser intercepted! Setting files...")
            await file_chooser.set_files(test_img)
            print("File uploaded via file chooser!")
            await flow_page.wait_for_timeout(4000)
        except Exception as e:
            print(f"File chooser error: {e}")
            # 检查 DOM 是否新增了 input[type='file']
            file_inputs = await flow_page.locator("input[type='file']").all()
            print(f"Current file inputs count: {len(file_inputs)}")
            if file_inputs:
                await file_inputs[0].set_input_files(test_img)
                print("Uploaded via newly discovered input[type='file']!")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(upload_to_flow())
