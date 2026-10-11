# -*- coding: utf-8 -*-
"""剧本质检 · 机器层：11 项自动校验，输出 JSON + 可读报告。"""
import os, re, json, traceback
from collections import defaultdict, OrderedDict

BASE = r"D:\BaiduNetdiskDownload\北宋杨家将"
SRC = os.path.join(BASE, r"动画改编方案\杨家将_剧本与分镜全本.html")
OCR = os.path.join(BASE, r".workbuddy\_tmp\ocr\pages.jsonl")
OUTDIR = os.path.join(BASE, r".workbuddy\_tmp\qc")
os.makedirs(OUTDIR, exist_ok=True)
LOG = os.path.join(OUTDIR, "machine_report.json")
TXT = os.path.join(OUTDIR, "machine_report.txt")

BOOKS = [("01", "杨令公归宋", 82), ("02", "邠阳城救驾", 74), ("03", "殉国李陵碑", 106),
         ("04", "六郎收三将", 74), ("05", "八姐闯幽州", 82), ("06", "智救杨郡马", 82),
         ("07", "大破天门阵", 90), ("08", "穆桂英挂帅", 82)]
PAGES = {i + 1: b[2] for i, b in enumerate(BOOKS)}

EPISODES = [
    (1,1,"北汉风雪",1,1,41),(2,1,"归宋·天波府",1,42,82),
    (3,1,"邠阳城·围",2,1,37),(4,1,"邠阳城·血",2,38,74),
    (5,1,"误卯牌",3,1,35),(6,1,"李陵碑·殉国",3,36,63),
    (7,1,"七郎之死",3,64,85),(8,1,"汴京审潘",3,86,106),
    (9,2,"辞官",4,1,22),(10,2,"佳山寨",4,23,54),(11,2,"焦赞",4,55,74),
    (12,2,"双龙谷",5,1,45),(13,2,"八姐闯幽州",5,46,82),
    (14,2,"天波楼",6,1,30),(15,2,"智救杨郡马",6,31,60),(16,2,"魏州解围",6,61,82),
    (17,3,"天门阵",7,1,22),(18,3,"穆阁寨",7,23,44),(19,3,"辕门斩子",7,45,60),(20,3,"大破天门阵",7,61,90),
    (21,3,"碑上的字",8,1,21),(22,3,"寿宴请缨",8,22,42),(23,3,"内外夹攻",8,43,61),(24,3,"穆桂英挂帅",8,62,82),
]

# P01–P10 道具回收链（设计意图）道具 -> [(关键词, 应出现集...)]
PROPS = OrderedDict([
 ("P01 定宋金刀", [("刀", 2, 6, 8, 24)]),
 ("P02 龙头拐杖", [("拐杖", 19, 21, 23)]),
 ("P03 延平的剑", [("剑", 4, 8, 24)]),
 ("P04 酒囊",     [("酒囊", 6, 7, 21)]),
 ("P05 降龙木",   [("降龙木", 18, 19, 20)]),
 ("P06 银枪",     [("枪", 4, 12, 21)]),
 ("P07 第九副碗筷",[("碗筷", 8, 21, 23)]),
 ("P08 象牙算筹", [("算筹", 17, 20)]),
 ("P09 天波府匾额",[("匾", 2, 14, 16)]),
 ("P10 枯柳",     [("柳", 6, 8, 21, 24)]),
])

# 同一人物的写法变体——只列"疑似错误写法"（有意使用的称呼如六郎/七郎不算问题）
NAME_VARIANTS = [
 ("佘太君", ["余太君", "折太君"]),
 ("天波府", ["无波府", "无倭府", "无安府", "无傻府", "无楼府", "无府"]),
 ("杨延昭", ["杨延招"]),
 ("潘仁美", ["潘美"]),
 ("萧太后", ["肖太后"]),
]

BANNED = ["写实", "体积光", "渐变", "3D渲染", "photorealistic", "赛璐珞", "cel-shading", "二八比例"]
EMPTY_ADJ = ["气氛悲壮", "气氛紧张", "十分感人", "非常震撼", "气势恢宏", "情感饱满", "画面唯美", "很有张力"]


def load_ocr():
    d = {}
    with open(OCR, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            segs = r.get("segs") or []
            band = [s for s in segs if s.get("yf", 1.0) >= 0.60] or segs
            band.sort(key=lambda s: (s["y"] // 40, s["x"]))
            d[(r["book"], r["page"])] = re.sub(r"\s+", "", "".join(s["t"] for s in band))
    return d


def main():
    html = open(SRC, "r", encoding="utf-8").read()
    issues = []
    def add(sev, dim, ep, detail):
        issues.append(dict(sev=sev, dim=dim, ep=ep, detail=detail))

    # ---- 切集 ----
    ep_blocks = re.split(r'<div class="ep">', html)[1:]
    parsed = []
    for blk in ep_blocks:
        m = re.search(r'<div class="n">(\d+)</div><div class="t">(.*?)</div><div class="pages">(.*?)</div>', blk)
        if not m:
            add("致命", "结构", "?", "集块缺少标准表头（.ep-h），无法解析")
            continue
        num, title, pages = int(m.group(1)), m.group(2).strip(), m.group(3).strip()
        scenes = re.findall(r'<div class="slug">(.*?)</div>', blk)
        shots = re.findall(r'<p class="act">(.*?)</p>', blk, re.S)
        marks = []
        for s in shots:
            pm = re.search(r'<span class="pg">(\d+)-(\d+)</span>', s)
            marks.append((int(pm.group(1)), int(pm.group(2))) if pm else None)
        parsed.append(dict(ep=num, title=title, pages=pages, scenes=scenes,
                           shots=shots, marks=marks, raw=blk))

    # ---- 1. 集数与顺序 ----
    if len(parsed) != 24:
        add("致命", "结构", "全局", "集块数 = %d，应为 24" % len(parsed))
    for i, p in enumerate(parsed, 1):
        if p["ep"] != i:
            add("高", "结构", p["ep"], "集号不连续：第 %d 个集块的编号是 %d" % (i, p["ep"]))

    # ---- 2/3/4. 页码覆盖 / 越界 / 乱序 ----
    coverage = {}
    for p in parsed:
        e = next((x for x in EPISODES if x[0] == p["ep"]), None)
        if not e:
            add("致命", "分集", p["ep"], "不在分集表内")
            continue
        _, _, _, bk, p0, p1 = e
        got = [m for m in p["marks"] if m]
        inside = [m for m in got if bk == m[0] and p0 <= m[1] <= p1]
        outside = [m for m in got if not (bk == m[0] and p0 <= m[1] <= p1)]
        for m in outside:
            add("高", "页码", p["ep"], "页码标记 %d-%d 越出本集范围（册%d 第%d-%d页）" % (m[0], m[1], bk, p0, p1))
        # 乱序
        seq = [m[1] for m in inside]
        for a, b in zip(seq, seq[1:]):
            if b < a:
                add("中", "页码", p["ep"], "页码标记乱序：%d 之后出现 %d" % (a, b))
                break
        # 覆盖：跨页承接（相邻页已落镜）降级为提示
        body = [x for x in range(max(5, p0), min(p1, PAGES[bk] - 1) + 1)]
        covered = set(m[1] for m in inside)
        missing = [x for x in body if x not in covered]
        real = [x for x in missing if (x - 1) not in covered and (x + 1) not in covered]
        carries = [x for x in missing if x not in real]
        coverage[p["ep"]] = dict(book=bk, range=[p0, p1], body=len(body),
                                 covered=len([x for x in body if x in covered]),
                                 missing=missing, real=real, carry=carries)
        if carries:
            add("提示", "跨页承接", p["ep"],
                "共 %d 页未单独标注（与相邻页共用一个镜头，连环画换页处语句续接属正常）：册%d 第 %s 页"
                % (len(carries), bk, ",".join(map(str, carries))))
        if real:
            add("中", "真缺口", p["ep"],
                "正文页既无本页标记、也无相邻页标记，疑似漏内容 %d 页：册%d 第 %s 页"
                % (len(real), bk, ",".join(map(str, real))))

    # ---- 5. 分集页范围与集名 ----
    for p in parsed:
        e = next((x for x in EPISODES if x[0] == p["ep"]), None)
        if not e:
            continue
        if e[2].replace(" ", "") != p["title"].replace(" ", ""):
            add("低", "分集", p["ep"], "集名不一致：分集表作《%s》，剧本作《%s》" % (e[2], p["title"]))
        exp = "册 %d · 页 %d–%d" % (e[3], e[4], e[5])
        if exp.replace(" ", "") not in p["pages"].replace(" ", ""):
            add("低", "分集", p["ep"], "页码范围声明不一致：分集表 %s，剧本写「%s」" % (exp, p["pages"]))

    # ---- 6. 道具回收链 ----
    ep_text = {p["ep"]: p["raw"] for p in parsed}
    for prop, specs in PROPS.items():
        kw = specs[0][0]
        want = specs[0][1:]
        for ep in want:
            if ep not in ep_text:
                continue
            if kw not in ep_text[ep]:
                add("中", "回收链", ep, "%s：应出现关键词「%s」，该集全文未找到" % (prop, kw))

    # ---- 7. 朱砂纪律（三处指定：第 2 / 6 / 23 集）----
    for p in parsed:
        for kw in ("朱砂", "红色", "红装", "红缨", "一抹红", "红烛", "朱漆"):
            if kw in p["raw"]:
                if p["ep"] not in (2, 6, 23, 22):
                    add("中", "朱砂纪律", p["ep"], "出现「%s」——不在三处指定场景（第2/6/23集）内" % kw)

    # ---- 8. 李陵碑三镜 ----
    for ep, tag in ((8, "无字碑"), (21, "刻满名字"), (24, "碑前开花")):
        blk = ep_text.get(ep, "")
        if "李陵碑" not in blk and "碑" not in blk:
            add("致命", "贯穿意象", ep, "缺少李陵碑镜头（%s）" % tag)
        else:
            if "同机位" not in blk and "同 机位" not in blk and "同一机位" not in blk:
                add("中", "贯穿意象", ep, "有碑的镜头但未标注「同机位」——三镜一致性会失守")

    # ---- 9. 人名写法（排除片尾史实标注——那里「折太君」是刻意写的）----
    whole = html.replace("史书作折太君", "").replace("史书作杨继业", "")
    for canon, variants in NAME_VARIANTS:
        for v in variants:
            if v in whole:
                add("低", "人名一致性", "-", "「%s」出现在正文（规范写法：%s）" % (v, canon))

    # ---- 10. 禁用词（排除第 1 节风格声明——那里是"禁用词清单"本身） ----
    body_only = html.split('<section id="s6">')[1] if '<section id="s6">' in html else html
    for kw in BANNED:
        if kw in body_only:
            add("高", "禁用词", "-", "正文出现禁用词「%s」（会污染下游提示词）" % kw)
    for kw in EMPTY_ADJ:
        if kw in body_only:
            add("中", "空话形容词", "-", "出现不可拍的形容词「%s」——分镜里应改成具体动作" % kw)

    # ---- 11. 镜头/台词配比 ----
    stats = []
    for p in parsed:
        nsh = len(p["shots"])
        dlg = len(re.findall(r'<p class="dlg">', p["raw"]))
        vo = len(re.findall(r'<p class="vo">', p["raw"]))
        stats.append(dict(ep=p["ep"], title=p["title"], scenes=len(p["scenes"]),
                          shots=nsh, dlg=dlg, vo=vo,
                          sec_by_shot=nsh * 3, min=nsh * 3 / 60))
        if nsh < 15:
            add("中", "节奏", p["ep"], "镜头数仅 %d，偏少（全剧均值约 34）" % nsh)
    # 时长缺口：按本片实际节奏（慢，平均 5–7 秒/镜）估算
    LO, HI = 5, 7
    for s in stats:
        s["lo_min"] = round(s["shots"] * LO / 60, 1)
        s["hi_min"] = round(s["shots"] * HI / 60, 1)
    tot_lo = round(sum(s["shots"] for s in stats) * LO / 60, 1)
    tot_hi = round(sum(s["shots"] for s in stats) * HI / 60, 1)
    add("致命", "格式匹配", "全局",
        "全剧 %d 镜，按本片节奏（%d–%d 秒/镜）估算总时长仅 %s–%s 分钟；"
        "声明格式「24 集 × 22 分钟」= 528 分钟，缺口约 %.1f 倍。当前剧本属「关键分镜级」，不是可拍摄的逐镜头级"
        % (sum(s["shots"] for s in stats), LO, HI, tot_lo, tot_hi, 528 / max(tot_hi, 1)))

    tot_shots = sum(s["shots"] for s in stats)
    tot_dlg = sum(s["dlg"] for s in stats)
    report = dict(
        episodes=len(parsed), scenes=sum(s["scenes"] for s in stats),
        shots=tot_shots, dialogue=tot_dlg,
        est_minutes=round(tot_shots * 3 / 60, 1),
        coverage=coverage, stats=stats, issues=issues,
    )
    with open(LOG, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)

    # 可读报告
    by = defaultdict(list)
    for it in issues:
        by[it["sev"]].append(it)
    L = ["剧本质检 · 机器层报告",
         "=" * 70,
         "集=%d  场=%d  镜头=%d  台词块=%d" % (len(parsed), report["scenes"], tot_shots, tot_dlg),
         "总时长估算：按 5 秒/镜 = %.0f 分钟；按 7 秒/镜 = %.0f 分钟   （声明格式 24×22 = 528 分钟）"
         % (tot_shots * 5 / 60, tot_shots * 7 / 60),
         "",
         "问题分级：致命 %d / 高 %d / 中 %d / 低 %d / 提示 %d  合计 %d" %
         (len(by["致命"]), len(by["高"]), len(by["中"]), len(by["低"]), len(by["提示"]), len(issues)), ""]
    for sev in ("致命", "高", "中", "低", "提示"):
        if not by[sev]:
            continue
        L.append("── %s（%d）" % (sev, len(by[sev])))
        for it in by[sev]:
            L.append("   [%s] 第%s集  %s" % (it["dim"], it["ep"], it["detail"]))
        L.append("")
    L.append("── 逐集覆盖")
    for s in stats:
        c = coverage[s["ep"]]
        L.append("   第%2d集 %-14s 册%d %2d-%3d | 正文%3d页 覆盖%3d 缺%2d | 场%2d 镜%3d 台词%2d" %
                 (s["ep"], s["title"], c["book"], c["range"][0], c["range"][1],
                  c["body"], c["covered"], len(c["missing"]), s["scenes"], s["shots"], s["dlg"]))
    open(TXT, "w", encoding="utf-8").write("\n".join(L))
    return len(issues)


try:
    n = main()
    msg = "OK issues=%d" % n
except Exception:
    msg = "FATAL\n" + traceback.format_exc()
print(msg)
