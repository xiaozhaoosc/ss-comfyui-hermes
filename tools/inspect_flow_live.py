import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def inspect_live():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        flow_page = None
        for page in context.pages:
            if "flow.google.com/project" in page.url:
                flow_page = page
                break
                
        if not flow_page:
            print("Flow project page not found!")
            await browser.close()
            return

        print(f"Connected to Flow page: {flow_page.url}")
        
        # 截取当前界面
        today = "2026-10-10"
        debug_dir = os.path.abspath(f"output/{today}/flow_debug")
        os.makedirs(debug_dir, exist_ok=True)
        await flow_page.screenshot(path=os.path.join(debug_dir, "live_flow_init.png"))
        print(f"Saved init screenshot to: {debug_dir}")

        # 查找输入框区域的所有按钮与标签
        buttons = await flow_page.locator("button, [role='button']").all()
        print(f"Total buttons: {len(buttons)}")
        model_btn = None
        for idx, btn in enumerate(buttons):
            txt = (await btn.inner_text()).strip().replace('\n', ' ')
            aria = await btn.get_attribute("aria-label")
            if any(k in (txt + str(aria)).lower() for k in ["banana", "veo", "nano", "model", "imagen"]):
                print(f"Candidate Model Btn [{idx}]: text='{txt}', aria='{aria}'")
                model_btn = btn

        if model_btn:
            print("Clicking candidate model button...")
            await model_btn.click()
            await flow_page.wait_for_timeout(1500)
            await flow_page.screenshot(path=os.path.join(debug_dir, "live_flow_model_menu.png"))
            
            # 查找弹出的菜单项
            options = await flow_page.locator("[role='menuitem'], [role='option'], mat-option, .mat-mdc-menu-item, div[role='menu'] button, div[role='listbox'] *").all()
            print(f"Found {len(options)} options in menu:")
            for j, opt in enumerate(options):
                opt_txt = (await opt.inner_text()).strip().replace('\n', ' | ')
                if opt_txt:
                    print(f"  Option [{j}]: {opt_txt}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect_live())
