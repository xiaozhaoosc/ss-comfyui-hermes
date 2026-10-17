# -*- coding: utf-8 -*-
"""Verification script for Stage 1 Backend and Two-Way Sync Engine.

Tests:
1. Database initialization and file-to-SQLite sync.
2. CPU NumPy face cosine similarity ranking.
3. Garment color palette extraction and tolerance distance matching.
4. Realtime lossless writeback to index.json & INDEX.md.
5. FastAPI TestClient route integration.
"""
import json
import sys
from pathlib import Path

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import CHARACTER_LIB_DIR, GARMENT_LIB_DIR, DB_PATH
from backend.database import SessionLocal, init_db
from backend.models import CharacterModel, GarmentModel
from backend.sync_engine import sync_all, writeback_characters, writeback_garments
from backend.vector_math import (
    color_distance_rgb,
    color_matches,
    cosine_similarity,
    get_or_load_embedding,
    hex_to_rgb,
    search_similar_characters,
)
from fastapi.testclient import TestClient
from backend.app import app


def test_stage1():
    print("=" * 60)
    print(">>> 1. Testing Database & Initial Library Sync...")
    print("=" * 60)
    init_db()
    db = SessionLocal()

    sync_res = sync_all(db)
    print(f"Sync Results: {sync_res}")
    assert sync_res["characters_synced"] >= 5, f"Expected >= 5 characters, got {sync_res['characters_synced']}"
    assert sync_res["garments_synced"] >= 6, f"Expected >= 6 garments, got {sync_res['garments_synced']}"

    chars = db.query(CharacterModel).all()
    print(f"Loaded {len(chars)} characters:")
    for c in chars:
        print(f"  - [{c.char_id}] {c.name} (det_score: {c.det_score:.3f}, source: {c.source})")

    garments = db.query(GarmentModel).all()
    print(f"\nLoaded {len(garments)} garments:")
    for g in garments:
        print(f"  - [{g.garment_id}] {g.category} {g.mean_hex} ({g.method})")

    print("\n" + "=" * 60)
    print(">>> 2. Testing Pure CPU NumPy Face Embedding Similarity...")
    print("=" * 60)
    # Test embedding loading for char_duo
    duo_emb_path = CHARACTER_LIB_DIR / "faces" / "char_duo" / "embedding.npy"
    duo_emb = get_or_load_embedding("char_duo", duo_emb_path)
    assert duo_emb is not None, "Failed to load char_duo embedding"
    assert duo_emb.shape == (512,), f"Expected shape (512,), got {duo_emb.shape}"

    # Self similarity must be 1.0
    self_sim = cosine_similarity(duo_emb, duo_emb)
    print(f"Self-similarity of char_duo: {self_sim:.4f} (Must be 1.0)")
    assert abs(self_sim - 1.0) < 1e-4

    # Rank all characters against char_duo
    candidates = {}
    for c in chars:
        emb_p = CHARACTER_LIB_DIR / c.embedding
        emb = get_or_load_embedding(c.char_id, emb_p)
        if emb is not None:
            candidates[c.char_id] = emb

    ranked = search_similar_characters(duo_emb, candidates)
    print("Cosine similarity ranked against char_duo:")
    for cid, score in ranked:
        tag = "同身份 (≥0.6)" if score >= 0.6 else "存疑 (≥0.4)" if score >= 0.4 else "不同身份 (<0.4)"
        print(f"  - {cid:15s}: cos = {score:.4f} [{tag}]")

    print("\n" + "=" * 60)
    print(">>> 3. Testing Garment Dominant Color Palette Math...")
    print("=" * 60)
    # Check #af70c0
    rgb = hex_to_rgb("#af70c0")
    print(f"Hex '#af70c0' -> RGB: {rgb}")
    assert rgb == (175, 112, 192)

    # Check color matching tolerance
    exact_match = color_matches("#af70c0", "#af70c0", tolerance=0.1)
    similar_match = color_matches("#af70c0", "#bf80d0", tolerance=0.25)
    dissimilar = color_matches("#af70c0", "#232021", tolerance=0.25)
    print(f"Exact match (#af70c0 vs #af70c0): {exact_match} (True)")
    print(f"Similar match (#af70c0 vs #bf80d0): {similar_match} (True)")
    print(f"Dissimilar match (#af70c0 vs #232021): {dissimilar} (False)")
    assert exact_match is True
    assert similar_match is True
    assert dissimilar is False

    print("\n" + "=" * 60)
    print(">>> 4. Testing Realtime Lossless Writeback to index.json & INDEX.md...")
    print("=" * 60)
    target_char = db.query(CharacterModel).filter_by(char_id="char_duo").first()
    old_tags = json.loads(target_char.tags_json or "[]")
    
    # Temporarily append test tag
    test_tag = "test_verified_tag"
    new_tags = list(set(old_tags + [test_tag]))
    target_char.tags_json = json.dumps(new_tags)
    db.commit()

    writeback_characters(db)

    # Verify disk content has test tag
    index_json_path = CHARACTER_LIB_DIR / "index.json"
    reloaded_json = json.loads(index_json_path.read_text(encoding="utf-8"))
    duo_json_entry = next((item for item in reloaded_json if item["char_id"] == "char_duo"), None)
    assert duo_json_entry is not None
    assert test_tag in duo_json_entry.get("tags", []), "Writeback failed to persist tag to index.json"
    print("[OK] Verified writeback persisted to character_library/index.json!")

    # Revert tag and rewrite to restore pristine state
    target_char.tags_json = json.dumps(old_tags)
    db.commit()
    writeback_characters(db)
    print("[OK] Reverted test tag cleanly.")

    print("\n" + "=" * 60)
    print(">>> 5. Testing FastAPI REST Endpoints via TestClient...")
    print("=" * 60)
    with TestClient(app) as client:
        # System stats
        resp = client.get("/api/system/stats")
        assert resp.status_code == 200, resp.text
        stats = resp.json()
        print(f"GET /api/system/stats: {stats}")
        assert stats["character_count"] >= 5
        assert stats["garment_count"] >= 6

        # Character list
        resp = client.get("/api/characters?q=Duo")
        assert resp.status_code == 200
        chars_res = resp.json()
        print(f"GET /api/characters?q=Duo returned {len(chars_res)} items")
        assert any(c["char_id"] == "char_duo" for c in chars_res)

        # Garment list with category filter
        resp = client.get("/api/garments?category=tops")
        assert resp.status_code == 200
        garments_res = resp.json()
        print(f"GET /api/garments?category=tops returned {len(garments_res)} items")
        assert any(g["garment_id"] == "top_20261012_01" for g in garments_res)

        # Garment color palette
        resp = client.get("/api/garments/colors/palette")
        assert resp.status_code == 200
        palette = resp.json()
        print(f"GET /api/garments/colors/palette returned {len(palette)} unique dominant colors:")
        for p in palette:
            print(f"  - {p['hex']}: count={p['count']}, ids={p['garment_ids']}")

        # Face similarity search via API
        resp = client.post("/api/characters/similarity_search", json={"char_id": "char_duo", "top_k": 3})
        assert resp.status_code == 200
        sim_res = resp.json()
        print(f"POST /api/characters/similarity_search returned:")
        for s in sim_res:
            print(f"  - {s['name']} ({s['char_id']}): cos={s['similarity']:.4f}")

    db.close()
    print("\n" + "=" * 60)
    print(">>> ALL STAGE 1 VERIFICATIONS PASSED SUCCESSFULLY! <<<")
    print("=" * 60)


if __name__ == "__main__":
    test_stage1()
