import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def test_ingredients():
    img_path = r"d:\ai_projects\ComfyUI\output\2026-10-09\yangjiajiang_ep03\comparison\shot01_input.jpg"
    print(f"Target image exists: {os.path.exists(img_path)}")
    
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

        print("Testing 'Add ingredients to the prompt box'...")
        ing_btn = flow_page.locator("button[aria-label='Add ingredients to the prompt box']").first
        if await ing_btn.count() > 0:
            await ing_btn.click()
            await flow_page.wait_for_timeout(1000)
            
            # 探测弹出的面板
            overlays = await flow_page.locator(".cdk-overlay-pane, [role='menu'], .mat-mdc-menu-panel").all()
            print(f"Overlay panels: {len(overlays)}")
            for i, o in enumerate(overlays):
                txt = (await o.inner_text()).strip().replace('\n', ' | ')
                print(f"  Pane [{i}]: {txt}")
                
            # 检查是否有 input[type='file'] 出现
            file_inputs = await flow_page.locator("input[type='file']").all()
            print(f"File inputs now available: {len(file_inputs)}")
            for i, fi in enumerate(file_inputs):
                print(f"  Input [{i}]: id={await fi.get_attribute('id')}, name={await fi.get_attribute('name')}")
        else:
            print("Button not found!")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_ingredients())
