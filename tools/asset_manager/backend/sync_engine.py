# -*- coding: utf-8 -*-
"""Bidirectional synchronization engine.

Synchronizes local library directories (character_library/ & garment_library/)
with the SQLite cache database, and performs lossless real-time writebacks
to preserve full CLI script compatibility.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from .config import CHARACTER_LIB_DIR, GARMENT_LIB_DIR, ROOT_DIR
from .models import CharacterModel, ComboModel, GarmentModel
from .vector_math import get_or_load_embedding

logger = logging.getLogger(__name__)


# ============================================================================
# Scanning and Loading from Library Files
# ============================================================================

def sync_characters_from_disk(db: Session) -> int:
    """Read character_library/index.json and sync into SQLite."""
    index_file = CHARACTER_LIB_DIR / "index.json"
    if not index_file.exists():
        logger.warning(f"Character index not found: {index_file}")
        return 0

    try:
        raw_data = json.loads(index_file.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Failed to parse {index_file}: {e}")
        return 0

    count = 0
    for item in raw_data:
        cid = item.get("char_id")
        if not cid:
            continue

        model = db.query(CharacterModel).filter_by(char_id=cid).first()
        if not model:
            model = CharacterModel(char_id=cid)
            db.add(model)

        model.name = item.get("name", cid)
        model.face = item.get("face", f"faces/{cid}/face.png")
        model.thumb = item.get("thumb", f"faces/{cid}/thumb.png")
        model.embedding = item.get("embedding", f"faces/{cid}/embedding.npy")
        model.emb_dim = item.get("emb_dim", 512)
        model.emb_model = item.get("emb_model", "insightface/w600k_r50")
        model.det_model = item.get("det_model", "insightface/det_10g")
        model.det_score = float(item.get("det_score", 0.0))
        model.face_bbox_json = json.dumps(item.get("face_bbox", []))
        model.img_shape_json = json.dumps(item.get("img_shape", []))
        model.alts_json = json.dumps(item.get("alts", []))
        model.ref_outputs_json = json.dumps(item.get("ref_outputs", []))
        model.source = item.get("source", "")
        model.added_date = item.get("added_date", "")
        model.note = item.get("note", "")

        # Preserve existing tags if present
        if not model.tags_json or model.tags_json == "[]":
            model.tags_json = json.dumps(item.get("tags", []))

        # Preload embedding vector into memory cache
        emb_path = CHARACTER_LIB_DIR / model.embedding
        if emb_path.exists():
            get_or_load_embedding(cid, emb_path)

        count += 1

    db.commit()
    return count


def sync_garments_from_disk(db: Session) -> int:
    """Read garment_library/index.json and sync into SQLite."""
    index_file = GARMENT_LIB_DIR / "index.json"
    if not index_file.exists():
        logger.warning(f"Garment index not found: {index_file}")
        return 0

    try:
        raw_data = json.loads(index_file.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Failed to parse {index_file}: {e}")
        return 0

    count = 0
    for item in raw_data:
        gid = item.get("garment_id")
        if not gid:
            continue

        model = db.query(GarmentModel).filter_by(garment_id=gid).first()
        if not model:
            model = GarmentModel(garment_id=gid)
            db.add(model)

        model.category = item.get("category", "full")
        model.label = item.get("label", "")
        model.mean_hex = item.get("mean_hex", "#000000")
        model.mask_area_px = int(item.get("mask_area_px", 0))
        model.crop_bbox_json = json.dumps(item.get("crop_bbox", []))
        model.size_json = json.dumps(item.get("size", []))
        model.method = item.get("method", "sam2_box")
        model.versions_count = int(item.get("versions_count", 1))
        model.source_image = item.get("source_image", "")
        model.source_url = item.get("source_url", "")
        model.origin_dir = item.get("origin_dir", "")
        model.added_date = item.get("added_date", "")
        
        dir_p = item.get("dir", f"{model.category}/{gid}")
        model.dir_path = dir_p
        model.thumb = item.get("thumb", f"{dir_p}/thumb.png")

        # Set transparent and white asset paths relative to garment_library
        model.transparent_path = f"{dir_p}/transparent.png".replace("\\", "/")
        model.white_path = f"{dir_p}/white.png".replace("\\", "/")

        model.note = item.get("note", "")

        if not model.tags_json or model.tags_json == "[]":
            model.tags_json = json.dumps(item.get("tags", []))

        count += 1

    db.commit()
    return count


def sync_combos_from_disk(db: Session) -> int:
    """Read combos.json and sync into SQLite."""
    combos_file = ROOT_DIR / "combos.json"
    if not combos_file.exists():
        return 0

    try:
        raw_data = json.loads(combos_file.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Failed to parse {combos_file}: {e}")
        return 0

    count = 0
    for item in raw_data:
        cid = item.get("combo_id")
        if not cid:
            continue

        model = db.query(ComboModel).filter_by(combo_id=cid).first()
        if not model:
            model = ComboModel(combo_id=cid)
            db.add(model)

        model.name = item.get("name", cid)
        model.char_id = item.get("char_id", "")
        model.garment_id = item.get("garment_id", "")
        model.preview_image = item.get("preview_image", "")
        model.preview_video = item.get("preview_video", "")
        model.prompt_preset = item.get("prompt_preset", "")
        model.note = item.get("note", "")
        model.tags_json = json.dumps(item.get("tags", []))
        model.added_date = item.get("added_date", "")

        count += 1

    db.commit()
    return count


def sync_all(db: Session) -> Dict[str, int]:
    """Run full initial or on-demand synchronization."""
    chars = sync_characters_from_disk(db)
    garments = sync_garments_from_disk(db)
    combos = sync_combos_from_disk(db)
    return {"characters_synced": chars, "garments_synced": garments, "combos_synced": combos}


# ============================================================================
# Lossless Writebacks to JSON & Markdown
# ============================================================================

def writeback_characters(db: Session) -> Path:
    """Serialize characters from SQLite back to character_library/index.json and INDEX.md."""
    records = db.query(CharacterModel).order_by(CharacterModel.added_date.desc(), CharacterModel.char_id).all()
    output_list = []

    for r in records:
        item: Dict[str, Any] = {
            "char_id": r.char_id,
            "name": r.name,
            "face": r.face,
            "thumb": r.thumb,
            "embedding": r.embedding,
            "emb_dim": r.emb_dim,
            "emb_model": r.emb_model,
            "det_model": r.det_model,
            "det_score": round(r.det_score, 4),
            "face_bbox": json.loads(r.face_bbox_json or "[]"),
            "img_shape": json.loads(r.img_shape_json or "[]"),
            "alts": json.loads(r.alts_json or "[]"),
            "ref_outputs": json.loads(r.ref_outputs_json or "[]"),
            "source": r.source,
            "added_date": r.added_date,
            "note": r.note,
        }
        tags = json.loads(r.tags_json or "[]")
        if tags:
            item["tags"] = tags
        output_list.append(item)

    # 1. Write index.json
    target_json = CHARACTER_LIB_DIR / "index.json"
    target_json.write_text(
        json.dumps(output_list, ensure_ascii=False, indent=1),
        encoding="utf-8"
    )

    # 2. Update INDEX.md
    md_lines = [
        "# 角色库清单（INDEX.md）\n",
        "> 本文件由资产管理系统双向同步引擎自动维护，勿直接手改。",
        "> 机器可读版本：`index.json`｜可视化：`index.html`｜数据库映射：`assets.db`\n",
        "## 角色总表\n",
        "| char_id | 显示名 | 主脸文件 | 检测分 | 备选角度（cos→主脸） | 入库日期 |",
        "|---|---|---|---|---|---|",
    ]
    for c in output_list:
        alts_str = "、".join([
            f"{Path(a.get('file', '')).name}({a.get('cos_to_main', 0.0):.2f})"
            for a in c.get("alts", [])
        ]) or "无"
        md_lines.append(
            f"| `{c['char_id']}` | {c['name']} | `{c['face']}` | {c['det_score']:.3f} | {alts_str} | {c['added_date']} |"
        )
        if c.get("note"):
            md_lines.append(f"| ↳ 备注 | {c['note']} | | | | |")

    target_md = CHARACTER_LIB_DIR / "INDEX.md"
    target_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    return target_json


def writeback_garments(db: Session) -> Path:
    """Serialize garments from SQLite back to garment_library/index.json and INDEX.md."""
    records = db.query(GarmentModel).order_by(GarmentModel.added_date.desc(), GarmentModel.garment_id).all()
    output_list = []

    for g in records:
        item: Dict[str, Any] = {
            "garment_id": g.garment_id,
            "category": g.category,
            "label": g.label,
            "mean_hex": g.mean_hex,
            "mask_area_px": g.mask_area_px,
            "crop_bbox": json.loads(g.crop_bbox_json or "[]"),
            "size": json.loads(g.size_json or "[]"),
            "method": g.method,
            "versions_count": g.versions_count,
            "source_image": g.source_image,
            "source_url": g.source_url,
            "origin_dir": g.origin_dir,
            "added_date": g.added_date,
            "dir": g.dir_path,
            "thumb": g.thumb,
            "note": g.note,
        }
        tags = json.loads(g.tags_json or "[]")
        if tags:
            item["tags"] = tags
        output_list.append(item)

    # 1. Write index.json
    target_json = GARMENT_LIB_DIR / "index.json"
    target_json.write_text(
        json.dumps(output_list, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # 2. Update INDEX.md
    md_lines = [
        "# 服装库清单 · garment_library\n",
        f"> 自动生成，共 **{len(output_list)}** 件，同步于 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n",
        "## 一、总表\n",
        "| # | garment_id | 类别 | 主色 | 尺寸 | 掩码面积 | 版本 | 方法 | 来源标签 | 库内路径 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for idx, it in enumerate(output_list, 1):
        size_str = f"{it['size'][0]}×{it['size'][1]}" if len(it['size']) >= 2 else "未知"
        hex_color = it.get("mean_hex", "#000000")
        color_span = f'<span style="color:{hex_color}">■</span> `{hex_color}`'
        md_lines.append(
            f"| {idx} | `{it['garment_id']}` | {it['category']} | {color_span} | {size_str} | "
            f"{it['mask_area_px']:,} | {it['versions_count']} | {it['method']} | {it['label']} | `{it['dir']}` |"
        )

    target_md = GARMENT_LIB_DIR / "INDEX.md"
    target_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    return target_json
