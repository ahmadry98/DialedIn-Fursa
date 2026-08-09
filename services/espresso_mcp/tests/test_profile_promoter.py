import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.espresso_mcp import grinder_profiles, machine_profiles, profile_candidates, profile_promoter


class ProfilePromoterTest(unittest.TestCase):
    def setUp(self):
        self.env_patch = patch.dict(os.environ, {"DIALEDIN_PROFILE_STORAGE": "json"})
        self.env_patch.start()
        self.tmp = TemporaryDirectory()
        self.original_candidates_path = profile_candidates.CANDIDATES_PATH
        self.original_machine_path = machine_profiles.PROFILE_PATH
        self.original_grinder_path = grinder_profiles.PROFILE_PATH
        base = Path(self.tmp.name)
        profile_candidates.CANDIDATES_PATH = base / "profile_candidates.json"
        machine_profiles.PROFILE_PATH = base / "machine_profiles.json"
        grinder_profiles.PROFILE_PATH = base / "grinder_profiles.json"
        profile_candidates.CANDIDATES_PATH.write_text("[]\n", encoding="utf-8")
        machine_profiles.PROFILE_PATH.write_text(
            json.dumps([{"machine_name": "Generic Espresso Machine", "aliases": []}]) + "\n",
            encoding="utf-8",
        )
        grinder_profiles.PROFILE_PATH.write_text(
            json.dumps([{"grinder_name": "Generic Numeric Grinder", "aliases": []}]) + "\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.env_patch.stop()
        profile_candidates.CANDIDATES_PATH = self.original_candidates_path
        machine_profiles.PROFILE_PATH = self.original_machine_path
        grinder_profiles.PROFILE_PATH = self.original_grinder_path
        machine_profiles.load_machine_profiles.cache_clear()
        self.tmp.cleanup()

    def test_promote_machine_candidate_inserts_before_generic(self):
        candidate = profile_candidates.save_profile_candidate("machine", "Meraki", "user-1", {})
        draft = {
            "machine_name": "Meraki",
            "aliases": ["meraki espresso machine"],
            "specs": {},
            "brew_defaults": {},
            "grind_adjustment_notes": "Reviewed.",
            "sources": {},
            "image": {
                "media_key": "dialchat-media/admin/machine_photo/meraki.jpg",
                "storage_mode": "s3",
                "status": "reviewed",
            },
        }
        data = profile_candidates.load_profile_candidates()
        data[0]["status"] = "draft_ready"
        data[0]["draft_profile"] = draft
        profile_candidates._write_candidates(data)  # type: ignore[attr-defined]

        result = profile_promoter.promote_candidate(candidate["candidate_key"])

        self.assertEqual(result["status"], "inserted")
        profiles = json.loads(machine_profiles.PROFILE_PATH.read_text())
        self.assertEqual(profiles[0]["machine_name"], "Meraki")
        self.assertEqual(profiles[1]["machine_name"], "Generic Espresso Machine")
        self.assertEqual(profile_candidates.load_profile_candidates(), [])
        self.assertTrue(result["candidate_removed"])

    def test_promote_machine_candidate_requires_reviewed_image(self):
        candidate = profile_candidates.save_profile_candidate("machine", "No Image Machine", "user-1", {})
        draft = {
            "machine_name": "No Image Machine",
            "aliases": [],
            "specs": {},
            "brew_defaults": {},
            "grind_adjustment_notes": "Reviewed.",
            "sources": {},
        }
        data = profile_candidates.load_profile_candidates()
        data[0]["status"] = "draft_ready"
        data[0]["draft_profile"] = draft
        profile_candidates._write_candidates(data)  # type: ignore[attr-defined]

        with self.assertRaisesRegex(ValueError, "reviewed image"):
            profile_promoter.promote_candidate(candidate["candidate_key"])

        self.assertEqual(len(profile_candidates.load_profile_candidates()), 1)



if __name__ == "__main__":
    unittest.main()
