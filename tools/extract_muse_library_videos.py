#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键自动化安全提取 Muse.ai 已生成视频产物
特性：
1. 纯前端读取已渲染的媒体 Blob 数据流，100% 零周额消耗、零计费接口调用
2. 自动匹配镜头场景标题（如 辽军溃散宋军欢呼、大开城门恭迎圣驾 等）
3. 按项目规范落盘至 output/2026-10-10/yangjiajiang_ep03/muse_videos/
4. 生成完整的元数据清单 videos_metadata.json
"""

import asyncio
import os
import sys
import re
import json
import base64
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = r"D:\ai_projects\ComfyUI"
OUTPUT_DIR = os.path.join(ROOT, "output", "2026-10-10", "yangjiajiang_ep03", "muse_videos")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def sanitize_filename(name):
    # 保留中英文字符、数字和下划线，去除特殊符号
    cleaned = re.sub(r'[\\/*?:"<>| \n\r\t]+', '_', name)
    cleaned = re.sub(r'_+', '_', cleaned).strip('_')
    return cleaned[:40] if cleaned else "video"

async def extract_all_videos():
    print("=" * 65)
    print("【Muse.ai 成品视频】一键自动化安全提取管线")
    print(f"目标归档目录: {OUTPUT_DIR}")
    print("安全策略: 纯读取已有渲染 Blob，0 额度消耗")
    print("=" * 65)

    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        except Exception as e:
            print(f"[!] 无法连接到 Chrome CDP (端口 9222): {e}")
            return

        context = browser.contexts[0]
        muse_page = None
        for page in context.pages:
            if "muse.ai" in page.url:
                muse_page = page
                break

        if not muse_page:
            print("[!] 未找到已打开的 Muse.ai 页面！")
            await browser.close()
            return

        print(f"[√] 成功接入 Muse 页面: {muse_page.url}")

        # 提取页面中所有视频及其关联的文本上下文
        video_entries = await muse_page.evaluate("""() => {
            const list = [];
            const videos = Array.from(document.querySelectorAll('video'));

            videos.forEach((v, idx) => {
                const src = v.src || v.currentSrc || v.getAttribute('src') || '';
                if (!src) return;

                // 寻找最相关的标题或文本描述
                let container = v.closest('div[role="article"]') || 
                                v.closest('.message') || 
                                v.parentElement?.parentElement?.parentElement || 
                                v.parentElement;
                
                let title = '';
                if (container) {
                    // 获取前面紧挨着的文本或标题
                    const text = container.innerText.trim();
                    const lines = text.split('\\n').map(s => s.trim()).filter(s => s && !s.includes('video') && !s.includes('助手消息') && s.length < 50);
                    if (lines.length > 0) {
                        title = lines[0];
                    }
                }

                list.push({
                    index: idx + 1,
                    src: src,
                    title: title,
                    width: v.videoWidth || 0,
                    height: v.videoHeight || 0,
                    duration: v.duration || 0
                });
            });
            return list;
        }""")

        print(f"[*] 检测到待提取的视频元素数量: {len(video_entries)}")
        if not video_entries:
            print("[!] 未检测到任何可提取的视频元素。")
            await browser.close()
            return

        metadata_records = []
        total_bytes = 0
        success_count = 0

        for item in video_entries:
            idx = item["index"]
            raw_title = item.get("title", "")
            title_clean = sanitize_filename(raw_title)
            filename = f"muse_{idx:02d}_{title_clean}.mp4"
            save_path = os.path.join(OUTPUT_DIR, filename)

            print(f"\n[{idx}/{len(video_entries)}] 正在提取: {filename}...")
            print(f"  分辨率: {item['width']}x{item['height']}, 时长: {item['duration']:.1f}s")

            try:
                # 在浏览器内部将 blob URL 转成 base64 返回
                b64_data = await muse_page.evaluate("""async (videoSrc) => {
                    const resp = await fetch(videoSrc);
                    const blob = await resp.blob();
                    return new Promise((resolve, reject) => {
                        const reader = new FileReader();
                        reader.onloadend = () => resolve(reader.result.split(',')[1]);
                        reader.onerror = reject;
                        reader.readAsDataURL(blob);
                    });
                }""", item["src"])

                video_bytes = base64.b64decode(b64_data)
                with open(save_path, "wb") as f:
                    f.write(video_bytes)

                size_mb = len(video_bytes) / (1024 * 1024)
                total_bytes += len(video_bytes)
                success_count += 1
                print(f"  [√] 落盘成功: {save_path} ({size_mb:.2f} MB)")

                metadata_records.append({
                    "index": idx,
                    "filename": filename,
                    "title": raw_title,
                    "save_path": save_path,
                    "width": item["width"],
                    "height": item["height"],
                    "duration": item["duration"],
                    "size_bytes": len(video_bytes),
                    "size_mb": round(size_mb, 2)
                })

            except Exception as e:
                print(f"  [!] 提取失败: {e}")

        # 保存元数据清单
        meta_path = os.path.join(OUTPUT_DIR, "videos_metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "date": "2026-10-10",
                "source": "muse.ai",
                "total_count": success_count,
                "total_size_mb": round(total_bytes / (1024 * 1024), 2),
                "videos": metadata_records
            }, f, ensure_ascii=False, indent=2)

        print("\n" + "=" * 65)
        print(f"[√] 全量安全提取圆满完成！")
        print(f"  成功提取视频数: {success_count} / {len(video_entries)}")
        print(f"  总归档体积: {total_bytes / (1024 * 1024):.2f} MB")
        print(f"  归档目录: {OUTPUT_DIR}")
        print(f"  元数据清单: {meta_path}")
        print("=" * 65)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(extract_all_videos())
