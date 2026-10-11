#!/usr/bin/env python3
"""「赤壁夜袭」30s 预告片 — 6 段高清(1344x768) 视频+音频联合生成"""
import json, urllib.request, uuid, time

BASE_URL = "http://127.0.0.1:8188"

STYLE = ("写实主义战争史诗，新古典主义构图，HDR高动态范围光影。靛蓝墨黑夜色与赤金焰红火焰的极端冷暖对冲。"
         "35mm胶片颗粒感，浅景深，变形宽银幕，电影级调色。三国时期，长江赤壁，中国古代战船。")
NEGATIVE = ("不要现代元素、现代战舰、塑料桶、尼龙绳、钢结构、电线、现代发型、卡通风格、动漫渲染、游戏画面、"
            "低多边形、3D默认打光、科幻光泽、人物脸部变形、多余手指、肢体融化、漂浮武器、透明手、"
            "帧间变形、场景突然跳变、火炬频闪、过曝死白、旗帜文字乱码。")
HUANGGAI = "东吴老将黄盖，古铜色皮肤，花白络腮胡，额系暗红抹额，身披黑铁扎甲，眼神坚毅如铁。"
SHIP = "曹军铁索连环双体楼船，主帆为暗黄色粗麻布，上有黑色曹字古隶书。"
FIRE = "火焰内焰白蓝、外焰橙红的真实化学燃烧色温。"

SEGMENTS = [
    ("chibi_01_00-04_环境定场", 96,
     "超远景环境定场，夜空中孤月被浓雾遮蔽，长江江面漆黑如墨，远处曹军水寨连绵百里灯火点点如鬼火，"
     + SHIP + "镜头极缓慢向前推轨像潜行的猛兽，焦段从50mm标准镜头后拉至广角。"
     + "声音：开场全黑静默，随后极低频水流暗涌声缓缓升起，伴随一声遥远孤零零的铜锣定音。"),
    ("chibi_02_04-09_黄盖登场", 120,
     HUANGGAI + "面部大特写，他猛地拔掉火船船头油布遮盖，火把映红他满是刀刻般皱纹的脸，"
     + "眼部大特写切至手部动作特写。" + FIRE
     + "声音：定音鼓开始微弱滚奏速度极慢如心跳加速，火把在风中烈烈燃烧的爆裂声。"),
    ("chibi_03_09-15_舰队疾行", 144,
     "航拍俯视，数十艘蒙冲斗舰降下所有风帆，全员黑甲短刃如幽灵般在浓雾中破浪疾行，船桨整齐划一入水激起白色碎浪，"
     + "镜头从高空急速俯冲拉近。" + SHIP
     + "声音：弦乐演奏不和谐下行音阶制造极度不安感，鼓点加速变为三连音滚奏。"),
    ("chibi_04_15-22_火箭齐发", 168,
     HUANGGAI + "剑指前方一声暴喝口型可见，千弩齐发，火箭如逆飞的萤火虫群划破夜空照亮整条大江，"
     + "低机位拍摄火箭撞向曹军高耸楼船，船帆瞬间点燃，油布油脂剧烈燃烧形成巨大火墙。" + FIRE
     + "声音：火箭升空时屏息静默一秒，随后极其爆裂的金属撕裂声与爆炸低频，战鼓爆裂为疯狂快板，铜管奏响战斗号角。"),
    ("chibi_05_22-26_战旗坠落", 96,
     "升格慢动作，一面绣着巨大曹字的残破焦黑旗帜燃烧着从主桅杆顶端缓缓坠落，"
     + "镜头焦点从旗帜浅景深虚化，背景是混乱的火海与坠江士兵剪影。" + FIRE
     + "声音：战斗音效抽离，刺耳耳鸣声高频泛音切入，女声空灵吟唱单一长音浮现凄美肃杀。"),
    ("chibi_06_26-30_黑幕火影", 96,
     "黑幕切出，黑幕中巨大的火球倒影在江面波纹中摇曳，火光在水面上晃动。"
     + "声音：一声沉重的战鼓重击，接着是巨大的心跳声与画面同步落地。"),
]

with open("workflows/v1/h3_t2va_segment_audio.json", encoding="utf-8") as f:
    template = json.load(f)

submitted = []
for name, length, scene in SEGMENTS:
    wf = json.loads(json.dumps(template))
    wf["6"]["inputs"]["prompt"] = scene + " " + STYLE + " " + NEGATIVE
    wf["6"]["inputs"]["length"] = length
    wf["6"]["inputs"]["width"] = 1344
    wf["6"]["inputs"]["height"] = 768
    wf["10"]["inputs"]["filename_prefix"] = f"chibi_audio/{name}"
    wf["11"]["inputs"]["filename_prefix"] = f"chibi/{name}"
    payload = {"prompt": wf, "client_id": str(uuid.uuid4())}
    req = urllib.request.Request(f"{BASE_URL}/prompt", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
        pid = resp.get("prompt_id")
        submitted.append((name, length, pid))
        print(f"已提交 {name} (length={length}, 1344x768) -> {pid}")
    except Exception as e:
        print(f"提交失败 {name}: {e}")
    time.sleep(1)

print(f"\n=== 提交完成，共 {len(submitted)} 段 ===")
with open("workflows/v1/chibi_pids.json", "w", encoding="utf-8") as f:
    json.dump([{"name": n, "length": l, "pid": p} for n, l, p in submitted], f, ensure_ascii=False, indent=2)
print("prompt_ids 已保存到 workflows/v1/chibi_pids.json")
