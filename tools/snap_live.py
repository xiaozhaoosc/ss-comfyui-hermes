import asyncio
import os
from playwright.async_api import async_playwright

async def snap():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        page = [pg for pg in b.contexts[0].pages if 'flow.google.com/project' in pg.url][0]
        out_dir = os.path.abspath('output/2026-10-10/route_a/debug')
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, 'inspect_flow_live.png')
        await page.screenshot(path=path)
        print('Live canvas snap saved to:', path)
        await b.close()

if __name__ == '__main__':
    asyncio.run(snap())
