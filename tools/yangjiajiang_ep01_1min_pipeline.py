#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《北宋杨家将 · 忠烈千秋》第一集《北汉风雪》1分钟剧情全自动流水线
功能：
1. 自动化向 ComfyUI 提交第 1 集前 12 镜（约 60 秒）分镜生成任务
2. 支持使用 wan22_animate_story_9x16_api.json 工作流
3. 生成完成后，自动使用 ffmpeg 拼接为 1 分钟剧情成片，归档到 output/YYYY-MM-DD/
"""

import os
import sys
import json
import time
import argparse
import subprocess
from datetime import datetime

COMFY_API_URL = "http://127.0.0.1:8188"
WORKFLOW_TEMPLATE = r"d:\ai_projects\ComfyUI\workflows\v3\wan22_animate_story_9x16_api.json"
TODAY_STR = datetime.now().strftime("%Y-%m-%d")
OUTPUT_DIR = os.path.join(r"d:\ai_projects\ComfyUI\output", TODAY_STR, "yangjiajiang")

# 第一集《北汉风雪》前 12 镜（共计约 58~60 秒）
EPISODE_1_SHOTS = [
    {
        "id": "shot01",
        "dur": 8,
        "title": "帅府后堂风雪入画",
        "prompt": "Vertical shot, camera slowly tilts upward from flagstones to walls to a snow line. Nine figures stand in layered depth inside a northern frontier hall, father centre-front, sons and daughters receding behind, snow-covered city wall, vintage Shanghai Animation Film Studio style, new baimiao, flat mineral pigment color blocks, clear brush strokes, rice paper texture",
        "image": "anime_ref_character.jpg",
        "video": "video_wan2_2_14B_animate_original_video.mp4"
    },
    {
        "id": "shot02",
        "dur": 4,
        "title": "九子层层退开",
        "prompt": "Vertical shot, camera slowly pulls back along depth. Nine generals in distinct Song dynasty armour recede into ranks one after another, wife, sons and daughters, distinct readable colours, vintage Shanghai Animation Film Studio style, new baimiao, flat mineral pigment",
        "image": "anime_ref_character.jpg",
        "video": "video_wan2_2_14B_animate_original_video.mp4"
    },
    {
        "id": "shot03",
        "dur": 4,
        "title": "帅印推至掌心",
        "prompt": "Static medium vertical shot, a wooden commander seal slides across dark table toward open hands, seal low in frame, hands in centre, blank textured wall above, vintage Shanghai Animation Film Studio style, new baimiao",
        "image": "anime_ref_character.jpg",
        "video": "video_wan2_2_14B_animate_original_video.mp4"
    },
    {
        "id": "shot04",
        "dur": 4,
        "title": "双手握印低头",
        "prompt": "Close vertical shot, static, ancient general hands close tightly around wooden commander seal, lowers head solemnly, empty space above, vintage Shanghai Animation Film Studio style, new baimiao",
        "image": "anime_ref_character.jpg",
        "video": "video_wan2_2_14B_animate_original_video.mp4"
    },
    {
        "id": "shot05",
        "dur": 8,
        "title": "大营连绵升镜头",
        "prompt": "Vertical shot, camera rises steadily, rows of ochre army tents recede into blank cold distance across lower third, empty snowy sky above, vintage Shanghai Animation Film Studio style, new baimiao",
        "image": "anime_ref_character.jpg",
        "video": "video_wan2_2_14B_animate_original_video.mp4"
    },
    {
        "id": "shot06",
        "dur": 4,
        "title": "三将立于石阶",
        "prompt": "Static medium vertical shot, three Song dynasty officers in armour stand firmly on stone step facing camera, blank snowy sky above, vintage Shanghai Animation Film Studio style, new baimiao",
        "image": "anime_ref_character.jpg",
        "video": "video_wan2_2_14B_animate_original_video.mp4"
    },
    {
        "id": "shot07",
        "dur": 4,
        "title": "画外指引与注目",
        "prompt": "Static medium vertical shot, courtier raises one arm pointing off-frame, ruler gaze follows silently, hand held high in upper third, vintage Shanghai Animation Film Studio style, new baimiao",
        "image": "anime_ref_character.jpg",
        "video": "video_wan2_2_14B_animate_original_video.mp4"
    },
    {
        "id": "shot08",
        "dur": 4,
        "title": "行军纵深深入",
        "prompt": "Vertical shot, camera moves slowly upward along marching soldiers advancing away into deep horizon from bottom of frame, ochre plain, blank sky, vintage Shanghai Animation Film Studio style, new baimiao",
        "image": "anime_ref_character.jpg",
        "video": "video_wan2_2_14B_animate_original_video.mp4"
    },
    {
        "id": "shot09",
        "dur": 4,
        "title": "杨延定单骑纵深",
        "prompt": "Static medium vertical shot, young general officer rides horse directly away from camera into distance, shrinking toward low horizon, resolute, vintage Shanghai Animation Film Studio style, new baimiao",
        "image": "anime_ref_character.jpg",
        "video": "video_wan2_2_14B_animate_original_video.mp4"
    },
    {
        "id": "shot10",
        "dur": 4,
        "title": "回书落于掌心",
        "prompt": "Close vertical shot, static, folded letter scroll placed into open palm, hand in lower third, vintage Shanghai Animation Film Studio style, new baimiao",
        "image": "anime_ref_character.jpg",
        "video": "video_wan2_2_14B_animate_original_video.mp4"
    },
    {
        "id": "shot11",
        "dur": 4,
        "title": "兵要地图纵深俯推",
        "prompt": "High angle vertical shot pushing forward along ancient strategic map on wooden table, deep perspective, ink markings of frontier passes, vintage Shanghai Animation Film Studio style, new baimiao",
        "image": "anime_ref_character.jpg",
        "video": "video_wan2_2_14B_animate_original_video.mp4"
    },
    {
        "id": "shot12",
        "dur": 6,
        "title": "边关落日与雪原",
        "prompt": "Static wide vertical shot, ancient Song frontier beacon tower against twilight sky, single banner fluttering in cold wind, snow drifting across ground, vintage Shanghai Animation Film Studio style, new baimiao",
        "image": "anime_ref_character.jpg",
        "video": "video_wan2_2_14B_animate_original_video.mp4"
    }
]

def load_template():
    with open(WORKFLOW_TEMPLATE, "r", encoding="utf-8") as f:
        return json.load(f)

def submit_shot(shot_info, dry_run=False):
    import urllib.request
    wf = load_template()
    # 注入当前分镜参数
    wf["8"]["inputs"]["text"] = shot_info["prompt"]
    wf["10"]["inputs"]["image"] = shot_info["image"]
    wf["12"]["inputs"]["file"] = shot_info["video"]
    if "seed" in shot_info:
        wf["18"]["inputs"]["seed"] = shot_info["seed"]
    wf["21"]["inputs"]["filename_prefix"] = f"{TODAY_STR}/yangjiajiang/{shot_info['id']}"

    payload = {"prompt": wf}
    if dry_run:
        print(f"[DRY-RUN] 镜 {shot_info['id']} ({shot_info['title']}): {shot_info['dur']}s -> 提示词注入完成")
        return "dry-run-pid"

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{COMFY_API_URL}/prompt", data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            pid = res.get("prompt_id")
            print(f"[SUBMIT] 镜 {shot_info['id']} ({shot_info['title']}) 提交成功, Prompt ID: {pid}")
            return pid
    except Exception as e:
        print(f"[ERROR] 提交失败: {e}")
        return None

def merge_1min_video(shots_dir=OUTPUT_DIR, output_file=None):
    if not output_file:
        output_file = os.path.join(OUTPUT_DIR, "yang_ep01_1min_merged.mp4")
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    file_list_txt = os.path.join(OUTPUT_DIR, "shots_concat_list.txt")

    mp4_files = []
    for s in EPISODE_1_SHOTS:
        # 寻找匹配的前缀文件
        prefix = s["id"]
        found = False
        if os.path.exists(OUTPUT_DIR):
            for f in sorted(os.listdir(OUTPUT_DIR)):
                if f.startswith(prefix) and f.endswith(".mp4"):
                    full_p = os.path.join(OUTPUT_DIR, f).replace("\\", "/")
                    mp4_files.append(f"file '{full_p}'")
                    found = True
                    break
        if not found:
            print(f"[WARN] 未找到镜头产物: {prefix}")

    if not mp4_files:
        print("[ERROR] 没有找到可拼接的 mp4 镜头文件！")
        return False

    with open(file_list_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(mp4_files))

    print(f"[MERGE] 准备将 {len(mp4_files)} 个分镜拼接为 1 分钟漫剧成片...")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", file_list_txt,
        "-c", "copy",
        output_file
    ]
    try:
        subprocess.run(cmd, check=True)
        print(f"[SUCCESS] 1分钟漫剧成片导出完成: {output_file}")
        return True
    except Exception as e:
        print(f"[ERROR] ffmpeg 拼接失败: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="杨家将第一集1分钟流水线")
    parser.add_argument("--dry-run", action="store_true", help="演练模式，不真实提交 ComfyUI")
    parser.add_argument("--shot", type=str, default=None, help="仅提交单镜 (如 shot01)")
    parser.add_argument("--merge-only", action="store_true", help="仅执行视频拼接")
    parser.add_argument("--skip-existing", action="store_true", default=True, help="跳过已生成的镜头")
    parser.add_argument("--no-skip-existing", dest="skip_existing", action="store_false", help="不跳过已生成的镜头")
    args = parser.parse_args()

    if args.merge_only:
        merge_1min_video()
        return

    targets = EPISODE_1_SHOTS
    if args.shot:
        targets = [s for s in EPISODE_1_SHOTS if s["id"] == args.shot]

    print(f"=== 《北宋杨家将》第一集 1分钟漫剧分镜调度 (共 {len(targets)} 镜) ===")
    pids = []
    for idx, s in enumerate(targets):
        # 检查是否已存在产物
        if args.skip_existing and os.path.exists(OUTPUT_DIR):
            existing = [f for f in os.listdir(OUTPUT_DIR) if f.startswith(s["id"]) and f.endswith(".mp4")]
            if existing:
                print(f"[SKIP] 镜 {s['id']} ({s['title']}) 已存在成品 ({existing[0]})，跳过生成")
                pids.append({"id": s["id"], "title": s["title"], "dur": s["dur"], "pid": "already_done", "seed": 20261003 + idx})
                continue

        s_copy = dict(s)
        s_copy["seed"] = 20261003 + idx
        pid = submit_shot(s_copy, dry_run=args.dry_run)
        if pid:
            pids.append({"id": s["id"], "title": s["title"], "dur": s["dur"], "pid": pid, "seed": s_copy["seed"]})
        time.sleep(0.5)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    record_file = os.path.join(OUTPUT_DIR, "submitted_tasks.json")
    with open(record_file, "w", encoding="utf-8") as f:
        json.dump(pids, f, ensure_ascii=False, indent=2)

    active_pids = [p for p in pids if p.get("pid") != "already_done"]
    print(f"\n全部推送完毕: {len(active_pids)} 个新任务已推入 GPU 加速队列 ({len(pids)-len(active_pids)} 个已跳过)")
    print(f"任务记录已保存至: {record_file}")
    print(f"待所有分镜生成完成后，执行以下命令即可一键拼接 1 分钟漫剧成片:")
    print(f"cmd /c python tools/yangjiajiang_ep01_1min_pipeline.py --merge-only")

if __name__ == "__main__":
    main()
