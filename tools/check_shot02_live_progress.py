import asyncio
import os
import time
import base64
from playwright.async_api import async_playwright

async def check_progress():
    save_path = os.path.abspath('output/2026-10-10/route_a/videos/shot_02_veo_8s.mp4')
    debug_dir = os.path.abspath('output/2026-10-10/route_a/debug')
    
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        page = [pg for pg in b.contexts[0].pages if 'flow.google.com/project' in pg.url][0]

        # 截图保存当前工作台
        snap_path = os.path.join(debug_dir, "shot02_render_progress.png")
        await page.screenshot(path=snap_path)
        print(f"Canvas snap saved to: {snap_path}")

        # 检查是否有警告/错误
        toasts = await page.locator(".mat-mdc-snack-bar-container, [role='alert']").all()
        for t in toasts:
            print("Toast alert:", await t.inner_text())

        # 检查所有 video 元素
        videos = await page.locator("video").all()
        print(f"Total video elements: {len(videos)}")
        for idx, v in enumerate(videos):
            src = await v.get_attribute("src")
            print(f"  Video [{idx}]: {src[:70] if src else 'No src'}")

        # 如果检测到了新的第二个视频，或者最新的视频不属于旧的 shot 01 (aca8e9e4)
        if len(videos) >= 2 or (len(videos) == 1 and "aca8e9e4" not in (await videos[0].get_attribute("src") or "")):
            # 找到最新的不是旧 shot 01 的视频
            target_v = None
            for v in videos:
                src = await v.get_attribute("src")
                if src and "aca8e9e4" not in src:
                    target_v = v
                    break
            if not target_v and len(videos) >= 2:
                target_v = videos[0]

            if target_v:
                v_src = await target_v.get_attribute("src")
                print("Downloading new video from:", v_src[:70])
                b64 = await page.evaluate("""async (url) => {
                    const res = await fetch(url);
                    const blob = await res.blob();
                    return new Promise((r) => {
                        const rd = new FileReader();
                        rd.onloadend = () => r(rd.result.split(',')[1]);
                        rd.readAsDataURL(blob);
                    });
                }""", v_src)
                with open(save_path, "wb") as f:
                    f.write(base64.b64decode(b64))
                print(f"[✓] Successfully downloaded Shot 02 video to: {save_path} ({os.path.getsize(save_path)} bytes)")

        await b.close()

if __name__ == '__main__':
    asyncio.run(check_progress())
