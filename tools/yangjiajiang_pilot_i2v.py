#!/usr/bin/env python3
"""北宋杨家将 · 六镜试片 I2V 批量生成与拼合器

基于《杨家将 · 忠烈千秋》6 张真实分镜原画（shot01.jpg ~ shot06.jpg）
与《Flow提示词_可直接粘贴.txt》中的运镜及音效提示词，
采用 MiniMax H3 4-Step Turbo 快线 I2V（纯 GPU 加速）逐镜生成真正符合剧本的样片，
并自动使用 ffmpeg 拼接为完整试片成片。

规范约束：
- 严格按日期输出至 output/2026-10-04/yangjiajiang_pilot/
- 画幅 16:9（960x544）
- 严禁修改 workflows/v2学习/
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error

ROOT = r"D:\ai_projects\ComfyUI"
INPUT_ROOT = os.path.join(ROOT, "input")
TODOS_ROOT = os.path.join(ROOT, "todos", "北宋杨家将", "动画改编方案", "试片")
DATE_STR = "2026-10-04"
OUTPUT_DIR = os.path.join(ROOT, "output", DATE_STR, "yangjiajiang_pilot")
WORKFLOW_PATH = os.path.join(ROOT, "workflows", "v5", "h3_fast_i2v_9x16_api.json")
FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
if not os.path.exists(FFMPEG):
    FFMPEG = shutil.which("ffmpeg") or "ffmpeg"

BASE_URL = "http://127.0.0.1:8188"

# 6 镜头元数据（提示词来自 Flow提示词_可直接粘贴.txt）
SHOTS = [
    {
        "id": 1,
        "name": "shot01",
        "title": "退守土岗",
        "input_image": "yang_shot01.jpg",
        "raw_image": "shot01.jpg",
        "sec": 6.0,
        "length": 141,  # 17 * 8 + 5 = 141 (5.88s ~ 6s)
        "prompt": (
            "Low aerial wide shot, camera very slowly pushing in. "
            "Dozens of ragged Song-dynasty soldiers in broken armour sit scattered on a bare frontier hilltop at dusk, "
            "heads bowed, almost motionless. One man stands alone just outside the circle, back to camera, "
            "his dark cloak torn down to a half, armour split open in three places, both hands hanging empty at his sides. "
            "Frozen ochre earth under a thin film of moon-white snow, layered celadon-green mountains receding into vast empty space. "
            "Traditional hand-painted 2D animation, flat solid blocks of mineral pigment colour, "
            "simplified contours with visible brush outlines, film grain, vintage Shanghai Animation Film Studio manner. "
            "Every form is one flat shape of colour; light is expressed only by adjacent colour blocks. SFX: low wind across bare ground."
        ),
    },
    {
        "id": 2,
        "name": "shot02",
        "title": "见碑",
        "input_image": "yang_shot02.jpg",
        "raw_image": "shot02.jpg",
        "sec": 6.0,
        "length": 141,  # 17 * 8 + 5 = 141 (5.88s ~ 6s)
        "prompt": (
            "Close shot, camera slowly tilts down and settles to rest. "
            "A broken stone stele leans at an angle in frozen ochre earth, its face eroded and flaking, "
            "its edges chipped away, the characters it once carried worn almost flat and unreadable. "
            "To its left stands a dead willow, every branch snapped off. A thin film of moon-white snow lies on the ground. "
            "Wide empty space fills the upper frame. Traditional hand-painted 2D animation, "
            "flat solid blocks of mineral pigment colour, simplified contours with visible brush outlines, "
            "film grain, vintage Shanghai Animation Film Studio manner. Every form is one flat shape of colour. "
            "The camera comes to a complete stop and holds. SFX: faint wind."
        ),
    },
    {
        "id": 3,
        "name": "shot03",
        "title": "碑面横移",
        "input_image": "yang_shot03.jpg",
        "raw_image": "shot03.jpg",
        "sec": 8.0,
        "length": 192,  # 17 * 11 + 5 = 192 (8.00s)
        "prompt": (
            "Extreme close-up filling the entire frame with the surface of an ancient stone stele. "
            "Coarse weathered stone, hairline cracks and chisel marks; "
            "rows of horizontal incisions where characters were once carved have been worn almost smooth, "
            "as if scoured by water for many years. Only a fragment of one chiselled stroke survives at the lower right. "
            "Camera drifts slowly and steadily sideways across the surface. "
            "Pale ochre stone and ink-black line fill the whole frame; the image is built from these two tones alone. "
            "Traditional hand-painted 2D animation, flat solid blocks of mineral pigment colour, "
            "simplified contours with visible brush outlines, film grain, vintage Shanghai Animation Film Studio manner. "
            "SFX: wind ceases abruptly at the very start, complete silence through the middle, a single thread of wind at the end."
        ),
    },
    {
        "id": 4,
        "name": "shot04",
        "title": "撞碑·高潮",
        "input_image": "yang_shot04.jpg",
        "raw_image": "shot04.jpg",
        "sec": 8.0,
        "length": 192,  # 17 * 11 + 5 = 192 (8.00s)
        "prompt": (
            "Monochrome ink-wash image, black white and grey, drawn like an old woodblock illustration. "
            "A weathered stone stele stands on a bare hillside. Before it a lone warrior in broken armour, "
            "back to camera, facing the stone, small within the frame. Beside him a long sword is planted upright in the ground, "
            "its tassel the only cinnabar-red note in the entire image. Sparse snow drifts down. "
            "Camera rises very slowly from behind the figure, passing over his shoulder toward the stele. "
            "Vast empty sky above. Every value sits as one flat shape of ink, the way an old woodblock print is cut. "
            "SFX: wind, then one low short dull impact like wood striking stone, then long wind."
        ),
    },
    {
        "id": 5,
        "name": "shot05",
        "title": "碑前开花",
        "input_image": "yang_shot05.jpg",
        "raw_image": "shot05.jpg",
        "sec": 8.0,
        "length": 192,  # 17 * 11 + 5 = 192 (8.00s)
        "prompt": (
            "Same hillside, same camera position and framing, years later, early spring afternoon. "
            "The stele now carries dense vertical rows of carved names. Beside it the willow has come back to life, "
            "hung with fresh pale-green leaves. The slope in front is covered with a broad carpet of small wildflowers, "
            "celadon and moon white. A sword is planted in the ground, its tassel still cinnabar red, "
            "the single most vivid colour in the frame. The horizon sits low with a wide blank sky above. "
            "Camera completely static. Traditional hand-painted 2D animation, flat solid blocks of mineral pigment colour, "
            "simplified contours with visible brush outlines, film grain, vintage Shanghai Animation Film Studio manner. "
            "SFX: wind moving gently through willow leaves."
        ),
    },
    {
        "id": 6,
        "name": "shot06",
        "title": "枯柳新芽",
        "input_image": "yang_shot06.jpg",
        "raw_image": "shot06.jpg",
        "sec": 4.0,
        "length": 124,  # 17 * 7 + 5 = 124 (5.17s)
        "prompt": (
            "Extreme close-up. A single snapped-off dead willow branch enters from the lower left, "
            "its bark drawn in heavy ink-black line, every old twig broken. "
            "At its very tip one small new shoot has emerged, two young leaves of pale celadon green, very small. "
            "The rest of the frame is blank moon-white space. Camera pushes in almost imperceptibly and then holds still. "
            "Traditional hand-painted 2D animation, flat solid blocks of mineral pigment colour, "
            "simplified contours with visible brush outlines, film grain, vintage Shanghai Animation Film Studio manner. "
            "SFX: a single thread of wind."
        ),
    },
]


def post_json(path, payload, timeout=60):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(path, timeout=30):
    with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ensure_input_assets():
    """确保 6 张分镜首帧图已拷贝至 input 目录"""
    os.makedirs(INPUT_ROOT, exist_ok=True)
    for s in SHOTS:
        dst = os.path.join(INPUT_ROOT, s["input_image"])
        src = os.path.join(TODOS_ROOT, s["raw_image"])
        if not os.path.exists(dst):
            if os.path.exists(src):
                shutil.copy(src, dst)
                print(f"[资源准备] 拷贝 {src} -> {dst}")
            else:
                raise FileNotFoundError(f"未找到原画资源: {src}")


def inject_workflow(wf_template, shot, width=960, height=544, seed=20261004):
    prefix = f"{DATE_STR}/yangjiajiang_pilot/{shot['name']}"
    values = {
        "first_frame": shot["input_image"],
        "prompt": shot["prompt"],
        "width": width,
        "height": height,
        "length": shot["length"],
        "seed": seed + shot["id"] * 7,
        "filename_prefix": prefix,
    }

    def walk(obj):
        if isinstance(obj, str):
            if obj.startswith("[inject:") and obj.endswith("]"):
                k = obj[len("[inject:"):-1]
                return values[k]
            return obj
        if isinstance(obj, list):
            return [walk(x) for x in obj]
        if isinstance(obj, dict):
            return {k: walk(v) for k, v in obj.items()}
        return obj

    return walk(wf_template)


def wait_prompt_done(prompt_id, timeout=900, poll=10):
    """等待单镜头生成完成"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            hist = get_json(f"/history/{prompt_id}")
        except Exception as e:
            time.sleep(poll)
            continue
        if prompt_id in hist:
            item = hist[prompt_id]
            st = item.get("status", {})
            if st.get("status_str") == "error":
                print(f"  [执行失败] prompt_id={prompt_id}: {st}")
                return None
            outputs = item.get("outputs", {})
            # 提取生成的视频文件路径
            for nid, out in outputs.items():
                for k, v in out.items():
                    if isinstance(v, list):
                        for file_info in v:
                            if isinstance(file_info, dict) and "filename" in file_info:
                                sub = file_info.get("subfolder", "")
                                fn = file_info["filename"]
                                full_p = os.path.join(ROOT, "output", sub, fn)
                                if os.path.exists(full_p) and full_p.endswith((".mp4", ".mov", ".mkv")):
                                    return full_p
            if item.get("status", {}).get("completed"):
                return True
        time.sleep(poll)
    print(f"  [等待超时] prompt_id={prompt_id}")
    return None


def merge_pilot_video():
    """将已生成的 6 镜视频自动拼接为成片"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    shot_files = []
    for s in SHOTS:
        # 在 output/2026-10-04/yangjiajiang_pilot/ 下寻找该 shot
        prefix = s["name"]
        matches = [
            f for f in os.listdir(OUTPUT_DIR)
            if f.startswith(prefix) and f.endswith(".mp4") and "merged" not in f
        ]
        if not matches:
            print(f"[拼接提示] 缺少镜头文件: {prefix}")
            return None
        # 取最新生成的一个
        matches.sort(key=lambda x: os.path.getmtime(os.path.join(OUTPUT_DIR, x)), reverse=True)
        shot_files.append(os.path.join(OUTPUT_DIR, matches[0]))

    print("\n=== 找到全部 6 镜视频，开始拼接 ===")
    for idx, sf in enumerate(shot_files, 1):
        print(f"  镜 {idx:02d}: {os.path.basename(sf)}")

    list_file = os.path.join(OUTPUT_DIR, "concat_list.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for sf in shot_files:
            # ffmpeg concat demuxer 格式: file 'path' (斜杠转义)
            clean_path = sf.replace("\\", "/")
            f.write(f"file '{clean_path}'\n")

    output_merged = os.path.join(OUTPUT_DIR, "yangjiajiang_pilot_merged.mp4")
    cmd = [
        FFMPEG, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        output_merged
    ]
    print(f"执行拼接命令: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and os.path.exists(output_merged):
        print(f"\n[拼接成功] 完整试片已输出至: {output_merged}")
        # 输出成片信息
        dur_cmd = [
            FFMPEG, "-i", output_merged
        ]
        probe = subprocess.run(dur_cmd, capture_output=True, text=True)
        print("成片信息详情:")
        for line in probe.stderr.splitlines():
            if "Duration:" in line or "Video:" in line or "Audio:" in line:
                print(f"  {line.strip()}")
        return output_merged
    else:
        print(f"[拼接失败]: {res.stderr}")
        return None


def main():
    parser = argparse.ArgumentParser(description="北宋杨家将六镜试片生成与拼接")
    parser.add_argument("--shot", type=int, default=0, help="指定生成单镜(1-6)，0 表示批量跑全部 6 镜")
    parser.add_argument("--start-shot", type=int, default=1, help="从指定镜头开始批量生成(例如 2 表示跑 2-6 镜)")
    parser.add_argument("--merge-only", action="store_true", help="跳过生成，直接执行 6 镜拼接")
    parser.add_argument("--width", type=int, default=960, help="视频宽度 (默认 960)")
    parser.add_argument("--height", type=int, default=544, help="视频高度 (默认 544)")
    parser.add_argument("--seed", type=int, default=20261004, help="随机种子基准")
    args = parser.parse_args()

    ensure_input_assets()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if args.merge_only:
        return 0 if merge_pilot_video() else 1

    with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
        wf_template = json.load(f)

    if args.shot > 0:
        target_shots = [s for s in SHOTS if s["id"] == args.shot]
    else:
        target_shots = [s for s in SHOTS if s["id"] >= args.start_shot]

    print(f"==================================================")
    print(f"《北宋杨家将》六镜试片 I2V 批量任务启动")
    print(f"待处理镜头数: {len(target_shots)} (镜 {target_shots[0]['id']} ~ 镜 {target_shots[-1]['id']})")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"分辨率: {args.width}x{args.height} (16:9)")
    print(f"==================================================")

    generated_videos = []
    for s in target_shots:
        print(f"\n>>> 正在处理【镜 {s['id']:02d}：{s['title']}】 (帧长 {s['length']}, 约 {s['sec']}s)")
        print(f"    首帧原画: {s['input_image']}")
        print(f"    提示词: {s['prompt'][:80]}...")

        wf = inject_workflow(wf_template, s, width=args.width, height=args.height, seed=args.seed)
        payload = {"prompt": wf}
        try:
            resp = post_json("/prompt", payload)
            pid = resp.get("prompt_id")
            print(f"    已提交至 ComfyUI, prompt_id: {pid}")
        except Exception as e:
            print(f"    [提交失败] {e}")
            return 1

        print(f"    等待 GPU 渲染完成 (4 步 Turbo, 预计 ~1 分钟)...")
        video_path = wait_prompt_done(pid)
        if video_path and os.path.exists(video_path):
            print(f"    [完成] 产物已落盘: {video_path}")
            generated_videos.append(video_path)
        else:
            print(f"    [失败] 镜头 {s['id']} 生成未成功，终止批处理。")
            return 1

    print("\n==================================================")
    print(f"本次计划的 {len(generated_videos)} 个镜头均已生成完毕！")
    print("==================================================")

    print("\n自动执行六镜全片拼接...")
    merged = merge_pilot_video()
    if merged:
        print(f"\n🎉 样片生成与拼接全链路达成！成片: {merged}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
