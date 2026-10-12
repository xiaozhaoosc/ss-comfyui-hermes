#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根据 garment_library/index.json 生成人类可读的清单与可视化目录

产物（都在 garment_library/ 下）:
  INDEX.md    Markdown 清单表格（概览 + 分组图片墙），适合贴文档/对话
  index.html  可视化目录（缩略图卡片网格 + 类别筛选 + 搜索 + 一键复制路径），双击浏览器打开

用法:
  python tools/garment_extract/library_build_index.py        # 刷新索引
  python tools/garment_extract/library_build_index.py --no-html
"""
import argparse
import json
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
LIB = os.path.join(ROOT, "garment_library")

CAT_CN = {"tops": "上装", "bottoms": "下装", "full": "整套", "outerwear": "外套", "shoes": "鞋"}
THUMB_MAX = 320

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>服装库目录 · garment_library</title>
<style>
  :root{
    --bg:#f7f8fa; --card:#ffffff; --bd:#e3e6ec; --tx:#1d2129; --tx2:#5c6373;
    --accent:#3b6ef6; --chip:#eef2ff; --shadow:0 1px 3px rgba(0,0,0,.06);
  }
  @media (prefers-color-scheme: dark){
    :root{ --bg:#15171c; --card:#1e2128; --bd:#2c313b; --tx:#e6e8ee; --tx2:#9aa2b1;
           --accent:#6f9bff; --chip:#263049; --shadow:0 1px 3px rgba(0,0,0,.3); }
  }
  *{box-sizing:border-box}
  body{margin:0;padding:24px;background:var(--bg);color:var(--tx);
       font:14px/1.5 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
  h1{font-size:20px;margin:0 0 4px}
  .sub{color:var(--tx2);font-size:13px;margin-bottom:18px}
  .bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:16px}
  .bar input{padding:7px 11px;border:1px solid var(--bd);border-radius:8px;background:var(--card);
             color:var(--tx);width:220px;font-size:13px}
  .tab{padding:6px 12px;border:1px solid var(--bd);border-radius:999px;background:var(--card);
       color:var(--tx2);cursor:pointer;font-size:13px;user-select:none}
  .tab.on{background:var(--accent);color:#fff;border-color:var(--accent)}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:14px}
  .card{background:var(--card);border:1px solid var(--bd);border-radius:12px;overflow:hidden;
        box-shadow:var(--shadow);display:flex;flex-direction:column}
  .thumb{height:230px;background:#fff;display:flex;align-items:center;justify-content:center;padding:6px}
  .thumb img{max-width:100%;max-height:100%;object-fit:contain}
  .body{padding:10px 12px 12px;border-top:1px solid var(--bd)}
  .gid{font-weight:600;font-size:13px;word-break:break-all}
  .meta{color:var(--tx2);font-size:12px;margin-top:4px}
  .row{display:flex;align-items:center;gap:6px;margin-top:6px;flex-wrap:wrap}
  .sw{width:16px;height:16px;border-radius:4px;border:1px solid var(--bd)}
  .chip{background:var(--chip);color:var(--tx2);border-radius:6px;padding:1px 7px;font-size:11px}
  .btn{margin-top:9px;width:100%;padding:6px;border:1px solid var(--bd);border-radius:8px;
       background:transparent;color:var(--tx2);cursor:pointer;font-size:12px}
  .btn:hover{border-color:var(--accent);color:var(--accent)}
  .empty{color:var(--tx2);padding:30px;text-align:center}
  .toast{position:fixed;left:50%;bottom:28px;transform:translateX(-50%);background:var(--tx);
         color:var(--bg);padding:8px 16px;border-radius:8px;font-size:13px;opacity:0;
         transition:opacity .2s;pointer-events:none}
  .toast.on{opacity:.95}
</style>
</head>
<body>
<h1>服装库目录</h1>
<div class="sub" id="sub"></div>
<div class="bar">
  <input id="q" placeholder="搜索 ID / 来源 / 备注">
  <span class="tab on" data-c="__all">全部</span>
  __TABS__
</div>
<div class="grid" id="grid"></div>
<div class="empty" id="empty" style="display:none">没有匹配的服装</div>
<div class="toast" id="toast"></div>
<script>
const DATA = __DATA__;
const CAT_CN = __CATCN__;
const grid = document.getElementById('grid');
const empty = document.getElementById('empty');
let cur = '__all', kw = '';

document.getElementById('sub').textContent =
  `共 ${DATA.length} 件 · ` + Object.entries(
    DATA.reduce((m,g)=>(m[g.category]=(m[g.category]||0)+1,m),{})
  ).map(([k,v])=>`${CAT_CN[k]||k} ${v}`).join(' / ') + ' · 点击卡片下方按钮复制透明底路径';

function card(g){
  const d = document.createElement('div');
  d.className = 'card';
  const thumb = g.thumb || (g.dir + '/white.png');
  d.innerHTML = `
    <div class="thumb"><img src="${thumb}" alt="${g.garment_id}" loading="lazy"></div>
    <div class="body">
      <div class="gid">${g.garment_id}</div>
      <div class="meta">${g.size ? g.size[0]+'×'+g.size[1] : '-'} · ${g.mask_area_px ? (g.mask_area_px/1000).toFixed(0)+'k px' : '-'}${g.versions_count>1?' · '+g.versions_count+' 版本':''}</div>
      <div class="row">
        <span class="sw" style="background:${g.mean_hex}"></span>
        <span class="meta">${g.mean_hex}</span>
        <span class="chip">${CAT_CN[g.category]||g.category}</span>
        ${g.method?`<span class="chip">${g.method}</span>`:''}
      </div>
      <div class="meta" style="margin-top:6px">${g.label||''}${g.source_url?` · <a href="${g.source_url}" target="_blank" style="color:var(--accent)">来源</a>`:''}</div>
      <button class="btn" data-p="${g.dir}/transparent.png">复制路径</button>
    </div>`;
  d.querySelector('button').onclick = () => copy(g.dir + '/transparent.png');
  return d;
}
function render(){
  const list = DATA.filter(g =>
    (cur==='__all' || g.category===cur) &&
    (!kw || (g.garment_id+' '+(g.label||'')+' '+(g.note||'')+' '+g.mean_hex).toLowerCase().includes(kw))
  );
  grid.innerHTML = '';
  list.forEach(g => grid.appendChild(card(g)));
  empty.style.display = list.length ? 'none' : 'block';
}
function copy(p){
  const t = document.getElementById('toast');
  const done = () => { t.textContent = '已复制: ' + p; t.classList.add('on');
                       setTimeout(()=>t.classList.remove('on'), 1600); };
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(p).then(done).catch(()=>prompt('手动复制:', p));
  } else {
    const ta = document.createElement('textarea'); ta.value = p;
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); done(); } catch(e){ prompt('手动复制:', p); }
    ta.remove();
  }
}
document.getElementById('q').oninput = e => { kw = e.target.value.trim().toLowerCase(); render(); };
document.querySelectorAll('.tab').forEach(t => t.onclick = () => {
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
  t.classList.add('on'); cur = t.dataset.c; render();
});
render();
</script>
</body>
</html>
"""


def ensure_thumb(gdir):
    """目录缺 thumb.png 时用 white.png 补一张"""
    w = os.path.join(gdir, "white.png")
    t = os.path.join(gdir, "thumb.png")
    if os.path.isfile(t) or not os.path.isfile(w):
        return os.path.isfile(t)
    im = Image.open(w).convert("RGB")
    im.thumbnail((THUMB_MAX, THUMB_MAX), Image.LANCZOS)
    im.save(t)
    return True


def main():
    ap = argparse.ArgumentParser(description="生成服装库清单与可视化目录")
    ap.add_argument("--no-html", action="store_true")
    a = ap.parse_args()

    idx_path = os.path.join(LIB, "index.json")
    if not os.path.isfile(idx_path):
        sys_exit = f"找不到 {idx_path}"
        raise SystemExit(sys_exit)
    with open(idx_path, encoding="utf-8") as f:
        items = json.load(f)

    # 补 thumb + 缺漏的 size + 读 meta 里的 note
    changed = False
    for g in items:
        gdir = os.path.join(LIB, g["dir"])
        if ensure_thumb(gdir):
            g["thumb"] = os.path.relpath(os.path.join(gdir, "thumb.png"), LIB).replace("\\", "/")
        tp = os.path.join(gdir, "transparent.png")
        if not g.get("size") and os.path.isfile(tp):
            with Image.open(tp) as im:
                g["size"] = list(im.size)
            changed = True
        mp = os.path.join(gdir, "meta.json")
        if os.path.isfile(mp):
            try:
                with open(mp, encoding="utf-8") as f:
                    meta = json.load(f)
                g["note"] = meta.get("note", "")
                if not g.get("method"):
                    g["method"] = meta.get("method", "")
                if changed and "size" in g:
                    meta["size"] = g["size"]
                    with open(mp, "w", encoding="utf-8") as f:
                        json.dump(meta, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
    if changed:
        with open(idx_path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        print(f"index.json 补全 size 字段 -> {idx_path}")

    # ---------------- INDEX.md ----------------
    by_cat = {}
    for g in items:
        by_cat.setdefault(g["category"], []).append(g)

    L = []
    L.append("# 服装库清单 · garment_library\n")
    L.append(f"> 自动生成，请勿手改；重跑 `python tools/garment_extract/library_build_index.py` 刷新。"
             f"  共 **{len(items)}** 件，更新于 {__import__('time').strftime('%Y-%m-%d %H:%M')}\n")

    L.append("\n## 一、总表\n")
    L.append("| # | garment_id | 类别 | 主色 | 尺寸 | 掩码面积 | 版本 | 方法 | 来源标签 | 库内路径 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for i, g in enumerate(items, 1):
        L.append("| {} | `{}` | {} | <span style=\"color:{}\">■</span> `{}` | {}×{} | {} | {} | {} | {} | `{}` |".format(
            i, g["garment_id"], CAT_CN.get(g["category"], g["category"]),
            g.get("mean_hex", "#000"), g.get("mean_hex", ""),
            g.get("size", ["?", "?"])[0], g.get("size", ["?", "?"])[1],
            f"{g['mask_area_px']:,}" if g.get("mask_area_px") else "-",
            g.get("versions_count", 1), g.get("method", "-"),
            g.get("label", "-"), g.get("dir", "").replace("\\", "/")))

    L.append("\n## 二、缩略图墙\n")
    for cat in sorted(by_cat):
        L.append(f"\n### {CAT_CN.get(cat, cat)}（{cat}/，共 {len(by_cat[cat])} 件）\n")
        for g in by_cat[cat]:
            url = f" [{g['source_url']}]({g['source_url']})" if g.get("source_url") else ""
            L.append(f"**`{g['garment_id']}`** · {g.get('mean_hex','')} · {g.get('size',['?','?'])[0]}×{g.get('size',['?','?'])[1]}"
                     f" · {g.get('label','')}{url}\n")
            L.append(f"![{g['garment_id']}]({g.get('thumb', g['dir'].replace(chr(92),'/') + '/white.png')})\n")
            if g.get("note"):
                L.append(f"> {g['note']}\n")

    L.append("\n## 三、文件结构\n")
    L.append("```\ngarment_library/\n"
             "├── index.json     机读索引（脚本/工作流读这个）\n"
             "├── INDEX.md       本清单（人读）\n"
             "├── index.html     可视化目录（双击打开，可筛选/复制路径）\n"
             "├── tops/ bottoms/ full/   每件一个子目录\n"
             "│   └── <garment_id>/{transparent.png, white.png, thumb.png, meta.json, alts/}\n"
             "└── sources/       原始参考图存档\n```\n")
    L.append("\n## 四、常用命令\n")
    L.append("```bash\n"
             "# 单图提取（人工框更稳）：\n"
             "python tools/garment_extract/extract_from_image.py <图片> <运行目录> [--boxes top=x0,y0,x1,y1]\n"
             "python tools/garment_extract/library_add.py <运行目录> --source-url ... --note ...\n\n"
             "# 既有产物批量入库（extract_garment.py 的视频产物）：\n"
             "python tools/garment_extract/library_import.py output/2026-10-11/garment_extract --category full\n\n"
             "# 刷新本清单与 HTML 目录：\n"
             "python tools/garment_extract/library_build_index.py\n```\n")

    md = os.path.join(LIB, "INDEX.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"INDEX.md -> {md} ({len(items)} 件)")

    # ---------------- index.html ----------------
    if not a.no_html:
        cats = sorted(by_cat)
        tabs = "\n  ".join(
            f'<span class="tab" data-c="{c}">{CAT_CN.get(c, c)} {len(by_cat[c])}</span>' for c in cats)
        keys = ("garment_id", "category", "label", "mean_hex", "size",
                "mask_area_px", "versions_count", "method", "dir",
                "thumb", "note", "source_url")
        slim = []
        for g in items:
            d = {k: g.get(k) for k in keys}
            # file:// 下浏览器不认反斜杠，统一成正斜杠
            for k in ("dir", "thumb"):
                if d.get(k):
                    d[k] = d[k].replace("\\", "/")
            if not d.get("thumb") and d.get("dir"):
                d["thumb"] = d["dir"] + "/thumb.png"
            slim.append(d)
        html = (HTML.replace("__TABS__", tabs)
                    .replace("__DATA__", json.dumps(slim, ensure_ascii=False))
                    .replace("__CATCN__", json.dumps(CAT_CN, ensure_ascii=False)))
        hp = os.path.join(LIB, "index.html")
        with open(hp, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"index.html -> {hp}")


if __name__ == "__main__":
    main()
