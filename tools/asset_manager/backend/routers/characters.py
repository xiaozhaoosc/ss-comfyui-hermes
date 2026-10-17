# -*- coding: utf-8 -*-
"""Character asset API router."""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..config import CHARACTER_LIB_DIR
from ..database import get_db
from ..models import (
    CharacterAlt,
    CharacterModel,
    CharacterResponse,
    CharacterUpdate,
    SimilarityResult,
)
from ..sync_engine import writeback_characters
from ..vector_math import (
    _EMBEDDINGS_CACHE,
    get_or_load_embedding,
    search_similar_characters,
)

router = APIRouter(prefix="/api/characters", tags=["Characters"])


def _model_to_response(model: CharacterModel) -> CharacterResponse:
    """Format CharacterModel to API response with preview URLs and absolute filesystem paths."""
    alts_raw = json.loads(model.alts_json or "[]")
    alts = []
    for a in alts_raw:
        item = dict(a)
        if "file" in item and item["file"]:
            item["abs_file"] = str((CHARACTER_LIB_DIR / item["file"]).resolve())
        alts.append(CharacterAlt(**item))

    abs_face_path = str((CHARACTER_LIB_DIR / model.face).resolve()) if model.face else ""

    return CharacterResponse(
        char_id=model.char_id,
        name=model.name,
        face=model.face,
        thumb=model.thumb,
        embedding=model.embedding,
        emb_dim=model.emb_dim,
        emb_model=model.emb_model,
        det_model=model.det_model,
        det_score=model.det_score,
        face_bbox=json.loads(model.face_bbox_json or "[]"),
        img_shape=json.loads(model.img_shape_json or "[]"),
        alts=alts,
        ref_outputs=json.loads(model.ref_outputs_json or "[]"),
        source=model.source,
        added_date=model.added_date,
        note=model.note or "",
        tags=json.loads(model.tags_json or "[]"),
        face_url=f"/static/characters/{model.face}".replace("\\", "/"),
        thumb_url=f"/static/characters/{model.thumb if (CHARACTER_LIB_DIR / model.thumb).exists() else model.face}".replace("\\", "/"),
        abs_face_path=abs_face_path,
    )



@router.get("", response_model=List[CharacterResponse])
def list_characters(
    q: Optional[str] = Query(None, description="Search by name, ID, or note"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    min_det_score: Optional[float] = Query(None, description="Minimum detection score"),
    db: Session = Depends(get_db),
):
    """List characters with search and filtering."""
    query = db.query(CharacterModel)

    if q:
        kw = f"%{q.strip()}%"
        query = query.filter(
            or_(
                CharacterModel.name.ilike(kw),
                CharacterModel.char_id.ilike(kw),
                CharacterModel.note.ilike(kw),
                CharacterModel.source.ilike(kw),
            )
        )

    if min_det_score is not None:
        query = query.filter(CharacterModel.det_score >= min_det_score)

    items = query.order_by(CharacterModel.added_date.desc(), CharacterModel.char_id).all()

    # In-memory tag filtering if specified
    if tag:
        t_clean = tag.strip().lstrip("#")
        items = [
            m for m in items
            if any(t_clean.lower() == str(t).lstrip("#").lower() for t in json.loads(m.tags_json or "[]"))
        ]

    return [_model_to_response(m) for m in items]


@router.get("/{char_id}", response_model=CharacterResponse)
def get_character(char_id: str, db: Session = Depends(get_db)):
    """Get single character details."""
    model = db.query(CharacterModel).filter_by(char_id=char_id).first()
    if not model:
        raise HTTPException(status_code=404, detail=f"Character '{char_id}' not found")
    return _model_to_response(model)


class SimilaritySearchRequest(BaseModel):
    char_id: Optional[str] = None
    query_vector: Optional[List[float]] = None
    top_k: int = 10
    min_threshold: float = 0.0


@router.post("/similarity_search", response_model=List[SimilarityResult])
def similarity_search(
    req: SimilaritySearchRequest,
    db: Session = Depends(get_db),
):
    """Find similar characters using InsightFace 512-d embeddings on CPU."""
    import numpy as np

    # Ensure all embeddings are cached in memory
    all_chars = db.query(CharacterModel).all()
    candidates = {}
    for c in all_chars:
        emb_path = CHARACTER_LIB_DIR / c.embedding
        emb = get_or_load_embedding(c.char_id, emb_path)
        if emb is not None:
            candidates[c.char_id] = emb

    # Determine query vector
    if req.char_id:
        if req.char_id not in candidates:
            raise HTTPException(
                status_code=404,
                detail=f"Character '{req.char_id}' has no valid embedding loaded",
            )
        query_emb = candidates[req.char_id]
    elif req.query_vector:
        if len(req.query_vector) != 512:
            raise HTTPException(
                status_code=400,
                detail=f"Query vector dimension must be 512 (got {len(req.query_vector)})",
            )
        query_emb = np.array(req.query_vector, dtype=np.float32)
    else:
        raise HTTPException(status_code=400, detail="Must supply either 'char_id' or 'query_vector'")

    ranked = search_similar_characters(
        query_emb=query_emb,
        candidates=candidates,
        top_k=req.top_k,
        min_threshold=req.min_threshold,
    )

    results = []
    char_map = {c.char_id: c for c in all_chars}

    for cid, sim in ranked:
        c = char_map.get(cid)
        results.append(
            SimilarityResult(
                char_id=cid,
                name=c.name if c else cid,
                similarity=sim,
                is_same_identity=(sim >= 0.6),
                is_suspicious=(0.4 <= sim < 0.6),
                thumb_url=f"/static/characters/{c.thumb}".replace("\\", "/") if c else None,
            )
        )

    return results


@router.put("/{char_id}", response_model=CharacterResponse)
def update_character(
    char_id: str,
    update_data: CharacterUpdate,
    db: Session = Depends(get_db),
):
    """Update character details and automatically perform lossless sync back to index.json."""
    model = db.query(CharacterModel).filter_by(char_id=char_id).first()
    if not model:
        raise HTTPException(status_code=404, detail=f"Character '{char_id}' not found")

    if update_data.name is not None:
        model.name = update_data.name
    if update_data.note is not None:
        model.note = update_data.note
    if update_data.tags is not None:
        model.tags_json = json.dumps(update_data.tags)

    db.commit()
    db.refresh(model)

    # Realtime lossless writeback to disk
    writeback_characters(db)

    return _model_to_response(model)
