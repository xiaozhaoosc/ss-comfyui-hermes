#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""北宋杨家将 · 影视级古风字幕与人物战局注解生成器

功能：
1. 【自动时间轴生成】依据分镜清单自动计算毫秒级精准时序，生成标准 SRT / ASS 电影字幕文件。
2. 【古风连环画字幕】采用经典楷体（KaiTi）、暖象牙白字身、墨色微描边，完美契合上美影水墨画风。
3. 【人物登场与战局注疏】支持重要人物登场（如杨业、赵匡胤、潘仁美、高怀德）印章名片与战役时空背景注解卡。
4. 【ffmpeg 一键烧录】无损将字幕与注解烧录至 MP4 视频，全播放器即开即看。
"""

import os
import sys
import subprocess

ROOT = r"D:\ai_projects\ComfyUI"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
if not os.path.exists(FFMPEG):
    import shutil
    FFMPEG = shutil.which("ffmpeg") or "ffmpeg"

FONT_KAI = r"C:\Windows\Fonts\simkai.ttf"

# 全集分镜解说词与注解元数据
EP01_SUBTITLES = [
    # Act I
    {"id": 1, "sec": 6.0, "sub": "开宝二年，宋太祖亲率大军，兵逼北汉太原城下。", "tag": "【开宝二年 · 塞北风雪】"},
    {"id": 2, "sec": 4.0, "sub": "残碑卧雪，风卷黄沙，晋阳自古兵家必争之地。", "tag": None},
    {"id": 3, "sec": 4.0, "sub": "北汉建雄军节度使杨业，镇守关隘，号称‘无敌’。", "tag": "【杨 业】· 建雄军节度使"},
    {"id": 4, "sec": 4.0, "sub": "朱砂画戟，寒甲凝霜，宋军铁骑连营百里。", "tag": None},
    {"id": 5, "sec": 4.0, "sub": "一轮冷日出群山，战云密布杀气腾。", "tag": None},
    {"id": 6, "sec": 4.0, "sub": "边关告急，狼烟四起。", "tag": None},
    {"id": 7, "sec": 3.0, "sub": "北宋杨家将 · 第一集《北汉风雪》", "tag": None},
    {"id": 8, "sec": 4.0, "sub": "天明破晓，寒风刺骨，两军对峙不发。", "tag": None},
    {"id": 9, "sec": 8.0, "sub": "北汉烽火台巍然耸立，哨楼金铎鸣响。", "tag": "【太原要塞 · 晋阳关】"},
    {"id": 10, "sec": 6.0, "sub": "‘杨’字战旗迎风猎猎，军容肃穆整齐。", "tag": None},
    {"id": 11, "sec": 4.0, "sub": "铁画银钩，金戈铁马，威震塞北三十州。", "tag": None},
    {"id": 12, "sec": 9.0, "sub": "哨卒按刀远眺，一场恶战在所难免！", "tag": None},

    # Act II
    {"id": 13, "sec": 4.0, "sub": "北汉两路精骑出营，左右包抄接敌。", "tag": "【晋阳血战 · 双龙谷】"},
    {"id": 14, "sec": 4.0, "sub": "两军铁骑迎头冲撞，刀枪激荡，杀声震天！", "tag": None},
    {"id": 15, "sec": 8.0, "sub": "乱军中利箭破空！杨家战马人立而起，利齿一口衔住来袭雕翎！", "tag": "【战阵神骏 · 衔箭护主】"},
    {"id": 16, "sec": 4.0, "sub": "短兵相接，宋军先锋与北汉铁骑血战在一处。", "tag": None},
    {"id": 17, "sec": 4.0, "sub": "杨业拍马赶到，金刀一展，挑落先锋潘仁美！", "tag": "【潘仁美】· 宋军前锋副将"},
    {"id": 18, "sec": 4.0, "sub": "潘仁美狼狈跌入泥泞，回望杨业背影，暗怀恨毒之意。", "tag": None},
    {"id": 19, "sec": 4.0, "sub": "两侧高崖伏兵齐发，滚木礌石截断宋军后续归路。", "tag": "【两路伏兵 · 大破先锋】"},

    # Act III
    {"id": 20, "sec": 8.0, "sub": "太祖御帐之外，暗夜沉沉。太祖背手观天，欲行劫营之策。", "tag": "【赵匡胤】· 宋太祖皇帝"},
    {"id": 21, "sec": 4.0, "sub": "杨业识破玄机，夜入中军大帐。", "tag": None},
    {"id": 22, "sec": 4.0, "sub": "帅案之上画圈布阵：今夜腾空后营，设炮伏兵以待。", "tag": "【巧设空营 · 引敌入瓮】"},
    {"id": 23, "sec": 4.0, "sub": "宋军敢死勇士夜摸空营，四野寂无一人，顿觉中计！", "tag": None},
    {"id": 24, "sec": 6.0, "sub": "轰然炮响，火光冲天！夜雾迷漫中，宋军两路兵马自相误杀！", "tag": "【自相践踏 · 溃不成军】"},
    {"id": 25, "sec": 4.0, "sub": "信炮再发，杨家铁骑自两侧山冈掩杀而下！", "tag": None},
    {"id": 26, "sec": 4.0, "sub": "大将高怀德负伤还营，泥血满甲，伏地请罪。", "tag": "【高怀德】· 宋军开国宿将"},
    {"id": 27, "sec": 8.0, "sub": "太祖仰望北方星斗，浩然长叹：‘得此虎将，何愁天下不归一统！’", "tag": "【太祖惜才 · 志在天下】"},

    # Act IV
    {"id": 28, "sec": 8.0, "sub": "塞北连阴雨，苦战数月，天地尽是一片泥泞萧索。", "tag": "【晋阳困局 · 阴雨连绵】"},
    {"id": 29, "sec": 4.0, "sub": "北汉军士居高临下，早储干柴干粮，阵脚不动如山。", "tag": None},
    {"id": 30, "sec": 4.0, "sub": "宋太祖帐外跺靴长叹，雨水浇熄炉灶，粮道难行。", "tag": None},
    {"id": 31, "sec": 6.0, "sub": "宋军士卒饥寒交迫，蜷伏枯柳之下，士气低落。", "tag": None},
    {"id": 32, "sec": 6.0, "sub": "杨业登高遥望，借风雨之势调度诸子，再布伏兵。", "tag": None},
    {"id": 33, "sec": 4.0, "sub": "红信炮冲天炸响，风雨之中北汉铁骑踏泥破敌！", "tag": "【借雨破敌 · 奠定相持】"},

    # Act V
    {"id": 34, "sec": 6.0, "sub": "北汉参军杨光美进言讲和：辽邦窥伺于北，南北息兵方合生民之福。", "tag": "【杨光美】· 北汉直言之臣"},
    {"id": 35, "sec": 6.0, "sub": "太祖皇帝深思天下大局，紧握之龙拳缓缓松开，传旨暂息兵戈。", "tag": "【罢兵讲和 · 暂缓兵锋】"},
    {"id": 36, "sec": 4.0, "sub": "北汉主刘钧加盖玉印，两朝订盟罢战。", "tag": "【刘 钧】· 北汉国主"},
    {"id": 37, "sec": 8.0, "sub": "汴京寝殿，烛火摇曳。宋太祖病榻托孤，难忘太原杨无敌。", "tag": "【开宝九年 · 汴京寝殿】"},
    {"id": 38, "sec": 6.0, "sub": "晋王光义受旨接诏，太祖遗诏：‘务纳杨业归宋，保我北疆！’", "tag": "【宋太宗赵光义】· 受遗诏"},
    {"id": 39, "sec": 8.0, "sub": "太平兴国四年，晨光微曦，旌旗如海，大宋王师再启北伐之役！", "tag": "【太平兴国四年 · 挥师北伐】"},
    {"id": 40, "sec": 6.0, "sub": "飞骑黄幡使者，怀抱先帝亲笔诏书，绝尘奔赴应州！", "tag": None},
    {"id": 41, "sec": 4.0, "sub": "金色锦绢之上赫然写就——赦罪抚顺，封杨令公右领军卫大将军！", "tag": "【大义归宋 · 满门忠烈之始】"},
]

try:
    from tools.yangjiajiang_ep02_metadata import EP02_METADATA
    EP02_SUBTITLES = [{"id": s["id"], "sec": s["sec"], "sub": s["sub"], "tag": s["tag"]} for s in EP02_METADATA]
except Exception:
    EP02_SUBTITLES = []


def format_srt_time(seconds):
    """格式化秒数为 SRT 时间戳 00:00:00,000"""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    msecs = int(round((seconds - int(seconds)) * 1000))
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{msecs:03d}"


def generate_srt_file(shots_metadata, output_srt_path):
    """根据镜头时长生成标准 SRT 字幕文件"""
    cur_t = 0.0
    entries = []
    for idx, item in enumerate(shots_metadata, start=1):
        dur = item["sec"]
        t_start = cur_t
        t_end = cur_t + dur
        sub_text = item["sub"]

        entries.append(f"{idx}\n{format_srt_time(t_start)} --> {format_srt_time(t_end)}\n{sub_text}\n")
        cur_t = t_end

    os.makedirs(os.path.dirname(output_srt_path), exist_ok=True)
    with open(output_srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(entries))

    print(f"[字幕生成成功] 已生成标准字幕: {output_srt_path} (共 {len(entries)} 句)")
    return output_srt_path


def burn_subtitles_and_tags(input_video, output_video, shots_metadata):
    """使用 ffmpeg 将底部楷体字幕与右上角人物战局注解卡烧录至视频中"""
    srt_path = input_video.replace(".mp4", "_sub.srt")
    generate_srt_file(shots_metadata, srt_path)

    # 规范化 Windows 路径用于 ffmpeg subtitles 滤镜
    escaped_srt = srt_path.replace("\\", "/").replace(":", "\\:")
    escaped_font = FONT_KAI.replace("\\", "/").replace(":", "\\:")

    # 构建右上角人物战局注解 drawtext 滤镜链
    filter_parts = []
    # 1. 底部楷体电影字幕 (金石白字、深色微描边、居中底边距)
    sub_filter = (
        f"subtitles='{escaped_srt}':force_style="
        f"'FontName=KaiTi,FontSize=18,PrimaryColour=&H00F5F5DC,OutlineColour=&H00111111,"
        f"Outline=2,Shadow=1,MarginV=25,Alignment=2'"
    )
    filter_parts.append(sub_filter)

    # 2. 右上角战局/人物注解卡 (仅在存在 tag 的镜头区间显示)
    cur_t = 0.0
    for s in shots_metadata:
        dur = s["sec"]
        t_start = cur_t
        t_end = cur_t + dur
        tag = s.get("tag")
        if tag:
            # 持续时间为该镜头前 3.5 秒淡出，或者镜头全程
            display_end = min(t_start + 4.0, t_end)
            tag_text = tag.replace("'", "'\\''")
            draw_tag = (
                f"drawtext=fontfile='{escaped_font}':text='{tag_text}':"
                f"fontsize=15:fontcolor=white@0.95:box=1:boxcolor=black@0.45:boxborderw=6:"
                f"x=w-tw-30:y=30:enable='between(t,{t_start:.2f},{display_end:.2f})'"
            )
            filter_parts.append(draw_tag)
        cur_t += dur

    full_filter = ",".join(filter_parts)

    burn_cmd = [
        FFMPEG, "-y",
        "-i", input_video,
        "-vf", full_filter,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "19",
        "-c:a", "copy",
        output_video
    ]

    print(f"\n=== 开始烧录影视级楷体字幕与人物注疏卡: {os.path.basename(output_video)} ===")
    res = subprocess.run(burn_cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"[交付成功] 完整字幕注解版成片已输出: {output_video}")
        return output_video
    else:
        print(f"[烧录错误] {res.stderr[-400:]}")
        return None


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="字幕与人物战局注解烧录工具")
    parser.add_argument("--ep", type=int, default=1, help="指定集数 (1 或 2)")
    parser.add_argument("--act", type=int, default=2, help="指定幕次 (例如 1~5)")
    parser.add_argument("--grid", type=int, default=None, help="指定九宫格组号 (1~6)")
    parser.add_argument("--input", type=str, help="输入视频路径")
    parser.add_argument("--output", type=str, help="输出视频路径")
    args = parser.parse_args()

    if args.ep == 2:
        out_dir = os.path.join(ROOT, "output", "2026-10-08", "yangjiajiang_ep02")
        act_shot_ranges = {
            1: (1, 9),
            2: (10, 18),
            3: (19, 27),
            4: (28, 38),
            5: (39, 54),
        }
        all_subs = EP02_SUBTITLES
    else:
        out_dir = os.path.join(ROOT, "output", "2026-10-04", "yangjiajiang_ep01")
        act_shot_ranges = {
            1: (1, 12),
            2: (13, 19),
            3: (20, 27),
            4: (28, 33),
            5: (34, 41),
        }
        all_subs = EP01_SUBTITLES

    if args.grid is not None:
        start_id = (args.grid - 1) * 9 + 1
        end_id = args.grid * 9
    else:
        start_id, end_id = act_shot_ranges.get(args.act, act_shot_ranges[1])
    act_subs = [s for s in all_subs if start_id <= s["id"] <= end_id]

    in_v = args.input or os.path.join(out_dir, f"yang_ep0{args.ep}_act{args.act}_clean_merged.mp4")
    out_v = args.output or os.path.join(out_dir, f"yang_ep0{args.ep}_act{args.act}_annotated.mp4")

    if os.path.exists(in_v):
        burn_subtitles_and_tags(in_v, out_v, act_subs)
    else:
        print(f"未找到输入视频: {in_v}")
