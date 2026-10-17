# -*- coding: utf-8 -*-
"""Pure CPU NumPy vector similarity and color math algorithms.

Zero GPU requirement. Instantaneous math calculation on CPU for 512-d face
embeddings and hex color palette distances.
"""
import colorsys
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# In-memory embedding cache: {char_id: np.ndarray (512,)}
_EMBEDDINGS_CACHE: Dict[str, np.ndarray] = {}


# ============================================================================
# Face Cosine Similarity (InsightFace 512-d)
# ============================================================================

def normalize_vector(v: np.ndarray) -> np.ndarray:
    """Ensure vector is unit L2-normalized."""
    norm = np.linalg.norm(v)
    if norm > 1e-6:
        return v / norm
    return v


def load_embedding_file(path: Path) -> Optional[np.ndarray]:
    """Load 512-d embedding from .npy file."""
    if not path.exists():
        return None
    try:
        arr = np.load(str(path))
        arr = arr.astype(np.float32).reshape(-1)
        return normalize_vector(arr)
    except Exception:
        return None


def get_or_load_embedding(char_id: str, emb_path: Path) -> Optional[np.ndarray]:
    """Get embedding from in-memory cache or read from disk."""
    if char_id in _EMBEDDINGS_CACHE:
        return _EMBEDDINGS_CACHE[char_id]
    emb = load_embedding_file(emb_path)
    if emb is not None:
        _EMBEDDINGS_CACHE[char_id] = emb
    return emb


def clear_embedding_cache():
    """Clear memory embedding cache."""
    _EMBEDDINGS_CACHE.clear()


def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    """Calculate cosine similarity between two 512-d vectors."""
    v1_norm = normalize_vector(v1)
    v2_norm = normalize_vector(v2)
    return float(np.dot(v1_norm, v2_norm))


def search_similar_characters(
    query_emb: np.ndarray,
    candidates: Dict[str, np.ndarray],
    top_k: int = 10,
    min_threshold: float = 0.0,
) -> List[Tuple[str, float]]:
    """Rank characters by cosine similarity to query vector.

    Returns:
        List of (char_id, similarity_score) sorted descending.
    """
    if len(candidates) == 0:
        return []

    q = normalize_vector(query_emb)
    results = []

    for cid, emb in candidates.items():
        sim = float(np.dot(q, normalize_vector(emb)))
        if sim >= min_threshold:
            results.append((cid, round(sim, 4)))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_k]


# ============================================================================
# Garment Color Metric & Palette Filtering
# ============================================================================

def hex_to_rgb(hex_code: str) -> Tuple[int, int, int]:
    """Convert hex string (e.g. '#af70c0' or 'af70c0') to RGB tuple (0-255)."""
    hex_code = hex_code.strip().lstrip("#")
    if len(hex_code) == 3:
        hex_code = "".join(c * 2 for c in hex_code)
    if len(hex_code) != 6:
        return (0, 0, 0)
    try:
        r = int(hex_code[0:2], 16)
        g = int(hex_code[2:4], 16)
        b = int(hex_code[4:6], 16)
        return (r, g, b)
    except ValueError:
        return (0, 0, 0)


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert RGB tuple to hex string."""
    return f"#{r:02x}{g:02x}{b:02x}"


def rgb_to_hsv(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """Convert RGB (0-255) to HSV (h: 0-360, s: 0-1, v: 0-1)."""
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    return (h * 360.0, s, v)


def color_distance_rgb(hex1: str, hex2: str) -> float:
    """Normalized Euclidean color distance in RGB space [0.0, 1.0]."""
    r1, g1, b1 = hex_to_rgb(hex1)
    r2, g2, b2 = hex_to_rgb(hex2)
    dist = math.sqrt((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2)
    max_dist = math.sqrt(255**2 * 3)
    return dist / max_dist


def color_matches(garment_hex: str, target_hex: str, tolerance: float = 0.25) -> bool:
    """Check if garment dominant color is within tolerance threshold of target.

    Tolerance is in range [0.0, 1.0], where:
      0.10: Very strict match (nearly identical shade)
      0.25: Standard match (similar color tone / same color family)
      0.40: Broad match
    """
    if not garment_hex or not target_hex:
        return False
    # If exact hex match
    if garment_hex.lower().strip() == target_hex.lower().strip():
        return True

    dist = color_distance_rgb(garment_hex, target_hex)
    return dist <= tolerance
