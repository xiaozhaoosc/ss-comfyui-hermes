# -*- coding: utf-8 -*-
"""Garment asset API router."""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..config import GARMENT_LIB_DIR
from ..database import get_db
from ..models import GarmentModel, GarmentResponse, GarmentUpdate
from ..sync_engine import writeback_garments
from ..vector_math import color_matches, hex_to_rgb

router = APIRouter(prefix="/api/garments", tags=["Garments"])


def _model_to_response(model: GarmentModel) -> GarmentResponse:
    """Format GarmentModel to API response with preview URLs and absolute filesystem paths."""
    dir_p = model.dir_path.replace("\\", "/")
    rel_trans = f"{dir_p}/transparent.png"
    rel_white = f"{dir_p}/white.png"
    abs_trans = str((GARMENT_LIB_DIR / rel_trans).resolve())
    abs_white = str((GARMENT_LIB_DIR / rel_white).resolve())

    return GarmentResponse(
        garment_id=model.garment_id,
        category=model.category,
        label=model.label or "",
        mean_hex=model.mean_hex or "#000000",
        mask_area_px=model.mask_area_px,
        crop_bbox=json.loads(model.crop_bbox_json or "[]"),
        size=json.loads(model.size_json or "[]"),
        method=model.method or "",
        versions_count=model.versions_count,
        source_image=model.source_image or "",
        source_url=model.source_url or "",
        origin_dir=model.origin_dir or "",
        added_date=model.added_date or "",
        dir_path=dir_p,
        thumb=model.thumb.replace("\\", "/"),
        transparent_path=rel_trans,
        white_path=rel_white,
        note=model.note or "",
        tags=json.loads(model.tags_json or "[]"),
        thumb_url=f"/static/garments/{model.thumb}".replace("\\", "/"),
        transparent_url=f"/static/garments/{dir_p}/transparent.png",
        white_url=f"/static/garments/{dir_p}/white.png",
        abs_transparent_path=abs_trans,
        abs_white_path=abs_white,
    )



@router.get("", response_model=List[GarmentResponse])
def list_garments(
    q: Optional[str] = Query(None, description="Search by label, ID, note, or source URL"),
    category: Optional[str] = Query(None, description="Filter by category (tops, bottoms, full)"),
    color_hex: Optional[str] = Query(None, description="Filter by dominant color hex (e.g. #af70c0)"),
    color_tolerance: float = Query(0.25, ge=0.0, le=1.0, description="Color match tolerance [0.0-1.0]"),
    method: Optional[str] = Query(None, description="Filter by extraction method (sam2_box, atr+sam2)"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    db: Session = Depends(get_db),
):
    """List garments with multi-dimensional filtering (category, color, tags, search)."""
    query = db.query(GarmentModel)

    if category and category != "all":
        query = query.filter(GarmentModel.category == category.lower().strip())

    if method:
        query = query.filter(GarmentModel.method == method.strip())

    if q:
        kw = f"%{q.strip()}%"
        query = query.filter(
            or_(
                GarmentModel.garment_id.ilike(kw),
                GarmentModel.label.ilike(kw),
                GarmentModel.note.ilike(kw),
                GarmentModel.source_url.ilike(kw),
            )
        )

    items = query.order_by(GarmentModel.added_date.desc(), GarmentModel.garment_id).all()

    # In-memory color distance filtering if requested
    if color_hex:
        items = [
            m for m in items
            if color_matches(m.mean_hex, color_hex, tolerance=color_tolerance)
        ]

    # In-memory tag filtering if requested
    if tag:
        t_clean = tag.strip().lstrip("#")
        items = [
            m for m in items
            if any(t_clean.lower() == str(t).lstrip("#").lower() for t in json.loads(m.tags_json or "[]"))
        ]

    return [_model_to_response(m) for m in items]


@router.get("/colors/palette")
def get_color_palette(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Return list of dominant hex colors in library with counts and category breakdown."""
    items = db.query(GarmentModel).all()
    palette: Dict[str, Dict[str, Any]] = {}

    for item in items:
        hex_c = (item.mean_hex or "#000000").lower().strip()
        if hex_c not in palette:
            r, g, b = hex_to_rgb(hex_c)
            palette[hex_c] = {
                "hex": hex_c,
                "rgb": [r, g, b],
                "count": 0,
                "garment_ids": [],
            }
        palette[hex_c]["count"] += 1
        palette[hex_c]["garment_ids"].append(item.garment_id)

    res = list(palette.values())
    res.sort(key=lambda x: x["count"], reverse=True)
    return res


@router.get("/{garment_id}", response_model=GarmentResponse)
def get_garment(garment_id: str, db: Session = Depends(get_db)):
    """Get single garment details."""
    model = db.query(GarmentModel).filter_by(garment_id=garment_id).first()
    if not model:
        raise HTTPException(status_code=404, detail=f"Garment '{garment_id}' not found")
    return _model_to_response(model)


@router.put("/{garment_id}", response_model=GarmentResponse)
def update_garment(
    garment_id: str,
    update_data: GarmentUpdate,
    db: Session = Depends(get_db),
):
    """Update garment and perform realtime lossless writeback to index.json & INDEX.md."""
    model = db.query(GarmentModel).filter_by(garment_id=garment_id).first()
    if not model:
        raise HTTPException(status_code=404, detail=f"Garment '{garment_id}' not found")

    if update_data.category is not None:
        model.category = update_data.category
    if update_data.note is not None:
        model.note = update_data.note
    if update_data.tags is not None:
        model.tags_json = json.dumps(update_data.tags)

    db.commit()
    db.refresh(model)

    # Realtime lossless writeback
    writeback_garments(db)

    return _model_to_response(model)
