#!/usr/bin/env python3
"""重跑 7 个分段，补生成 H3 原生音频（32kHz 立体声），同 seed=42 保证画面一致"""
import json, urllib.request, uuid, time

BASE_URL = "http://127.0.0.1:8188"

CHARACTER = "年轻中国古代女将，深色重甲，头戴战盔，黑色长发，神情冷峻坚定，手握长刀，骑黑色战马。"
STYLE = ("史诗级写实电影预告片质感，真实电影摄影，超高细节，真实皮肤毛发，真实盔甲冷兵器，"
         "体积光，烟尘风沙火光，冷暖对比，浅景深，电影级调色，IMAX史诗战争片。镜头自然流畅。"
         "避免AI生成感、人物变形、手部异常、武器结构错误、现代建筑、现代武器、现代服装、卡通游戏CG感。")

SEGMENTS = [
    ("seg01_0-4s_边城远景", 96,
     "超远景，苍茫中国北方边疆，夕阳即将落下，巨大古代边城矗立在荒漠与群山之间，城墙上旌旗被狂风吹动，远处烽火台燃起狼烟，镜头缓慢向前推进，气氛压抑肃杀。"),
    ("seg02_4-8s_女将奔马", 96,
     "快速近景，黑色战马在黄沙中高速奔跑，马蹄扬起漫天尘土，马背上是" + CHARACTER + "镜头从战马侧面高速跟拍，快速推近女将坚毅的眼神。"),
    ("seg03_8-12s_城门戒备", 96,
     "巨大古代城门缓缓关闭，大量中国古代铠甲士兵手持长刀长枪弓箭站在城墙和城门两侧神情紧张，" + CHARACTER + "骑马来到城门前猛然勒住战马，战马前蹄扬起嘶鸣，女将拔出长刀，刀刃在夕阳中闪过寒光。"),
    ("seg04_12-16s_战争爆发", 96,
     "大量敌军骑兵从远处荒漠冲锋而来漫天黄沙，城墙上的弓箭手同时拉满弓弦，特写手指松开弓弦，大量箭矢破空射出形成密集箭雨飞向远处冲锋的骑兵，镜头跟随一支箭矢高速飞行。"),
    ("seg05_16-21s_战争蒙太奇", 120,
     "高速战争蒙太奇，连续快速剪辑：" + CHARACTER + "骑马冲入战场挥刀斩向敌军，两名士兵近距离挥刀交锋刀剑猛烈碰撞迸发火花，盾牌被长枪撞击，战马从镜头前高速掠过，士兵在城墙上奔跑，箭矢不断从天空划过，火焰烟尘黄沙和飞舞的旗帜充满整个战场，充满压迫感和速度感。"),
    ("seg06_21-26s_女将蓄势", 120,
     "战场短暂安静，" + CHARACTER + "独自骑马站在漫天黄沙之中，身后是燃烧的烽火和残破的城墙，缓缓抬起手中的长刀，风吹动战旗，镜头从背后缓慢推进最终切换到坚定而冷峻的正面特写。"),
    ("seg07_26-30s_骑兵冲锋", 96,
     "最终高潮，" + CHARACTER + "率领大量骑兵向敌军发起冲锋，数百匹战马同时奔腾，马蹄震动大地，黄沙漫天，镜头从低机位拍摄战马冲过镜头再快速升至高空，展现宏大的古代战场，定格在女将挥刀冲锋的瞬间。"),
]

with open("workflows/v1/h3_t2va_segment_audio.json", encoding="utf-8") as f:
    template = json.load(f)

submitted = []
for name, length, scene in SEGMENTS:
    wf = json.loads(json.dumps(template))
    wf["6"]["inputs"]["prompt"] = scene + " " + STYLE
    wf["6"]["inputs"]["length"] = length
    wf["10"]["inputs"]["filename_prefix"] = f"fenghuo_audio/{name}"
    wf["11"]["inputs"]["filename_prefix"] = f"fenghuo/{name}"
    payload = {"prompt": wf, "client_id": str(uuid.uuid4())}
    req = urllib.request.Request(f"{BASE_URL}/prompt", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
        pid = resp.get("prompt_id")
        submitted.append((name, length, pid))
        print(f"已提交 {name} (length={length}) -> {pid}")
    except Exception as e:
        print(f"提交失败 {name}: {e}")
    time.sleep(1)

print()
print(f"=== 提交完成，共 {len(submitted)} 个分段 ===")
with open("workflows/v1/h3_audio_pids.json", "w", encoding="utf-8") as f:
    json.dump([{"name": n, "length": l, "pid": p} for n, l, p in submitted], f, ensure_ascii=False, indent=2)
print("prompt_ids 已保存到 workflows/v1/h3_audio_pids.json")
