import asyncio
import os
import base64
import sys
import time
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def main():
    target_path = os.path.abspath('output/2026-10-10/route_a/videos/shot_02_veo_8s.mp4')
    debug_dir = os.path.abspath('output/2026-10-10/route_a/debug')
    user_downloads = os.path.expanduser(r'~\Downloads')
    
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        page = [pg for pg in b.contexts[0].pages if 'flow.google.com' in pg.url][0]
        print(f"Connected to page: {page.url}")

        # 1. 尝试直接点击 'Download media'
        dl_btn = page.locator("button[aria-label='Download media'], button:has-text('download')").first
        if await dl_btn.count() > 0:
            print("Found 'Download media' button. Clicking...")
            # 记录点击前 Downloads 目录里的文件
            before_files = set(os.listdir(user_downloads))
            
            # 点击下载按钮
            await dl_btn.click()
            await page.wait_for_timeout(4000)
            
            # 检查是否有下载对话框或菜单弹出
            menu_items = await page.locator("[role='menuitem'], [role='option'], button:has-text('MP4'), button:has-text('Original')").all()
            if menu_items:
                print(f"Found {len(menu_items)} popup options. Clicking the first one...")
                await menu_items[0].click()
                await page.wait_for_timeout(4000)

            # 检查 Downloads 目录是否有新增文件
            after_files = set(os.listdir(user_downloads))
            new_files = [f for f in (after_files - before_files) if f.endswith('.mp4')]
            if new_files:
                new_f_path = os.path.join(user_downloads, new_files[0])
                print(f"[✓] Found new file downloaded in Downloads: {new_f_path}")
                # 移动/复制到 target_path
                import shutil
                shutil.copy2(new_f_path, target_path)
                print(f"[✓] Successfully copied to {target_path} ({os.path.getsize(target_path)} bytes)")
                await b.close()
                return

        # 2. 如果 Downloads 没新增，点击 'Done' 返回画布主页
        done_btn = page.locator("button:has-text('Done'), button[aria-label*='Done']").first
        if await done_btn.count() > 0:
            print("Clicking 'Done' button to return to canvas...")
            await done_btn.click()
            await page.wait_for_timeout(3000)

        # 3. 在主画布上查找所有 video 标签
        print(f"Now on page: {page.url}")
        await page.screenshot(path=os.path.join(debug_dir, "canvas_after_done.png"))
        
        videos = await page.locator("video").all()
        print(f"Canvas total videos: {len(videos)}")
        target_src = None
        for idx, v in enumerate(videos):
            src = await v.get_attribute("src")
            print(f"  Canvas Video #{idx}: {src[:80] if src else 'None'}")
            if src and "aca8e9e4" not in src:
                target_src = src

        # 如果没有直接的 video src，或者是 blob/asb，检查最新的卡片
        if not target_src and videos:
            target_src = await videos[-1].get_attribute("src")

        if target_src:
            print(f"Downloading from canvas video src: {target_src[:80]}...")
            b64 = await page.evaluate("""async (url) => {
                const res = await fetch(url);
                const blob = await res.blob();
                return new Promise((r) => {
                    const rd = new FileReader();
                    rd.onloadend = () => r(rd.result.split(',')[1]);
                    rd.readAsDataURL(blob);
                });
            }""", target_src)

            with open(target_path, "wb") as f:
                f.write(base64.b64decode(b64))
            print(f"[✓] Successfully saved to {target_path} ({os.path.getsize(target_path)} bytes)")
        else:
            print("[!] Could not locate target video src on canvas.")

        await b.close()

if __name__ == '__main__':
    asyncio.run(main())
