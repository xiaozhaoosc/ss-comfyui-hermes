import asyncio
import os
import sys
import base64
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def run_shot02_muse():
    shot02_img = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/comparison/shot02.jpg")
    save_path = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/comparison/muse_shot02.mp4")
    print(f"Shot 02 image: {shot02_img} (exists: {os.path.exists(shot02_img)})")
    
    prompt = "请基于上传的这张首帧原画，生成一段4秒竖屏水墨国风视频：镜头缓缓推向汴京殿堂，宰相寇准伏地力谏，宋太宗身披黄袍垂手静听。上美影传统水墨剪纸动画风格。"

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        
        muse_page = None
        for page in context.pages:
            if "muse.ai" in page.url:
                muse_page = page
                break
                
        if not muse_page:
            print("Muse page not found!")
            await browser.close()
            return
            
        print("Connected to Muse.ai...")
        # 1. 记录当前已有 video 标签数量
        old_videos = await muse_page.locator("video").all()
        old_count = len(old_videos)
        print(f"Current video tags count: {old_count}")

        # 2. 上传 shot02.jpg
        file_input = muse_page.locator("input[type='file']").first
        print("Uploading shot02.jpg to Muse...")
        await file_input.set_input_files(shot02_img)
        await muse_page.wait_for_timeout(3000)

        # 3. 输入提示词并按 Enter 发送
        chat_box = muse_page.locator("textarea[placeholder='消息']").first
        print("Typing prompt into Muse chat box...")
        await chat_box.fill(prompt)
        await muse_page.wait_for_timeout(1000)
        
        print("Submitting prompt (Enter)...")
        await chat_box.press("Enter")
        await muse_page.wait_for_timeout(5000)

        # 4. 截图记录提交状态
        shot_path = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/flow_debug/muse_shot02_submitted.png")
        try:
            await muse_page.screenshot(path=shot_path, timeout=5000)
            print(f"Submission screenshot saved: {shot_path}")
        except Exception as se:
            print(f"Screenshot skip: {se}")

        # 5. 轮询等待新视频生成 (最长等待 120s)
        print("Waiting for Muse to generate new video...")
        new_video_found = False
        for tick in range(24): # 24 * 5s = 120s
            await muse_page.wait_for_timeout(5000)
            curr_videos = await muse_page.locator("video").all()
            if len(curr_videos) > old_count:
                print(f"[√] New video detected on Muse at tick {tick+1}!")
                new_video_found = True
                target_video = curr_videos[0] # 最新视频通常在最前或最后
                src = await target_video.get_attribute("src")
                print(f"New video src: {src}")
                
                # 从页面上下文下载 blob
                b64_data = await muse_page.evaluate("""async (videoSrc) => {
                    const resp = await fetch(videoSrc);
                    const blob = await resp.blob();
                    return new Promise((resolve, reject) => {
                        const reader = new FileReader();
                        reader.onloadend = () => resolve(reader.result.split(',')[1]);
                        reader.onerror = reject;
                        reader.readAsDataURL(blob);
                    });
                }""", src)
                
                video_bytes = base64.b64decode(b64_data)
                with open(save_path, "wb") as f:
                    f.write(video_bytes)
                print(f"[√] muse_shot02.mp4 successfully saved: {save_path} ({len(video_bytes)} bytes)")
                break
            else:
                print(f"  ... Still generating ({tick*5}s elapsed)")

        if not new_video_found:
            print("[!] Timeout waiting for new video, check status screenshot.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_shot02_muse())
