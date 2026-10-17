# -*- coding: utf-8 -*-
"""SQLAlchemy database models and Pydantic schemas for assets."""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import Column, Float, Integer, String, Text, DateTime
from .database import Base


# ============================================================================
# SQLAlchemy ORM Models
# ============================================================================

class CharacterModel(Base):
    """Character face & identity asset table."""
    __tablename__ = "characters"

    char_id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False, default="")
    face = Column(String(255), default="")  # relative path e.g. faces/char_duo/face.png
    thumb = Column(String(255), default="")  # relative path e.g. faces/char_duo/thumb.png
    embedding = Column(String(255), default="")  # faces/char_duo/embedding.npy
    emb_dim = Column(Integer, default=512)
    emb_model = Column(String(64), default="insightface/w600k_r50")
    det_model = Column(String(64), default="insightface/det_10g")
    det_score = Column(Float, default=0.0)
    face_bbox_json = Column(Text, default="[]")
    img_shape_json = Column(Text, default="[]")
    alts_json = Column(Text, default="[]")
    ref_outputs_json = Column(Text, default="[]")
    source = Column(String(255), default="")
    added_date = Column(String(32), default="")
    note = Column(Text, default="")
    tags_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class GarmentModel(Base):
    """Garment clothing item & cutout asset table."""
    __tablename__ = "garments"

    garment_id = Column(String(64), primary_key=True, index=True)
    category = Column(String(32), index=True, default="full")  # tops, bottoms, full, accessories
    label = Column(String(128), default="")
    mean_hex = Column(String(16), index=True, default="#000000")  # Dominant color hex e.g. #af70c0
    mask_area_px = Column(Integer, default=0)
    crop_bbox_json = Column(Text, default="[]")
    size_json = Column(Text, default="[]")
    method = Column(String(32), default="sam2_box")
    versions_count = Column(Integer, default=1)
    source_image = Column(String(255), default="")
    source_url = Column(String(255), default="")
    origin_dir = Column(String(255), default="")
    added_date = Column(String(32), default="")
    dir_path = Column(String(255), default="")
    thumb = Column(String(255), default="")
    transparent_path = Column(String(255), default="")
    white_path = Column(String(255), default="")
    note = Column(Text, default="")
    tags_json = Column(Text, default="[]")
    alts_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ComboModel(Base):
    """Character + Garment Lookbook combination table."""
    __tablename__ = "combos"

    combo_id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), default="")
    char_id = Column(String(64), index=True, default="")
    garment_id = Column(String(64), index=True, default="")
    preview_image = Column(String(255), default="")
    preview_video = Column(String(255), default="")
    prompt_preset = Column(Text, default="")
    note = Column(Text, default="")
    tags_json = Column(Text, default="[]")
    added_date = Column(String(32), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================================================
# Pydantic Schemas
# ============================================================================

class CharacterAlt(BaseModel):
    file: str
    cos_to_main: Optional[float] = None
    det_score: Optional[float] = None
    note: Optional[str] = ""
    abs_file: Optional[str] = None


class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    note: Optional[str] = None
    tags: Optional[List[str]] = None


class CharacterResponse(BaseModel):
    char_id: str
    name: str
    face: str
    thumb: str
    embedding: str
    emb_dim: int = 512
    emb_model: str = "insightface/w600k_r50"
    det_model: str = "insightface/det_10g"
    det_score: float = 0.0
    face_bbox: List[float] = Field(default_factory=list)
    img_shape: List[int] = Field(default_factory=list)
    alts: List[CharacterAlt] = Field(default_factory=list)
    ref_outputs: List[str] = Field(default_factory=list)
    source: str = ""
    added_date: str = ""
    note: str = ""
    tags: List[str] = Field(default_factory=list)

    # Absolute preview URLs for frontend
    face_url: Optional[str] = None
    thumb_url: Optional[str] = None
    abs_face_path: Optional[str] = None

    class Config:
        from_attributes = True


class GarmentUpdate(BaseModel):
    category: Optional[str] = None
    note: Optional[str] = None
    tags: Optional[List[str]] = None


class GarmentResponse(BaseModel):
    garment_id: str
    category: str
    label: str = ""
    mean_hex: str = "#000000"
    mask_area_px: int = 0
    crop_bbox: List[int] = Field(default_factory=list)
    size: List[int] = Field(default_factory=list)
    method: str = ""
    versions_count: int = 1
    source_image: str = ""
    source_url: str = ""
    origin_dir: str = ""
    added_date: str = ""
    dir_path: str = ""
    thumb: str = ""
    transparent_path: str = ""
    white_path: str = ""
    note: str = ""
    tags: List[str] = Field(default_factory=list)

    # Frontend preview URLs and absolute paths
    thumb_url: Optional[str] = None
    transparent_url: Optional[str] = None
    white_url: Optional[str] = None
    abs_transparent_path: Optional[str] = None
    abs_white_path: Optional[str] = None


    class Config:
        from_attributes = True


class SimilarityResult(BaseModel):
    char_id: str
    name: str
    similarity: float
    is_same_identity: bool  # cos >= 0.6
    is_suspicious: bool     # 0.4 <= cos < 0.6
    thumb_url: Optional[str] = None


class SystemStats(BaseModel):
    character_count: int
    garment_count: int
    combo_count: int
    categories: Dict[str, int]
    tags: List[str]
    last_sync_time: Optional[str] = None
