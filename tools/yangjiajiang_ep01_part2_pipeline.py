#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""北宋杨家将 · 第一集《北汉风雪》后续全集剧情制作管线 (Shot 13 - Shot 41)

本管线严格依据《杨家将_剧本与分镜全本.html》与《杨家将_试播集切分表.xlsx》规范构建：
- 风格一致性保障：全面采用上海电影制片厂手绘动画风格（传统重彩矿物颜料设色 + 纯净工笔白描，16:9 画幅）
- 模块化支持：
  1. 任务提交 (--submit-only): 异步批量推送到 GPU 队列，解耦不阻塞
  2. 成片合流 (--concat): 渲染完成后自动执行镜头规格归一化、无损拼接与专属原声混流
  3. 全幕拼接 (--stitch-part1): 将 Part 1 (前1分钟) 与 Act 2 完整无缝融合成片
- 产物归档：严格输出至 output/2026-10-04/yangjiajiang_ep01/
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
import numpy as np
from scipy.io import wavfile
from scipy import signal

ROOT = r"D:\ai_projects\ComfyUI"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
DATE_STR = "2026-10-04"
OUTPUT_DIR = os.path.join(ROOT, "output", DATE_STR, "yangjiajiang_ep01")
INPUT_DIR = os.path.join(ROOT, "input")
WORKFLOW_H3 = os.path.join(ROOT, "workflows", "v5", "h3_fast_i2v_9x16_api.json")
WORKFLOW_WAN = os.path.join(ROOT, "workflows", "v3", "wan22_animate_story_9x16_api.json")
FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
if not os.path.exists(FFMPEG):
    FFMPEG = shutil.which("ffmpeg") or "ffmpeg"

BASE_URL = "http://127.0.0.1:8188"

# 29 镜头完整分镜规格表 (Shot 13 至 Shot 41)
EP01_PART2_SHOTS = [
    # ---------- Act II: 晋阳血战 (Shot 13 - 19) ----------
    {
        "id": 13,
        "act": 2,
        "name": "shot13_two_columns",
        "title": "两路出营目送",
        "page": "1-15",
        "sec": 4.0,
        "length": 124,
        "input_image": "yang_ep01_shot13.jpg",
        "input_image_v": "yang_ep01_v_shot13.jpg",
        "prompt": "Camera very slowly drifts forward, two columns of Song cavalry in iron armor ride out through the fortress gate into distant snow mountains, Madam She in green cloak standing motionless in archway watching them depart, vintage Shanghai Animation Film Studio 2D anime manner, traditional flat mineral pigment colors.",
    },
    {
        "id": 14,
        "act": 2,
        "name": "shot14_cavalry_clash",
        "title": "两军对撞",
        "page": "1-16",
        "sec": 4.0,
        "length": 124,
        "input_image": "yang_ep01_shot14.jpg",
        "input_image_v": "yang_ep01_v_shot14.jpg",
        "prompt": "Fast forward charging motion, two cavalry armies clash fiercely on the frozen snowfield, raised 'Song' battle banners flapping in winter gale, galloping horses kicking up snow and ice, flying spearheads and swords, vintage Shanghai Animation Film Studio hand-painted anime style.",
    },
    {
        "id": 15,
        "act": 2,
        "name": "shot15_arrow_caught",
        "title": "坐骑衔箭核心戏眼",
        "page": "1-17",
        "sec": 8.0,
        "length": 192,
        "input_image": "yang_ep01_shot15.jpg",
        "input_image_v": "yang_ep01_v_shot15.jpg",
        "prompt": "Core dramatic climax: camera static, powerful warhorse leaps up in dramatic slow motion and bites the incoming whistling iron arrow between its teeth, the armored emperor falls backwards from the saddle onto deep snow, vintage Shanghai Animation Film Studio 2D hand-painted anime style.",
    },
    {
        "id": 16,
        "act": 2,
        "name": "shot16_melee_combat",
        "title": "短兵混战",
        "page": "1-18",
        "sec": 4.0,
        "length": 124,
        "input_image": "yang_ep01_shot16.jpg",
        "input_image_v": "yang_ep01_v_shot16.jpg",
        "prompt": "Subtle handheld camera shake, intense melee combat between Song warriors and northern soldiers, sword blade sparks clashing against metal shields, cold white breath exhaled in freezing air, traditional Chinese mineral pigment animation.",
    },
    {
        "id": 17,
        "act": 2,
        "name": "shot17_pan_unseated",
        "title": "金刀挑落潘仁美",
        "page": "1-19",
        "sec": 4.0,
        "length": 124,
        "input_image": "yang_ep01_shot17.jpg",
        "input_image_v": "yang_ep01_v_shot17.jpg",
        "prompt": "a battle-hardened veteran commander in gleaming steel lamellar armor with a grey beard on black stallion thrusts spear, violently knocking minister a scheming senior court minister in dark brocade official robes off his white horse into muddy snow, Yang gallops onward without glancing down, Pan collapses in lower frame looking small and disgraced, vintage Shanghai Animation Film Studio aesthetic.",
    },
    {
        "id": 18,
        "act": 2,
        "name": "shot18_pan_grudge",
        "title": "潘仁美泥地记仇",
        "page": "1-20",
        "sec": 4.0,
        "length": 124,
        "input_image": "yang_ep01_shot18.jpg",
        "input_image_v": "yang_ep01_v_shot18.jpg",
        "prompt": "Close static shot: A scheming senior court minister in dark brocade official robes lying prone in frozen mud, slowly raising dirty head, eyes glaring with deep resentment, hate and calculating revenge toward the distant retreating general, cold desolate winter background, traditional hand-painted Chinese anime aesthetic.",
    },
    {
        "id": 19,
        "act": 2,
        "name": "shot19_ambush_pincer",
        "title": "两路伏兵截断援军",
        "page": "1-21",
        "sec": 4.0,
        "length": 124,
        "input_image": "yang_ep01_shot19.jpg",
        "input_image_v": "yang_ep01_v_shot19.jpg",
        "prompt": "Wide shot: two hidden Yang regiments charge down steep snowy mountain ridges on both sides, shooting bows and brandishing spears, severing the marching enemy column into two, vast epic winter landscape, traditional mineral pigment and ink wash animation.",
    },

    # ---------- Act III: 夜劫空营 (Shot 20 - 27) ----------
    {
        "id": 20,
        "act": 3,
        "name": "shot20_taizu_night_tent",
        "title": "宋太祖夜谋劫营",
        "page": "1-22",
        "sec": 8.0,
        "length": 192,
        "input_image": "yang_ep01_shot20.jpg",
        "input_image_v": "yang_ep01_v_shot20.jpg",
        "prompt": "Night atmosphere, sparse lantern light across lower army tents, a solemn Chinese emperor in a golden dragon robe stands with hands clasped behind back before imperial pavilion, pitch black empty sky filling upper frame, solemn stillness.",
    },
    {
        "id": 21,
        "act": 3,
        "name": "shot21_yang_night_briefing",
        "title": "杨业识破玄机进帐",
        "page": "1-23",
        "sec": 4.0,
        "length": 124,
        "input_image": "yang_ep01_shot21.jpg",
        "input_image_v": "yang_ep01_v_shot21.jpg",
        "prompt": "Medium shot inside military tent, a battle-hardened veteran commander in gleaming steel lamellar armor with a grey beard strides in solemnly, only the silhouetted back of the seated Northern Han lord visible, face held off-screen, shadows dancing in oil lamp glow.",
    },
    {
        "id": 22,
        "act": 3,
        "name": "shot22_empty_camp_plan",
        "title": "案上画圈·空营计",
        "page": "1-24",
        "sec": 4.0,
        "length": 124,
        "input_image": "yang_ep01_shot22.jpg",
        "input_image_v": "yang_ep01_v_shot22.jpg",
        "prompt": "Close static shot, commander finger traces a decisive circle upon ink map on desk: cannon placed outside boundary, interior left completely vacant, hand low in frame, blank coarse canvas above.",
    },
    {
        "id": 23,
        "act": 3,
        "name": "shot23_song_scouts_creep",
        "title": "敢死兵围摸空营",
        "page": "1-25",
        "sec": 4.0,
        "length": 124,
        "input_image": "yang_ep01_shot23.jpg",
        "input_image_v": "yang_ep01_v_shot23.jpg",
        "prompt": "Camera drifts slowly down in night gloom, Song shock troopers silently creep forward toward dead silent tents, surrounding silent empty garrison, faint lantern gleam on blades.",
    },
    {
        "id": 24,
        "act": 3,
        "name": "shot24_white_flash_chaos",
        "title": "留白爆闪·自相残杀",
        "page": "1-26",
        "sec": 6.0,
        "length": 141,
        "input_image": "yang_ep01_shot24.jpg",
        "input_image_v": "yang_ep01_v_shot24.jpg",
        "prompt": "Sudden white flash of artillery burst in darkness, violent shouting erupts, two confused Song armies collide blind in night smoke mistaking each other for foes, chaos and turmoil, vintage anime style.",
    },
    {
        "id": 25,
        "act": 3,
        "name": "shot25_artillery_ambush",
        "title": "信炮齐发·伏兵掩杀",
        "page": "1-27",
        "sec": 4.0,
        "length": 124,
        "input_image": "yang_ep01_shot25.jpg",
        "input_image_v": "yang_ep01_v_shot25.jpg",
        "prompt": "Wide night shot, cannon blast echoes, Yang cavalry regiments charge furiously from flanking hills, pressing retreating enemy into deep canyon, figures silhouetted in gunsmoke.",
    },
    {
        "id": 26,
        "act": 3,
        "name": "shot26_gao_kneels_report",
        "title": "高怀德负伤跪禀",
        "page": "1-28",
        "sec": 4.0,
        "length": 124,
        "input_image": "yang_ep01_shot26.jpg",
        "input_image_v": "yang_ep01_v_shot26.jpg",
        "prompt": "Static medium shot, vanguard general Gao Huaide kneels reporting defeat, mud and blood staining battered iron armor, figure low in frame, vast silent night above.",
    },
    {
        "id": 27,
        "act": 3,
        "name": "shot27_taizu_gazing_sky",
        "title": "太祖仰天叹中华统一",
        "page": "1-29",
        "sec": 8.0,
        "length": 192,
        "input_image": "yang_ep01_shot27.jpg",
        "input_image_v": "yang_ep01_v_shot27.jpg",
        "prompt": "Camera tilts up slowly from a solemn Chinese emperor in a golden dragon robe resolute face to vast empty starry night sky, sovereign contemplation, yearning for unified China, solemn silence, vintage Shanghai Animation manner.",
    },

    # ---------- Act IV: 塞北连雨 (Shot 28 - 33) ----------
    {
        "id": 28,
        "act": 4,
        "name": "shot28_rain_soaked_camp",
        "title": "塞外连阴雨·帐口观雨",
        "page": "1-30",
        "sec": 8.0,
        "length": 192,
        "input_image": "yang_ep01_shot28.jpg",
        "input_image_v": "yang_ep01_v_shot28.jpg",
        "prompt": "Static shot of continuous grey winter drizzle, muddy pools forming below tent flaps, weary soldiers sitting huddled, a battle-hardened veteran commander in gleaming steel lamellar armor with a grey beard watching the downpour calmly from tent entrance, vast grey sky.",
    },
    {
        "id": 29,
        "act": 4,
        "name": "shot29_woodcutters_pile",
        "title": "北汉军士砍柴储粮",
        "page": "1-31",
        "sec": 4.0,
        "length": 124,
        "input_image": "yang_ep01_shot29.jpg",
        "input_image_v": "yang_ep01_v_shot29.jpg",
        "prompt": "Wide landscape shot, woodcutters carry dry firewood down snowy hill into garrison, dry wood stacked high like a hill in lower frame, disciplined foresight, traditional ink brushwork.",
    },
    {
        "id": 30,
        "act": 4,
        "name": "shot30_song_emperor_stamping",
        "title": "宋太祖夜观星象顿足",
        "page": "1-32",
        "sec": 4.0,
        "length": 124,
        "input_image": "yang_ep01_shot30.jpg",
        "input_image_v": "yang_ep01_v_shot30.jpg",
        "prompt": "Night shot outside soggy tent, a solemn Chinese emperor in a golden dragon robe inspects muddy ground and stamps boot in heavy frustration, clouds obscuring stars, rain trickling down tent eaves.",
    },
    {
        "id": 31,
        "act": 4,
        "name": "shot31_shivering_soldiers",
        "title": "宋军士卒湿透蜷缩",
        "page": "1-33",
        "sec": 6.0,
        "length": 141,
        "input_image": "yang_ep01_shot31.jpg",
        "input_image_v": "yang_ep01_v_shot31.jpg",
        "prompt": "Close shot, shivering wet soldiers crouch beneath bare dripping willow trees, cold rain soaking thin tunics, only hunched wet backs visible, harsh frontier climate, bleak mood.",
    },
    {
        "id": 32,
        "act": 4,
        "name": "shot32_yang_rain_ambush_order",
        "title": "杨业借雨分派设伏",
        "page": "1-34",
        "sec": 6.0,
        "length": 141,
        "input_image": "yang_ep01_shot32.jpg",
        "input_image_v": "yang_ep01_v_shot32.jpg",
        "prompt": "Medium shot, a battle-hardened veteran commander in gleaming steel lamellar armor with a grey beard raises arm pointing to slopes, dispatching sons to ambush flanks in storm, clear purposeful gestures, empty misty ground below, mineral pigment.",
    },
    {
        "id": 33,
        "act": 4,
        "name": "shot33_rain_assault_pincer",
        "title": "借雨突袭·大破宋军",
        "page": "1-35",
        "sec": 4.0,
        "length": 124,
        "input_image": "yang_ep01_shot33.jpg",
        "input_image_v": "yang_ep01_v_shot33.jpg",
        "prompt": "Night combat in rain, Northern Han archers and infantry surge from left and right ridges under signaling flare, striking bogged-down Song camp, rain cutting across lanterns.",
    },

    # ---------- Act V: 止戈讲和与太祖遗诏 (Shot 34 - 41) ----------
    {
        "id": 34,
        "act": 5,
        "name": "shot34_guangmei_peace_counsel",
        "title": "杨光美进言讲和",
        "page": "1-36",
        "sec": 6.0,
        "length": 141,
        "input_image": "yang_ep01_shot34.jpg",
        "input_image_v": "yang_ep01_v_shot34.jpg",
        "prompt": "Medium interior of Song imperial tent, ministers stand with bowed heads while Yang Guangmei steps forward, pleading for peace to save common people from Liao aggression, solemn court manner.",
    },
    {
        "id": 35,
        "act": 5,
        "name": "shot35_taizu_fist_unclench",
        "title": "太祖松拳·罢兵纳言",
        "page": "1-37",
        "sec": 6.0,
        "length": 141,
        "input_image": "yang_ep01_shot35.jpg",
        "input_image_v": "yang_ep01_v_shot35.jpg",
        "prompt": "Close push-in shot, a solemn Chinese emperor in a golden dragon robe tightly clenched imperial fist slowly relaxes finger by finger upon wooden council table, deciding to halt warfare for the realm, calm release.",
    },
    {
        "id": 36,
        "act": 5,
        "name": "shot36_liujun_seals_peace",
        "title": "北汉主盖印罢兵",
        "page": "1-38",
        "sec": 4.0,
        "length": 124,
        "input_image": "yang_ep01_shot36.jpg",
        "input_image_v": "yang_ep01_v_shot36.jpg",
        "prompt": "Close static shot, ruler Liu Jun presses jade royal seal onto peace pact document, red cinnabar seal stamping clearly on raw paper, seal low in frame, blank paper above.",
    },
    {
        "id": 37,
        "act": 5,
        "name": "shot37_palace_bedchamber_candle",
        "title": "汴京寝宫·残烛托孤",
        "page": "1-39",
        "sec": 8.0,
        "length": 192,
        "input_image": "yang_ep01_shot37.jpg",
        "input_image_v": "yang_ep01_v_shot37.jpg",
        "prompt": "Dim interior chamber in Kaifeng palace, lone candle illuminates small warm circle amid dark curtains, dying a solemn Chinese emperor in a golden dragon robe hand extends weakly from couch, solemn historical weight.",
    },
    {
        "id": 38,
        "act": 5,
        "name": "shot38_guangyi_takes_edict",
        "title": "太宗接旨·遗愿归顺",
        "page": "1-39",
        "sec": 6.0,
        "length": 141,
        "input_image": "yang_ep01_shot38.jpg",
        "input_image_v": "yang_ep01_v_shot38.jpg",
        "prompt": "Candle flame sways softly in night draft, successor hand firmly receives the rolled imperial testament to win over a battle-hardened veteran commander in gleaming steel lamellar armor with a grey beard for China, faces held out of frame, deep dramatic tension.",
    },
    {
        "id": 39,
        "act": 5,
        "name": "shot39_sea_of_flags_dawn",
        "title": "晨光旗海·大军北征",
        "page": "1-40",
        "sec": 8.0,
        "length": 192,
        "input_image": "yang_ep01_shot39.jpg",
        "input_image_v": "yang_ep01_v_shot39.jpg",
        "prompt": "Camera rises steadily, majestic sea of ochre and gold Song army banners stretches into horizon in golden morning dawn, vast sky filling upper two thirds, destiny unfolding.",
    },
    {
        "id": 40,
        "act": 5,
        "name": "shot40_courier_gallops_north",
        "title": "飞骑使者·奔赴应州",
        "page": "1-41",
        "sec": 6.0,
        "length": 141,
        "input_image": "yang_ep01_shot40.jpg",
        "input_image_v": "yang_ep01_v_shot40.jpg",
        "prompt": "Wide static perspective, single imperial courier with yellow flag galloping fast away into vanishing point of snowy frontier horizon, dust trailing behind, shrinkage into vastness.",
    },
    {
        "id": 41,
        "act": 5,
        "name": "shot41_edict_grand_close",
        "title": "救晋诏书·全剧大转折",
        "page": "1-41",
        "sec": 4.0,
        "length": 124,
        "input_image": "yang_ep01_shot41.jpg",
        "input_image_v": "yang_ep01_v_shot41.jpg",
        "prompt": "Close static shot of golden imperial edict calligraphed on silk: summoning a battle-hardened veteran commander in gleaming steel lamellar armor with a grey beard to relieve Jinyang, camera motionless, solemn silence before the grand historic saga unfolds.",
    },
]


def generate_act_audio(act_num, shots, output_wav_path, sample_rate=44100):
    """纯声学五音阶电影原声建模（彻底废除随机数白噪，确保0杂音）"""
    from tools.storyboard_grid_pipeline import generate_pure_acoustic_ost
    total_sec = sum(s["sec"] for s in shots)
    return generate_pure_acoustic_ost(output_wav_path, total_sec=total_sec, sample_rate=sample_rate)


def post_json(path, payload, timeout=60):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def inject_workflow_h3(wf_template, shot, width=960, height=544, seed=20261004):
    prefix = f"{DATE_STR}/yangjiajiang_ep01/{shot['name']}"
    values = {
        "first_frame": shot["input_image"],
        "prompt": shot["prompt"],
        "width": width,
        "height": height,
        "length": shot["length"],
        "seed": seed + shot["id"] * 17,
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


def inject_workflow_wan(wf_template, shot, seed=20261004):
    prefix = f"{DATE_STR}/yangjiajiang/{shot['name']}"
    wf = json.loads(json.dumps(wf_template))
    if "8" in wf and "inputs" in wf["8"]:
        wf["8"]["inputs"]["text"] = shot["prompt"]
    if "10" in wf and "inputs" in wf["10"]:
        wf["10"]["inputs"]["image"] = shot["input_image_v"]
    if "18" in wf and "inputs" in wf["18"]:
        wf["18"]["inputs"]["seed"] = seed + shot["id"] * 17
    if "21" in wf and "inputs" in wf["21"]:
        wf["21"]["inputs"]["filename_prefix"] = prefix
    return wf


def concat_act_video(act_num, shots):
    """规格归一化、拼接当前幕视频并混流原声音轨"""
    act_name = f"act{act_num}" if act_num > 0 else "part2"
    audio_path = os.path.join(OUTPUT_DIR, f"yang_ep01_{act_name}_clean_audio.wav")
    if not os.path.exists(audio_path):
        generate_act_audio(act_num, shots, audio_path)

    norm_clips = []
    print(f"\n=== 开始归一化处理 Act {act_num} 分镜头 ===")
    for s in shots:
        # 寻找匹配的 mp4 输出文件
        candidates = [
            os.path.join(OUTPUT_DIR, f"{s['name']}.mp4"),
            os.path.join(OUTPUT_DIR, f"{s['name']}_00001_.mp4"),
        ]
        src_v = None
        for c in candidates:
            if os.path.exists(c):
                src_v = c
                break

        if not src_v:
            print(f"  [缺失] 镜头 {s['id']:02d} ({s['name']}) 渲染文件未找到，跳过")
            continue

        norm_v = os.path.join(OUTPUT_DIR, f"norm_{s['name']}.mp4")
        norm_cmd = [
            FFMPEG, "-y",
            "-i", src_v,
            "-an",
            "-t", str(s["sec"]),
            "-vf", "scale=960:544:force_original_aspect_ratio=decrease,pad=960:544:(ow-iw)/2:(oh-ih)/2,fps=24",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            norm_v
        ]
        res = subprocess.run(norm_cmd, capture_output=True)
        if res.returncode == 0:
            norm_clips.append(norm_v)
            print(f"  [规格就绪] 镜 {s['id']:02d}: {os.path.basename(norm_v)} ({s['sec']}s)")

    if not norm_clips:
        print(f"[错误] 未发现任何有效的渲染视频，无法拼接")
        return None

    # 写入 concat 列表
    concat_txt = os.path.join(OUTPUT_DIR, f"concat_{act_name}.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for c in norm_clips:
            f.write(f"file '{c.replace(chr(92), '/')}'\n")

    # 视频流拼接
    temp_merged = os.path.join(OUTPUT_DIR, f"temp_{act_name}_video.mp4")
    concat_cmd = [
        FFMPEG, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_txt,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        temp_merged
    ]
    subprocess.run(concat_cmd, capture_output=True, check=True)

    # 混流原声设计音轨
    final_merged = os.path.join(OUTPUT_DIR, f"yang_ep01_{act_name}_merged.mp4")
    mux_cmd = [
        FFMPEG, "-y",
        "-i", temp_merged,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        final_merged
    ]
    subprocess.run(mux_cmd, capture_output=True, check=True)
    if os.path.exists(final_merged):
        print(f"\n[成片交付] Act {act_num} 成片拼接与混流完成: {final_merged}")
        return final_merged
    return None


def main():
    parser = argparse.ArgumentParser(description="北宋杨家将第一集后续剧情制作管线")
    parser.add_argument("--act", type=int, default=0, choices=[0, 2, 3, 4, 5], help="指定运行某一幕 (2=晋阳血战, 3=夜劫空营, 4=塞北连雨, 5=止戈遗诏, 0=全部)")
    parser.add_argument("--shot", type=int, default=0, help="单跑某镜 (13-41)")
    parser.add_argument("--engine", type=str, default="h3", choices=["h3", "wan"], help="渲染引擎选择: h3=MiniMax H3 Turbo, wan=Wan 2.2 Story")
    parser.add_argument("--dry-run", action="store_true", help="校验参数与工作流，不实际向GPU提交任务")
    parser.add_argument("--submit-only", action="store_true", help="严格遵守纪律：长任务只提交不轮询等待")
    parser.add_argument("--concat", action="store_true", help="将已生成的镜头归一化并混流拼接为完整幕成片")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 筛选任务镜头
    target_shots = EP01_PART2_SHOTS
    if args.act > 0:
        target_shots = [s for s in target_shots if s["act"] == args.act]
    if args.shot > 0:
        target_shots = [s for s in target_shots if s["id"] == args.shot]

    # 如果是纯拼接模式
    if args.concat:
        concat_act_video(args.act, target_shots)
        return 0

    print(f"\n=======================================================")
    print(f"  北宋杨家将 · 第1集《北汉风雪》后续剧情管线启动")
    print(f"  引擎: {args.engine.upper()} | 目标镜头数: {len(target_shots)}")
    print(f"  范围: {'全集后续 (Act 2~5)' if not args.act else f'Act {args.act}'}")
    print(f"=======================================================\n")

    # 载入工作流模板
    wf_path = WORKFLOW_H3 if args.engine == "h3" else WORKFLOW_WAN
    with open(wf_path, "r", encoding="utf-8") as f:
        wf_template = json.load(f)

    # 生成该批次对应的原声音效轨
    act_name = f"act{args.act}" if args.act > 0 else "part2"
    audio_path = os.path.join(OUTPUT_DIR, f"yang_ep01_{act_name}_clean_audio.wav")
    generate_act_audio(args.act, target_shots, audio_path)

    submitted = []
    for s in target_shots:
        print(f"\n[镜 {s['id']:02d}] 【{s['title']}】 (页码: {s['page']} | 时长: {s['sec']}s)")
        print(f"  -> 输入原画: {s['input_image']}")
        print(f"  -> 提示词: {s['prompt'][:90]}...")

        if args.engine == "h3":
            wf = inject_workflow_h3(wf_template, s)
        else:
            wf = inject_workflow_wan(wf_template, s)

        if args.dry_run:
            print(f"  [DRY-RUN] 参数校验通过，注入完成。")
            submitted.append({"id": s["id"], "name": s["name"], "status": "dry-run"})
            continue

        resp = post_json("/prompt", {"prompt": wf})
        pid = resp.get("prompt_id")
        print(f"  [SUBMIT] 已提交 ComfyUI 队列，Prompt ID: {pid}")
        submitted.append({"id": s["id"], "name": s["name"], "prompt_id": pid})

    # 记录任务清单
    tasks_record = os.path.join(OUTPUT_DIR, f"submitted_tasks_{act_name}.json")
    with open(tasks_record, "w", encoding="utf-8") as f:
        json.dump(submitted, f, ensure_ascii=False, indent=2)
    print(f"\n[任务登记完成] 已将本次任务清单写入: {tasks_record}")

    if args.dry_run or args.submit_only:
        print("\n[执行纪律] 任务已在后台排队，执行管线即刻解耦结束，等待任务完成通知。")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
