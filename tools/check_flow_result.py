import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def check_flow_result():
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

        print("Checking Flow generation cards...")
        # 截屏当前完成状态
        shot_path = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/flow_debug/flow_generation_done.png")
        await flow_page.screenshot(path=shot_path, timeout=8000)
        print(f"Flow canvas screenshot saved: {shot_path}")
        
        # 查找生成的 img 元素
        imgs = await flow_page.locator("img").all()
        print(f"Total img elements on Flow canvas: {len(imgs)}")
        
        save_dir = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/comparison")
        saved_count = 0
        for i, img in enumerate(imgs):
            src = await img.get_attribute("src")
            if src and ("googleusercontent.com" in src or "blob:" in src or "data:" in src):
                print(f"  Img [{i}]: src='{src[:80]}...'")
                # 下载图片
                try:
                    img_save_path = os.path.join(save_dir, f"flow_generated_{saved_count+1}.png")
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
                    print(f"    -> Saved: {img_save_path}")
                    saved_count += 1
                except Exception as e:
                    print(f"    -> Download error: {e}")
                    
        await browser.close()

if __name__ == "__main__":
    asyncio.run(check_flow_result())
