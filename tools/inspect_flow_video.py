import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def inspect():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        page = [pg for pg in b.contexts[0].pages if 'flow.google.com' in pg.url][0]
        print("Page URL:", page.url)

        # Inspect all video, canvas, iframe, shadow dom
        res = await page.evaluate("""() => {
            function findVideos(root) {
                let vids = Array.from(root.querySelectorAll('video')).map(v => v.src || v.currentSrc);
                let iframes = Array.from(root.querySelectorAll('iframe'));
                let allElems = Array.from(root.querySelectorAll('*'));
                for (let el of allElems) {
                    if (el.shadowRoot) {
                        vids = vids.concat(findVideos(el.shadowRoot));
                    }
                }
                return vids;
            }
            
            // Check top action buttons
            let buttons = Array.from(document.querySelectorAll('button')).map(b => ({
                text: b.innerText ? b.innerText.trim() : '',
                aria: b.getAttribute('aria-label') || '',
                title: b.getAttribute('title') || '',
                className: b.className
            }));
            
            return {
                videos: findVideos(document),
                buttons: buttons.filter(b => b.text || b.aria || b.title)
            };
        }""")

        print("Found Videos in DOM/ShadowDOM:", res['videos'])
        print("\nFound Buttons:")
        for b in res['buttons']:
            if any(k in (b['text'] + b['aria'] + b['title']).lower() for k in ['down', 'done', 'save', 'export', 'video', 'play']):
                print(f"  - text='{b['text']}', aria='{b['aria']}', title='{b['title']}'")

        await b.close()

if __name__ == '__main__':
    asyncio.run(inspect())
