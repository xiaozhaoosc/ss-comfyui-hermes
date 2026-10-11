import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def inspect_flow():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        
        flow_page = None
        for page in context.pages:
            if "flow.google.com" in page.url:
                flow_page = page
                break
                
        if not flow_page:
            print("Flow page not found!")
            await browser.close()
            return
            
        print("Inspecting buttons/elements on Flow...")
        # 获取所有包含 'New project' 或相关文本的元素
        elements = await flow_page.locator("text='New project'").all()
        print(f"Found {len(elements)} elements with 'New project'")
        for i, el in enumerate(elements):
            tag = await el.evaluate("e => e.tagName")
            box = await el.bounding_box()
            parent_tag = await el.evaluate("e => e.parentElement ? e.parentElement.tagName : 'None'")
            print(f"  El [{i}]: Tag={tag}, Parent={parent_tag}, BoundingBox={box}")

        # 如果找到，点击该位置
        if elements:
            print("Clicking the first visible New project element...")
            await elements[0].click(force=True)
            await flow_page.wait_for_timeout(4000)
            print(f"URL after click: {flow_page.url}")
            shot_path = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/flow_debug/flow_project_canvas.png")
            await flow_page.screenshot(path=shot_path)
            print(f"Screenshot: {shot_path}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect_flow())
