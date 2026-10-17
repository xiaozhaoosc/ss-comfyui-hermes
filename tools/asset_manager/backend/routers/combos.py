# -*- coding: utf-8 -*-
"""Lookbook Combos API router."""
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CharacterModel, ComboModel, GarmentModel

router = APIRouter(prefix="/api/combos", tags=["Combos"])


class ComboResponse(BaseModel):
    combo_id: str
    name: str
    char_id: str
    garment_id: str
    char_name: str = ""
    char_thumb_url: str = ""
    char_face_path: str = ""
    garment_label: str = ""
    garment_thumb_url: str = ""
    garment_category: str = ""
    garment_transparent_path: str = ""
    garment_white_path: str = ""
    preview_image: str = ""
    preview_image_url: str = ""
    prompt_preset: str = ""
    note: str = ""
    tags: List[str] = []
    added_date: str = ""


@router.get("", response_model=List[ComboResponse])
def list_combos(db: Session = Depends(get_db)):
    """List all character + garment combinations in the Lookbook matrix."""
    records = db.query(ComboModel).order_by(ComboModel.added_date.desc(), ComboModel.combo_id).all()
    results = []

    for c in records:
        char = db.query(CharacterModel).filter_by(char_id=c.char_id).first()
        garment = db.query(GarmentModel).filter_by(garment_id=c.garment_id).first()

        char_name = char.name if char else c.char_id
        char_thumb_url = f"/static/characters/{char.thumb}".replace("\\", "/") if char and char.thumb else ""
        char_face_path = char.face if char else ""

        garment_label = garment.label if garment else c.garment_id
        garment_thumb_url = f"/static/garments/{garment.thumb}".replace("\\", "/") if garment and garment.thumb else ""
        garment_category = garment.category if garment else ""
        garment_transparent_path = garment.transparent_path if garment else ""
        garment_white_path = garment.white_path if garment else ""

        preview_url = f"/static/{c.preview_image}".replace("\\", "/") if c.preview_image else ""

        results.append(ComboResponse(
            combo_id=c.combo_id,
            name=c.name,
            char_id=c.char_id,
            garment_id=c.garment_id,
            char_name=char_name,
            char_thumb_url=char_thumb_url,
            char_face_path=char_face_path,
            garment_label=garment_label,
            garment_thumb_url=garment_thumb_url,
            garment_category=garment_category,
            garment_transparent_path=garment_transparent_path,
            garment_white_path=garment_white_path,
            preview_image=c.preview_image,
            preview_image_url=preview_url,
            prompt_preset=c.prompt_preset,
            note=c.note or "",
            tags=json.loads(c.tags_json or "[]"),
            added_date=c.added_date or "",
        ))

    return results
