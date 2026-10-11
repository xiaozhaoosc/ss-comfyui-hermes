#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""北宋杨家将 · 第 3 集《邠阳城救驾》Muse.ai 云端图生视频批量流水线

特性：
1. 继承 Playwright CDP 远程调试端口 9222，接管已登录的 Muse.ai 会话
2. 严格按 54 镜元数据逐镜上传首帧切片 (yang_ep03_shotXX.jpg) 并发送定制水墨国风 Prompt
3. 智能视频定位：通过比对新旧 blob src 集合，精准捕获最新生成的 720P 竖屏视频
4. 断点续跑与自动去重：已有产物 (>100KB) 自动秒级跳过
5. 产物规范归档：保存至 output/2026-10-09/yangjiajiang_ep03/muse_videos/
"""

import asyncio
import os
import sys
import base64
import time
import argparse
from playwright.async_api import async_playwright

ROOT = r"D:\ai_projects\ComfyUI"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.yangjiajiang_ep03_metadata import EP03_METADATA

DATE_STR = "2026-10-09"
OUTPUT_DIR = os.path.join(ROOT, "output", DATE_STR, "yangjiajiang_ep03", "muse_videos")
INPUT_DIR = os.path.join(ROOT, "input")
DEBUG_DIR = os.path.join(ROOT, "output", DATE_STR, "yangjiajiang_ep03", "flow_debug")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DEBUG_DIR, exist_ok=True)

sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def build_shot_prompt(item):
    return (
        f"9:16 vertical format (720x1280), Vertical shot. 请基于上传的这张首帧原画，生成一段4秒竖屏水墨国风视频："
        f"{item['camera']}，{item['visual']}。"
        f"传统上美影水墨剪纸动画风格，笔触苍劲，宣纸肌理，画面自然流畅无闪烁。"
    )


async def get_current_video_srcs(muse_page):
    try:
        videos = await muse_page.locator("video").all()
        srcs = set()
        for v in videos:
            src = await v.get_attribute("src")
            if src:
                srcs.add(src)
        return srcs
    except Exception as e:
        print(f"  [!] 获取已有 video 列表异常: {e}")
        return set()


async def process_single_shot(muse_page, item, retry=2):
    sid = item["id"]
    save_path = os.path.join(OUTPUT_DIR, f"muse_shot{sid:02d}.mp4")

    # 1. 断点续跑校验
    if os.path.exists(save_path) and os.path.getsize(save_path) > 100000:
        print(f"[-] Shot {sid:02d} 已存在 ({os.path.getsize(save_path)} bytes)，跳过")
        return True

    input_img = os.path.join(INPUT_DIR, f"yang_ep03_shot{sid:02d}.jpg")
    if not os.path.exists(input_img):
        print(f"[!] 警告: Shot {sid:02d} 首帧图片不存在: {input_img}")
        return False

    prompt = build_shot_prompt(item)
    print(f"\n==================================================")
    print(f"[*] 开始处理 Shot {sid:02d} ({item['sub'][:16]})")
    print(f"    首帧: {os.path.basename(input_img)}")
    print(f"    目标: {save_path}")
    print(f"==================================================")

    for attempt in range(1, retry + 1):
        try:
            # 记录当前已有 video src 集合
            old_srcs = await get_current_video_srcs(muse_page)
            print(f"  [+] 当前已有视频数量: {len(old_srcs)}")

            # 滚动到底部
            await muse_page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await muse_page.wait_for_timeout(500)

            # 上传首帧图片
            file_input = muse_page.locator("input[type='file']").first
            print(f"  [+] 上传首帧原画...")
            await file_input.set_input_files(input_img)
            await muse_page.wait_for_timeout(3000)

            # 输入提示词
            chat_box = muse_page.locator("textarea[placeholder='消息']").first
            await chat_box.fill(prompt)
            await muse_page.wait_for_timeout(1000)

            # 发送生成请求
            print(f"  [+] 发送提示词请求 (Enter)...")
            await chat_box.press("Enter")
            await muse_page.wait_for_timeout(6000)

            # 等待新视频生成 (最长等待 120 秒)
            print(f"  [+] 监控视频渲染进度...")
            new_src = None
            for tick in range(24): # 24 * 5s = 120s
                await muse_page.wait_for_timeout(5000)
                curr_srcs = await get_current_video_srcs(muse_page)
                diff = curr_srcs - old_srcs
                if diff:
                    new_src = list(diff)[0]
                    print(f"  [√] 成功检测到新视频渲染完成 (耗时约 {(tick+1)*5}s)!")
                    break
                else:
                    if (tick + 1) % 4 == 0:
                        print(f"      ... 正在渲染中 (已等待 {(tick+1)*5}s)")

            if not new_src:
                # 容错：如果 diff 没拿到，但 video 总数增加了，取最后一个 video 的 src
                all_vids = await muse_page.locator("video").all()
                if len(all_vids) > len(old_srcs):
                    last_v = all_vids[-1]
                    new_src = await last_v.get_attribute("src")
                    print(f"  [√] 容错捕获末尾最新视频: {new_src[:45]}...")

            if not new_src:
                print(f"  [!] 尝试 {attempt}: 等待超时，未捕获到新视频")
                if attempt < retry:
                    await muse_page.wait_for_timeout(3000)
                    continue
                return False

            # 下载 blob 视频
            print(f"  [+] 提取视频数据流并保存...")
            b64_data = await muse_page.evaluate("""async (videoSrc) => {
                const resp = await fetch(videoSrc);
                const blob = await resp.blob();
                return new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result.split(',')[1]);
                    reader.onerror = reject;
                    reader.readAsDataURL(blob);
                });
            }""", new_src)

            video_bytes = base64.b64decode(b64_data)
            with open(save_path, "wb") as f:
                f.write(video_bytes)

            size_mb = len(video_bytes) / (1024 * 1024)
            print(f"  [√] Shot {sid:02d} 视频入库成功: {save_path} ({size_mb:.2f} MB)")
            return True

        except Exception as e:
            print(f"  [!] Shot {sid:02d} 尝试 {attempt} 发生异常: {e}")
            if attempt < retry:
                await muse_page.wait_for_timeout(5000)
            else:
                return False

    return False


async def run_batch(start_shot=1, end_shot=54, count=None):
    print("=" * 65)
    print(f"  【北宋杨家将】第 3 集 Muse.ai 云端图生视频自动化批量管线")
    print(f"  范围: Shot {start_shot:02d} ~ Shot {end_shot:02d}")
    print(f"  产物目录: {OUTPUT_DIR}")
    print("=" * 65)

    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        except Exception as e:
            print(f"[!] 无法连接到 CDP 端口 9222: {e}")
            return

        context = browser.contexts[0]
        muse_page = None
        for page in context.pages:
            if "muse.ai" in page.url:
                muse_page = page
                break

        if not muse_page:
            print("[!] 未找到已打开的 Muse.ai 标签页！")
            await browser.close()
            return

        print("[√] 成功连接至 Muse.ai 浏览器页面！")

        items = [m for m in EP03_METADATA if start_shot <= m["id"] <= end_shot]
        if count:
            items = items[:count]

        total = len(items)
        success_count = 0

        for i, item in enumerate(items, 1):
            print(f"\n>>> 进度: [{i}/{total}] 全剧第 {item['id']:02d} 镜 <<<")
            ok = await process_single_shot(muse_page, item)
            if ok:
                success_count += 1
            # 镜头间隔短暂休眠以保证云端会话平稳
            await muse_page.wait_for_timeout(2000)

        print("\n" + "=" * 65)
        print(f"【批处理完成】成功生成/校验 {success_count}/{total} 个镜头视频！")
        print("=" * 65)

        await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Muse.ai 批量跑片管线")
    parser.add_argument("--start", type=int, default=1, help="起始镜头 ID (1~54)")
    parser.add_argument("--end", type=int, default=54, help="结束镜头 ID (1~54)")
    parser.add_argument("--count", type=int, default=None, help="最大处理数量")
    args = parser.parse_args()

    asyncio.run(run_batch(start_shot=args.start, end_shot=args.end, count=args.count))
