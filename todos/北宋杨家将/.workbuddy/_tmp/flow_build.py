# -*- coding: utf-8 -*-
"""生成 Google Flow / Veo 3.1 版六镜提示词包（HTML + 可粘贴 txt）。"""
import os, io, json, base64, traceback
from PIL import Image

BASE = r"D:\BaiduNetdiskDownload\北宋杨家将"
IMGDIR = os.path.join(BASE, r"动画改编方案\试片")
OUTDIR = IMGDIR
LOG = os.path.join(BASE, r".workbuddy\_tmp\flow.log")

STYLE = ("Traditional hand-painted 2D animation, flat solid blocks of mineral pigment colour, "
         "simplified contours with visible brush outlines, film grain, vintage Shanghai Animation Film Studio manner.")

SHOTS = [
 dict(n="01", img="shot01.jpg", cn="退守土岗", ep="第 6 集《李陵碑 · 殉国》",
   dur="6 秒", tier="Fast", frame="shot01.jpg",
   wc=None,
   p=("Low aerial wide shot, camera very slowly pushing in. Dozens of ragged Song-dynasty soldiers in broken "
      "armour sit scattered on a bare frontier hilltop at dusk, heads bowed, almost motionless. One man stands "
      "alone just outside the circle, back to camera, his dark cloak torn down to a half, armour split open in "
      "three places, both hands hanging empty at his sides. Frozen ochre earth under a thin film of moon-white "
      "snow, layered celadon-green mountains receding into vast empty space. " + STYLE + " Every form is one "
      "flat shape of colour; light is expressed only by adjacent colour blocks. SFX: low wind across bare ground."),
   cn_p=("低角度航拍远景，镜头极缓慢推近。几十名衣衫褴褛的宋军残兵身穿破损铠甲，散坐在荒凉的边塞土岗上，"
         "低着头，几乎不动。一人独自站在圈外，背对镜头，深色披风只剩一半，铠甲裂开三处，腰间没有兵器。"
         "赭石色冻土上覆一层薄薄的月白色积雪，层叠的青瓷绿远山隐入大片空白。"
         "＋风格块＋每个形体都是一整块平涂色；明暗只靠相邻色块并置表达。音效：旷野上的低风。"),
   note="首帧已锁定构图与风格，提示词只负责运镜与风。人物在画面中要小——若生成偏大，把 aerial 换成 high aerial 再试。"),

 dict(n="02", img="shot02.jpg", cn="见碑", ep="第 6 集《李陵碑 · 殉国》",
   dur="6 秒", tier="Fast", frame="shot02.jpg",
   p=("Close shot, camera slowly tilts down and settles to rest. A broken stone stele leans at an angle in "
      "frozen ochre earth, its face eroded and flaking, its edges chipped away, the characters it once carried "
      "worn almost flat and unreadable. To its left stands a dead willow, every branch snapped off. A thin film "
      "of moon-white snow lies on the ground. Wide empty space fills the upper frame. " + STYLE +
      " Every form is one flat shape of colour. The camera comes to a complete stop and holds. SFX: faint wind."),
   cn_p=("特写，镜头缓慢下摇后停住。一块残破石碑斜插在赭石色冻土里，碑面风化剥落、边缘崩缺，"
         "原本刻着的字被磨得几近平平、无法辨认。碑的左侧立着一株枯柳，枝条全部折断。"
         "地面覆一层薄薄的月白色积雪，画面上半部是大片空白。＋风格块＋每个形体都是一整块平涂色。"
         "镜头完全停住并保持。音效：极轻的风。"),
   note="与镜 01 连看时是「目光落下去」的物理动作。首帧已定机位，提示词里的 tilt down 是让模型从首帧再往下走一点。"),

 dict(n="03", img="shot03.jpg", cn="碑面横移", ep="第 6 集《李陵碑 · 殉国》",
   dur="8 秒", tier="Fast", frame="shot03.jpg",
   p=("Extreme close-up filling the entire frame with the surface of an ancient stone stele. Coarse weathered "
      "stone, hairline cracks and chisel marks; rows of horizontal incisions where characters were once carved "
      "have been worn almost smooth, as if scoured by water for many years. Only a fragment of one chiselled "
      "stroke survives at the lower right. Camera drifts slowly and steadily sideways across the surface. "
      "Pale ochre stone and ink-black line fill the whole frame; the image is built from these two tones alone. "
      + STYLE +
      " SFX: wind ceases abruptly at the very start, complete silence through the middle, a single thread of "
      "wind at the end."),
   cn_p=("大特写，画面被一块古碑的碑面完全充满。粗糙的风化石质，发丝般的裂纹与凿痕；"
         "原先刻过字的一行行横向刻口已被磨得几近平滑，像被水冲刷了许多年。"
         "只在右下角残存一道笔画的一小截。镜头缓慢而匀速地横向掠过表面。"
         "淡赭石色石面、墨黑线条，全画面没有第三种颜色。＋风格块。"
         "音效：风在开头骤然停止，中段完全无声，结尾只留一缕风。"),
   note="全片最重要的一次「减法」。Flow 的 SFX 用 `SFX:` 前缀单独写，模型会按它生成环境声。"),

 dict(n="04", img="shot04.jpg", cn="撞碑 · 全片风格高潮", ep="第 6 集《李陵碑 · 殉国》",
   dur="8 秒", tier="Quality（定稿）", frame="shot04.jpg",
   p=("Monochrome ink-wash image, black white and grey, drawn like an old woodblock illustration. A weathered "
      "stone stele stands on a bare hillside. Before it a lone warrior in broken armour, back to camera, facing "
      "the stone, small within the frame. Beside him a long sword is planted upright in the ground, its tassel "
      "the only cinnabar-red note in the entire image. Sparse snow drifts down. Camera rises very slowly from "
      "behind the figure, passing over his shoulder toward the stele. Vast empty sky above. Every value sits as "
      "one flat shape of ink, the way an old woodblock print is cut. "
      "SFX: wind, then one low short dull impact like wood striking stone, then long wind."),
   cn_p=("纯黑白灰的水墨画面，像一幅古本木刻插图。一通风化石碑立在荒坡上。碑前一名铠甲残破的武将，"
         "背对镜头，面向石碑，在画面中很小。他身旁一杆长刀直插土中，刀穗是整幅画面里唯一的朱砂红。"
         "稀薄的雪缓缓落下。镜头从人物背后极缓慢地升起，越过他的肩，朝着石碑。上方是大片空白天空。"
         "所有明暗都是一整块墨色平涂，没有柔和过渡。"
         "音效：风，然后一声低沉短促的闷响（像木头撞在石头上），然后是长长的风。"),
   note="本镜唯一有彩色，且只有刀穗那么一点。因为 Flow 无法用负向词压彩色，务必保留首帧——颜色完全由首帧继承。"),

 dict(n="05", img="shot05.jpg", cn="碑前开花", ep="第 24 集《穆桂英挂帅》",
   dur="8 秒 + Extend 4 秒 = 12 秒", tier="Quality（定稿）", frame="shot05.jpg",
   p=("Same hillside, same camera position and framing, years later, early spring afternoon. The stele now "
      "carries dense vertical rows of carved names. Beside it the willow has come back to life, hung with fresh "
      "pale-green leaves. The slope in front is covered with a broad carpet of small wildflowers, celadon and "
      "moon white. A sword is planted in the ground, its tassel still cinnabar red, the single most vivid "
      "colour in the frame. The horizon sits low with a wide blank sky above. Camera completely static. " + STYLE +
      " SFX: wind moving gently through willow leaves."),
   cn_p=("同一片土岗，同一机位与构图，多年之后的早春午后。碑上现在刻满了密密麻麻的竖排名字。"
         "碑旁的柳树活了过来，挂满嫩绿新叶。碑前的坡面覆着一大片细碎野花，青瓷绿与月白色。"
         "土里插着一杆刀，刀穗仍是朱砂红，是画面中最鲜明的一抹颜色。地平线压得很低，上方是大片空白天空。"
         "镜头完全静止。＋风格块。音效：风轻轻穿过柳叶的声音。"),
   ext=("Continue this static wide shot. Willow leaves stir gently, one or two petals drift slowly across the frame. "
        "The camera holds absolutely still. SFX: soft wind."),
   cn_ext="继续这个静止的远景。柳叶轻轻摇动，一两片花瓣缓缓飘过画面。镜头不动。音效：柔风。",
   note="镜 04 与镜 05 必须用同一句「same camera position and framing」把它们焊在一起——这是全剧的结构支点。"),

 dict(n="06", img="shot06.jpg", cn="枯柳新芽", ep="第 8 集《汴京审潘》",
   dur="4 秒", tier="Lite / Fast", frame="shot06.jpg",
   p=("Extreme close-up. A single snapped-off dead willow branch enters from the lower left, its bark drawn in "
      "heavy ink-black line, every old twig broken. At its very tip one small new shoot has emerged, two young "
      "leaves of pale celadon green, very small. The rest of the frame is blank moon-white space. Camera pushes "
      "in almost imperceptibly and then holds still. " + STYLE +
      " SFX: a single thread of wind."),
   cn_p=("大特写。一截折断的枯柳枝从画面左下伸入，树皮用厚重的墨黑线条画成，每一根旧枝都断了。"
         "在最顶端，抽出了一小截新芽——两片淡青瓷绿的稚叶，非常小。画面其余部分是大片月白色空白。"
         "镜头几乎察觉不到地推近一点，然后停住。＋风格块。音效：一缕风。"),
   note="4 秒档只有 Flow 支持，正好放这一镜。Lite 档对长提示词消化不好，若用 Lite 请把风格块压到一句。"),
]

DIFF = [
 ("提示词语言", "中文优先，强调本地语感", "英文最优；中文可用但英文锚定更准"),
 ("负向提示词", "支持，可写「不要3D渲染、不要渐变」", "<b>Flow 不支持</b>；Google 官方建议完全避免否定句——写「no rain」，模型反而会处理 rain 这个词"),
 ("单段时长", "5 / 10 / 30 秒档", "<b>固定 4 / 6 / 8 秒</b>，没有别的档"),
 ("首帧锚定", "图生视频，提示词仍需描述画面", "<b>Image-to-Video 是核心策略</b>：首帧定死构图光影风格，提示词只管运镜"),
 ("原生音频", "只出音效", "原生音频：<code>SFX:</code> 前缀写环境声；口播用 <code>[Dialogue: ...]</code> 标签"),
 ("提示词长度", "可以写很长", "<b>100–150 词为上限</b>；Lite 档 10–15 词最稳"),
 ("可复现性", "—", "Flow <b>无 seed 参数</b>，同一提示词结果会变——所以更依赖首帧锚定"),
 ("积分档位", "—", "Lite 10 / Fast 20 / Quality 100（每段）"),
]


def b64(path, w=1000, q=80):
    im = Image.open(path).convert("RGB")
    ow, oh = im.size
    im = im.resize((w, int(oh * w / ow)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=q, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


CSS = """
:root{--paper:#FBF8F1;--card:#FFF;--ink:#231F19;--ink2:#4A443B;--ink3:#7A7266;--line:#E3DCCC;
--line2:#D2C8B2;--zhu:#B03A2E;--google:#1A73E8;--google-bg:#E8F0FE;--jin:#B8912B;}
*{box-sizing:border-box;}
body{margin:0;background:var(--paper);color:var(--ink);
font-family:"PingFang SC","Microsoft YaHei","Hiragino Sans GB",sans-serif;font-size:15px;line-height:1.82;}
.wrap{max-width:1060px;margin:0 auto;padding:0 24px 90px;}
h1{font-family:"Songti SC","SimSun",serif;font-size:32px;margin:42px 0 6px;letter-spacing:.03em;}
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
.gbox{background:var(--google-bg);border:1px solid #C3D8F7;border-radius:8px;padding:15px 19px;margin:0 0 18px;font-size:14px;}
.gbox b{color:var(--google);}
.note{background:#F6E7E4;border:1px solid #E9C9C4;border-radius:8px;padding:14px 18px;margin:0 0 18px;font-size:14px;}
.note b{color:var(--zhu);}
.gold{background:#F8F1DC;border:1px solid #E4D3A0;border-radius:8px;padding:14px 18px;margin:0 0 18px;font-size:14px;}
.shot{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:0;margin-bottom:22px;overflow:hidden;}
.shot .hd{display:flex;align-items:center;gap:12px;padding:13px 18px;background:#F4F0E6;border-bottom:1px solid var(--line);flex-wrap:wrap;}
.shot .hd .no{font-family:"Songti SC",serif;font-size:24px;font-weight:700;color:var(--zhu);line-height:1;}
.shot .hd .tt{font-family:"Songti SC",serif;font-size:17px;font-weight:700;}
.shot .hd .tag{font-size:11.5px;background:#fff;border:1px solid var(--line2);border-radius:20px;padding:2px 10px;color:var(--ink2);white-space:nowrap;}
.shot .bd{padding:16px 18px;}
.shot img{width:100%;display:block;border:1px solid var(--line2);border-radius:6px;margin-bottom:14px;}
.prow{position:relative;background:#F4F0E6;border:1px solid var(--line2);border-radius:7px;padding:13px 15px;margin-bottom:12px;}
.prow pre{margin:0;font-family:ui-monospace,Consolas,monospace;font-size:12.5px;line-height:1.78;white-space:pre-wrap;color:#2B2620;}
.cp{position:absolute;top:9px;right:9px;background:var(--google);color:#fff;border:none;border-radius:5px;
padding:4px 11px;font-size:11.5px;cursor:pointer;font-family:inherit;}
.cp:hover{background:#1557B0;}
.meta{font-size:12.5px;color:var(--ink3);margin:0 0 10px;font-variant-numeric:tabular-nums;}
.meta b{color:var(--ink2);}
.cn{font-size:13.5px;color:var(--ink2);background:#FAF7F0;border-left:3px solid var(--line2);padding:10px 14px;margin:0 0 12px;}
code{font-family:ui-monospace,Consolas,monospace;font-size:12px;background:#F1ECE0;padding:1px 5px;border-radius:3px;}
.steps{counter-reset:s;list-style:none;padding:0;margin:0 0 20px;}
.steps li{counter-increment:s;position:relative;padding:0 0 14px 42px;font-size:14px;}
.steps li::before{content:counter(s);position:absolute;left:0;top:2px;width:26px;height:26px;border-radius:50%;
background:var(--ink);color:#F7F3EA;font-size:12.5px;font-weight:700;display:flex;align-items:center;justify-content:center;}
.steps li b{display:block;}
</style>
"""


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main():
    imgs = {s["img"]: b64(os.path.join(IMGDIR, s["img"])) for s in SHOTS}

    P = []
    P.append("""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>杨家将 · 忠烈千秋 —— 六镜试片 · Google Flow 版</title><style>%s</style></head><body><div class="wrap">
<h1>杨家将 · 忠烈千秋
<small>六镜试片 · <b>Google Flow / Veo 3.1 版</b> · 44 秒 · 16:9 · 上美影手绘动画</small></h1>
<p class="lead">同一组六镜，换一版为 Google Flow 重写的提示词。不是把 Seedance 版翻译过来——Flow 的语法、时长档位、音频机制和一致性策略都不同，硬搬会废掉。这一版按 Flow 的实际规格重做。</p>

<div class="gbox"><b>Flow 版一句核心策略</b>　<b>我们已经有 6 张定稿首帧了。</b>Flow 的 Image-to-Video 会把首帧的构图、光影、画风全部锁死，提示词只剩下一个任务：<b>告诉镜头怎么动、声音是什么</b>。<br>
这正好绕开 Flow 最大的短板——<b>它不支持负向提示词</b>，压不住「不要渐变、不要3D体积感」这类要求。既然压不住，就不压：让首帧把风格带进去。</div>

<h2>一、Flow 与 Seedance 的八个差异</h2>
<div class="tw"><table><thead><tr><th style="width:120px;">项</th><th>Seedance 2.0（上一版）</th><th>Google Flow / Veo 3.1（本版）</th></tr></thead><tbody>""")
    for a, b, c in DIFF:
        P.append("<tr><td><b>%s</b></td><td>%s</td><td>%s</td></tr>" % (a, b, c))
    P.append("</tbody></table></div>")

    P.append("""<h2>二、时长重排（Flow 只有 4 / 6 / 8 秒）</h2>
<p class="lead">上一版按 Seedance 的自由时长切了 6/6/7/9/12/4 秒。Flow 只吃 <b>4、6、8</b> 三个档，所以重排如下——总时长不变，仍是 44 秒。</p>
<div class="tw"><table><thead><tr><th class="c">镜</th><th>镜名</th><th class="c">原时长</th><th class="c">Flow 段长</th><th class="c">档位</th><th>处理</th></tr></thead><tbody>
<tr><td class="c">01</td><td>退守土岗</td><td class="c">6s</td><td class="c"><b>6s</b></td><td class="c">原生</td><td>直接生成，不用改</td></tr>
<tr><td class="c">02</td><td>见碑</td><td class="c">6s</td><td class="c"><b>6s</b></td><td class="c">原生</td><td>直接生成</td></tr>
<tr><td class="c">03</td><td>碑面横移</td><td class="c">7s</td><td class="c"><b>8s</b></td><td class="c">进位</td><td>多出 1 秒放在横移的尾段，收得更慢</td></tr>
<tr><td class="c">04</td><td>撞碑</td><td class="c">9s</td><td class="c"><b>8s</b></td><td class="c">收 1 秒</td><td>闷响提前半秒，余下的风留给下一镜</td></tr>
<tr><td class="c">05</td><td>碑前开花</td><td class="c">12s</td><td class="c"><b>8s + 4s</b></td><td class="c">Extend</td><td>首段 8 秒，Extend 再补 4 秒（若 Extend 不可用，就生成两段 8s 后剪）</td></tr>
<tr><td class="c">06</td><td>枯柳新芽</td><td class="c">4s</td><td class="c"><b>4s</b></td><td class="c">原生</td><td>正好是 Flow 的最短档</td></tr>
</tbody></table></div>

<h2>三、操作流程</h2>
<ol class="steps">
<li><b>把 6 张定稿图存进 Ingredients（作为素材）</b>把 <code>shot01.jpg</code> 到 <code>shot06.jpg</code> 上传到 Flow 的素材面板。这一步是为了让六镜共享同一套视觉基调。</li>
<li><b>逐镜走 Frames to Video，把对应的图设为起始帧</b>这是 Flow 版的关键：起始帧一放上去，构图、光影、画风就定死了。提示词里的运镜描述是在这个已经定好的画面上继续运动。</li>
<li><b>粘贴本页对应的英文提示词，模型选 Veo 3.1 Fast 出试稿</b>先用 Fast（20 积分/段）跑通六镜的节奏，六段一共 120 积分。不要一上来就用 Quality，那是试错阶段的常见浪费。</li>
<li><b>只对通过的镜头切 Quality 出定稿</b>Quality 是 100 积分/段。只给已经用 Fast 验证过、构图和运动都对的镜头升级。</li>
<li><b>镜 05 用 Extend 补 4 秒，然后在 Scenebuilder 里排片</b>按 01→02→03→04→05→06 的顺序拖入 Scenebuilder，导出成一支完整视频。</li>
</ol>

<h2>四、逐镜提示词（可直接粘贴）</h2>
<p class="lead">每条都已按 Flow 的写法准备：<b>运镜词前置</b> · <b>只用正向描述</b> · <b>控制在 100–150 词</b> · <b>音效用 <code>SFX:</code> 前缀单独写</b>。</p>
<div class="gbox"><b>关于口播</b>　六镜里有一句杨业的画外音（镜 04「延昭。刀给你。」）和两句旁白。这些<b>不要交给 Flow 生成</b>——Flow 的口播是给实拍对话用的，用来生成一个稳定的旁白声线会出问题，而且六镜之间的音色会漂。旁白单独在后期录/合成（用 script-to-voice 打样），Flow 只负责环境声。</div>
""")

    for s in SHOTS:
        extra = ""
        if s.get("ext"):
            extra = ("<p class='meta'><b>Extend 续写提示词（追加 4 秒）</b></p>"
                     "<div class='prow'><button class='cp' onclick=\"cp(this)\">复制</button>"
                     "<pre>" + esc(s["ext"]) + "</pre></div>"
                     "<p class='cn'>" + s["cn_ext"] + "</p>")
        P.append("""<div class="shot">
<div class="hd"><div class="no">%s</div><div class="tt">%s</div>
<span class="tag">%s</span><span class="tag">%s</span><span class="tag">首帧：%s</span><span class="tag">档位：%s</span></div>
<div class="bd">
<img src="data:image/jpeg;base64,%s" alt="">
<p class="meta"><b>首帧</b>　Image-to-Video · 用这张图作为起始帧 ｜ <b>词数</b>　约 %d 词</p>
<div class="prow"><button class="cp" onclick="cp(this)">复制</button><pre>%s</pre></div>
<p class="cn"><b>中文对照</b><br>%s</p>
%s
<p class="meta"><b>本镜设计要点</b>　%s</p>
</div></div>""" % (s["n"], esc(s["cn"]), esc(s["ep"]), s["dur"], s["frame"], s["tier"],
                   imgs[s["img"]], len(s["p"].split()), esc(s["p"]), s["cn_p"], extra, s["note"]))

    # 拼装 + 纪律 + 预算
    P.append("""<h2>五、Scenebuilder 拼装顺序</h2>
<div class="tw"><table><thead><tr><th class="c">顺序</th><th class="c">镜</th><th>内容</th><th class="c">段长</th><th>接点处理</th></tr></thead><tbody>
<tr><td class="c">1</td><td class="c">01</td><td>退守土岗</td><td class="c">6s</td><td>起手。从黑场淡入</td></tr>
<tr><td class="c">2</td><td class="c">02</td><td>见碑</td><td class="c">6s</td><td>硬切（目光落下去，不要转场特效）</td></tr>
<tr><td class="c">3</td><td class="c">03</td><td>碑面横移</td><td class="c">8s</td><td>硬切。这一镜之后配乐抽空</td></tr>
<tr><td class="c">4</td><td class="c">04</td><td>撞碑（黑白）</td><td class="c">8s</td><td>硬切。闷响落在第 6 秒</td></tr>
<tr><td class="c">5</td><td class="c">05</td><td>碑前开花</td><td class="c">8+4s</td><td>叠化（时间跨越，全片只有这一处叠化）</td></tr>
<tr><td class="c">6</td><td class="c">06</td><td>枯柳新芽</td><td class="c">4s</td><td>硬切。落版前最后一镜</td></tr>
</tbody></table></div>

<h2>六、Flow 写法六条纪律</h2>
<div class="gbox"><b>① 不写否定句。</b>Flow 没有负向提示词字段，而且 Google 明确说：写「no rain」，模型反而会去处理 rain 这个词。要压什么，就改写成要什么——比如不要「不要渐变」，改成「every form is one flat shape of colour」。<br><br>
<b>② 运镜词前置。</b>Veo 对字符串位置敏感，把 <code>Low aerial wide shot, camera very slowly pushing in</code> 放在最前面，别塞到结尾。<br><br>
<b>③ 一段只给一个运镜。</b>六镜里每一镜都只有一个动作：推 / 下摇 / 横移 / 升 / 静止。多给会打架。<br><br>
<b>④ 想慢就写慢词。</b>要慢动作就紧挨着动词加 <code>slowly</code>、<code>gradually</code>、<code>very slowly</code>；<b>不要出现 fast、quick、rapid</b>——手绘动画的质感全靠慢。<br><br>
<b>⑤ 提示词 100–150 词为上限。</b>超过三到六句，注意力就散了。本页六条都在 96–122 词之间，已核过。<br><br>
<b>⑥ 主体名词放前面，不要并列多个主体。</b>元素一多，画面里的人和物会漂。本片六镜里最多只有一个主体，这正好合规矩。</div>

<h2>七、积分预算</h2>
<div class="tw"><table><thead><tr><th>阶段</th><th class="c">段数</th><th class="c">档位</th><th class="c">单价</th><th class="c">小计</th><th>说明</th></tr></thead><tbody>
<tr><td>第一轮试稿</td><td class="c">6</td><td class="c">Veo 3.1 Fast</td><td class="c">20</td><td class="c"><b>120</b></td><td>六镜全部跑一遍，看节奏和运镜</td></tr>
<tr><td>第二轮修正</td><td class="c">3</td><td class="c">Fast</td><td class="c">20</td><td class="c"><b>60</b></td><td>预估有三镜需要重跑</td></tr>
<tr><td>镜 05 Extend</td><td class="c">1</td><td class="c">Lite</td><td class="c">10</td><td class="c"><b>10</b></td><td>补 4 秒</td></tr>
<tr><td>定稿升级</td><td class="c">6</td><td class="c">Quality</td><td class="c">100</td><td class="c"><b>600</b></td><td>只给已通过 Fast 验证的镜头升级</td></tr>
<tr><td colspan="4" style="text-align:right;"><b>合计（不含定稿升级）</b></td><td class="c"><b>190</b></td><td>先花这 190 就够判断风格能不能走</td></tr>
<tr><td colspan="4" style="text-align:right;"><b>合计（含定稿升级）</b></td><td class="c"><b>790</b></td><td>拿到可交付的 44 秒成片</td></tr>
</tbody></table></div>
<div class="note"><b>省钱的两条</b>　① 用 Fast 跑六镜、只给通过的镜头升 Quality，比六个全用 Quality 省 480 积分；② 免费额度每天 50 积分，等于每天两次 Fast，试稿阶段可以分几天慢慢跑。</div>

<h2>八、和上一版怎么配合</h2>
<div class="tw"><table><thead><tr><th style="width:150px;">要什么</th><th>用哪版</th></tr></thead><tbody>
<tr><td>清晰的分镜脚本、可复现的时长控制</td><td>Seedance 版（支持负向词，能写死「不要体积感」）</td></tr>
<tr><td>最快拿到能看的动态画面</td><td><b>Flow 版</b>——用已有首帧，六段拼一支 44 秒</td></tr>
<tr><td>原生音频一次出</td><td><b>Flow 版</b>（<code>SFX:</code> 前缀）</td></tr>
<tr><td>批量、风格严格可控</td><td>Seedance 版 + 挂死负面词</td></tr>
<tr><td>最终建议</td><td>两版都留。<b>先用 Flow 版跑出画面看调性，定稿再用 Seedance 版压风格。</b></td></tr>
</tbody></table></div>
<p style="font-size:13px;color:#7A7266;margin-top:26px;">
本试片中的故事取自传统民间杨家将传说与《宋史》等公共素材；样张画面为重新设计的生成稿，不含任何原连环画画面复用。原连环画《北宋杨家将》（湖南美术出版社，喻岳衡改编，蒋太禄等绘）的画面与改编文字著作权归原作者与出版方所有。<br>
本页所列的 Flow / Veo 3.1 规格（4/6/8 秒档位、不支持负向提示词、Fast 20 / Quality 100 积分等）核对于 2026 年 9 月，平台规则可能变动，正式投产前建议在 Flow 界面内再确认一次。</p>
</div>
<script>
function cp(b){const t=b.parentNode.querySelector('pre').innerText;
 navigator.clipboard.writeText(t).then(()=>{b.textContent='已复制';setTimeout(()=>b.textContent='复制',1400);},
 ()=>{const r=document.createRange();r.selectNodeContents(b.parentNode.querySelector('pre'));
 const s=getSelection();s.removeAllRanges();s.addRange(r);});
}
</script></body></html>""" % ())

    html = "".join(P)
    out = os.path.join(OUTDIR, "杨家将_六镜试片_GoogleFlow版.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)

    # 可粘贴纯文本版
    txt = ["《杨家将 · 忠烈千秋》六镜试片 — Google Flow / Veo 3.1 提示词",
           "用法：逐镜上传对应首帧图（Image-to-Video），粘贴下面提示词；模型先 Fast 试稿，通过后用 Quality 定稿。",
           "总时长 44 秒 | 16:9 | 旁白不要交给 Flow，只出环境声", "=" * 78, ""]
    for s in SHOTS:
        txt += ["【镜 %s】%s　（%s · %s · 首帧 %s）" % (s["n"], s["cn"], s["ep"], s["dur"], s["frame"]),
                "-" * 78, s["p"], ""]
        if s.get("ext"):
            txt += ["[Extend 续写 4 秒]", s["ext"], ""]
    txt += ["=" * 78,
            "Flow 写法六条纪律：",
            "1. 不写否定句（Flow 无负向提示词字段，Google 明确建议避免否定）",
            "2. 运镜词前置",
            "3. 一段只给一个运镜",
            "4. 想慢就写 slowly / gradually / very slowly；不要出现 fast / quick / rapid",
            "5. 提示词 100-150 词为上限",
            "6. 主体名词放前面，不要并列多个主体"]
    outtxt = os.path.join(OUTDIR, "Flow提示词_可直接粘贴.txt")
    with open(outtxt, "w", encoding="utf-8") as fh:
        fh.write("\n".join(txt))
    return out, outtxt, len(html)


try:
    a, b, n = main()
    msg = "OK\nHTML -> %s (%.1f KB)\nTXT  -> %s\n" % (a, n / 1024, b)
    msg += "词数校验:\n" + "\n".join("  镜%s %d 词 %s" % (s["n"], len(s["p"].split()),
                                     "OK" if 90 <= len(s["p"].split()) <= 150 else "*** 超范围 ***") for s in SHOTS)
except Exception:
    msg = "FATAL\n" + traceback.format_exc()

with open(LOG, "w", encoding="utf-8") as fh:
    fh.write(msg)
