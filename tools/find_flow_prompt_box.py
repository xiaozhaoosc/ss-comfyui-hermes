import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def find_flow_input():
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

        print("Inspecting prompt bar on Flow...")
        # 查找所有 contenteditable 或 input 或 textbox
        textboxes = await flow_page.locator("[contenteditable='true'], [role='textbox'], .prompt-input, .input-container, mat-form-field").all()
        print(f"Found {len(textboxes)} textboxes/containers:")
        for i, tb in enumerate(textboxes):
            tag = await tb.evaluate("e => e.tagName")
            cls = await tb.get_attribute("class")
            print(f"  [{i}]: Tag={tag}, Class='{cls}'")

        # 尝试通过点击 Btn [8] 和 Btn [10] 之间的中间区域来聚焦
        btn8 = flow_page.locator("button[aria-label='Add ingredients to the prompt box']").first
        btn10 = flow_page.locator("button[aria-label='Settings trigger']").first
        if await btn8.count() > 0 and await btn10.count() > 0:
            box8 = await btn8.bounding_box()
            box10 = await btn10.bounding_box()
            print(f"Btn8: {box8}")
            print(f"Btn10: {box10}")
            if box8 and box10:
                mid_x = (box8['x'] + box10['x']) / 2
                mid_y = (box8['y'] + box10['y']) / 2
                print(f"Clicking middle of prompt bar at ({mid_x}, {mid_y})...")
                await flow_page.mouse.click(mid_x, mid_y)
                await flow_page.wait_for_timeout(500)
                
                # 检查当前 activeElement
                active_tag = await flow_page.evaluate("() => document.activeElement ? document.activeElement.tagName + ' (class: ' + document.activeElement.className + ')' : 'None'")
                print(f"Active Element after click: {active_tag}")
                
                # 输入提示词
                prompt_text = "Vertical shot, camera tilts up slowly. Grand Song imperial carriage procession marching north under bleak winter skies, giant ochre-yellow dragon flag fluttering violently in freezing howling wind. Traditional Chinese ink wash cut-paper animation style."
                await flow_page.keyboard.type(prompt_text, delay=20)
                print("Typed prompt via keyboard!")
                await flow_page.wait_for_timeout(1000)
                
                # 点击生成 (arrow_forward)
                gen_btn = flow_page.locator("button[aria-label='Start generation'], button:has-text('arrow_forward')").first
                print("Clicking Start generation...")
                await gen_btn.click(force=True)
                await flow_page.wait_for_timeout(4000)
                
                shot_path = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/flow_debug/flow_generation_triggered.png")
                try:
                    await flow_page.screenshot(path=shot_path, timeout=5000)
                    print(f"Screenshot saved: {shot_path}")
                except Exception as se:
                    print(f"Screenshot timeout/skipped: {se}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(find_flow_input())
