# -*- coding: utf-8 -*-
"""补齐 4 条道具回收链 + 修正 余太君 写法。"""
import os, traceback

BASE = r"D:\BaiduNetdiskDownload\北宋杨家将"
SRC = os.path.join(BASE, r"动画改编方案\杨家将_剧本与分镜全本.html")
LOG = os.path.join(BASE, r".workbuddy\_tmp\qc\fix2.log")

EDITS = [
 # P10 枯柳：第6集 初见碑时就立起来
 ("落在一块歪在土里的碑上。</p>",
  "落在一块歪在土里的碑上。<b>碑的左侧立着一株枯柳，枝条全部折断。</b></p>",
  "P10 枯柳 @第6集：初见碑时立起枯柳"),

 # P04 酒囊：第21集 碑前找到七郎那个酒囊
 ('<p class="act"><span class="pg">8-4</span>中景。宗保站在稍远处。',
  '<p class="act"><span class="pg">8-4</span>近景。宗保在碑脚的土里，摸出一样东西——<b>一只旧酒囊</b>。'
  '皮子已经烂了，但绳子还在。<b>——这是第 6 集杨业扔给七郎的那一只；第 7 集用它做了七郎坟上的记号；'
  '现在它回到了碑前。</b></p>\n      <p class="act"><span class="pg">8-4</span>中景。宗保站在稍远处。',
  "P04 酒囊 @第21集：碑前找到酒囊，回收链闭合"),

 # P07 第九副碗筷：第23集 连同拐杖交给桂英
 ('桌上还摆着那第九副碗筷',
  '桌上还摆着那第九副碗筷',
  None),  # 占位，见下
 ('<b>——第 8 集她说过"他那把刀，我拔得动"；现在她把杖交出去了。</b></p>',
  '<b>——第 8 集她说过"他那把刀，我拔得动"；现在她把杖交出去了。</b>'
  '镜头横移：桌上还摆着那<b>第九副碗筷</b>。<b>——第 8 集她单独留出来的那一副。'
  '她把碗筷也推到了桂英面前。</b></p>',
  "P07 第九副碗筷 @第23集：连碗筷一并交给桂英"),

 # P03 延平的剑：第24集 碑前立剑
 ('<p class="act"><span class="pg">8-81</span>中景。穆桂英在碑前停下来。她把手里那根<b>龙头拐杖</b>立在碑旁。</p>',
  '<p class="act"><span class="pg">8-81</span>中景。穆桂英在碑前停下来。她把手里那根<b>龙头拐杖</b>立在碑旁。</p>\n'
  '      <p class="act"><span class="pg">8-81</span>近景。她又解下腰间那柄<b>剑</b>——延平当年赴死前留在营里、'
  '第 8 集摆在佘太君面前的那一柄——横放在碑脚。<b>——全剧的剑，到这里才真正落地。</b></p>',
  "P03 延平的剑 @第24集：碑前横放，回收链闭合"),
]


def main():
    s = open(SRC, "r", encoding="utf-8").read()
    log = []
    for old, new, tag in EDITS:
        if tag is None:
            continue
        c = s.count(old)
        if c == 1:
            s = s.replace(old, new)
            log.append("【补】%s" % tag)
        else:
            log.append("【跳过】%s（锚点出现 %d 次）" % (tag, c))

    # 人名：余太君 -> 佘太君（正文 4 处）
    c = s.count("余太君")
    if c:
        s = s.replace("余太君", "佘太君")
        log.append("【人名】余太君 → 佘太君：%d 处" % c)

    open(SRC, "w", encoding="utf-8").write(s)
    log.append("")
    log.append("已写回 %.1f KB" % (len(s.encode("utf-8")) / 1024))
    return "\n".join(log)


try:
    msg = main()
except Exception:
    msg = "FATAL\n" + traceback.format_exc()
open(LOG, "w", encoding="utf-8").write(msg)
print("done")
