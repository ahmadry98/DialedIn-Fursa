import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.agent import app as agent_app
from services.agent import equipment_profiles
from services.espresso_mcp import machine_profiles


class ProfileApiTest(unittest.TestCase):
    def setUp(self):
        self.env_patch = patch.dict(os.environ, {"DIALEDIN_PROFILE_STORAGE": "json"})
        self.env_patch.start()
        machine_profiles.load_machine_profiles.cache_clear()
        self.client = TestClient(agent_app.app)

    def tearDown(self):
        self.env_patch.stop()
        machine_profiles.load_machine_profiles.cache_clear()

    def test_list_machines_returns_mobile_safe_shape(self):
        response = self.client.get("/machines")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreater(payload["count"], 0)
        machine = payload["machines"][0]
        self.assertIn("slug", machine)
        self.assertIn("display_name", machine)
        self.assertIn("tags", machine)
        self.assertIn("specs", machine)
        self.assertNotEqual(machine["display_name"], "Generic Espresso Machine")

    def test_get_machine_by_slug(self):
        response = self.client.get("/machines/rancilio-silvia")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["display_name"], "Rancilio Silvia")
        self.assertEqual(payload["specs"]["portafilter_mm"], 58)

    def test_get_machine_by_alias(self):
        response = self.client.get("/machines/BES870")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["display_name"], "Breville Barista Express")

    def test_get_machine_includes_reviewed_local_image_metadata(self):
        response = self.client.get("/machines/rancilio-silvia")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["has_image"])
        self.assertEqual(payload["image"]["local_asset_key"], "machine-rancilio-silvia")
        self.assertEqual(payload["image"]["status"], "reviewed")

    def test_unreviewed_machine_image_is_hidden(self):
        original_path = machine_profiles.PROFILE_PATH
        try:
            with tempfile.TemporaryDirectory() as tmp:
                machine_profiles.PROFILE_PATH = Path(tmp) / "machine_profiles.json"
                machine_profiles.PROFILE_PATH.write_text(
                    json.dumps([
                        {
                            "machine_name": "Draft Image Machine",
                            "dialedin_slug": "draft-image-machine",
                            "aliases": [],
                            "specs": {"portafilter_mm": 58},
                            "brew_defaults": {},
                            "image": {
                                "url": "https://example.com/draft.jpg",
                                "status": "needs_review",
                            },
                        },
                        {"machine_name": "Generic Espresso Machine", "aliases": [], "specs": {}, "brew_defaults": {}},
                    ]) + "\n",
                    encoding="utf-8",
                )
                machine_profiles.load_machine_profiles.cache_clear()

                response = self.client.get("/machines/draft-image-machine")

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertFalse(payload["has_image"])
                self.assertIsNone(payload["image_url"])
        finally:
            machine_profiles.PROFILE_PATH = original_path
            machine_profiles.load_machine_profiles.cache_clear()

    def test_get_machine_unknown_returns_404(self):
        response = self.client.get("/machines/not-a-real-machine")

        self.assertEqual(response.status_code, 404)

    def test_list_grinders_returns_mobile_safe_shape_without_images(self):
        response = self.client.get("/grinders")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreater(payload["count"], 0)
        grinder = payload["grinders"][0]
        self.assertIn("slug", grinder)
        self.assertIn("display_name", grinder)
        self.assertIn("espresso_range", grinder)
        self.assertIn("small_step", grinder)
        self.assertIn("notes", grinder)
        self.assertNotIn("has_image", grinder)
        self.assertNotIn("image", grinder)
        self.assertNotIn("image_url", grinder)



    def test_s3_machine_image_returns_signed_image_url(self):
        original_path = machine_profiles.PROFILE_PATH
        original_signer = equipment_profiles.storage.create_media_read_url
        try:
            with tempfile.TemporaryDirectory() as tmp:
                machine_profiles.PROFILE_PATH = Path(tmp) / "machine_profiles.json"
                machine_profiles.PROFILE_PATH.write_text(
                    json.dumps([
                        {
                            "machine_name": "Ascaso Steel UNO PID / DUO PID",
                            "dialedin_slug": "ascaso-steel-uno-pid-duo-pid",
                            "aliases": ["ascaso steel duo pid"],
                            "specs": {"portafilter_mm": 58},
                            "brew_defaults": {},
                            "image": {
                                "media_key": "dialchat-media/admin/machine_photo/ascaso.jpg",
                                "storage_mode": "s3",
                                "status": "reviewed",
                            },
                        },
                        {"machine_name": "Generic Espresso Machine", "aliases": [], "specs": {}, "brew_defaults": {}},
                    ]) + "\n",
                    encoding="utf-8",
                )
                machine_profiles.load_machine_profiles.cache_clear()
                equipment_profiles.storage.create_media_read_url = lambda **_: "https://signed.example/ascaso.jpg"

                response = self.client.get("/machines/ascaso-steel-duo-pid")

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["has_image"])
                self.assertEqual(payload["image_url"], "https://signed.example/ascaso.jpg")
        finally:
            equipment_profiles.storage.create_media_read_url = original_signer
            machine_profiles.PROFILE_PATH = original_path
            machine_profiles.load_machine_profiles.cache_clear()

    def test_attach_machine_image_updates_profile_metadata(self):
        original_path = machine_profiles.PROFILE_PATH
        try:
            with tempfile.TemporaryDirectory() as tmp:
                machine_profiles.PROFILE_PATH = Path(tmp) / "machine_profiles.json"
                machine_profiles.PROFILE_PATH.write_text(
                    json.dumps([
                        {
                            "machine_name": "Rancilio Silvia",
                            "dialedin_slug": "rancilio-silvia",
                            "aliases": ["silvia"],
                            "specs": {"portafilter_mm": 58},
                            "brew_defaults": {},
                        },
                        {"machine_name": "Generic Espresso Machine", "aliases": [], "specs": {}, "brew_defaults": {}},
                    ]) + "\n",
                    encoding="utf-8",
                )
                machine_profiles.load_machine_profiles.cache_clear()

                response = self.client.post(
                    "/machines/rancilio-silvia/image",
                    json={
                        "media_key": "uploads/admin/machine_photo/rancilio.jpg",
                        "storage_mode": "s3",
                        "content_type": "image/jpeg",
                        "source_url": "admin upload: rancilio.jpg",
                    },
                )

                self.assertEqual(response.status_code, 200)
                payload = response.json()["machine"]
                self.assertTrue(payload["has_image"])
                self.assertEqual(payload["image"]["media_key"], "uploads/admin/machine_photo/rancilio.jpg")
                self.assertEqual(payload["image"]["storage_mode"], "s3")
        finally:
            machine_profiles.PROFILE_PATH = original_path
            machine_profiles.load_machine_profiles.cache_clear()

    def test_get_grinder_by_slug(self):
        response = self.client.get("/grinders/varia-vs3")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["display_name"], "Varia VS3")

    def test_compat_machine_endpoint_returns_list(self):
        response = self.client.get("/api/machines/")

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)


if __name__ == "__main__":
    unittest.main()
