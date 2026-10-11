# -*- coding: utf-8 -*-
"""生成竖屏版规格书 HTML。"""
import os, json, traceback
from collections import Counter

BASE = r"D:\BaiduNetdiskDownload\北宋杨家将"
J = os.path.join(BASE, r".workbuddy\_tmp\qc\shots.json")
OUT = os.path.join(BASE, r"动画改编方案\杨家将_竖屏版规格书.html")
LOG = os.path.join(BASE, r".workbuddy\_tmp\qc\vspec.log")

d = json.load(open(J, "r", encoding="utf-8"))
rows, summ = d["rows"], d["summary"]
tot = len(rows)
cnt = Counter(r["dur"] for r in rows)
risk = [r for r in rows if r["vfix"]]
short = [s for s in summ if s["gap"] > 0]

CSS = """
:root{--paper:#FBF8F1;--card:#FFF;--ink:#231F19;--ink2:#4A443B;--ink3:#7A7266;--line:#E3DCCC;--line2:#D2C8B2;
--zhu:#B03A2E;--zhu-bg:#F6E7E4;--green:#3E6B5A;--green-bg:#E6EFE9;--jin:#B8912B;--jin-bg:#F8F1DC;--dai:#3E4E5A;--dai-bg:#E8EDF0;}
*{box-sizing:border-box;}
body{margin:0;background:var(--paper);color:var(--ink);font-family:"PingFang SC","Microsoft YaHei","Hiragino Sans GB",sans-serif;font-size:15px;line-height:1.82;-webkit-font-smoothing:antialiased;}
.wrap{max-width:1060px;margin:0 auto;padding:0 24px 90px;}
h1{font-family:"Songti SC","SimSun",serif;font-size:32px;margin:44px 0 6px;letter-spacing:.03em;}
h1 small{display:block;font-size:14.5px;color:var(--ink2);font-weight:400;margin-top:10px;letter-spacing:.06em;}
h2{font-family:"Songti SC","SimSun",serif;font-size:21px;margin:44px 0 14px;padding-bottom:11px;border-bottom:2px solid var(--ink);}
h3{font-size:16.5px;margin:26px 0 10px;padding-left:11px;border-left:4px solid var(--zhu);}
.lead{color:var(--ink2);border-left:3px solid var(--line2);padding-left:14px;margin:0 0 22px;}
.tw{overflow-x:auto;margin:0 0 20px;}
table{width:100%;border-collapse:collapse;background:var(--card);font-size:13px;line-height:1.7;border:1px solid var(--line2);}
th,td{padding:9px 11px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top;}
thead th{background:var(--ink);color:#F7F3EA;font-size:12.5px;font-weight:600;border-bottom:none;}
tbody tr:nth-child(even){background:#FCFAF5;}
td.c{text-align:center;white-space:nowrap;font-variant-numeric:tabular-nums;}
.note{background:var(--zhu-bg);border:1px solid #E9C9C4;border-radius:8px;padding:15px 19px;margin:0 0 18px;font-size:14px;}
.note b{color:var(--zhu);}
.green{background:var(--green-bg);border:1px solid #C2D6CB;border-radius:8px;padding:15px 19px;margin:0 0 18px;font-size:14px;}
.green b{color:var(--green);}
.gold{background:var(--jin-bg);border:1px solid #E4D3A0;border-radius:8px;padding:15px 19px;margin:0 0 18px;font-size:14px;}
.dai{background:var(--dai-bg);border:1px solid #C9D6DE;border-radius:8px;padding:15px 19px;margin:0 0 18px;font-size:14px;}
.dai b{color:var(--dai);}
code{font-family:ui-monospace,Consolas,monospace;font-size:12px;background:#F1ECE0;padding:1px 5px;border-radius:3px;}
.kpi{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:0 0 22px;}
@media(max-width:760px){.kpi{grid-template-columns:repeat(2,1fr);}}
.kpi div{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:15px 17px;border-top:3px solid var(--zhu);}
.kpi .v{font-family:"Songti SC",serif;font-size:28px;font-weight:700;line-height:1.15;}
.kpi .l{font-size:12.5px;color:var(--ink3);margin-top:3px;}
.phone{display:flex;gap:22px;align-items:flex-start;margin:0 0 22px;flex-wrap:wrap;}
.phone .dev{border:2px solid var(--ink);border-radius:16px;padding:6px;background:#141210;}
.phone .dev i{display:block;width:112px;height:200px;border-radius:10px;
background:linear-gradient(180deg,#E8EAE6 0%,#E8EAE6 30%,#4A5A63 30%,#4A5A63 34%,#B5651D 34%,#B5651D 62%,#8C5A3C 62%,#8C5A3C 74%,#B5651D 74%,#B5651D 100%);}
.phone .dev span{display:block;text-align:center;font-size:11px;color:#8C8378;padding:5px 0 1px;}
.phone .desc{flex:1;min-width:300px;font-size:14px;}
.safe{border:1px dashed var(--zhu);border-radius:8px;padding:11px 15px;font-size:13.5px;background:#FFF;margin:0 0 10px;}
.steps{counter-reset:s;list-style:none;padding:0;margin:0 0 20px;}
.steps li{counter-increment:s;position:relative;padding:0 0 14px 42px;font-size:14.5px;}
.steps li::before{content:counter(s);position:absolute;left:0;top:2px;width:26px;height:26px;border-radius:50%;background:var(--ink);color:#F7F3EA;font-size:12.5px;font-weight:700;display:flex;align-items:center;justify-content:center;}
.badge{display:inline-block;font-size:11.5px;padding:2px 9px;border-radius:20px;font-weight:600;margin-right:6px;}
.b-z{background:var(--zhu-bg);color:var(--zhu);}
.b-j{background:var(--jin-bg);color:#8A6C12;}
.b-g{background:var(--green-bg);color:var(--green);}
.b-d{background:var(--dai-bg);color:var(--dai);}
"""

P = []
P.append("""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>杨家将 · 忠烈千秋 —— 竖屏版规格书</title><style>@@CSS@@</style></head><body><div class="wrap">
<h1>杨家将 · 忠烈千秋 · 竖屏版规格书
<small>24 集 × 3 分 30 秒 · 9:16 · 全片 812 段 · 上美影手绘动画</small></h1>
<p class="lead">按你选的 B 方案（竖屏短剧）排的规格。要做的事分五块：定格式、把横屏的构图全部改成竖的、把每一段切成 Flow 能吃的 4/6/8 秒、排生产成本、标出这版会踩的坑。</p>

<div class="dai"><b>先说一句最要紧的</b>　这一版<b>不是把横屏内容换个画幅</b>。竖屏的信息容量是"上天下地"，横屏是"左到右"——这两件事不通用。全片有 <b>@@RISK@@ 个镜头</b>是横屏专属运镜（横移、平摇、大远景、全景），在 9:16 里会直接失效，<b>必须重写运镜</b>。清单在第三章。</div>

<div class="kpi">
  <div><div class="v">24 × 3:30</div><div class="l">集数 × 集长</div></div>
  <div><div class="v">@@TOT@@</div><div class="l">Flow 段数（全片）</div></div>
  <div><div class="v">@@RISK@@</div><div class="l">需重写运镜的镜头</div></div>
  <div><div class="v">84</div><div class="l">分钟 · 全片总长</div></div>
</div>

<h2>一、格式定义</h2>
<div class="tw"><table>
<thead><tr><th style="width:170px;">项</th><th>设定</th><th>理由</th></tr></thead>
<tbody>
<tr><td><b>画幅</b></td><td>9:16（1080 × 1920）</td><td>竖屏短剧标准；Flow 直接支持 9:16</td></tr>
<tr><td><b>集数 / 集长</b></td><td>24 集 × 3 分 30 秒 = 210 秒</td><td>竖屏短剧的主流长度；也正好装下当前 812 镜</td></tr>
<tr><td><b>全片总长</b></td><td>84 分钟</td><td>与现有剧本 68–95 分钟的估算体量吻合，不用膨化</td></tr>
<tr><td><b>镜头密度</b></td><td>平均 6.2 秒/镜</td><td>上美影风格是慢节奏手绘，比短视频常规的 2–3 秒要慢。这是有意的</td></tr>
<tr><td><b>段长分配</b></td><td>4 秒 @@D4@@ 段 · 6 秒 @@D6@@ 段 · 8 秒 @@D8@@ 段</td><td>Flow 单段只有 4/6/8 三档。8 秒给空镜与情绪镜，4 秒给爆闪与快切</td></tr>
<tr><td><b>全片段数</b></td><td>@@TOT@@ 段（1 镜 = 1 段）</td><td>不做 1 镜多段，控制生成成本</td></tr>
<tr><td><b>字幕</b></td><td>硬字幕，位置见第四章</td><td>竖屏短剧以硬字幕为主，旁白与字幕同步</td></tr>
</tbody></table></div>

<h2>二、横改竖：构图要重做，不是缩放</h2>
<p class="lead">横屏的叙事靠"从左到右"（队伍、疆域、地平线）；竖屏靠"从上到下"（天、人、地）。我们原剧本里有大量横向调度，这是改编里最大的一块工作量。</p>

<div class="phone">
  <div class="dev"><i></i><span>9:16</span></div>
  <div class="desc">
    <b>竖屏的三层结构</b><br>
    把横屏的一个横向画面，拆成竖向三层叠置：<br><br>
    <b>上 1/3</b>　天空、留白、旗帜、远山剪影 → 承担"辽阔"<br>
    <b>中 1/3</b>　人物 / 主体 → 承担"叙事"<br>
    <b>下 1/3</b>　地面、道具、字幕 → 承担"落点"<br><br>
    这三层恰好对应我们原剧本里最常用的三个元素——留白天空、人物背影、插在土里的刀。<b>竖屏其实更适合《李陵碑》那种"上天下地中间一个人"的构图。</b>
  </div>
</div>

<h3>三条改写原则</h3>
<ol class="steps">
<li><b>横向展开 → 竖向叠置。</b>横屏的"一队人马从左走到右"，改成"人马从画面下方走入、向画面深处去"。信息不减，方向从横变纵。</li>
<li><b>横移 / 平摇 → 竖移 / 纵深推。</b>横向摇镜在竖屏里两侧全在画外，等于没摇。改成自下而上摇起（地→人→天），或者沿纵深推进。</li>
<li><b>远景 → 分层。</b>竖屏装不下横向的地平线，硬拍远景人物会小到看不清。改法是把远景拆成"前景人物剪影 / 中景坡地 / 远景留白"三层，靠叠置营造纵深。</li>
</ol>

<h3>运镜改写对照</h3>
<div class="tw"><table>
<thead><tr><th style="width:130px;">横屏原运镜</th><th style="width:140px;">竖屏改写</th><th>说明</th><th class="c" style="width:60px;">优先级</th></tr></thead>
<tbody>""")
CMP = [
 ("横移 / 平摇", "竖移（上下摇）", "把横向展开的信息改成纵向递进，或改为纵深推进", "高"),
 ("大远景", "中景 + 远山分层", "竖屏装不下横向地平线，拆成「前景人物／中景坡地／远景留白」三层竖向叠置", "高"),
 ("全景", "中近景", "横构图全景在竖屏里人物太小，环境靠画外暗示", "高"),
 ("俯拍", "高角度纵深俯拍", "保留俯视但沿纵深方向推，不要横向扫", "中"),
 ("一镜到底", "拆 2–3 段", "竖屏一镜到底容易失焦", "中"),
 ("推 / 缓推", "直接可用", "竖屏最安全的运镜", "—"),
 ("升 / 降", "直接可用", "竖向运动天生适配 9:16", "—"),
 ("下摇", "直接可用", "同上", "—"),
 ("特写 / 近景", "直接可用", "竖屏的天然优势画幅", "—"),
 ("仰拍", "直接可用", "竖向构图增强崇高感", "—"),
 ("固定机位", "直接可用", "适合空镜与情绪镜", "—"),
]
for a, b, c, pr in CMP:
    P.append("<tr><td><b>%s</b></td><td>%s</td><td>%s</td><td class='c'>%s</td></tr>" % (a, b, c, pr))
P.append("""</tbody></table></div>

<h2>三、需要重写运镜的镜头（%d 个）</h2>
<p class="lead">这些镜头在 9:16 下会失效，必须改。改法照上一章的对照表。<b>完整清单见《Flow 片段切分表》的"竖屏运镜改写"列</b>，这里是全部 %d 条。</p>
<div class="tw"><table>
<thead><tr><th class="c" style="width:52px;">集</th><th class="c" style="width:50px;">镜</th><th class="c" style="width:60px;">原书页</th><th>画面</th><th style="width:120px;">改为</th></tr></thead>
<tbody>""" % (len(risk), len(risk)))
for r in risk:
    P.append("<tr><td class='c'>%d</td><td class='c'>%d</td><td class='c'>%s</td><td>%s</td><td><b>%s</b></td></tr>"
             % (r["ep"], r["idx"], r["mark"] or "—", r["txt"][:78], r["vfix"]))
P.append("""</tbody></table></div>
<div class="green"><b>好消息</b>　这 %d 个里有相当一部分是<b>空镜和氛围镜</b>（山谷、城墙、雪原、阵图）。这类镜头改竖向相对容易——把横向的"扫"改成竖向的"摇起"就行，而且竖屏的"上天下地"其实更适合《李陵碑》那种构图。<br><br>
<b>真正的硬骨头</b>是少数几个横向调度：第 1 集的九人列队横移、第 12/20 集的战场全景、第 17 集天门阵的阵图俯瞰。<b>这三个需要重新设计，不是改运镜能解决的。</b></div>

<h2>四、字幕与旁白规范</h2>
<div class="safe"><b>安全区</b>　9:16 画面中，上下各留 12% 不放关键信息（平台 UI 会遮住）；左右各留 6%。核心信息压在中间 76% 的区域内。</div>
<div class="safe"><b>字幕位</b>　底边向上 14% 处，单行居中，字号按 1080 宽取 48–56 px。最多两行。</div>
<div class="safe"><b>旁白</b>　本片旁白是"说书人体制"，语速慢、句短。每句控制在 4–8 秒，正好对上一段 Flow 片段的长度。<b>旁白不交给 Flow 生成</b>（跨镜音色会漂），单独合成后与画面同步。</div>
<div class="safe"><b>片头</b>　每集前 3 秒必须是钩子画面，不出现片名。片名只在第 1 集出现一次。</div>

<h2>五、24 集开场 3 秒钩子</h2>
<p class="lead">竖屏短剧的留存全靠前 3 秒。每集用一个"强画面"开场，不解释、不铺垫。</p>
<div class="tw"><table>
<thead><tr><th class="c" style="width:52px;">集</th><th style="width:150px;">集名</th><th>开场 3 秒钩子</th><th class="c" style="width:64px;">镜头</th><th class="c" style="width:64px;">时长</th><th class="c" style="width:64px;">改运镜</th></tr></thead>
<tbody>""")
for s in summ:
    P.append("<tr><td class='c'>%d</td><td>%s</td><td><b>%s</b></td><td class='c'>%d</td><td class='c'>%d:%02d</td><td class='c'>%d</td></tr>"
             % (s["ep"], s["name"], s["hooks"], s["shots"], s["total"] // 60, s["total"] % 60, s["risk"]))
P.append("""</tbody></table></div>

<h2>六、Flow 生产管线</h2>
<ol class="steps">
<li><b>出首帧（全片 %d 张）</b>先用锁定的色盘与角色锚点批量出图。风格锚定用我们已有的六镜样张。<b>不要逐镜返工</b>——先把 C01–C16 角色四视图和 S01–S18 三机位定死，再批量出。</li>
<li><b>逐段生成（全片 %d 段）</b>每段走 Frames to Video：对应首帧设为起始帧，粘贴该段的英文提示词。模型先 Veo 3.1 Lite 出 animatic，通过后再升 Fast / Quality。</li>
<li><b>镜长不足 8 秒的补 Extend</b>本规格里最大段长就是 8 秒，正常不需要 Extend。只有第 9 / 11 集可能需要（见第八章）。</li>
<li><b>Scenebuilder 拼装</b>按集拖入、排序、导出。每集 ≈ 34 段，接点全部硬切——<b>全片只有第 6 集→第 24 集的李陵碑三镜之间用叠化</b>，其余不转场。</li>
<li><b>后期</b>旁白合成、硬字幕、音效铺底。配乐只在片头片尾与三个朱砂点出现。</li>
</ol>

<h2>七、成本与投产策略</h2>
<div class="tw"><table>
<thead><tr><th>项</th><th class="c">数量</th><th class="c">单价（积分）</th><th class="c">小计</th></tr></thead>
<tbody>
<tr><td>首帧出图</td><td class="c">@@TOT@@ 张</td><td class="c">5–10</td><td class="c">@@IMGLO@@ – @@IMGHI@@</td></tr>
<tr><td>视频生成 · Lite</td><td class="c">@@TOT@@ 段</td><td class="c">10</td><td class="c">@@VLITE@@</td></tr>
<tr><td>视频生成 · Fast</td><td class="c">@@TOT@@ 段</td><td class="c">20</td><td class="c">@@VFAST@@</td></tr>
<tr><td>视频生成 · Quality</td><td class="c">@@TOT@@ 段</td><td class="c">100</td><td class="c">@@VQUAL@@</td></tr>
</tbody></table></div>
<div class="note"><b>不要一上来铺全片。</b>全片都用 Quality 是 8 万积分级别，而且试错阶段的返工全按 Quality 计价，非常浪费。推荐三步走。</div>
<div class="gold">
<b>第一步 · 试播集（约 720 积分）</b>　只做第 1 集和第 6 集，共 72 镜，Lite 档跑。目的不是出片，是验证<b>竖屏构图改法是否成立</b>——特别是那 8 个需要重写运镜的镜头。<br><br>
<b>第二步 · 定风格（约 600 积分）</b>　对试播集里通过的约 30 镜升 Fast，剪成两支 3 分 30 秒的样片，对外看。<br><br>
<b>第三步 · 铺全片</b>　按集推进，每集先用 Lite 出 animatic 定节奏，选定的镜头再升 Fast。Quality 只留给李陵碑三镜、第 6 集殉国、第 24 集挂帅这几个必须精的段落。
</div>

<h2>八、这一版会踩的三个坑</h2>""")

P.append("""<div class="note"><b>坑一 · 第 9 集和第 11 集撑不满 3 分 30 秒</b><br><br>
把全片每段都拉满到 Flow 的上限 8 秒，这两集也只有 <b>184 秒</b>（3:04），<b>各缺 26 秒</b>。<br>
原因不是时长分配算法的问题，是这两个集的<b>镜头数不够</b>——第 9 集《辞官》和第 11 集《焦赞》各只有 23 镜。<br><br>
三条解法：<br>
① <b>补镜头</b>（推荐）：各补 4–5 个镜头。第 9 集补"六郎辞官出京"的过场与母亲的反应；第 11 集补焦赞在山洞里的几笔。这两处原文素材够，补出来是加分；<br>
② <b>把这两集并成一集</b>：第 9+11 集合成一集 46 镜，但这样全片变 23 集；<br>
③ <b>接受 3:04</b>：不改。集长不齐整，但内容完整。<br><br>
第 23 集也差 2 秒，可以忽略。</div>

<div class="note"><b>坑二 · 竖屏人物密度</b><br><br>
原剧本有几处是"多人并列"的构图——第 2 集的七子二女列队、第 4 集的三子战死、第 19 集的众将求情、第 23 集的女将点将。这些在横屏里是"一字排开"，竖屏里排不下。<br><br>
改法：<b>改成竖向纵深排列</b>（前中后三层），或者干脆拆成单人短切。第 2 集那个"一、二、三、四、五、六、七"的横移数人头，在竖屏里应该改成"从队尾推到队首"的纵深推。</div>

<div class="dai"><b>坑三 · 开场钩子与剧本首镜可能冲突</b><br><br>
原剧本每集的第一镜是按叙事顺序写的（承接上一集），不是按"抓人"写的。我上面给的 24 个钩子是从各集最有冲击力的画面里挑的，<b>可能需要把它们提到片头，或者重写每集的首镜</b>。<br><br>
这一条建议：<b>先按现有顺序做试播集</b>，把成片给三五个人看，看第 1 集前 3 秒的跳出率。如果留存不行，再动钩子。</div>

<p style="font-size:13px;color:#7A7266;margin-top:28px;">
本规格中的故事取自传统民间杨家将传说与《宋史》等公共素材。原连环画《北宋杨家将》（湖南美术出版社，喻岳衡改编，蒋太禄等绘）的画面与改编文字著作权归原作者与出版方所有，本方案不含任何原画复用。<br>
Flow / Veo 3.1 的规格（4/6/8 秒档位、9:16 支持、Lite 10 / Fast 20 / Quality 100 积分）核对于 2026 年 9 月，平台规则可能变动，投产前建议在 Flow 界面内再确认一次。</p>
</div></body></html>""")

html = "".join(P)
for _k, _v in [("@@CSS@@", CSS), ("@@TOT@@", str(tot)), ("@@RISK@@", str(len(risk))),
               ("@@D4@@", str(cnt[4])), ("@@D6@@", str(cnt[6])), ("@@D8@@", str(cnt[8])),
               ("@@IMGLO@@", format(tot * 5, ",")), ("@@IMGHI@@", format(tot * 10, ",")),
               ("@@VLITE@@", format(tot * 10, ",")), ("@@VFAST@@", format(tot * 20, ",")),
               ("@@VQUAL@@", format(tot * 100, ","))]:
    html = html.replace(_k, _v)
open(OUT, "w", encoding="utf-8").write(html)
print("OK -> %s  (%.1f KB)" % (OUT, len(html.encode("utf-8")) / 1024))
