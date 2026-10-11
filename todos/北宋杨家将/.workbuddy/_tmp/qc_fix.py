# -*- coding: utf-8 -*-
"""剧本自洽性修复 v2：只做零风险机械修正。"""
import os, re, shutil, traceback

BASE = r"D:\BaiduNetdiskDownload\北宋杨家将"
SRC = os.path.join(BASE, r"动画改编方案\杨家将_剧本与分镜全本.html")
BAK = os.path.join(BASE, r".workbuddy\_tmp\qc\剧本_修复前备份.html")
LOG = os.path.join(BASE, r".workbuddy\_tmp\qc\fix.log")

NEW_EP = {1:(1,1,41),2:(1,42,82),3:(2,1,37),4:(2,38,74),5:(3,1,35),6:(3,36,63),
          7:(3,64,85),8:(3,86,106),
          9:(4,1,22),10:(4,23,54),11:(4,55,74),
          12:(5,1,45),13:(5,46,82),
          14:(6,1,30),15:(6,31,60),16:(6,61,82),
          17:(7,1,22),18:(7,23,44),19:(7,45,60),20:(7,61,90),
          21:(8,1,21),22:(8,22,42),23:(8,43,61),24:(8,62,82)}

# 页码标记修正（仅在全文唯一出现时应用，避免误改）
MARK_FIX = {"1-62":"1-63", "2-38":"2-39", "3-16":"3-17", "3-23":"3-24", "3-71":"3-72"}


def find_block(s, start):
    i, depth = start, 0
    pat = re.compile(r"<div\b|</div>")
    while True:
        m = pat.search(s, i)
        if not m:
            raise ValueError("unbalanced")
        depth += 1 if m.group(0) == "<div" else -1
        i = m.end()
        if depth == 0:
            return i, s[start:i]


def scenes(blk):
    out = []
    for m in re.finditer(r'<div class="sc">', blk):
        en, b = find_block(blk, m.start())
        sm = re.search(r'<div class="slug">(.*?)</div>', b)
        out.append((m.start(), en, sm.group(1).strip() if sm else "", b))
    return out


def main():
    html = open(SRC, "r", encoding="utf-8").read()
    shutil.copy(SRC, BAK)
    log = ["备份 -> %s" % BAK, ""]

    eps = []
    for m in re.finditer(r'<div class="ep">', html):
        en, blk = find_block(html, m.start())
        nm = re.search(r'<div class="n">(\d+)</div>', blk)
        eps.append(dict(num=int(nm.group(1)), start=m.start(), end=en, blk=blk))
    eps.sort(key=lambda x: x["num"])
    assert len(eps) == 24, len(eps)

    def E(n):
        return next(x for x in eps if x["num"] == n)

    # 1. 删 第6集 场6-7（与第7集场7-1 重复）
    e6 = E(6)
    for st, en, slug, b in scenes(e6["blk"]):
        if slug.startswith("6-7"):
            e6["blk"] = e6["blk"][:st] + e6["blk"][en:]
            log.append("【删重复】第6集 场 %s（%d 字符）——与第7集场7-1 内容重复" % (slug, len(b)))
            break

    # 2. 移 第13集 场13-1/13-2 → 第12集
    e12, e13 = E(12), E(13)
    mv = [b for b in scenes(e13["blk"]) if b[2].startswith(("13-1", "13-2"))]
    txt = "".join(b[3] for b in mv)
    for st, en, slug, b in sorted(mv, key=lambda x: -x[0]):
        e13["blk"] = e13["blk"][:st] + e13["blk"][en:]
    last = scenes(e12["blk"])[-1]
    e12["blk"] = e12["blk"][:last[1]] + txt + e12["blk"][last[1]:]
    log.append("【移】第13集 → 第12集：%d 场（%s）" % (len(mv), "、".join(b[2] for b in mv)))

    # 3. 移 第23集 场23-3 → 第24集 开头
    e23, e24 = E(23), E(24)
    mv2 = [b for b in scenes(e23["blk"]) if b[2].startswith("23-3")]
    if mv2:
        st, en, slug, b = mv2[0]
        e23["blk"] = e23["blk"][:st] + e23["blk"][en:]
        f24 = scenes(e24["blk"])[0]
        e24["blk"] = e24["blk"][:f24[0]] + b + e24["blk"][f24[0]:]
        log.append("【移】第23集 → 第24集：场 %s（内外夹攻决战）" % slug)

    # 4. 重排场号 + 集头 .pages
    for e in eps:
        n = e["num"]; bk, p0, p1 = NEW_EP[n]
        scs = scenes(e["blk"])
        for i, (st, en, slug, b) in enumerate(scs, 1):
            ns = re.sub(r"^\d+-\d+", "%d-%d" % (n, i), slug)
            if ns != slug:
                e["blk"] = e["blk"].replace('<div class="slug">%s</div>' % slug,
                                            '<div class="slug">%s</div>' % ns, 1)
        e["blk"] = re.sub(r'<div class="pages">.*?</div>',
                          '<div class="pages">册 %d · 页 %d–%d · %d 页</div>' % (bk, p0, p1, p1 - p0 + 1),
                          e["blk"], count=1)

    # 5. 回写（从后往前，避免索引失效）
    out = html
    for e in sorted(eps, key=lambda x: -x["start"]):
        out = out[:e["start"]] + e["blk"] + out[e["end"]:]

    # 6. 页码标记修正（只改唯一出现的）
    for old, new in MARK_FIX.items():
        tk = '<span class="pg">%s</span>' % old
        c = out.count(tk)
        if c == 1:
            out = out.replace(tk, '<span class="pg">%s</span>' % new)
            log.append("【标记】%s → %s" % (old, new))
        else:
            log.append("【标记】跳过 %s（出现 %d 次，需人工定位）" % (old, c))

    # 7. 朱砂纪律口径统一
    reps = [
        ("归宋誓师（第 2 集）、杨业殉国（第 8 集）、桂英挂帅（第 24 集）",
         "归宋誓师（第 2 集）、杨业殉国（第 6 集）、桂英挂帅（第 23 集）"),
        ("归宋誓师 / 杨业殉国 / 桂英挂帅", "归宋誓师（第2集）/ 杨业殉国（第6集）/ 桂英挂帅（第23集）"),
        ("<b>归宋誓师</b>（第 2 集）、<b>杨业殉国</b>（第 6 集）、<b>桂英挂帅</b>（第 24 集）",
         "<b>归宋誓师</b>（第 2 集）、<b>杨业殉国</b>（第 6 集）、<b>桂英挂帅</b>（第 23 集）"),
        ("全片朱砂只有三处：归宋誓师 / 杨业殉国 / 桂英挂帅",
         "全片朱砂只有三处：归宋誓师（第2集）/ 杨业殉国（第6集）/ 桂英挂帅（第23集）"),
        ("（第2集）/ 杨业殉国（第6集）/ 桂英挂帅（第24集）",
         "（第2集）/ 杨业殉国（第6集）/ 桂英挂帅（第23集）"),
    ]
    for a, b in reps:
        if a in out and a != b:
            c = out.count(a); out = out.replace(a, b); log.append("【口径】替换 %d 处：%s" % (c, a[:34]))

    # 8. 第21集 补同机位
    if "【本集的核心镜头 · 李陵碑第二次出现】" in out:
        out = out.replace("【本集的核心镜头 · 李陵碑第二次出现】",
                          "【本集的核心镜头 · 李陵碑第二次出现 · 与第 8 集同机位】")
        log.append("【标注】第21集 李陵碑镜头补「与第8集同机位」")

    # 9. 第2节分集表同步
    def fix_row(m):
        n = int(m.group(1))
        bk, p0, p1 = NEW_EP[n]
        rest = m.group(4)
        return ('<tr><td class="num">%d</td><td class="c">%s</td><td><b>%s</b></td>'
                '<td class="c">%d</td><td class="c">%d–%d</td><td class="num">%d</td><td>%s</td></tr>'
                % (n, m.group(2), m.group(3), bk, p0, p1, p1 - p0 + 1, rest))
    pat = re.compile(r'<tr><td class="num">(\d+)</td><td class="c">([一二三])</td><td><b>(.*?)</b></td>'
                     r'<td class="c">\d+</td><td class="c">[\d–\-]+</td><td class="num">\d+</td><td>(.*?)</td></tr>')
    out, cnt = pat.subn(fix_row, out)
    log.append("【分集表】同步 %d 行" % cnt)

    open(SRC, "w", encoding="utf-8").write(out)
    log.append("")
    log.append("已写回（%.1f KB）" % (len(out.encode("utf-8")) / 1024))
    log.append("新分集表：")
    for n in range(1, 25):
        bk, p0, p1 = NEW_EP[n]
        log.append("  %2d  册%d  %3d-%3d  (%d 页)" % (n, bk, p0, p1, p1 - p0 + 1))
    return "\n".join(log)


try:
    msg = main()
except Exception:
    msg = "FATAL\n" + traceback.format_exc()
open(LOG, "w", encoding="utf-8").write(msg)
print("done")
