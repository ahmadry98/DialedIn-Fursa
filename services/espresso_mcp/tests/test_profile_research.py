import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.espresso_mcp import profile_candidates, profile_research


class ProfileResearchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.original_path = profile_candidates.CANDIDATES_PATH
        profile_candidates.CANDIDATES_PATH = Path(self.tmp.name) / "profile_candidates.json"
        profile_candidates.CANDIDATES_PATH.write_text("[]\n", encoding="utf-8")

    def tearDown(self):
        profile_candidates.CANDIDATES_PATH = self.original_path
        self.tmp.cleanup()

    def test_prepare_machine_research_packet(self):
        candidate = profile_candidates.save_profile_candidate("machine", "Mystery Machine X", "user-1", {})

        packet = profile_research.prepare_research_packet(candidate["candidate_key"])

        self.assertEqual(packet["type"], "machine")
        self.assertIn("official manufacturer", packet["instructions"])
        self.assertIn("machine_name", packet["expected_schema"])

    def test_attach_valid_machine_draft_marks_ready(self):
        candidate = profile_candidates.save_profile_candidate("machine", "Mystery Machine X", "user-1", {})
        draft = {
            "machine_name": "Mystery Machine X",
            "aliases": ["mystery machine x"],
            "specs": {
                "portafilter_mm": 58,
                "pump_type": "vibration",
                "pressure_type": "15 bar vibration pump",
                "has_preinfusion": False,
            },
            "brew_defaults": {
                "target_total_shot_seconds": [25, 32],
                "target_visible_flow_seconds": [20, 28],
                "typical_startup_delay_seconds": [2, 6],
            },
            "grind_adjustment_notes": "Use conservative grind changes.",
            "sources": {
                "aliases": ["https://example.com/manual"],
                "portafilter_mm": ["https://example.com/manual"],
                "pump_type": ["https://example.com/manual"],
                "pressure_type": ["https://example.com/manual"],
                "has_preinfusion": ["https://example.com/manual"],
            },
        }

        updated = profile_research.attach_draft_profile(candidate["candidate_key"], draft, "Official manual checked.")

        self.assertEqual(updated["status"], "draft_ready")
        self.assertTrue(updated["draft_validation"]["is_valid"])
        self.assertEqual(updated["draft_profile"]["machine_name"], "Mystery Machine X")

    def test_invalid_grinder_draft_needs_review(self):
        candidate = profile_candidates.save_profile_candidate("grinder", "Mystery Grinder Y", "user-1", {})

        updated = profile_research.attach_draft_profile(candidate["candidate_key"], {"grinder_name": "Mystery Grinder Y"})

        self.assertEqual(updated["status"], "draft_needs_review")
        self.assertFalse(updated["draft_validation"]["is_valid"])
        self.assertIn("aliases", updated["draft_validation"]["missing_fields"])


if __name__ == "__main__":
    unittest.main()
