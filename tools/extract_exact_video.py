import asyncio
import os
import base64
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def main():
    save_path = os.path.abspath('output/2026-10-10/route_a/videos/shot_02_veo_8s.mp4')
    debug_dir = os.path.abspath('output/2026-10-10/route_a/debug')
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    os.makedirs(debug_dir, exist_ok=True)

    async with async_playwright() as p:
        try:
            b = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        except Exception as e:
            print(f"[ERROR] Could not connect to CDP: {e}")
            return

        pages = b.contexts[0].pages
        flow_page = None
        for page in pages:
            if 'flow.google.com' in page.url:
                flow_page = page
                break

        if not flow_page:
            print("[ERROR] Flow page not found among open pages:")
            for idx, page in enumerate(pages):
                print(f"  Page {idx}: {page.url}")
            await b.close()
            return

        print(f"[INFO] Found Flow page: {flow_page.url}")
        await flow_page.screenshot(path=os.path.join(debug_dir, "current_editor_state.png"))
        print("[INFO] Saved current_editor_state.png")

        # 检查页面内的所有 video
        videos = await flow_page.locator("video").all()
        print(f"[INFO] Found {len(videos)} video tags on page")
        target_src = None
        for idx, v in enumerate(videos):
            src = await v.get_attribute("src")
            print(f"  Video #{idx}: src={src[:100] if src else 'None'}")
            if src and "blob:" not in src and "aca8e9e4" not in src:
                target_src = src
            elif src and not target_src:
                target_src = src

        # 如果没有直接的 src，检查当前页面是否有 download 按钮
        dl_btn = flow_page.locator("button[aria-label*='Download'], button:has-text('Download')").first
        has_dl = await dl_btn.count() > 0
        print(f"[INFO] Download button present: {has_dl}")

        if target_src:
            print(f"[INFO] Attempting fetch download from target_src: {target_src[:80]}...")
            try:
                b64 = await flow_page.evaluate("""async (url) => {
                    const res = await fetch(url);
                    const blob = await res.blob();
                    return new Promise((r) => {
                        const rd = new FileReader();
                        rd.onloadend = () => r(rd.result.split(',')[1]);
                        rd.readAsDataURL(blob);
                    });
                }""", target_src)

                with open(save_path, "wb") as f:
                    f.write(base64.b64decode(b64))
                file_size = os.path.getsize(save_path)
                print(f"[SUCCESS] Downloaded shot_02_veo_8s.mp4 ({file_size} bytes)")
            except Exception as e:
                print(f"[WARN] Fetch direct failed: {e}, attempting download event...")
                has_dl = True

        if (not os.path.exists(save_path) or os.path.getsize(save_path) == 0) and has_dl:
            print("[INFO] Triggering download via Download button...")
            async with flow_page.expect_download(timeout=15000) as download_info:
                await dl_btn.click()
            download = await download_info.value
            await download.save_as(save_path)
            print(f"[SUCCESS] Download event saved to: {save_path} ({os.path.getsize(save_path)} bytes)")

        await b.close()

if __name__ == '__main__':
    asyncio.run(main())
