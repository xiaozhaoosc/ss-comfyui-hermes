import asyncio
import os
import sys
import datetime
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def run_flow():
    prompt = "Traditional Chinese ink wash cut-paper animation style. Vertical 9:16 shot, camera tilts up slowly. Grand Song imperial carriage procession marching north under bleak winter skies, giant ochre-yellow dragon flag fluttering violently in freezing howling wind. Crisp black ink line art, muted cel shading, cinematic historical epic."
    
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
        
        # 1. 确保弹层关闭
        await flow_page.keyboard.press("Escape")
        await flow_page.wait_for_timeout(500)
        
        # 2. 定位主 prompt 输入框
        ta = flow_page.locator("textarea").first
        if await ta.count() > 0:
            print("Filling prompt into Flow prompt box...")
            await ta.fill(prompt)
            await flow_page.wait_for_timeout(1000)
            
            # 3. 点击生成按钮 (arrow_forward)
            gen_btn = flow_page.locator("button[aria-label='Start generation'], button:has-text('arrow_forward')").first
            if await gen_btn.count() > 0:
                print("Clicking 'Start generation' (arrow_forward)...")
                await gen_btn.click(force=True)
                await flow_page.wait_for_timeout(4000)
                
                # 4. 截屏记录
                shot_path = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/flow_debug/flow_submitted.png")
                try:
                    await flow_page.screenshot(path=shot_path, timeout=5000)
                    print(f"Flow screenshot saved: {shot_path}")
                except Exception as se:
                    print(f"Flow screenshot timeout/skip: {se}")
            else:
                print("Generation button not found!")
        else:
            print("Textarea not found on Flow!")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_flow())
