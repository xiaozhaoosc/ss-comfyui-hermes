import asyncio
import os
import sys
import base64
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def check_and_download():
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
            
        print("Checking Flow canvas...")
        shot_path = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/flow_debug/flow_shot02_done.png")
        await flow_page.screenshot(path=shot_path, timeout=5000)
        print(f"Canvas screenshot saved: {shot_path}")

        imgs = await flow_page.locator("img[src*='flow-content.google']").all()
        print(f"Total flow-content media cards: {len(imgs)}")

        for idx, img in enumerate(imgs):
            src = await img.get_attribute("src")
            save_p = os.path.join(save_dir, f"flow_shot02_gen_{idx+1}.png")
            print(f"Downloading card [{idx}]: {src[:60]}...")
            try:
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
            except Exception as e:
                print(f"[!] Error downloading card {idx}: {e}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(check_and_download())
