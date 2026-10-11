#!/usr/bin/env python3
"""烽火边关：24 段 × 5s ≈ 2 分钟 H3 视频生成（last_frame 首尾帧衔接 + 画质优化版）

基于 fenghuo 7 段实测扩展：
- 画质：width=960, height=544(540对齐32), 步数=28（已从 672×384×20步升级）
- 帧率：24fps, 每段 124 帧 ≈ 5.17s
- 衔接：第 1 段 t2v（不用 first_frame），第 2 段起以上一段末帧作为 first_frame
- 模型：minimax_h3_ref2va_pruned_int8_convrot + qwen3vl_32b + h3_video_vae_fp16

用法：
  python3 tools/build_h3_24segs.py            # 全部 24 段提交
  python3 tools/build_h3_24segs.py 0 3        # 只提交第 0~3 段（调试/分次）
  python3 tools/build_h3_24segs.py --estimate # 打印估算，不提交
"""
import json, urllib.request, uuid, time, sys, os

BASE = "http://127.0.0.1:8188"
OUT_DIR = r"D:\ai_projects\ComfyUI\output\fenghuo_24segs"

# ---------- 角色/风格全局（与 7 段 fenghuo 一致，便于参考） ----------
CHARACTER = ("年轻中国古代女将，深色重甲，头戴战盔，黑色长发，神情冷峻坚定，手握长刀，骑黑色战马。")
STYLE = ( "史诗级写实电影预告片质感，真实电影摄影，超高细节，真实皮肤毛发，真实盔甲冷兵器，"
 "体积光，烟尘风沙火光，冷暖对比，浅景深，电影级调色，IMAX史诗战争片。镜头自然流畅。"
 "避免AI生成感、人物变形、手部异常、武器结构错误、现代建筑、现代武器、现代服装、卡通游戏CG感。")

# ---------- 24 段 × 5s 分镜脚本 ----------
SEGMENTS = [
    # ---- 开篇：边疆 / 女将出场 (0-30s) ----
    ("seg01_0-5s_边城远景", 124,
     "超远景，苍茫中国北方边疆，夕阳即将落下，巨大古代边城矗立在荒漠与群山之间，城墙上旌旗被狂风吹动，远处烽火台燃起狼烟，镜头缓慢向前推进，气氛压抑肃杀。"),
    ("seg02_5-10s_女将登场", 124,
     "近景推近，" + CHARACTER + "静立在边城城门前，手握长刀，目光冷峻地望向远方，风掀起长发与衣袍，画面充满肃杀气息。"),
    ("seg03_10-15s_战马整装", 124,
     "特写，战马低头刨蹄嘶鸣，士兵们忙碌地搬运物资与武器，紧张备战气氛。"),
    ("seg04_15-20s_烽火列阵", 124,
     "高角度俯拍，金字塔形烽火台在秃山巅上，一列列火炬依次点燃，火舌与黑烟升上天空，气势磅礴。"),
    ("seg05_20-25s_夜幕降临", 124,
     "黄昏转夜，乌云遮蔽星空，寒风呼啸，城墙上的火把摇曳不定，防御工事暗藏不安。镜头缓慢下沉。"),
    ("seg06_25-30s_巡逻士兵", 124,
     "中景，3名古代铠甲士兵举火把沿城墙巡逻，脚步声回荡，警觉地望向黑暗深处，氛围紧张。"),
    ("seg07_30-35s_烽火冲天", 124,
     "特写，烽火台顶峰火焰与黑烟在空中爆燃，火光映亮周围的云层，充满罪恶感与预兆感。"),
    # ---- 冲突：敌军逼近 (30-60s) ----
    ("seg08_35-40s_敌军逼近", 124,
     "远景，黑色铁甲洪流在地平线上出现，数百丈烟尘滚滚而来，伴有马蹄与战鼓声，压迫感扑面而来。"),
    ("seg09_40-45s_号角齐鸣", 124,
     "特写，低沉号角在荒原上回响，敌军阵营士兵们齐齐举起武器，号角声震碎死寂。"),
    ("seg10_45-50s_哨兵回报", 124,
     "中景，一名哨兵从城墙上飞奔而下情绪激动大喊，女将转身接收急报眉头紧锁，整体信号紧张升级。"),
    ("seg11_50-55s_女将决定", 124,
     "近景，女将坚毅的表情凝视远方，握紧了悬挂在腰间的长刀，随后猛然转头准备迎战，气势凛然。"),
    ("seg12_55-60s_号令一出", 124,
     "远景，女将挥舞长刀发出号令，士兵们沸腾起来，战鼓擂动，万箭齐发准备迎敌，气氛达到高潮。"),
    # ---- 激战：箭雨 / 城墙 (60-90s) ----
    ("seg13_60-65s_箭雨齐发", 124,
     "大特写，弓箭手们神情专注拉满弓弦，数千支羽箭同时离弦呼啸而出，遮天蔽日的箭雨降下致命打击。"),
    ("seg14_65-70s_守城血战", 124,
     "激烈战争场面，城墙内外士兵们奋勇搏斗，刀光剑影火花四溅，血流成河，尸体满地，悲壮不已。"),
    ("seg15_70-75s_女将技击", 124,
     "中景，女将策马在人群中穿梭挥刀，一名敌军扑来被她轻易斩落，动作行云流水，毫不留情。"),
    ("seg16_75-80s_战鼓狂擂", 124,
     "特写，军士们大肆敲打战鼓，鼓声震耳欲聋，火光照亮每张扭曲的面孔，士气高涨。"),
    ("seg17_80-85s_云梯攻城", 124,
     "俯视，多架云梯搭上高大的城墙，士兵们奋力攀爬，弓矢如雨下，场面惨烈却壮观。"),
    ("seg18_85-90s_守城突破", 124,
     "中景，女将高举长刀大喊一声，数百名士兵同时冲出城门迎敌，战船撞击怒涛，气势磅礴。"),
    ("seg19_90-95s_烽火再燃", 124,
     "烽火台上的火焰被细心的士兵重新点燃，黑烟升起带来希望，燃烧的火光照亮废墟与血迹。"),
    ("seg20_95-100s_骑队冲锋", 124,
     "女将率领骑兵队发起冲锋，马蹄声狂奔如电，兵器挥舞激烈战斗，血流成河，画面极具冲击力。"),
    ("seg21_100-105s_决战将至", 124,
     "战争进入关键时刻，女将与敌军首领会面，双方千军万马对峙，视角紧绷而激烈，紧张感令人窒息。"),
    ("seg22_105-110s_残破长城", 124,
     "战场四处尸体遍野，破损的攻击器械，被毁的战车残骸斜立，血迹斑斑，凄凉至极。"),
    ("seg23_110-115s_停火令下", 124,
     "号角再次吹响，双方将领互相对视，部队停止厮杀张望，战场一片死寂，充满象征性与和平感。"),
    ("seg24_115-120s_英雄归来", 124,
     "全景，女将骑马缓缓前行，身后是百战百胜的soldiers威武阵型，夕阳照耀血染战场，充满英雄气概。"),
]

def post(path, payload):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())

def build(name, prompt_text, length, first_frame_path=None):
    """
    Build H3 workflow. If first_frame_path is provided, use LoadImage node.
    """
    wf = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors", "type": "minimax"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "4": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["1", 0], "shift_video": 12.0, "shift_audio": 3.0}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt_text}},
        "6": {"class_type": "KSampler", "inputs": {"model": ["4", 0], "seed": 42, "steps": 28, "cfg": 1.0,
              "sampler_name": "euler", "scheduler": "simple", "positive": ["5", 0], "negative": ["5", 0],
              "latent_image": ["5", 1], "denoise": 1.0}},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["3", 0]}},
        "8": {"class_type": "VHS_VideoCombine", "inputs": {
            "images": ["7", 0], "frame_rate": 24.0, "loop_count": 0,
            "filename_prefix": f"fenghuo_24segs/{name}", "format": "video/h264-mp4",
            "pingpong": False, "save_output": True}},
    }
    # Optional first frame for continuity
    if first_frame_path:
        # first_frame_path 是 PIL.Image 类型（_00007.png）
        wf["9"] = {"class_type": "LoadImage", "inputs": {"image": first_frame_path}}
        wf["5"]["inputs"]["first_frame"] = ["9", 0]
    return wf

def estimate(segs):
    # Per-segment estimate based on 960x544x28 steps measured ~28-38s/step => ~10min/段
    per_sec = 38
    per_steps = 28
    per_min = per_sec * per_steps / 60
    total_min = per_min * len(segs)
    return per_sec, per_steps, per_min, total_min

def main():
    if "--estimate" in sys.argv:
        per_sec, per_steps, per_min, total_min = estimate(SEGMENTS)
        print("=== 估算 ===")
        print(f"单段：每秒 {per_sec}s × {per_steps}步 = ~{per_min:.1f} 分钟")
        print(f"全部 24 段：约 {total_min:.0f} 分钟 = {total_min/60:.2f} 小时")
        print(f"输出目录: {OUT_DIR}/fenghuo_24segs/")
        return

    lo, hi = 0, len(SEGMENTS)
    args = [a for a in sys.argv[1:] if a.isdigit()]
    if len(args) >= 2:
        lo = int(args[0]); hi = int(args[1]) + 1
    elif len(args) == 1:
        lo = int(args[0]); hi = lo + 1
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"准备提交 第 {lo+1}~{hi} 段 (共 {hi-lo} 段)")
    submitted = []
    for idx, (name, length, scene) in enumerate(SEGMENTS):
        if idx < lo or idx >= hi: continue
        prompt = scene + " " + STYLE
        first_frame_path = None
        if idx > 0:
            prev_name = SEGMENTS[idx-1][0]
            prev_png = rf"{OUT_DIR}\{prev_name}\{prev_name}_00007.png"
            prev_png2 = rf"D:\ai_projects\ComfyUI\output\{prev_name}\{prev_name}_00007.png"
            if os.path.exists(prev_png):
                first_frame_path = prev_png.replace('\\', '/')
            elif os.path.exists(prev_png2):
                first_frame_path = prev_png2.replace('\\', '/')
        wf = build(name, prompt, length, first_frame_path)
        try:
            r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
            pid = r.get("prompt_id")
            submitted.append({"idx": idx, "name": name, "length": length, "pid": pid})
            print(f"✓ [{idx}] {name} length={length} first_frame={'√' if first_frame_path else '—'} pid={pid[:13]}", flush=True)
        except Exception as e:
            print(f"✗ [{idx}] {name} 提交失败: {e}", flush=True)
        time.sleep(1)
    with open(r"D:\ai_projects\ComfyUI\tools\h3_24segs_pids.json", "w", encoding="utf-8") as f:
        json.dump(submitted, f, ensure_ascii=False, indent=1)
    print(f"\n=== 已提交 {len(submitted)}/{hi-lo} 段 → {OUT_DIR} ===")

if __name__ == "__main__":
    main()
