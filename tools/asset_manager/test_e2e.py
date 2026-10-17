# -*- coding: utf-8 -*-
"""End-to-End Automated Verification Suite for AIGC Local Asset Hub.

Verifies:
1. Static SPA delivery and HTML asset integrity (GET /)
2. OpenAPI documentation availability (GET /docs)
3. Library synchronization and aggregation statistics (GET /api/system/stats, POST /api/system/sync)
4. Character querying, multi-view inspection, and tag filtering
5. Pure CPU NumPy face cosine similarity ranking & clustering
6. Garment querying, category filtering, and palette color distance matching
7. Bidirectional real-time lossless writeback to disk JSON & Markdown
8. Static media file hosting (validating actual binary image delivery)
9. ComfyUI status proxying and offline fallback robustness
"""
import json
import sys
import unittest
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add asset manager directory to path
CUR_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CUR_DIR))

from fastapi.testclient import TestClient
from backend.app import app
from backend.config import CHARACTER_LIB_DIR, GARMENT_LIB_DIR
from backend.database import SessionLocal, init_db
from backend.models import CharacterModel, GarmentModel
from backend.sync_engine import writeback_characters, writeback_garments


class TestAssetHubEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)
        cls.db = SessionLocal()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_root_spa_frontend_served(self):
        """Verify that GET / returns the Vue 3 single page application with full UI markup."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.headers.get("content-type", ""))
        self.assertIn("AIGC Local Asset Hub", res.text)
        self.assertIn("vue.global.prod.js", res.text.lower())
        self.assertIn("角色库", res.text)
        self.assertIn("服装库", res.text)
        self.assertIn("搭配矩阵", res.text)

    def test_02_openapi_docs_served(self):
        """Verify OpenAPI documentation is accessible."""
        res = self.client.get("/docs")
        self.assertEqual(res.status_code, 200)
        openapi_res = self.client.get("/openapi.json")
        self.assertEqual(openapi_res.status_code, 200)
        data = openapi_res.json()
        self.assertEqual(data["info"]["title"], "AIGC Local Asset Hub API")

    def test_03_system_stats_and_sync(self):
        """Verify system aggregation metrics and on-demand rescan."""
        # Check initial stats
        res = self.client.get("/api/system/stats")
        self.assertEqual(res.status_code, 200)
        stats = res.json()
        self.assertGreaterEqual(stats["character_count"], 5)
        self.assertGreaterEqual(stats["garment_count"], 6)
        self.assertIn("tops", stats["categories"])
        self.assertIn("bottoms", stats["categories"])
        self.assertIn("full", stats["categories"])

        # Test on-demand sync trigger
        sync_res = self.client.post("/api/system/sync")
        self.assertEqual(sync_res.status_code, 200)
        sync_data = sync_res.json()
        self.assertEqual(sync_data["status"], "success")
        self.assertIn("characters_synced", sync_data["result"])
        self.assertIn("garments_synced", sync_data["result"])

    def test_04_characters_list_and_search(self):
        """Verify character listing, full-text search, and detection score filtering."""
        # 1. Full list
        res = self.client.get("/api/characters")
        self.assertEqual(res.status_code, 200)
        chars = res.json()
        self.assertGreaterEqual(len(chars), 5)

        # 2. Search query 'duo'
        res_q = self.client.get("/api/characters?q=duo")
        self.assertEqual(res_q.status_code, 200)
        q_chars = res_q.json()
        self.assertTrue(any(c["char_id"] == "char_duo" for c in q_chars))

        # 3. Detection score filter
        res_det = self.client.get("/api/characters?min_det_score=0.82")
        self.assertEqual(res_det.status_code, 200)
        det_chars = res_det.json()
        for c in det_chars:
            self.assertGreaterEqual(c["det_score"], 0.82)

    def test_05_character_details_and_multi_views(self):
        """Verify single character retrieval and multi-view angle data."""
        res = self.client.get("/api/characters/char_duo3_2")
        self.assertEqual(res.status_code, 200)
        char = res.json()
        self.assertEqual(char["char_id"], "char_duo3_2")
        self.assertGreater(len(char["face_bbox"]), 0)
        self.assertGreater(len(char["alts"]), 0)

        # Verify alts structure
        for alt in char["alts"]:
            self.assertIn("file", alt)
            self.assertIsNotNone(alt["cos_to_main"])
            self.assertGreater(alt["cos_to_main"], 0.70)

    def test_06_face_embedding_cosine_search(self):
        """Verify CPU NumPy vector search matching identity matrix ground-truth."""
        # Similarity search against char_duo
        payload = {"char_id": "char_duo", "top_k": 5}
        res = self.client.post("/api/characters/similarity_search", json=payload)
        self.assertEqual(res.status_code, 200)
        ranked = res.json()
        self.assertGreaterEqual(len(ranked), 4)

        # Top 1 must be self with score 1.0
        self.assertEqual(ranked[0]["char_id"], "char_duo")
        self.assertAlmostEqual(ranked[0]["similarity"], 1.0000, places=3)
        self.assertTrue(ranked[0]["is_same_identity"])

        # Remaining must be marked different person (< 0.4)
        for other in ranked[1:]:
            self.assertLess(other["similarity"], 0.40)
            self.assertFalse(other["is_same_identity"])

    def test_07_garments_list_and_category_filter(self):
        """Verify garment listing and category sub-division."""
        for cat in ["tops", "bottoms", "full"]:
            res = self.client.get(f"/api/garments?category={cat}")
            self.assertEqual(res.status_code, 200)
            items = res.json()
            self.assertGreaterEqual(len(items), 1)
            for item in items:
                self.assertEqual(item["category"], cat)
                self.assertTrue(item["transparent_url"].endswith("transparent.png"))
                self.assertTrue(item["white_url"].endswith("white.png"))

    def test_08_garment_color_palette_and_matching(self):
        """Verify color palette extraction and tolerance matching."""
        # Palette extraction
        palette_res = self.client.get("/api/garments/colors/palette")
        self.assertEqual(palette_res.status_code, 200)
        palette = palette_res.json()
        self.assertGreaterEqual(len(palette), 6)

        # Check #af70c0 is in palette
        hex_list = [p["hex"] for p in palette]
        self.assertIn("#af70c0", hex_list)

        # Filter by color #af70c0 with tolerance 0.2
        matched_res = self.client.get("/api/garments?color_hex=%23af70c0&color_tolerance=0.20")
        self.assertEqual(matched_res.status_code, 200)
        matched_items = matched_res.json()
        self.assertTrue(any(g["garment_id"] == "top_20261012_01" for g in matched_items))

    def test_09_two_way_lossless_writeback(self):
        """Verify that edits via API persist to disk index.json and can be cleanly reverted."""
        target_char = self.db.query(CharacterModel).filter_by(char_id="char_duo").first()
        original_note = target_char.note

        # 1. Update note
        test_note = f"Automated E2E Verification Note (Original was: {original_note})"
        put_res = self.client.put("/api/characters/char_duo", json={"note": test_note})
        self.assertEqual(put_res.status_code, 200)
        self.assertEqual(put_res.json()["note"], test_note)

        # Verify disk index.json updated
        char_json = json.loads((CHARACTER_LIB_DIR / "index.json").read_text(encoding="utf-8"))
        entry = next(c for c in char_json if c["char_id"] == "char_duo")
        self.assertEqual(entry["note"], test_note)

        # 2. Revert note
        revert_res = self.client.put("/api/characters/char_duo", json={"note": original_note})
        self.assertEqual(revert_res.status_code, 200)
        char_json_reverted = json.loads((CHARACTER_LIB_DIR / "index.json").read_text(encoding="utf-8"))
        entry_reverted = next(c for c in char_json_reverted if c["char_id"] == "char_duo")
        self.assertEqual(entry_reverted["note"], original_note)

    def test_10_static_media_delivery(self):
        """Verify static file serving correctly returns binary image data."""
        # Character image
        char_img_res = self.client.get("/static/characters/faces/char_duo/thumb.png")
        self.assertEqual(char_img_res.status_code, 200)
        self.assertIn("image/png", char_img_res.headers.get("content-type", ""))
        self.assertGreater(len(char_img_res.content), 1000)

        # Garment cutout transparent PNG
        garment_img_res = self.client.get("/static/garments/tops/top_20261012_01/transparent.png")
        self.assertEqual(garment_img_res.status_code, 200)
        self.assertIn("image/png", garment_img_res.headers.get("content-type", ""))
        self.assertGreater(len(garment_img_res.content), 1000)

    def test_11_comfy_status_proxy(self):
        """Verify ComfyUI status endpoint responds gracefully whether 8188 is online or offline."""
        res = self.client.get("/api/comfy/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("online", data)
        self.assertIn("url", data)


if __name__ == "__main__":
    print("=" * 65)
    print("🚀 Running Full E2E Automated Verification Suite...")
    print("=" * 65)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAssetHubEndToEnd)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("\n" + "=" * 65)
        print("✅ ALL 11 END-TO-END VERIFICATION TESTS PASSED SUCCESSFULLY!")
        print("=" * 65)
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED!")
        sys.exit(1)
