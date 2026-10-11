# -*- coding: utf-8 -*-
"""把 OCR 结果整理成逐页分镜总表 xlsx（含分集统计 / 资产表 / 色盘）。"""
import os, json, re, traceback
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

BASE = r"D:\BaiduNetdiskDownload\北宋杨家将"
OCR = os.path.join(BASE, r".workbuddy\_tmp\ocr\pages.jsonl")
OUT = os.path.join(BASE, r"动画改编方案\杨家将_逐页分镜总表.xlsx")
LOG = os.path.join(BASE, r".workbuddy\_tmp\ocr\xlsx.log")

BOOKS = [("01","杨令公归宋",82),("02","邠阳城救驾",74),("03","殉国李陵碑",106),
         ("04","六郎收三将",74),("05","八姐闯幽州",82),("06","智救杨郡马",82),
         ("07","大破天门阵",90),("08","穆桂英挂帅",82)]

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

def ep_of(book, page):
    for e in EPISODES:
        if e[3] == book and e[4] <= page <= e[5]:
            return e
    return None

def norm(s):
    return re.sub(r"\s+", "", s or "")

def build_rows():
    raw = {}
    with open(OCR, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            raw[(r["book"], r["page"])] = r
    rows = []
    for bi, name, n in [(b[0], b[1], b[2]) for b in BOOKS]:
        bi = int(bi)
        for p in range(1, n + 1):
            r = raw.get((bi, p), {})
            segs = r.get("segs") or []
            H = r.get("h") or 1
            # 正文页：文字带内取 y 最大的连续块；封面/简介：全页
            if p <= 4:
                keep = sorted(segs, key=lambda s: (s["y"] // 40, s["x"]))
            else:
                # 整页 OCR：说明文字在页脚带（yf >= 0.60）
                band = [s for s in segs if s.get("yf", 1.0) >= 0.60]
                if not band:
                    band = segs
                keep = sorted(band, key=lambda s: (s["y"] // 40, s["x"]))
            txt = norm("".join(s["t"] for s in keep))
            m = re.match(r"^[（(]?(\d{1,3})[.．、）)]", txt)
            num = m.group(1) if m else ""
            body = txt[m.end():] if m else txt
            e = ep_of(bi, p)
            rows.append({
                "book": bi, "bookname": name, "page": p,
                "num": num, "text": body, "chars": len(body),
                "ep": e[0] if e else "", "epname": e[2] if e else "",
                "ptype": ("封面" if p==1 else "题名页" if p==2 else "内容简介" if p==3 else "版权/简介" if p==4 else "正文"),
            })
    return rows


C_ = "231F19"; ZHU = "B03A2E"; ALT = "FCFAF5"; PAPER = "FBF8F1"
thin = Side(style="thin", color="D2C8B2")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)

def sheet(ws, headers, rows, widths, ctr_cols=(), freeze="A2"):
    ws.append(headers)
    for c in range(1, len(headers)+1):
        cell = ws.cell(row=1, column=c)
        cell.font = Font(bold=True, color="F7F3EA", size=10.5, name="Microsoft YaHei")
        cell.fill = PatternFill("solid", fgColor=C_)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    ws.row_dimensions[1].height = 28
    for i, r in enumerate(rows, start=2):
        ws.append(list(r))
        for c in range(1, len(headers)+1):
            cell = ws.cell(row=i, column=c)
            cell.font = Font(size=9.5, name="Microsoft YaHei")
            cell.alignment = Alignment(vertical="top", wrap_text=True,
                                       horizontal="center" if c in ctr_cols else "left")
            cell.border = BORDER
            if i % 2 == 0:
                cell.fill = PatternFill("solid", fgColor=ALT)
    for idx, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = w
    if freeze:
        ws.freeze_panes = freeze


def main():
    rows = build_rows()
    wb = Workbook()

    # --- Sheet 1 逐页总表 ---
    ws1 = wb.active
    ws1.title = "逐页分镜总表672页"
    data = []
    for r in rows:
        data.append([r["book"], r["bookname"], r["page"], r["num"], r["ptype"],
                     r["ep"], r["epname"], r["text"]])
    sheet(ws1,
          ["册","册名","页","原图编号","页型","集","集名","原书说明文字（OCR）"],
          data, [4,14,5,8,10,5,14,110], ctr_cols=(1,3,4,6))

    # --- Sheet 2 分集统计 ---
    ws2 = wb.create_sheet("分集页数分配")
    cnt = {}
    for r in rows:
        if r["ptype"] == "正文" and r["ep"]:
            cnt[r["ep"]] = cnt.get(r["ep"], 0) + 1
    s2 = []
    for e in EPISODES:
        ep, season, name, bk, p0, p1 = e
        n = cnt.get(ep, 0)
        s2.append([ep, "第%d季" % season, name, "第%02d册" % bk, "%d–%d" % (p0, p1), p1-p0+1, n,
                   "约 %d 镜" % (n * 2), "%d:%.0f" % (22, (n*2*4)/60)])
    sheet(ws2, ["集","季","集名","册","页范围","页数","正文字数页","建议镜头量","预估时长"],
          s2, [5,8,16,9,10,7,11,12,10], ctr_cols=(1,2,4,5,6,7,8,9))

    # --- Sheet 3 色盘 ---
    ws3 = wb.create_sheet("剧组色盘与风格声明")
    pal = [
        ["《杨家将 · 忠烈千秋》剧组色盘与风格声明",""],
        ["",""],
        ["总风格","上美影风格（上海美术电影制片厂复古手绘动画）· 手绘墨线轮廓 + 水粉平涂上色，保留颜料笔触与手工感"],
        ["","矿物颜料色平涂、概括造型、胶片颗粒感；纯 2D，无阴影、无渐变、无 3D 体积感，大面积留白"],
        ["",""],
        ["主四色（中）","青瓷绿、朱砂红、鎏金、墨黑"],
        ["主四色（英）","celadon green, cinnabar red, gilt gold and ink black"],
        ["扩展色","赭石（荒原/悲壮）、月白（雪原/月色）、绛紫（暮色/阵图）、石青（天穹/水域）"],
        ["扩展色（英）","ochre, moon white, dark purple, azurite"],
        ["",""],
        ["朱砂纪律","全片朱砂仅三处：归宋誓师 / 杨业殉国 / 桂英挂帅。其余场景禁用红色系"],
        ["留白纪律","大面积空 negativespace 为强制项；反对满构图"],
        ["禁用词","photorealistic、皮肤纹理、二八比例、anime、cel-shading、赛璐珞、3D 渲染、体积光、渐变"],
        ["",""],
        ["硬约束（生图提示词末尾必附）","必须纯2D平涂！绝对不要阴影、不要渐变、不要3D体积感！必须大面积留白！"],
        ["",""],
        ["版权声明","故事取材于传统民间杨家将传说与《宋史》等公共素材；原连环画画面为湖南美术出版社演绎作品，本方案不含任何原画复用，造型与美术全部重新设计"],
    ]
    for i, (a, b) in enumerate(pal, start=1):
        ca = ws3.cell(row=i, column=1, value=a)
        cb = ws3.cell(row=i, column=2, value=b)
        ca.font = Font(size=10, bold=(i == 1 or (a and i > 6 and len(a) < 14)), name="Microsoft YaHei",
                       color=ZHU if i == 1 else C_)
        cb.font = Font(size=10, name="Microsoft YaHei")
        ca.alignment = Alignment(vertical="top", wrap_text=True)
        cb.alignment = Alignment(vertical="top", wrap_text=True)
    ws3.column_dimensions["A"].width = 26
    ws3.column_dimensions["B"].width = 100
    ws3.cell(row=1, column=1).font = Font(size=14, bold=True, color=ZHU, name="Microsoft YaHei")

    wb.save(OUT)
    return OUT, len(rows)


if __name__ == "__main__":
    try:
        p, n = main()
        msg = "OK rows=%d -> %s" % (n, p)
    except Exception:
        msg = "FATAL\n" + traceback.format_exc()
    with open(LOG, "w", encoding="utf-8") as fh:
        fh.write(msg)
