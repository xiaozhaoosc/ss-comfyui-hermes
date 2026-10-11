#!/usr/bin/env python3
r"""扁平画廊生成器：递归扫描指定目录，把图片/视频/音频平铺成一个自包含 HTML 页面。

特点：
  * 生成**真实缩略图**（图片用 PIL 缩放、视频用 ffmpeg 抽首帧做 poster），
    页面只加载几百 KB 的小图，不会因几百个 4K 原图而卡死；
  * 缩略图缓存在 <目录>/_thumbnails/ 下，按源文件 mtime 判断是否重建，
    重复运行只处理新增文件，速度极快；
  * 点击图片/视频可查看或播放原文件。

用途：解决 comfyui-browser 只能逐层点目录、无法一屏看完当天全部产物的问题。

命令行用法:
  python tools/flat_gallery.py                          # 默认扫描 output/ 下最新日期目录
  python tools/flat_gallery.py --date 2026-10-09        # 按日期目录
  python tools/flat_gallery.py output/2026-10-09/yangjiajiang_ep03
  python tools/flat_gallery.py -o D:/tmp/g.html --no-thumbs

脚本内接入（3 行）:
  from tools.flat_gallery import generate_gallery
  generate_gallery()                     # 最新日期目录
  generate_gallery(r"D:\...\yangjiajiang_ep03")
"""

import argparse
import hashlib
import html
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import quote

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
VIDEO_EXT = {".mp4", ".mov", ".avi", ".webm", ".mkv"}
AUDIO_EXT = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"}

COMFY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_ROOT = os.path.join(COMFY_ROOT, "output")

THUMB_DIRNAME = "_thumbnails"
GALLERY_NAME = "_gallery.html"
THUMB_SIZE = 400
THUMB_QUALITY = 82

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")

_FFMPEG_CACHE = []


# ---------------------------------------------------------------- 工具函数

def pick_latest_date_dir() -> str:
    """在 output/ 下挑选名称以日期开头的目录中最新的一天。"""
    if not os.path.isdir(OUTPUT_ROOT):
        raise FileNotFoundError(f"output 目录不存在: {OUTPUT_ROOT}")
    cands = [d for d in os.listdir(OUTPUT_ROOT)
             if DATE_RE.match(d) and os.path.isdir(os.path.join(OUTPUT_ROOT, d))]
    if not cands:
        raise FileNotFoundError("output 下没有按日期命名的目录")
    return os.path.join(OUTPUT_ROOT, sorted(cands)[-1])


def classify(ext: str) -> str:
    if ext in IMAGE_EXT:
        return "image"
    if ext in VIDEO_EXT:
        return "video"
    if ext in AUDIO_EXT:
        return "audio"
    return "other"


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"


def _ffmpeg_exe():
    """定位 ffmpeg：环境变量 > imageio-ffmpeg 自带 > PATH > 项目内已知路径。"""
    if _FFMPEG_CACHE:
        return _FFMPEG_CACHE[0]
    exe = os.environ.get("FLAT_GALLERY_FFMPEG")
    if not exe:
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            exe = None
    if not exe:
        exe = shutil.which("ffmpeg")
    if not exe:
        for cand in (
            os.path.join(COMFY_ROOT, "tools", "faceswap_app", "dist", "FaceswapApp_gpu", "ffmpeg.exe"),
            os.path.join(COMFY_ROOT, "tools", "faceswap_app", "dist", "FaceswapApp_cpu", "ffmpeg.exe"),
        ):
            if os.path.exists(cand):
                exe = cand
                break
    _FFMPEG_CACHE.append(exe)
    return exe


# ---------------------------------------------------------------- 缩略图

def _thumb_rel(rel_path: str) -> str:
    """由源文件相对路径推导缩略图相对路径（md5 命名，避免中文/超长路径问题）。"""
    digest = hashlib.md5(rel_path.encode("utf-8")).hexdigest()
    return f"{THUMB_DIRNAME}/{digest}.jpg"


def _make_image_thumb(src: str, dst: str, size: int) -> bool:
    try:
        from PIL import Image
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with Image.open(src) as im:
            if im.mode in ("RGBA", "LA", "P"):
                im = im.convert("RGBA")
                bg = Image.new("RGB", im.size, (18, 20, 24))
                bg.paste(im, mask=im.split()[-1])
                im = bg
            else:
                im = im.convert("RGB")
            im.thumbnail((size, size), Image.LANCZOS)
            im.save(dst, "JPEG", quality=THUMB_QUALITY, optimize=True)
        return True
    except Exception:
        return False


def _make_video_thumb(src: str, dst: str, size: int) -> bool:
    exe = _ffmpeg_exe()
    if not exe:
        return False
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        cmd = [
            exe, "-y", "-loglevel", "error",
            "-ss", "0.5", "-i", src,
            "-frames:v", "1",
            "-vf", f"scale={size}:{size}:force_original_aspect_ratio=decrease",
            dst,
        ]
        r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
        return r.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 0
    except Exception:
        return False


def _ensure_thumb(it: dict, root: str, size: int, enabled: bool) -> bool:
    """确保单个文件的缩略图存在且不过期，返回是否生成了缩略图。"""
    if not enabled or it["kind"] == "audio":
        return False
    src = os.path.join(root, it["rel"].replace("/", os.sep))
    dst = os.path.join(root, it["thumb_rel"].replace("/", os.sep))
    if os.path.exists(dst) and os.path.getmtime(dst) >= it["mtime"]:
        return True
    if it["kind"] == "image":
        return _make_image_thumb(src, dst, size)
    return _make_video_thumb(src, dst, size)


def _build_thumbs(items, root, size, workers, enabled, quiet):
    """并发生成全部缩略图，返回成功数量。"""
    if not enabled:
        return 0
    todo = [it for it in items if it["kind"] in ("image", "video")]
    if not todo:
        return 0
    ok = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_ensure_thumb, it, root, size, True): it for it in todo}
        for fut in as_completed(futs):
            it = futs[fut]
            try:
                good = fut.result()
            except Exception:
                good = False
            it["has_thumb"] = bool(good)
            if good:
                ok += 1
    if not quiet:
        print(f"[*] 缩略图 {ok}/{len(todo)} 就绪（缓存于 {THUMB_DIRNAME}/）")
    return ok


# ---------------------------------------------------------------- 扫描

def collect(root: str):
    items = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames
                             if d != THUMB_DIRNAME and not d.startswith("."))
        for fn in sorted(filenames):
            if fn == GALLERY_NAME or fn.startswith("."):
                continue
            ext = os.path.splitext(fn)[1].lower()
            kind = classify(ext)
            if kind == "other":
                continue
            abs_path = os.path.join(dirpath, fn)
            rel = os.path.relpath(abs_path, root).replace(os.sep, "/")
            items.append({
                "name": fn,
                "rel": rel,
                "thumb_rel": _thumb_rel(rel),
                "sub": os.path.dirname(rel) or ".",
                "kind": kind,
                "bytes": os.path.getsize(abs_path),
                "mtime": os.path.getmtime(abs_path),
                "has_thumb": False,
            })
    items.sort(key=lambda x: (-x["mtime"]))
    return items


# ---------------------------------------------------------------- 渲染

def render_card(it: dict) -> str:
    src = quote(it["rel"], safe="/")
    thumb = quote(it["thumb_rel"], safe="/")
    name = html.escape(it["name"])
    sub = html.escape(it["sub"])
    ts = datetime.fromtimestamp(it["mtime"]).strftime("%m-%d %H:%M")
    size = human_size(it["bytes"])
    kind = it["kind"]
    has_thumb = it["has_thumb"]

    if kind == "image":
        img_src = thumb if has_thumb else src
        media = (f'<a href="{src}" target="_blank" class="thumb">'
                 f'<img src="{img_src}" loading="lazy" decoding="async" alt="{name}"></a>')
    elif kind == "video":
        poster = f' poster="{thumb}"' if has_thumb else ""
        media = (f'<video class="thumb" src="{src}"{poster} controls '
                 f'preload="none" data-kind="video"></video>')
    else:
        media = (f'<div class="thumb audio-thumb"><span class="wave">♪</span>'
                 f'<audio src="{src}" controls preload="none"></audio></div>')

    return (
        f'<div class="card" data-kind="{kind}" data-name="{name.lower()}" data-sub="{sub.lower()}">'
        f'{media}'
        f'<div class="meta"><div class="fname" title="{name}">{name}</div>'
        f'<div class="sub"><span class="chip">{sub}</span></div>'
        f'<div class="stat">{ts} · {size}</div></div>'
        f'</div>'
    )


def build_html(root: str, items: list, title: str, thumb_note: str) -> str:
    counts = {"image": 0, "video": 0, "audio": 0}
    for it in items:
        counts[it["kind"]] += 1
    cards = "\n".join(render_card(it) for it in items)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_size = human_size(sum(it["bytes"] for it in items))

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: #14161a; color: #e6e8ec;
         font: 14px/1.5 "Segoe UI", "Microsoft YaHei", system-ui, sans-serif; }}
  header {{ position: sticky; top: 0; z-index: 10; padding: 16px 22px;
            background: rgba(20,22,26,.93); backdrop-filter: blur(8px);
            border-bottom: 1px solid #2a2e35; }}
  h1 {{ margin: 0 0 4px; font-size: 17px; font-weight: 600; }}
  .path {{ color: #8b93a1; font-size: 12px; word-break: break-all; }}
  .bar {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 12px; }}
  .pill {{ padding: 4px 11px; border-radius: 999px; background: #1e222a;
           border: 1px solid #2a2e35; font-size: 12px; color: #a8b0bd; }}
  .pill b {{ color: #e6e8ec; }}
  button.f {{ cursor: pointer; padding: 5px 13px; border-radius: 8px;
              background: #1e222a; border: 1px solid #2a2e35; color: #c3cad6; font-size: 12px; }}
  button.f.on {{ background: #2563eb; border-color: #2563eb; color: #fff; }}
  input#q {{ flex: 1; min-width: 200px; padding: 7px 12px; border-radius: 8px;
             background: #1e222a; border: 1px solid #2a2e35; color: #e6e8ec; outline: none; }}
  input#q:focus {{ border-color: #2563eb; }}
  main {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
          gap: 14px; padding: 18px 22px 60px; }}
  .card {{ background: #1a1d23; border: 1px solid #262a31; border-radius: 12px;
           overflow: hidden; display: flex; flex-direction: column; }}
  .card.hide {{ display: none; }}
  .thumb {{ width: 100%; height: 190px; object-fit: contain; display: block;
            background: #0e1013; }}
  a.thumb {{ display: block; }}
  a.thumb img {{ width: 100%; height: 190px; object-fit: contain; background: #0e1013; }}
  video.thumb {{ object-fit: contain; background: #000; }}
  .audio-thumb {{ display: flex; flex-direction: column; align-items: center;
                  justify-content: center; gap: 8px; }}
  .audio-thumb .wave {{ font-size: 34px; color: #4b5563; }}
  .audio-thumb audio {{ width: 90%; }}
  .meta {{ padding: 9px 11px 11px; }}
  .fname {{ font-size: 12.5px; white-space: nowrap; overflow: hidden;
            text-overflow: ellipsis; }}
  .sub {{ margin: 4px 0; }}
  .chip {{ font-size: 11px; padding: 2px 8px; border-radius: 6px;
           background: #232833; color: #93a0b4; }}
  .stat {{ font-size: 11px; color: #6f7889; }}
  .empty {{ grid-column: 1/-1; text-align: center; color: #6f7889; padding: 60px 0; }}
</style>
</head>
<body>
<header>
  <h1>{html.escape(title)}</h1>
  <div class="path">{html.escape(root)}</div>
  <div class="bar">
    <span class="pill">共 <b>{len(items)}</b> 个</span>
    <span class="pill">图片 <b>{counts['image']}</b></span>
    <span class="pill">视频 <b>{counts['video']}</b></span>
    <span class="pill">音频 <b>{counts['audio']}</b></span>
    <span class="pill">合计 <b>{total_size}</b></span>
    {thumb_note}
    <button class="f on" data-k="all">全部</button>
    <button class="f" data-k="image">图片</button>
    <button class="f" data-k="video">视频</button>
    <button class="f" data-k="audio">音频</button>
    <input id="q" type="search" placeholder="按文件名 / 子目录过滤…">
  </div>
</header>
<main id="grid">
{cards}
{'' if items else '<div class="empty">该目录下没有可展示的媒体文件</div>'}
</main>
<script>
  const grid = document.getElementById('grid');
  const cards = [...grid.querySelectorAll('.card')];
  const q = document.getElementById('q');
  let kind = 'all';
  function apply() {{
    const kw = q.value.trim().toLowerCase();
    cards.forEach(c => {{
      const okKind = kind === 'all' || c.dataset.kind === kind;
      const okKw = !kw || c.dataset.name.includes(kw) || c.dataset.sub.includes(kw);
      c.classList.toggle('hide', !(okKind && okKw));
    }});
  }}
  document.querySelectorAll('button.f').forEach(b => b.onclick = () => {{
    document.querySelectorAll('button.f').forEach(x => x.classList.remove('on'));
    b.classList.add('on'); kind = b.dataset.k; apply();
  }});
  q.oninput = apply;
</script>
<!-- 生成时间: {generated} -->
</body>
</html>
"""


# ---------------------------------------------------------------- 对外入口

def generate_gallery(root=None, output=None, title=None, thumbs=True,
                     thumb_size=THUMB_SIZE, workers=8, quiet=False) -> dict:
    """扫描 root 目录并生成扁平画廊 HTML。

    Args:
        root: 要扫描的目录；None 时自动选 output/ 下最新日期目录。
        output: HTML 输出路径；None 时写在 root/_gallery.html。
        title: 页面标题。
        thumbs: 是否生成真实缩略图。
        thumb_size: 缩略图最长边像素。
        workers: 缩略图并发线程数。
        quiet: 是否静默。

    Returns:
        dict: {"html": 路径, "root": 目录, "total": 总数, "thumbs": 缩略图数, "counts": {...}}
    """
    if root is None:
        root = pick_latest_date_dir()
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        raise FileNotFoundError(f"目录不存在: {root}")

    items = collect(root)
    thumb_ok = _build_thumbs(items, root, thumb_size, workers, thumbs, quiet)

    title = title or f"产物画廊 · {os.path.basename(root)}"
    out_path = output or os.path.join(root, GALLERY_NAME)

    if thumbs:
        thumb_note = f'<span class="pill">缩略图 <b>{thumb_ok}</b></span>'
    else:
        thumb_note = '<span class="pill" style="color:#e0a458">原图模式</span>'

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(build_html(root, items, title, thumb_note))

    counts = {"image": 0, "video": 0, "audio": 0}
    for it in items:
        counts[it["kind"]] += 1

    if not quiet:
        print(f"[OK] 已生成画廊: {out_path}")
        print(f"     共 {len(items)} 个媒体"
              f"（图片 {counts['image']} / 视频 {counts['video']} / 音频 {counts['audio']}）")

    return {"html": out_path, "root": root, "total": len(items),
            "thumbs": thumb_ok, "counts": counts}


def main():
    ap = argparse.ArgumentParser(description="扁平画廊生成器（真实缩略图版）")
    ap.add_argument("folder", nargs="?", default=None, help="要扫描的目录（默认 output 下最新日期目录）")
    ap.add_argument("--date", default=None, help="日期目录名，如 2026-10-09")
    ap.add_argument("-o", "--output", default=None, help="输出的 HTML 路径（默认 <目录>/_gallery.html）")
    ap.add_argument("-t", "--title", default=None, help="页面标题")
    ap.add_argument("--no-thumbs", action="store_true", help="不生成缩略图，直接引用原图")
    ap.add_argument("--thumb-size", type=int, default=THUMB_SIZE, help=f"缩略图最长边（默认 {THUMB_SIZE}）")
    ap.add_argument("--workers", type=int, default=8, help="缩略图并发线程数（默认 8）")
    args = ap.parse_args()

    if args.date:
        root = os.path.join(OUTPUT_ROOT, args.date)
    elif args.folder:
        root = args.folder
    else:
        root = None

    try:
        generate_gallery(root=root, output=args.output, title=args.title,
                         thumbs=not args.no_thumbs, thumb_size=args.thumb_size,
                         workers=args.workers)
    except FileNotFoundError as e:
        raise SystemExit(f"[!] {e}")


if __name__ == "__main__":
    main()