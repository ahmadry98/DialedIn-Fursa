import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.espresso_mcp import profile_candidates


class ProfileCandidatesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.original_path = profile_candidates.CANDIDATES_PATH
        profile_candidates.CANDIDATES_PATH = Path(self.tmp.name) / "profile_candidates.json"
        profile_candidates.CANDIDATES_PATH.write_text("[]\n", encoding="utf-8")

    def tearDown(self):
        profile_candidates.CANDIDATES_PATH = self.original_path
        self.tmp.cleanup()

    def test_capture_unknown_machine_and_grinder(self):
        candidates = profile_candidates.capture_unknown_gear(
            "user-1",
            "Mystery Machine X",
            "Mystery Grinder Y",
            {"total_shot_seconds": 29, "grind_setting": "12"},
        )

        self.assertEqual(len(candidates), 2)
        self.assertEqual({candidate["type"] for candidate in candidates}, {"machine", "grinder"})
        self.assertTrue(all(candidate["status"] == "needs_research" for candidate in candidates))

    def test_known_gear_is_not_captured(self):
        candidates = profile_candidates.capture_unknown_gear("user-1", "BES870", "Varia VS6", {})

        self.assertEqual(candidates, [])

    def test_duplicate_candidate_updates_seen_count(self):
        first = profile_candidates.save_profile_candidate("machine", "Mystery Machine X", "user-1", {})
        second = profile_candidates.save_profile_candidate("machine", "Mystery Machine X", "user-2", {})

        self.assertEqual(first["candidate_key"], second["candidate_key"])
        self.assertEqual(second["seen_count"], 2)
        self.assertEqual(second["user_ids"], ["user-1", "user-2"])


if __name__ == "__main__":
    unittest.main()
