# -*- coding: utf-8 -*-
"""ComfyUI imported (input/) & generated (output/) asset browsing router."""
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query

from ..config import COMFY_INPUT_DIR, COMFY_OUTPUT_DIR

router = APIRouter(prefix="/api/comfy-assets", tags=["ComfyUI Assets"])

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
VIDEO_EXTS = {".mp4", ".webm", ".mov", ".avi", ".mkv"}
MEDIA_EXTS = {"all": IMAGE_EXTS | VIDEO_EXTS, "image": IMAGE_EXTS, "video": VIDEO_EXTS}

SOURCE_DIRS = {"input": COMFY_INPUT_DIR, "output": COMFY_OUTPUT_DIR}

# (source, base) -> {"t": monotonic, "items": sorted-by-mtime-desc full listing}
# 短 TTL 缓存：避免翻页/切筛选时反复全量扫描上万文件；前端可带 refresh=1 强制重扫
_SCAN_CACHE: Dict[tuple, dict] = {}
CACHE_TTL_SECONDS = 10.0


def _resolve_segment(root: Path, segment: str, label: str) -> Path:
    """Validate an untrusted single path segment from the client and resolve it under root."""
    if (
        not segment
        or segment in {".", ".."}
        or ".." in segment
        or "/" in segment
        or "\\" in segment
        or ":" in segment
        or Path(segment).is_absolute()
    ):
        raise HTTPException(status_code=400, detail=f"非法的 {label} 参数: {segment}")
    target = (root / segment).resolve()
    root = root.resolve()
    if target == root or root not in target.parents:
        raise HTTPException(status_code=400, detail=f"非法的 {label} 参数: {segment}")
    return target


def _scan_media(base: Path, root: Path) -> List[dict]:
    """Recursively list media files under base via os.scandir (entry.stat is free on Windows)."""
    items = []
    static_prefix = "/static/input/" if root == COMFY_INPUT_DIR else "/static/output/"
    stack = [str(base)]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext not in MEDIA_EXTS["all"]:
                            continue
                        stat = entry.stat()
                        rel = os.path.relpath(entry.path, root).replace("\\", "/")
                        items.append({
                            "rel_path": rel,
                            "media": "video" if ext in VIDEO_EXTS else "image",
                            "size": stat.st_size,
                            "mtime_ts": stat.st_mtime,
                            "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                            "name": entry.name,
                            "preview_url": static_prefix + quote(rel),
                        })
                    except OSError:
                        continue
        except OSError:
            continue
    return items


def _get_listing(source: str, base: Path, refresh: bool) -> List[dict]:
    key = (source, str(base))
    now = time.monotonic()
    cached = _SCAN_CACHE.get(key)
    if cached and not refresh and now - cached["t"] < CACHE_TTL_SECONDS:
        return cached["items"]
    items = _scan_media(base, SOURCE_DIRS[source])
    items.sort(key=lambda item: item["mtime_ts"], reverse=True)
    _SCAN_CACHE[key] = {"t": now, "items": items}
    return items


@router.get("/output/tree")
def get_output_tree():
    """Two-level directory tree of output/: date folders with their project folders."""
    tree: List[Dict] = []
    if not COMFY_OUTPUT_DIR.is_dir():
        return tree

    with os.scandir(COMFY_OUTPUT_DIR) as it:
        date_names = sorted((e.name for e in it if e.is_dir()), reverse=True)

    for date_name in date_names:
        date_path = COMFY_OUTPUT_DIR / date_name
        with os.scandir(date_path) as it:
            projects = sorted((e.name for e in it if e.is_dir()), reverse=True)
        tree.append({"date": date_name, "projects": projects})

    return tree


@router.get("/{source}/files")
def list_comfy_files(
    source: str,
    media: str = Query("all", description="all | image | video"),
    date: Optional[str] = Query(None, description="output 日期目录名，仅 output 有效"),
    project: Optional[str] = Query(None, description="date 下的项目目录名，仅 output 有效"),
    page: int = Query(1, ge=1),
    page_size: int = Query(60, ge=1, le=200),
    refresh: bool = Query(False, description="跳过缓存强制重扫"),
):
    """List media files under input/ or output/ with pagination, newest first."""
    if source not in SOURCE_DIRS:
        raise HTTPException(status_code=404, detail=f"未知资产来源: {source}")
    if media not in MEDIA_EXTS:
        raise HTTPException(status_code=400, detail=f"未知媒体类型: {media}")

    root = SOURCE_DIRS[source]
    base = root
    if source == "output":
        if date:
            base = _resolve_segment(root, date, "date")
        if project:
            base = _resolve_segment(base, project, "project")

    listing = _get_listing(source, base, refresh)
    if media != "all":
        listing = [item for item in listing if item["media"] == media]
    start = (page - 1) * page_size
    items = [{k: v for k, v in item.items() if k != "mtime_ts"} for item in listing[start:start + page_size]]
    return {
        "total": len(listing),
        "page": page,
        "page_size": page_size,
        "items": items,
    }
