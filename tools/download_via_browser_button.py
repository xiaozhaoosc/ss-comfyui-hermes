import asyncio
import os
import sys
import time
import shutil
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def main():
    target_path = os.path.abspath('output/2026-10-10/route_a/videos/shot_02_veo_8s.mp4')
    user_downloads = os.path.expanduser(r'~\Downloads')
    
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        page = [pg for pg in b.contexts[0].pages if 'flow.google.com' in pg.url][0]
        print(f"Connected to page: {page.url}")

        # 查看 720p 选项
        btn_720p = page.locator("[role='menuitem']:has-text('720p')").first
        if await btn_720p.count() == 0:
            print("Menu might have closed, re-opening download menu...")
            dl_btn = page.locator("button[aria-label='Download media'], button:has-text('download')").first
            await dl_btn.click(force=True)
            await page.wait_for_timeout(1000)
            btn_720p = page.locator("[role='menuitem']:has-text('720p')").first

        print("Clicking '720p Original size'...")
        before_files = set(os.listdir(user_downloads))
        
        # 尝试监听 download 事件或者等待下载到 Downloads 目录
        try:
            async with page.expect_download(timeout=10000) as download_info:
                await btn_720p.click()
            download = await download_info.value
            await download.save_as(target_path)
            print(f"[✓] Download event intercepted and saved directly to: {target_path} ({os.path.getsize(target_path)} bytes)")
            await b.close()
            return
        except Exception as e:
            print(f"expect_download did not fire ({e}), checking Downloads folder...")

        # 检查本地 Downloads 目录是否生成了新文件 (或 .crdownload)
        for _ in range(30): # 最多等待 30 秒
            await asyncio.sleep(1)
            after_files = set(os.listdir(user_downloads))
            new_mp4s = [f for f in (after_files - before_files) if f.endswith('.mp4')]
            crdownloads = [f for f in after_files if f.endswith('.crdownload')]
            
            if crdownloads:
                print(f"Downloading in progress: {crdownloads}")
                continue
                
            if new_mp4s:
                latest_mp4 = os.path.join(user_downloads, new_mp4s[0])
                print(f"[✓] Detected completed download in user folder: {latest_mp4}")
                shutil.copy2(latest_mp4, target_path)
                print(f"[✓] Successfully copied to: {target_path} ({os.path.getsize(target_path)} bytes)")
                break
        else:
            print("[!] Download timed out or file not found in Downloads directory.")

        await b.close()

if __name__ == '__main__':
    asyncio.run(main())
