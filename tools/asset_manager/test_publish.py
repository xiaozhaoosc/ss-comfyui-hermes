# -*- coding: utf-8 -*-
"""Publish backend verification: job lifecycle, traversal guard, config roundtrip, disk reload."""
import json
import sys
import time
import unittest
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CUR_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CUR_DIR))

from fastapi.testclient import TestClient

import backend.routers.publish as publish_router
from backend.app import app


class TestPublishBackend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        self._created_jobs = []

    def tearDown(self):
        for job_id in self._created_jobs:
            publish_router._jobs.pop(job_id, None)
            (publish_router.PUBLISH_JOBS_DIR / f"{job_id}.json").unlink(missing_ok=True)

    def _sample_mp4_rel(self):
        mp4 = next(publish_router.OUTPUT_ROOT.rglob("*.mp4"))
        return mp4.relative_to(publish_router.OUTPUT_ROOT).as_posix()

    def _wait_terminal(self, job_id, timeout=15):
        deadline = time.time() + timeout
        job = {}
        while time.time() < deadline:
            job = self.client.get(f"/api/publish/jobs/{job_id}").json()
            if job["status"] in ("success", "failed", "need_login"):
                return job
            time.sleep(0.2)
        return job

    def test_01_config_roundtrip(self):
        res = self.client.post("/api/publish/config", json={
            "upload_post_api_key": "test-key-123", "upload_post_user": "test-user"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(publish_router.load_publish_config(),
                         {"upload_post_api_key": "test-key-123", "upload_post_user": "test-user"})
        res = self.client.get("/api/publish/config")
        self.assertEqual(res.json(), {"upload_post_api_key": "test-key-123", "upload_post_user": "test-user", "default_tags": []})
        # 恢复为空配置，避免残留测试密钥
        self.client.post("/api/publish/config", json={"upload_post_api_key": "", "upload_post_user": ""})

    def test_02_create_job_and_status_flow(self):
        def fake_publish(video_path, title, tags, log, publish_mode="publish"):
            log("模拟发布流程")
            return "success"

        original = publish_router.PUBLISHERS["douyin"]
        publish_router.PUBLISHERS["douyin"] = fake_publish
        self.addCleanup(publish_router.PUBLISHERS.__setitem__, "douyin", original)

        res = self.client.post("/api/publish/jobs", json={
            "file_rel_path": self._sample_mp4_rel(), "platforms": ["douyin"],
            "title": "测试发布", "tags": ["测试"]})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(len(body["jobs"]), 1)
        job_id = body["jobs"][0]["job_id"]
        self._created_jobs.append(job_id)

        job = self._wait_terminal(job_id)
        self.assertEqual(job["status"], "success")
        self.assertEqual(job["platform"], "douyin")
        self.assertTrue(any("模拟发布流程" in line for line in job["logs"]))
        self.assertTrue((publish_router.PUBLISH_JOBS_DIR / f"{job_id}.json").exists())

        listing = self.client.get("/api/publish/jobs").json()
        entry = next(j for j in listing if j["job_id"] == job_id)
        self.assertNotIn("logs", entry)
        detail = self.client.get(f"/api/publish/jobs/{job_id}").json()
        self.assertIn("logs", detail)

    def test_03_path_traversal_blocked(self):
        for bad in ("../assets.db", "..\\..\\secrets.txt"):
            res = self.client.post("/api/publish/jobs", json={
                "file_rel_path": bad, "platforms": ["douyin"]})
            self.assertEqual(res.status_code, 400, bad)

    def test_04_unknown_platform_rejected(self):
        res = self.client.post("/api/publish/jobs", json={
            "file_rel_path": self._sample_mp4_rel(), "platforms": ["weibo"]})
        self.assertEqual(res.status_code, 400)

    def test_05_upload_post_job_without_key_fails(self):
        self.client.post("/api/publish/config", json={"upload_post_api_key": "", "upload_post_user": ""})
        res = self.client.post("/api/publish/jobs", json={
            "file_rel_path": self._sample_mp4_rel(), "platforms": ["youtube"]})
        self.assertEqual(res.status_code, 200)
        job_id = res.json()["jobs"][0]["job_id"]
        self._created_jobs.append(job_id)
        job = self._wait_terminal(job_id)
        self.assertEqual(job["status"], "failed")
        self.assertTrue(any("Upload-Post" in line for line in job["logs"]))

    def test_06_reload_persisted_jobs_marks_interrupted_failed(self):
        jobs_dir = publish_router.PUBLISH_JOBS_DIR
        jobs_dir.mkdir(parents=True, exist_ok=True)
        fake = {"job_id": "reloadtest001", "batch_id": "b0", "platform": "douyin",
                "file_rel_path": "a/b.mp4", "video_path": "x", "title": "", "tags": [],
                "status": "running", "logs": [], "created_at": "2026-01-01T00:00:00",
                "updated_at": "2026-01-01T00:00:00"}
        (jobs_dir / "reloadtest001.json").write_text(json.dumps(fake, ensure_ascii=False), encoding="utf-8")
        try:
            publish_router._load_persisted_jobs()
            job = publish_router._jobs["reloadtest001"]
            self.assertEqual(job["status"], "failed")
            self.assertTrue(any("服务重启" in line for line in job["logs"]))
        finally:
            publish_router._jobs.pop("reloadtest001", None)
            (jobs_dir / "reloadtest001.json").unlink(missing_ok=True)

    def test_07_draft_mode_dispatch(self):
        received_modes = {}

        def fake_shipinhao(video_path, title, tags, log, publish_mode="publish", **kwargs):
            received_modes["shipinhao"] = publish_mode
            log(f"视频号收到模式: {publish_mode}")
            return "success"

        def fake_wechat_mp(video_path, title, tags, log, publish_mode="publish", media_type="video", **kwargs):
            received_modes["wechat_mp"] = (publish_mode, media_type)
            log(f"公众号收到模式: {publish_mode}, 媒介: {media_type}")
            return "success"

        orig_shipinhao = publish_router.PUBLISHERS["shipinhao"]
        orig_wechat_mp = publish_router.PUBLISHERS["wechat_mp"]
        publish_router.PUBLISHERS["shipinhao"] = fake_shipinhao
        publish_router.PUBLISHERS["wechat_mp"] = fake_wechat_mp
        self.addCleanup(publish_router.PUBLISHERS.__setitem__, "shipinhao", orig_shipinhao)
        self.addCleanup(publish_router.PUBLISHERS.__setitem__, "wechat_mp", orig_wechat_mp)

        res = self.client.post("/api/publish/jobs", json={
            "file_rel_path": self._sample_mp4_rel(),
            "platforms": ["shipinhao", "wechat_mp"],
            "title": "测试草稿发布",
            "publish_mode": "draft"
        })
        self.assertEqual(res.status_code, 200)
        jobs = res.json()["jobs"]
        for j in jobs:
            self._created_jobs.append(j["job_id"])
            terminal_job = self._wait_terminal(j["job_id"])
            self.assertEqual(terminal_job["status"], "success")

        self.assertEqual(received_modes["shipinhao"], "draft")
        self.assertEqual(received_modes["wechat_mp"], ("draft", "video"))


    def test_08_multi_image_suggest_and_batch_draft(self):
        png_sample = None
        for p in publish_router.OUTPUT_ROOT.rglob("*.png"):
            if p.is_file():
                png_sample = p.relative_to(publish_router.OUTPUT_ROOT).as_posix()
                break
        if not png_sample:
            test_img = publish_router.OUTPUT_ROOT / "test_publish_img.png"
            from PIL import Image
            im = Image.new("RGB", (64, 64), color="blue")
            im.save(test_img)
            self.addCleanup(test_img.unlink, missing_ok=True)
            png_sample = "test_publish_img.png"

        res_sug = self.client.get(f"/api/publish/suggest?file_rel_path={png_sample}")
        self.assertEqual(res_sug.status_code, 200)
        sug_data = res_sug.json()
        self.assertIn("title", sug_data)
        self.assertIn("content", sug_data)
        self.assertIn("tags", sug_data)
        self.assertIn("siblings", sug_data)

        received_call = {}
        def fake_wechat_mp_multi(video_path, title, tags, log, publish_mode="publish", media_type="images", content="", image_paths=None, **kwargs):
            received_call["mode"] = publish_mode
            received_call["media_type"] = media_type
            received_call["content"] = content
            received_call["count"] = len(image_paths) if image_paths else 1
            log("模拟公众号多图草稿成功")
            return "success"

        orig_mp = publish_router.PUBLISHERS["wechat_mp"]
        publish_router.PUBLISHERS["wechat_mp"] = fake_wechat_mp_multi
        self.addCleanup(publish_router.PUBLISHERS.__setitem__, "wechat_mp", orig_mp)

        res_job = self.client.post("/api/publish/jobs", json={
            "file_rel_path": png_sample,
            "file_rel_paths": [png_sample, png_sample],
            "platforms": ["wechat_mp"],
            "media_type": "images",
            "publish_mode": "draft",
            "title": "测试多图图文",
            "content": "精选系列正文描述",
            "tags": ["时尚", "精选"]
        })
        self.assertEqual(res_job.status_code, 200)
        job_id = res_job.json()["jobs"][0]["job_id"]
        self._created_jobs.append(job_id)
        terminal_job = self._wait_terminal(job_id)
        self.assertEqual(terminal_job["status"], "success")
        self.assertEqual(received_call["mode"], "draft")
        self.assertEqual(received_call["media_type"], "images")
        self.assertEqual(received_call["content"], "精选系列正文描述")
        self.assertEqual(received_call["count"], 2)

    def test_09_chinese_title_and_character_matching(self):
        from backend.database import SessionLocal
        from backend.models import CharacterModel
        db = SessionLocal()
        test_char_id = "char_test_cen_youqing_9999_01"
        try:
            db.query(CharacterModel).filter(CharacterModel.char_id == test_char_id).delete()
            char_obj = CharacterModel(
                char_id=test_char_id,
                name="岑幼晴 (Cen Youqing · 新中式清雅温婉)"
            )
            db.add(char_obj)
            db.commit()

            test_img = publish_router.OUTPUT_ROOT / "cen_youqing_portrait_test.png"
            from PIL import Image
            im = Image.new("RGB", (32, 32), color="pink")
            im.save(test_img)
            self.addCleanup(test_img.unlink, missing_ok=True)

            res = self.client.get("/api/publish/suggest?file_rel_path=cen_youqing_portrait_test.png")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertIn("岑幼清", data["title"])
            self.assertIn("新中式清雅温婉", data["title"])
            self.assertIn("写真集", data["title"])
            self.assertIn("✨ 【光影与视觉精选】", data["content"])
            self.assertIn("岑幼清", data["content"])
            self.assertIn("新中式清雅温婉", data["content"])
            self.assertIn("📷 画面构想 / 提示词：", data["content"])
        finally:
            db.query(CharacterModel).filter(CharacterModel.char_id == test_char_id).delete()
            db.commit()
            db.close()

    def test_10_face_cover_sorting_and_wechat_editorial_rules(self):
        from backend.publishers.wechat_mp import _sort_images_face_first
        test_images = [
            "D:/ai_projects/ComfyUI/output/body_full_001.png",
            "D:/ai_projects/ComfyUI/output/dress_detail_002.png",
            "D:/ai_projects/ComfyUI/output/char_cen_portrait_face_003.png",
            "D:/ai_projects/ComfyUI/output/scene_004.png",
        ]
        sorted_imgs = _sort_images_face_first(test_images)
        self.assertIn("portrait_face", sorted_imgs[0])


if __name__ == "__main__":
    unittest.main()