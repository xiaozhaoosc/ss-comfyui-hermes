import asyncio
import os
import sys
import base64
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def run_flow_shot02():
    prompt = "Traditional Chinese ink wash cut-paper animation style. Medium low angle shot in ancient imperial court hall at Kaifeng. An ancient prime minister in official crimson robes and a winged black court hat prostrating on the floor with folded hands, pleading earnestly before a solemn Chinese emperor in a golden dragon robe in golden dragon robe. Vintage Shanghai Animation Film Studio aesthetic, crisp black ink lines, muted cel shading, textured raw rice paper."
    save_dir = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/comparison")
    
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
            
        print("Connected to Google Flow...")
        await flow_page.keyboard.press("Escape")
        await flow_page.wait_for_timeout(500)

        # 记录已有 flow-content 图片数量
        old_imgs = await flow_page.locator("img[src*='flow-content.google']").all()
        old_count = len(old_imgs)
        print(f"Current Flow media images: {old_count}")

        # 定位并聚焦提示词输入框
        editor = flow_page.locator(".ProseMirror").first
        if await editor.count() > 0:
            print("Focusing ProseMirror prompt box (force=True)...")
            await editor.click(force=True)
            await flow_page.wait_for_timeout(500)
            # 全选清空
            await flow_page.keyboard.press("Control+A")
            await flow_page.keyboard.press("Backspace")
            # 填入提示词
            print("Typing prompt into Flow...")
            await flow_page.keyboard.type(prompt, delay=15)
            await flow_page.wait_for_timeout(1000)

            # 点击生成按钮
            gen_btn = flow_page.locator("button[aria-label='Start generation'], button:has-text('arrow_forward')").first
            print("Clicking Start generation (arrow_forward)...")
            await gen_btn.click(force=True)
            await flow_page.wait_for_timeout(5000)

            # 轮询等待生成完成
            print("Waiting for Flow to render Shot 02...")
            for tick in range(12): # 12 * 5s = 60s
                await flow_page.wait_for_timeout(5000)
                curr_imgs = await flow_page.locator("img[src*='flow-content.google']").all()
                if len(curr_imgs) > old_count:
                    print(f"[√] New Flow artwork detected at tick {tick+1}! (Total: {len(curr_imgs)})")
                    await flow_page.wait_for_timeout(3000)
                    
                    # 下载最新的两张卡片
                    new_cards = curr_imgs[0:2]
                    for idx, card in enumerate(new_cards, 1):
                        src = await card.get_attribute("src")
                        save_p = os.path.join(save_dir, f"flow_shot02_gen_{idx}.png")
                        print(f"Downloading Flow card {idx}: {src[:60]}...")
                        b64 = await flow_page.evaluate("""async (url) => {
                            const res = await fetch(url);
                            const blob = await res.blob();
                            return new Promise((r) => {
                                const rd = new FileReader();
                                rd.onloadend = () => r(rd.result.split(',')[1]);
                                rd.readAsDataURL(blob);
                            });
                        }""", src)
                        with open(save_p, "wb") as f:
                            f.write(base64.b64decode(b64))
                        print(f"[√] Saved: {save_p} ({os.path.getsize(save_p)} bytes)")
                    break
                else:
                    print(f"  ... Flow rendering ({tick*5}s)")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_flow_shot02())
