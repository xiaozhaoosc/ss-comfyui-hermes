# -*- coding: utf-8 -*-
"""System administration, synchronization, and stats router."""
import json
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CharacterModel, ComboModel, GarmentModel, SystemStats
from ..sync_engine import sync_all

router = APIRouter(prefix="/api/system", tags=["System"])


@router.get("/health")
def healthcheck():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@router.get("/stats", response_model=SystemStats)
def get_stats(db: Session = Depends(get_db)):
    """Return asset counts, categories, and all unique tags across libraries."""
    char_count = db.query(CharacterModel).count()
    garment_count = db.query(GarmentModel).count()
    combo_count = db.query(ComboModel).count()

    # Category breakdown
    cat_rows = (
        db.query(GarmentModel.category, func.count(GarmentModel.garment_id))
        .group_by(GarmentModel.category)
        .all()
    )
    categories = {cat: count for cat, count in cat_rows}

    # Aggregate unique tags across characters and garments
    tag_set = set()
    for row in db.query(CharacterModel.tags_json).all():
        for t in json.loads(row[0] or "[]"):
            tag_set.add(str(t).strip())

    for row in db.query(GarmentModel.tags_json).all():
        for t in json.loads(row[0] or "[]"):
            tag_set.add(str(t).strip())

    return SystemStats(
        character_count=char_count,
        garment_count=garment_count,
        combo_count=combo_count,
        categories=categories,
        tags=sorted(list(tag_set)),
        last_sync_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


@router.post("/sync")
def trigger_sync(db: Session = Depends(get_db)):
    """Trigger manual rescan and database sync."""
    result = sync_all(db)
    return {
        "status": "success",
        "result": result,
        "synced_at": datetime.now().isoformat(),
    }
