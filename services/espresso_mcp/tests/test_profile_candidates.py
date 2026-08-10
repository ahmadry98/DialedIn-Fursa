import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.espresso_mcp import notifications, profile_candidates


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

    def test_likely_grinder_typo_is_not_captured(self):
        candidates = profile_candidates.capture_unknown_gear("user-1", "Rancilio Silvia", "Varia V3", {})

        self.assertEqual(candidates, [])

    def test_gibberish_machine_and_grinder_are_not_captured(self):
        candidates = profile_candidates.capture_unknown_gear("user-1", "sfsts", "xqzzrp", {})

        self.assertEqual(candidates, [])

    def test_plausible_unknown_gear_is_still_captured(self):
        candidates = profile_candidates.capture_unknown_gear("user-1", "Acme Espresso X1", "Acme Grinder G2", {})

        self.assertEqual(len(candidates), 2)
        self.assertEqual({candidate["type"] for candidate in candidates}, {"machine", "grinder"})

    def test_duplicate_candidate_updates_seen_count(self):
        first = profile_candidates.save_profile_candidate("machine", "Mystery Machine X", "user-1", {})
        second = profile_candidates.save_profile_candidate("machine", "Mystery Machine X", "user-2", {})

        self.assertEqual(first["candidate_key"], second["candidate_key"])
        self.assertEqual(second["seen_count"], 2)
        self.assertEqual(second["user_ids"], ["user-1", "user-2"])

    def test_new_machine_candidate_sends_optional_email_notification(self):
        calls = []
        original_notify = notifications.notify_new_profile_candidate
        notifications.notify_new_profile_candidate = lambda candidate: calls.append(candidate) or True
        try:
            candidate = profile_candidates.save_profile_candidate("machine", "Mystery Machine X", "user-1", {})
        finally:
            notifications.notify_new_profile_candidate = original_notify

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["candidate_key"], candidate["candidate_key"])

    def test_duplicate_machine_candidate_does_not_send_email_again(self):
        calls = []
        original_notify = notifications.notify_new_profile_candidate
        notifications.notify_new_profile_candidate = lambda candidate: calls.append(candidate) or True
        try:
            profile_candidates.save_profile_candidate("machine", "Mystery Machine X", "user-1", {})
            profile_candidates.save_profile_candidate("machine", "Mystery Machine X", "user-2", {})
        finally:
            notifications.notify_new_profile_candidate = original_notify

        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
