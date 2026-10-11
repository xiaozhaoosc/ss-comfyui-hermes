import asyncio
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def main():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        context = b.contexts[0]
        muse_page = None
        for page in context.pages:
            if "muse.ai" in page.url:
                muse_page = page
                break
        if not muse_page:
            print("Muse page not found")
            await b.close()
            return
            
        print("Muse page URL:", muse_page.url)
        btns = await muse_page.evaluate("""() => {
            return Array.from(document.querySelectorAll('button, [role="button"], span, div'))
                .map(el => el.innerText ? el.innerText.trim() : '')
                .filter(t => t.length > 0 && t.length < 25 && (t.includes('9:16') || t.includes('16:9') || t.includes('1:1') || t.includes('比例') || t.includes('竖屏') || t.includes('设置') || t.includes('画质') || t.includes('720') || t.includes('1080')));
        }""")
        print("Relevant UI elements:", set(btns))
        
        # 截一张底部操作栏截图
        await muse_page.screenshot(path="output/2026-10-09/yangjiajiang_ep03/flow_debug/muse_chat_footer.png")
        print("Screenshot saved to muse_chat_footer.png")
        await b.close()

if __name__ == "__main__":
    asyncio.run(main())
