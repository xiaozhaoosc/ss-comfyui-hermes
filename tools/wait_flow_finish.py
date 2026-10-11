import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def wait_flow_finish():
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

        print("Waiting 10s for Flow 99% -> 100% complete...")
        await flow_page.wait_for_timeout(10000)

        shot_path = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/flow_debug/flow_generation_100.png")
        await flow_page.screenshot(path=shot_path, timeout=8000)
        print(f"100% Screenshot saved: {shot_path}")

        # 查看画布上的图片元素
        imgs = await flow_page.locator("img").all()
        print(f"Total img tags: {len(imgs)}")
        
        save_dir = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/comparison")
        saved_count = 0
        for i, img in enumerate(imgs):
            src = await img.get_attribute("src")
            # 过滤头像
            if src and "ogw/AF2b" not in src:
                print(f"  Valid Img [{i}]: src='{src[:60]}...'")
                try:
                    img_save_path = os.path.join(save_dir, f"flow_shot01_gen_{saved_count+1}.png")
                    b64_data = await flow_page.evaluate("""async (src) => {
                        const resp = await fetch(src);
                        const blob = await resp.blob();
                        return new Promise((resolve) => {
                            const reader = new FileReader();
                            reader.onloadend = () => resolve(reader.result.split(',')[1]);
                            reader.readAsDataURL(blob);
                        });
                    }""", src)
                    import base64
                    with open(img_save_path, "wb") as f:
                        f.write(base64.b64decode(b64_data))
                    print(f"    -> Saved: {img_save_path} ({os.path.getsize(img_save_path)} bytes)")
                    saved_count += 1
                except Exception as e:
                    print(f"    -> Download error: {e}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(wait_flow_finish())
