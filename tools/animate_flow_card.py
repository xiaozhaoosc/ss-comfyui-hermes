import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def animate_flow():
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

        print("Inspecting card click / hover actions on Flow...")
        # 找到第二张生成的图片卡片
        imgs = await flow_page.locator("img[src*='flow-content.google']").all()
        print(f"Flow generated media imgs: {len(imgs)}")
        
        if imgs:
            target_img = imgs[0]
            await target_img.scroll_into_view_if_needed()
            box = await target_img.bounding_box()
            print(f"Target card box: {box}")
            
            # 点击卡片
            await target_img.click()
            await flow_page.wait_for_timeout(1000)
            
            # 探测出现的工具栏或浮层按钮
            action_btns = await flow_page.locator("button, [role='button']").all()
            print(f"Buttons currently active: {len(action_btns)}")
            for i, b in enumerate(action_btns):
                txt = (await b.inner_text()).strip().replace('\n', ' ')
                aria = await b.get_attribute("aria-label")
                if txt or aria:
                    if any(k in (txt + str(aria)).lower() for k in ['animate', 'video', 'motion', 'create', 'generate', 'more', 'play']):
                        print(f"  Action Btn [{i}]: text='{txt}', aria='{aria}'")

            shot_path = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/flow_debug/flow_card_selected.png")
            await flow_page.screenshot(path=shot_path, timeout=5000)
            print(f"Screenshot saved: {shot_path}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(animate_flow())
