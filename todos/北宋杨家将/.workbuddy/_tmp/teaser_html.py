# -*- coding: utf-8 -*-
"""生成自包含的可播放六镜试片 HTML（图片 base64 内嵌，含运镜模拟）。"""
import os, io, base64, traceback
from PIL import Image

BASE = r"D:\BaiduNetdiskDownload\北宋杨家将"
SRCDIR = os.path.join(BASE, "generated-images")
OUTDIR = os.path.join(BASE, "动画改编方案", "试片")
os.makedirs(OUTDIR, exist_ok=True)
LOG = os.path.join(BASE, r".workbuddy\_tmp\teaser_html.log")

STYLE_LINE = ("上海美术电影制片厂经典手绘动画风格，手绘墨线轮廓，水粉平涂上色、保留颜料笔触与手工感，"
              "矿物颜料色（赭石、月白、青瓷绿、墨黑、朱砂红），概括造型，胶片颗粒感，"
              "不要3D渲染、不要写实感、不要体积光")

SHOTS = [
 dict(n="01", src="上美影风格_上海美术电影制片厂复古手绘动画__中国传统手绘二_2026-09-13T13-31-09.png",
   ep="第 6 集《李陵碑 · 殉国》", sz="大远景", ang="俯 35°", mv="缓推（升镜头）", sec=6, title="退守土岗",
   desc="土岗上只剩数十名残兵围坐成圈，都低着头。一人独立圈外，背对众人，甲裂三处，披风只剩一半，腰间空着没有佩刀。地面覆一层很薄的雪。",
   vo="杨业死了，七郎也死了。可杨家这一门，还有一个人活着回来。",
   sfx="风声（唯一的声音）。战鼓与配乐已全部抽离。",
   frm="scale(1.02) translateY(1%)", to="scale(1.10) translateY(-1%)",
   note="本镜不给任何人的脸。要的是「人被大地吞掉」。",
   sd=["0-3秒：荒坡远景建立 - 缓慢推镜头，赭石色冻土上覆一层薄雪，远处青瓷绿层叠远山，平涂色块分割画面，胶片颗粒感",
       "3-5秒：数十名残兵围坐成圈，甲胄残破，都低着头 - 镜头继续缓推，人物在画面中极小，压在下三分之一",
       "5-6秒：独立于圈外的一人背影 - 镜头停住，只剩他被风吹动的残破披风，大面积留白天空",
       "【声音】只生成音效，不要生成音乐。不要生成任何字幕。风声，由远及近。",
       "【参考】@图片1 场景与画风参考，严格保持参考图片的手绘动画画风与色盘"]),
 dict(n="02", src="上美影风格_上海美术电影制片厂复古手绘动画__中国传统手绘二_2026-09-13T13-31-39.png",
   ep="第 6 集《李陵碑 · 殉国》", sz="特写", ang="俯 60°", mv="下摇", sec=6, title="见碑",
   desc="顺着人物的目光下摇到地面：一块残破石碑歪倒在赭石冻土里，碑面风化剥落，碑侧一株枯柳，枝条全断。",
   vo="野地里，他有七座坟，一座碑。",
   sfx="风声。",
   frm="translateY(-4%) scale(1.06)", to="translateY(5%) scale(1.06)",
   note="镜 01 的俯角与镜 02 的下摇连成一气——是「目光落下去」的物理动作。",
   sd=["0-2秒：荒坡地面 - 镜头缓慢下摇，赭石色冻土与月白色薄雪，手绘墨线勾勒的石块，平涂色块",
       "2-5秒：一块残破石碑歪倒在土里，碑面严重风化剥落 - 镜头继续下摇，石碑进入画面中心，碑侧一株枯柳枝条全断",
       "5-6秒：碑面停住 - 镜头静止，大面积留白，只余淡淡的胶片颗粒感",
       "【声音】只生成音效，不要生成音乐。不要生成任何字幕。风声。",
       "【参考】@图片1 场景与画风参考，严格保持参考图片的手绘动画画风与色盘"]),
 dict(n="03", src="上美影风格_上海美术电影制片厂复古手绘动画__中国传统手绘二_2026-09-13T13-32-05.png",
   ep="第 6 集《李陵碑 · 殉国》", sz="大特写", ang="平视", mv="横移", sec=7, title="碑面横移",
   desc="碑面占满整个画面。风化石纹，一道道被岁月磨平的横向刻痕——曾经有字，现在一个也认不出。右下角只残留半个字的凿痕。",
   vo="（无旁白。只有画面。）",
   sfx="风声在进入本镜时完全停止。无声两秒。",
   frm="translateX(-6%) scale(1.12)", to="translateX(6%) scale(1.12)",
   note="全片最重要的一次「减法」：把字抹掉。观众认不出，才会去想那上面原本刻的是什么。",
   sd=["0-3秒：石碑碑面占满画面 - 镜头缓慢横向移镜，粗糙的风化石质肌理，墨线勾出的凿痕与裂纹，赭石色平涂",
       "3-6秒：一道道被岁月磨平的横向刻痕划过 - 镜头继续横移，曾刻过字但字口已平，像被水刷了很多年",
       "6-7秒：画面右下角残留半个字的凿痕轮廓 - 镜头缓停，静止",
       "【声音】只生成音效，不要生成音乐。不要生成任何字幕。风声在开头即切断，中段完全无声，结尾只有一缕风。",
       "【参考】@图片1 质感与画风参考，严格保持参考图片的手绘动画画风与色盘"]),
 dict(n="04", src="上美影风格_上海美术电影制片厂复古手绘动画__中国传统手绘二_2026-09-13T13-32-29.png",
   ep="第 6 集《李陵碑 · 殉国》", sz="远景", ang="平视（越肩）", mv="缓升", sec=9, title="撞碑 · 全片风格高潮",
   desc="抽去全部颜色，只剩黑白与一点朱砂——那一点朱砂在刀穗上。碑前立着武将的背影，面向石碑，身形很小。刀插在土里，雪落得极轻。",
   vo="延昭。刀给你。",
   sfx="一声闷响（木头撞石，低沉、短促）→ 风，很长。",
   frm="translateY(6%) scale(1.04)", to="translateY(-5%) scale(1.11)",
   note="全片朱砂第二次出现，也是最吝啬的一次：只有刀穗那么一点。整镜其余部分严禁任何彩色。",
   sd=["0-4秒：纯黑白水墨画面，碑前一个武将背影 - 镜头自人物背后缓缓升起，越过他的肩，对着石碑，身形很小，大面积留白",
       "4-7秒：碑旁土里插着一杆长刀，刀穗在风中微扬 - 镜头继续缓升，画面中唯一的彩色就是那一点朱砂红",
       "7-9秒：极淡的雪慢慢落下 - 镜头停住，黑、白、灰三色基调，古本木刻插图质感",
       "【声音】只生成音效，不要生成音乐。不要生成任何字幕。风声在末段抽走，只留一声低沉短促的闷响。",
       "【参考】@图片1 画风参考，严格保持参考图片的手绘水墨画风，全画面仅黑白灰加一点朱砂"]),
 dict(n="05", src="上美影风格_上海美术电影制片厂复古手绘动画__中国传统手绘二_2026-09-13T13-34-12.png",
   ep="第 24 集《穆桂英挂帅》", sz="远景（同机位）", ang="平视", mv="固定不动", sec=12, title="碑前开花",
   desc="与镜 04／第 8 集完全相同的机位与构图。碑上现已刻满密密麻麻的名字；碑侧柳树活了、嫩绿；碑前那片荒坡开满细碎野花。刀仍插在土里，刀穗是整幅画中最鲜明的一抹朱砂红。",
   vo="—— 现在，碑前有花了。",
   sfx="埙。主题旋律《天波引》第三段完整呈现。全剧最后一次。",
   frm="scale(1.0)", to="scale(1.03)",
   note="全片最后一个镜头。空 12 秒，是全剧最长的空镜。三张李陵碑画面到此闭合。",
   sd=["0-6秒：空旷的荒坡远景，地平线压在下四分之一处 - 镜头固定不动，上方大片空白天空，平涂色块与胶片颗粒感",
       "6-10秒：碑身上刻满了密密麻麻的竖排名字，碑侧柳树抽出嫩绿新叶，碑前开满细碎野花 - 镜头仍固定不动",
       "10-12秒：插在土里的长刀，刀穗是画面中最鲜明的一抹朱砂红，在风中微扬 - 镜头保持固定",
       "【声音】只生成音效，不要生成音乐。不要生成任何字幕。风穿过柳叶的声音，极轻。",
       "【参考】@图片1 场景与画风参考，严格保持参考图片的手绘动画画风与色盘"]),
 dict(n="06", src="上美影风格_上海美术电影制片厂复古手绘动画__中国传统手绘二_2026-09-13T13-33-15.png",
   ep="第 8 集《汴京审潘》", sz="特写", ang="平视", mv="固定不动", sec=4, title="枯柳新芽",
   desc="一截折断的枯柳枝从画面左下伸出，旧枝全断，最顶端抽出一小截新芽——嫩青瓷绿，只有两片稚叶。大片空白。",
   vo="（无旁白。）",
   sfx="风（唯一的声音）。",
   frm="scale(1.0)", to="scale(1.04)",
   note="第 8 集片尾三个空镜之末。它是「希望」在全剧第一次露头——比任何台词都早。",
   sd=["0-2秒：一截折断的枯柳枝从画面左下伸出，墨黑粗线勾画，旧枝全断 - 镜头固定不动，背景为大面积空白",
       "2-4秒：枝条最顶端抽出一小截新芽，嫩青瓷绿，只有两片稚叶 - 镜头极缓地推近一点，后又停住，平涂色块，没有阴影没有渐变",
       "【声音】只生成音效，不要生成音乐。不要生成任何字幕。风，唯一的声音。",
       "【参考】@图片1 画风参考，严格保持参考图片的手绘动画画风与色盘"]),
]

WATERMARK_CUT = 0.075
TARGET_W = 1280


def build_b64(src):
    im = Image.open(os.path.join(SRCDIR, src)).convert("RGB")
    w, h = im.size
    im = im.crop((0, 0, w, int(h * (1 - WATERMARK_CUT))))
    w, h = im.size
    im = im.resize((TARGET_W, int(h * TARGET_W / w)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=84, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii"), im.size


CSS = """
:root{--paper:#FBF8F1;--card:#FFFFFF;--ink:#231F19;--ink2:#4A443B;--ink3:#7A7266;
--line:#E3DCCC;--line2:#D2C8B2;--zhu:#B03A2E;--qing:#3E6B5A;--jin:#B8912B;}
*{box-sizing:border-box;}
body{margin:0;background:var(--paper);color:var(--ink);
font-family:"PingFang SC","Microsoft YaHei","Hiragino Sans GB",sans-serif;font-size:15px;line-height:1.8;}
.wrap{max-width:1120px;margin:0 auto;padding:0 24px 90px;}
h1{font-family:"Songti SC","SimSun",serif;font-size:32px;margin:44px 0 6px;letter-spacing:.03em;}
h1 small{display:block;font-size:15px;color:var(--ink2);font-weight:400;margin-top:10px;letter-spacing:.08em;}
h2{font-family:"Songti SC","SimSun",serif;font-size:21px;margin:44px 0 14px;padding-bottom:11px;
border-bottom:2px solid var(--ink);}
.lead{color:var(--ink2);border-left:3px solid var(--line2);padding-left:14px;margin:0 0 22px;}
/* ---- player ---- */
.player{background:#141210;border-radius:12px;padding:16px 16px 12px;box-shadow:0 8px 30px rgba(0,0,0,.18);}
.stage{position:relative;width:100%;aspect-ratio:16/9;background:#000;border-radius:7px;overflow:hidden;}
.stage img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;will-change:transform;}
.fade{position:absolute;inset:0;background:#000;opacity:0;transition:opacity .8s ease;pointer-events:none;}
.hud{position:absolute;left:0;right:0;top:0;padding:11px 15px;display:flex;gap:9px;flex-wrap:wrap;
background:linear-gradient(180deg,rgba(0,0,0,.55),transparent);}
.hud span{font-size:11.5px;color:#F2EDE3;background:rgba(0,0,0,.42);border:1px solid rgba(255,255,255,.16);
padding:2px 9px;border-radius:20px;letter-spacing:.02em;backdrop-filter:blur(2px);}
.hud span.k{color:#E8B44A;border-color:rgba(232,180,74,.4);}
.subs{position:absolute;left:0;right:0;bottom:0;padding:16px 20px 14px;
background:linear-gradient(0deg,rgba(0,0,0,.72),transparent);}
.subs p{margin:0 0 5px;color:#F5F1E8;font-size:14.5px;}
.subs p.vo{font-family:"Songti SC","SimSun",serif;font-size:16px;}
.subs p.sfx{font-size:12px;color:#9FC3A8;font-family:ui-monospace,Consolas,monospace;}
.bar{display:flex;align-items:center;gap:12px;margin-top:12px;}
.bar button{background:#2A2622;color:#F2EDE3;border:1px solid #453E37;border-radius:6px;
padding:7px 15px;font-size:13.5px;cursor:pointer;font-family:inherit;transition:.15s;}
.bar button:hover{background:#3A342E;border-color:var(--zhu);}
.bar button.main{background:var(--zhu);border-color:var(--zhu);font-weight:600;}
.track{flex:1;height:4px;background:#3A342E;border-radius:3px;overflow:hidden;}
.track i{display:block;height:100%;width:0;background:var(--zhu);transition:width .2s linear;}
.bar .t{color:#8C8378;font-size:12px;font-variant-numeric:tabular-nums;white-space:nowrap;}
/* ---- strip ---- */
.strip{display:grid;grid-template-columns:repeat(6,1fr);gap:9px;margin-top:16px;}
.strip div{cursor:pointer;border:2px solid transparent;border-radius:6px;overflow:hidden;position:relative;}
.strip div.on{border-color:var(--zhu);}
.strip img{width:100%;display:block;aspect-ratio:16/9;object-fit:cover;}
.strip span{position:absolute;left:5px;bottom:4px;font-size:11px;color:#fff;
background:rgba(0,0,0,.55);padding:1px 6px;border-radius:3px;}
/* ---- tables ---- */
.tw{overflow-x:auto;margin:0 0 20px;}
table{width:100%;border-collapse:collapse;background:var(--card);font-size:13px;line-height:1.7;
border:1px solid var(--line2);}
th,td{padding:8px 11px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top;}
thead th{background:var(--ink);color:#F7F3EA;font-size:12.5px;font-weight:600;border-bottom:none;}
tbody tr:nth-child(even){background:#FCFAF5;}
td.c{text-align:center;white-space:nowrap;font-variant-numeric:tabular-nums;}
.pal{display:flex;flex-wrap:wrap;gap:9px;margin:0 0 18px;}
.pal div{border:1px solid var(--line2);border-radius:6px;padding:7px 12px;background:var(--card);
font-size:13px;display:flex;align-items:center;gap:8px;}
.pal i{width:20px;height:20px;border-radius:4px;display:block;border:1px solid rgba(0,0,0,.12);}
.card{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--zhu);
border-radius:8px;padding:15px 19px;margin-bottom:16px;}
.card h4{margin:0 0 7px;font-size:15px;}
.note{background:#F6E7E4;border:1px solid #E9C9C4;border-radius:8px;padding:14px 18px;margin:0 0 18px;font-size:14px;}
.note b{color:var(--zhu);}
.gold{background:#F8F1DC;border:1px solid #E4D3A0;border-radius:8px;padding:14px 18px;margin:0 0 18px;font-size:14px;}
code{font-family:ui-monospace,Consolas,monospace;font-size:12px;background:#F1ECE0;padding:1px 5px;border-radius:3px;}
pre{background:#F4F0E6;border:1px solid var(--line2);border-radius:7px;padding:13px 15px;
font-family:ui-monospace,Consolas,monospace;font-size:12px;line-height:1.75;white-space:pre-wrap;
margin:0 0 14px;color:#3A352E;}
.trio{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:18px;}
.trio figure{margin:0;}
.trio img{width:100%;display:block;border:1px solid var(--line2);border-radius:6px;}
.trio figcaption{font-size:12.5px;color:var(--ink3);text-align:center;padding-top:6px;}
.typo{color:var(--zhu);font-weight:600;}
"""


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main():
    data = []
    for s in SHOTS:
        b64, size = build_b64(s["src"])
        data.append((s, b64, size))

    total = sum(s["sec"] for s in SHOTS)
    parts = []
    parts.append("""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>杨家将 · 忠烈千秋 —— 六镜试片</title>
<style>%s</style></head><body><div class="wrap">
<h1>杨家将 · 忠烈千秋
<small>六镜试片 · 风格验证版 · 总时长 %d 秒 · 16:9 · 上美影手绘动画（新白描）</small></h1>
<p class="lead">按阿 ken 的要求，只做六镜——第 6 集「退守土岗 → 见碑 → 碑面横移 → 撞碑」四镜，加第 24 集「碑前开花」、第 8 集「枯柳新芽」各一镜。这不是最终画稿，是<b>用来验证风格与调性是否成立</b>的一组样张：色盘对不对、留白敢不敢留、朱砂够不够吝啬、黑白那一镜立不立得住。</p>
<div class="note"><b>先看一句话结论</b>　六镜出图完成后逐张验看：镜 04（撞碑）达到预期——纯黑白加一点朱砂，是这组里最强的一张；镜 05 首版刀穗被生成成月白色，<b>丢掉了朱砂回收</b>，已重出并锁定朱砂刀穗。风格方向成立，但生图模型仍会在「平涂」上偷加体积感，批量生产前必须把负面词挂死。</div>

<div class="player">
  <div class="stage" id="stage">
    <img id="img" alt="">
    <div class="fade" id="fade"></div>
    <div class="hud" id="hud"></div>
    <div class="subs" id="subs"></div>
  </div>
  <div class="bar">
    <button class="main" id="play">▶ 播放试片</button>
    <button id="prev">上一镜</button>
    <button id="next">下一镜</button>
    <button id="reset">重播</button>
    <div class="track"><i id="prog"></i></div>
    <div class="t" id="tm">0.0 / %d.0 s</div>
  </div>
</div>
<div class="strip" id="strip"></div>
""" % (CSS, total, total))

    # ---- 风格锚点 ----
    parts.append("""<h2>一、风格锚点（本组样张的共同基准）</h2>
<div class="pal">
<div><i style="background:#7BA88E"></i>青瓷绿 celadon green</div>
<div><i style="background:#B03A2E"></i>朱砂红 cinnabar red</div>
<div><i style="background:#B8912B"></i>鎏金 gilt gold</div>
<div><i style="background:#1C1C1C"></i>墨黑 ink black</div>
<div><i style="background:#B5651D"></i>赭石 ochre</div>
<div><i style="background:#E8EAE6"></i>月白 moon white</div>
</div>
<div class="gold"><b>六镜共同遵守的三条</b><br>
① <b>留白优先</b>：天空与荒地必须大面积空着，人物在画面中越小越对；<br>
② <b>朱砂吝啬</b>：整组六镜里，朱砂只出现在镜 04 的刀穗（一点）和镜 05 的刀穗（一抹），其余四处一个红点都不许有；<br>
③ <b>不给脸</b>：六镜无一处人物面部特写——这是全片的表演纪律。</div>""")

    # ---- 数据表 ----
    parts.append('<h2>二、六镜镜头表</h2><div class="tw"><table><thead><tr>'
                 '<th class="c">镜</th><th>集</th><th class="c">镜名</th><th class="c">景别</th>'
                 '<th class="c">机位</th><th class="c">运镜</th><th class="c">时长</th><th>画面内容</th>'
                 '<th>旁白</th><th>音效</th></tr></thead><tbody>')
    for s, _, _ in data:
        parts.append("<tr><td class='c'><b>%s</b></td><td>%s</td><td class='c'><b>%s</b></td>"
                     "<td class='c'>%s</td><td class='c'>%s</td><td class='c'>%s</td><td class='c'>%ds</td>"
                     "<td>%s</td><td>%s</td><td>%s</td></tr>"
                     % (s["n"], esc(s["ep"]), esc(s["title"]), s["sz"], s["ang"], s["mv"], s["sec"],
                        esc(s["desc"]), esc(s["vo"]), esc(s["sfx"])))
    parts.append("</tbody></table></div>")

    # ---- 逐镜说明 + Seedance 提示词 ----
    parts.append('<h2>三、逐镜说明与下一步生成提示词</h2>')
    parts.append('<p class="lead">每一镜给出：设计意图 · 运镜规范 · 以及可直接投喂 Seedance 2.0 的提示词（首行风格行逐镜逐字相同）。</p>')
    for i, (s, _, _) in enumerate(data):
        parts.append('<div class="card"><h4>镜 %s · %s　<span style="color:#B03A2E;">%s</span></h4>'
                     '<p style="margin:0 0 8px;font-size:13.5px;color:#4A443B;">'
                     '<b>设计意图</b>　%s</p>'
                     '<pre>%s，%d秒，16:9横屏，%s\n\n%s</pre>'
                     '<p style="margin:0;"><b>运镜实现</b>　画面由 <code>%s</code> 过渡到 <code>%s</code>，%d 秒线性完成。'
                     '试片播放器里就是这个运动。</p></div>'
                     % (s["n"], esc(s["title"]), esc(s["sz"]), esc(s["note"]),
                        STYLE_LINE, s["sec"], esc(s["title"]),
                        "\n\n".join(esc(x) for x in s["sd"]),
                        esc(s["frm"]), esc(s["to"]), s["sec"]))

    # ---- 三张同机位校验 ----
    parts.append("""<h2>四、同机位校验</h2>
<p class="lead">全剧结构成立的技术前提：<b>李陵碑这一个场景，用同一个机位拍三次</b>。下面把其中两张放在一起比对。</p>
<div class="trio">
<figure><img src="data:image/jpeg;base64,%s" alt=""><figcaption>第 6 集 · 撞碑（黑白 · 碑面无字 · 刀插土中）</figcaption></figure>
<figure><img src="data:image/jpeg;base64,%s" alt=""><figcaption>第 24 集 · 碑前开花（碑上刻满名字 · 柳活 · 花开）</figcaption></figure>
<figure><img src="data:image/jpeg;base64,%s" alt=""><figcaption>第 8 集 · 枯柳新芽（第 8 集片尾，希望的第一次露头）</figcaption></figure>
</div>
<div class="note"><b>比对结论</b>　镜 04 与镜 05 的取景方向、地平线高度、碑与刀的相对位置基本对得上，可以作为同一机位的两次拍摄。但仍有两点需要在正式制作时用<b>同一场景资产锁定</b>：<br>
① 两图中的刀形制略有差异（镜 04 更瘦长）——按 P01 定宋金刀统一；<br>
② 镜 04 是越肩视角带人物，镜 05 无人，人物尺度需另做一张「有人的开花版」以保证三张严格同机位。</div>""")

    # ---- 结论 ----
    parts.append("""<h2>五、这组试片的结论</h2>
<div class="gold">
<b>成立的部分</b><br>
① <b>色盘成立</b>：赭石冻土 + 月白薄雪 + 青瓷绿远山，六张放在一起是一套，没有串色；<br>
② <b>留白成立</b>：镜 04、镜 06 敢空，画面没有填满，也没有出现写实光影；<br>
③ <b>黑白高潮立得住</b>：镜 04 抽掉全部颜色后，那一点朱砂的冲击力确实被放大了——朱砂纪律的设计得到验证；<br>
④ <b>叙事成立</b>：六镜连起来看，从「人」到「碑」到「芽」，情绪是递进的，不需要一句台词解释。</div>
<div class="note">
<b>需要修的部分</b><br>
① <b>平涂不彻底</b>：模型在人物铠甲与山体上仍会自行补上体积与渐变倾向。正式生产时必须在每条提示词后强制挂上负面词 —— <code>不要阴影，不要渐变，不要3D渲染，不要体积光，不要电影感打光，不要景深，不要写实照片，不要柔光光晕</code>；<br>
② <b>意象会漂</b>：镜 05 首版把朱砂刀穗生成了月白色。<b>凡是承担叙事功能的道具，必须在提示词里显式写死颜色</b>，不能依赖模型理解；<br>
③ <b>河山偏青绿山水</b>：镜 01、02 的远山偏「千里江山图」一路，比原连环画的白描清简要热闹。正式版应收敛山形，压掉一层装饰纹样。</div>
<div class="gold">
<b>建议的下一步</b>　这六镜目前是静帧 + 运镜模拟。要不要把它们变成真正的动态镜头？把 6 张首帧投给图生视频，逐镜生成 4–12 秒动态片段再合成，即可得到一支约 44 秒的正式动态试片。这一步会产生较大的积分消耗（<b>约 300–600 积分</b>，按 5 秒/镜 50–100 积分估算），需要你确认后再动。</div>
<p style="font-size:13px;color:#7A7266;margin-top:26px;">本试片中的故事取自传统民间杨家将传说与《宋史》等公共素材；样张画面为重新设计的生成稿，不含任何原连环画画面复用。原连环画《北宋杨家将》（湖南美术出版社，喻岳衡改编，蒋太禄等绘）的画面与改编文字著作权归原作者与出版方所有。</p>""")

    html = "\n".join(parts)

    # ---- JS ----
    js_shots = []
    for s, b64, _ in data:
        js_shots.append({
            "src": "data:image/jpeg;base64," + b64,
            "n": s["n"], "ep": s["ep"], "sz": s["sz"], "ang": s["ang"], "mv": s["mv"],
            "sec": s["sec"], "title": s["title"], "desc": s["desc"],
            "vo": s["vo"], "sfx": s["sfx"], "frm": s["frm"], "to": s["to"],
        })
    html += "\n<script>\nconst SHOTS=%s;\nconst TOTAL=%d;\n%s\n</script>\n</div></body></html>" % (
        __import__("json").dumps(js_shots, ensure_ascii=False), total, """
const img=document.getElementById('img'),frame=img,hud=document.getElementById('hud'),
subs=document.getElementById('subs'),prog=document.getElementById('prog'),tm=document.getElementById('tm'),
playBtn=document.getElementById('play'),strip=document.getElementById('strip'),fade=document.getElementById('fade');
let i=0,playing=false,timer=null,raf=null,t0=0,elapsedBefore=0;
const DUR=SHOTS.map(s=>s.sec*1000);
const CUM=DUR.reduce((a,b)=>a+0,0);
function fillHud(s){hud.innerHTML=
 '<span class="k">镜 '+s.n+'</span><span>'+s.ep+'</span><span>'+s.title+'</span>'+
 '<span>'+s.sz+'</span><span>'+s.ang+'</span><span>运镜：'+s.mv+'</span><span>'+s.sec+' 秒</span>';}
function fillSubs(s){subs.innerHTML=
 '<p class="vo">'+(s.vo||'')+'</p><p class="sfx">音　'+(s.sfx||'')+'</p>';}
function setFrame(s){frame.style.transition='none';frame.style.transform=s.frm;
 void frame.offsetWidth;frame.style.transition='transform '+s.sec+'s linear';frame.style.transform=s.to;}
function show(idx,run){i=idx;const s=SHOTS[i];img.src=s.src;fillHud(s);fillSubs(s);setFrame(s);
 [...strip.children].forEach((d,k)=>d.classList.toggle('on',k===i));
 if(run){timer=setTimeout(()=>{if(i<SHOTS.length-1){show(i+1,true);}else{stop();}},s.sec*1000);}}
function tick(){if(!playing)return;const now=performance.now();
 let done=0;for(let k=0;k<i;k++)done+=DUR[k];
 const cur=Math.min(done+(now-t0),CUM);
 prog.style.width=(cur/CUM*100)+'%';tm.textContent=(cur/1000).toFixed(1)+' / '+(CUM/1000).toFixed(1)+' s';
 raf=requestAnimationFrame(tick);}
function play(){if(playing)return;playing=true;playBtn.textContent='⏸ 暂停';
 t0=performance.now();fade.style.opacity=0;show(i,true);tick();}
function stop(){playing=false;playBtn.textContent='▶ 播放试片';clearTimeout(timer);cancelAnimationFrame(raf);}
playBtn.onclick=()=>{playing?stop():play();};
document.getElementById('next').onclick=()=>{stop();if(i<SHOTS.length-1)show(i+1,false);};
document.getElementById('prev').onclick=()=>{stop();if(i>0)show(i-1,false);};
document.getElementById('reset').onclick=()=>{stop();prog.style.width='0';tm.textContent='0.0 / '+(CUM/1000).toFixed(1)+' s';show(0,false);};
SHOTS.forEach((s,k)=>{const d=document.createElement('div');
 d.innerHTML='<img src="'+s.src+'"><span>'+s.n+'</span>';
 d.onclick=()=>{stop();show(k,false);};strip.appendChild(d);});
show(0,false);
""")

    out = os.path.join(OUTDIR, "杨家将_六镜试片.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    return out, len(html)


try:
    p, n = main()
    msg = "OK -> %s\nchars=%d  (%.1f KB)" % (p, n, n / 1024)
except Exception:
    msg = "FATAL\n" + traceback.format_exc()

with open(LOG, "w", encoding="utf-8") as fh:
    fh.write(msg)
