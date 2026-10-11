# -*- coding: utf-8 -*-
"""裁掉水印 -> 压成 jpg -> 生成自包含的可播放试片 HTML。"""
import os, io, base64, json, traceback
from PIL import Image

BASE = r"D:\BaiduNetdiskDownload\北宋杨家将"
SRCDIR = os.path.join(BASE, "generated-images")
OUTDIR = os.path.join(BASE, "动画改编方案", "试片")
os.makedirs(OUTDIR, exist_ok=True)
LOG = os.path.join(BASE, r".workbuddy\_tmp\teaser.log")

SHOTS = [
    dict(n="01", src="上美影风格_上海美术电影制片厂复古手绘动画__中国传统手绘二_2026-09-13T13-31-09.png",
         ep="第 6 集《李陵碑·殉国》", sz="大远景", ang="俯 35°", mv="缓推（升）", sec=6,
         title="退守土岗",
         desc="土岗上只剩数十名残兵围坐成圈，都低着头。一人独立圈外，背对众人，甲裂三处，披风只剩一半，腰间空着没有佩刀。",
         vo="杨业死了，七郎也死了。可杨家这一门，还有一个人活着回来。",
         sfx="风声（唯一的声音）。战鼓与配乐已全部抽离。",
         move=("scale(1.02) translateY(1%)", "scale(1.10) translateY(-1%)"),
         note="本镜不给任何人的脸。要的是「人被大地吞掉」。"),
    dict(n="02", src="上美影风格_上海美术电影制片厂复古手绘动画__中国传统手绘二_2026-09-13T13-31-39.png",
         ep="第 6 集《李陵碑·殉国》", sz="特写", ang="俯 60°", mv="下摇", sec=6,
         title="见碑",
         desc="顺着人物的目光下摇到地面：一块残破石碑歪倒在赭石冻土里，碑面风化剥落，碑侧一株枯柳，枝条全断。地面覆一层很薄的雪。",
         vo="野地里，他有七座坟，一座碑。",
         sfx="风声。",
         move=("translateY(-4%) scale(1.06)", "translateY(5%) scale(1.06)"),
         note="镜 01 的俯角与镜 02 的下摇要连成一气——是「目光落下去」的物理动作。"),
    dict(n="03", src="上美影风格_上海美术电影制片厂复古手绘动画__中国传统手绘二_2026-09-13T13-32-05.png",
         ep="第 6 集《李陵碑·殉国》", sz="大特写", ang="平视", mv="横移", sec=7,
         title="碑面横移",
         desc="碑面占满整个画面。风化石纹，一道道被岁月磨平的横向刻痕——曾经有字，现在一个也认不出。画面右下角只残留半个字的凿痕。",
         vo="（无旁白。只有画面。）",
         sfx="风声在进入本镜时完全停止。无声两秒。",
         move=("translateX(-6%) scale(1.12)", "translateX(6%) scale(1.12)"),
         note="全片最重要的一次「减法」：把字抹掉。观众认不出，才会去想那上面原本刻的是什么。"),
    dict(n="04", src="上美影风格_上海美术电影制片厂复古手绘动画__中国传统手绘二_2026-09-13T13-32-29.png",
         ep="第 6 集《李陵碑·殉国》", sz="远景", ang="平视（越肩）", mv="缓升", sec=9,
         title="撞碑 · 全片风格高潮",
         desc="抽去全部颜色，只剩黑白与一点朱砂——那一点朱砂在刀穗上。碑前立着武将的背影，面向石碑，身形很小。刀插在土里，雪落得极轻。",
         vo="延昭。刀给你。",
         sfx="一声闷响（木头撞石，低沉、短促）→ 风，很长。",
         move=("translateY(6%) scale(1.04)", "translateY(-5%) scale(1.11)"),
         note="全片朱砂第二次出现，也是最吝啬的一次：只有刀穗那么一点。整镜其余部分严禁任何彩色。"),
    dict(n="05", src="上美影风格_上海美术电影制片厂复古手绘动画__中国传统手绘二_2026-09-13T13-34-12.png",
         ep="第 24 集《穆桂英挂帅》", sz="远景（同机位）", ang="平视", mv="固定不动", sec=12,
         title="碑前开花",
         desc="与镜 04／第 8 集完全相同的机位与构图。碑上现已刻满密密麻麻的名字；碑侧柳树活了、嫩绿；碑前那片荒坡开满细碎野花。刀仍插在土里，刀穗是整幅画中最鲜明的一抹朱砂红。",
         vo="——现在，碑前有花了。",
         sfx="埙。主题旋律《天波引》第三段完整呈现。全剧最后一次。",
         move=("scale(1.0)", "scale(1.03)"),
         note="全片最后一个镜头。空 12 秒，是全剧最长的空镜。三张李陵碑画面（无字／刻满名字／碑前开花）到此闭合。"),
    dict(n="06", src="上美影风格_上海美术电影制片厂复古手绘动画__中国传统手绘二_2026-09-13T13-33-15.png",
         ep="第 8 集《汴京审潘》", sz="特写", ang="平视", mv="固定不动", sec=4,
         title="枯柳新芽",
         desc="一截折断的枯柳枝从画面左下伸出，旧枝全断，最顶端抽出一小截新芽——嫩青瓷绿，只有两片稚叶。大片空白。",
         vo="（无旁白。）",
         sfx="风（唯一的声音）。",
         move=("scale(1.0)", "scale(1.04)"),
         note="第 8 集片尾三个空镜之末。它是「希望」在全剧第一次露头——比任何台词都早。"),
]

WATERMARK_CUT = 0.075   # 底部裁掉比例（去水印）
TARGET_W = 1280

def prep(idx, sh):
    p = os.path.join(SRCDIR, sh["src"])
    im = Image.open(p).convert("RGB")
    w, h = im.size
    im = im.crop((0, 0, w, int(h * (1 - WATERMARK_CUT))))
    w, h = im.size
    nw = TARGET_W
    nh = int(h * nw / w)
    im = im.resize((nw, nh), Image.LANCZOS)
    out = os.path.join(OUTDIR, "shot%02d.jpg" % (idx + 1))
    im.save(out, "JPEG", quality=84, optimize=True)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=84, optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return out, b64, nw, nh

def main():
    items = []
    for i, sh in enumerate(SHOTS):
        path, b64, w, h = prep(i, sh)
        items.append(dict(sh, path=path, b64=b64, w=w, h=h))
    return items

try:
    items = main()
    # 落一份 json 供 HTML 生成使用
    with open(os.path.join(BASE, r".workbuddy\_tmp\teaser_items.json"), "w", encoding="utf-8") as fh:
        json.dump([{k: v for k, v in it.items() if k != "b64"} for it in items], fh, ensure_ascii=False, indent=1)
    msg = "OK\n" + "\n".join("%s %s %dx%d %d KB" % (it["n"], os.path.basename(it["path"]), it["w"], it["h"],
                                                   os.path.getsize(it["path"]) // 1024) for it in items)
except Exception:
    msg = "FATAL\n" + traceback.format_exc()

with open(LOG, "w", encoding="utf-8") as fh:
    fh.write(msg)
