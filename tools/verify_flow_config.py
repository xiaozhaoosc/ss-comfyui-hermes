import asyncio
import os
import sys
import re
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def configure_flow(model_target="Veo 3.1 - Lite", count="x1", duration="6s"):
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        flow_page = None
        for page in context.pages:
            if "flow.google.com/project" in page.url:
                flow_page = page
                break
                
        if not flow_page:
            print("[!] Flow project page not found!")
            await browser.close()
            return

        print(f"[+] Connected to Flow: {flow_page.url}")
        
        # 1. 连续按 Escape 关闭已有的下拉框或遮罩
        await flow_page.keyboard.press("Escape")
        await flow_page.wait_for_timeout(300)
        await flow_page.keyboard.press("Escape")
        await flow_page.wait_for_timeout(500)

        # 2. 定位并打开 Settings Trigger
        trigger = flow_page.locator("button[aria-label='Settings trigger']").first
        await trigger.click(force=True)
        await flow_page.wait_for_timeout(1000)

        # 3. 点击 [Video] 标签页
        video_tab = flow_page.locator(".cdk-overlay-pane button:has-text('Video'), div[role='dialog'] button:has-text('Video'), button:has-text('Video')").first
        await video_tab.click(force=True)
        await flow_page.wait_for_timeout(800)

        # 4. 选择数量 (x1)
        cnt_btn = flow_page.locator(f".cdk-overlay-pane button:has-text('{count}'), div[role='dialog'] button:has-text('{count}')").first
        if await cnt_btn.count() > 0:
            await cnt_btn.click(force=True)
            await flow_page.wait_for_timeout(500)
            print(f"[+] Selected count: {count}")

        # 5. 选择时长 (如 4s / 6s / 8s)
        dur_btn = flow_page.locator(f".cdk-overlay-pane button:has-text('{duration}'), div[role='dialog'] button:has-text('{duration}')").first
        if await dur_btn.count() > 0:
            await dur_btn.click(force=True)
            await flow_page.wait_for_timeout(500)
            print(f"[+] Selected duration: {duration}")

        # 6. 选择模型 (如果当前选中的不是目标模型)
        # 点击模型下拉框 (位于 settings 弹层内的下拉菜单触发器)
        model_dropdown = flow_page.locator(".cdk-overlay-pane button:has-text('Flash'), .cdk-overlay-pane button:has-text('Veo 3.1'), .cdk-overlay-pane div:has-text('arrow_drop_down')").first
        if await model_dropdown.count() > 0:
            curr_model_text = (await model_dropdown.inner_text()).strip()
            print(f"[+] Current model dropdown text: '{curr_model_text}'")
            if model_target not in curr_model_text:
                await model_dropdown.click(force=True)
                await flow_page.wait_for_timeout(800)
                target_opt = flow_page.locator(f"[role='menu'] button:has-text('{model_target}'), button:has-text('{model_target}')").first
                if await target_opt.count() > 0:
                    await target_opt.click(force=True)
                    await flow_page.wait_for_timeout(800)
                    print(f"[+] Switched model to: {model_target}")

        # 7. 读取最终计算的 Credits 消耗
        cost_elem = flow_page.locator("div.cdk-overlay-pane").get_by_text(re.compile(r"Generating will use \d+ credits")).first
        cost_text = await cost_elem.inner_text()
        print(f"[+] Final Credit Cost detected: '{cost_text}'")
        match = re.search(r"(\d+)\s*credits", cost_text)
        cost_val = int(match.group(1)) if match else 0
        print(f"[+] Parsed single generation cost: {cost_val} credits")

        # 8. 截屏留存
        today = "2026-10-10"
        debug_path = os.path.abspath(f"output/{today}/flow_debug/verify_flow_config.png")
        await flow_page.screenshot(path=debug_path)
        print(f"[+] Screenshot saved: {debug_path}")

        # 9. 按 Escape 收起设置面板
        await flow_page.keyboard.press("Escape")
        await browser.close()
        return cost_val

if __name__ == "__main__":
    asyncio.run(configure_flow())
