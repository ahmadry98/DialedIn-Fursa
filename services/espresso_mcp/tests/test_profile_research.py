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
        self.assertGreater(updated["research_quality"]["score"], 55)
        self.assertEqual(updated["draft_profile"]["machine_name"], "Mystery Machine X")


    def test_empty_machine_draft_with_no_sources_is_research_failed(self):
        candidate = profile_candidates.save_profile_candidate("machine", "Empty Machine", "user-1", {})
        draft = {
            "machine_name": "Empty Machine",
            "aliases": [],
            "specs": {
                "portafilter_mm": None,
                "pump_type": "unknown",
                "pressure_type": "unknown",
                "has_preinfusion": None,
            },
            "brew_defaults": {
                "target_total_shot_seconds": [25, 32],
                "target_visible_flow_seconds": [20, 28],
                "typical_startup_delay_seconds": None,
            },
            "grind_adjustment_notes": "unknown",
            "sources": {
                "aliases": [],
                "portafilter_mm": [],
                "pump_type": [],
                "pressure_type": [],
                "has_preinfusion": [],
            },
        }

        updated = profile_research.attach_draft_profile(candidate["candidate_key"], draft)

        self.assertEqual(updated["status"], "research_failed")
        self.assertEqual(updated["research_quality"]["status"], "research_failed")
        self.assertIn("no source URLs found", updated["research_quality"]["warnings"])

    def test_refresh_candidate_quality_marks_manual_sourced_draft_ready(self):
        candidate = profile_candidates.save_profile_candidate("machine", "Profitec Drive", "user-1", {})
        draft = {
            "machine_name": "Profitec Drive",
            "aliases": ["PROFITEC DRIVE", "Drive"],
            "specs": {
                "portafilter_mm": 58,
                "pump_type": "rotary",
                "pressure_type": "dual boiler with rotary pump and flow profile valve",
                "has_preinfusion": True,
                "has_built_in_grinder": False,
            },
            "brew_defaults": {
                "target_total_shot_seconds": [25, 32],
                "target_visible_flow_seconds": [20, 28],
                "typical_startup_delay_seconds": None,
            },
            "grind_adjustment_notes": "Use an external espresso grinder and make small changes.",
            "sources": {
                "aliases": ["https://www.profitec-espresso.com/en/products/drive"],
                "portafilter_mm": ["https://www.profitec-espresso.com/media/pages/produkte/drive/a59dfadb82-1782907095/ba-drive.pdf"],
                "pump_type": ["https://www.profitec-espresso.com/en/products/drive"],
                "pressure_type": ["https://www.profitec-espresso.com/en/products/drive"],
                "has_preinfusion": ["https://www.profitec-espresso.com/en/products/drive"],
                "has_built_in_grinder": ["https://www.profitec-espresso.com/en/products/drive"],
            },
        }

        profile_candidates.update_profile_candidate(candidate["candidate_key"], draft_profile=draft)
        updated = profile_research.refresh_candidate_quality(candidate["candidate_key"])

        self.assertTrue(updated["draft_validation"]["is_valid"])
        self.assertEqual(updated["status"], "draft_ready")
        self.assertGreater(updated["research_quality"]["score"], 55)


    def test_invalid_grinder_draft_without_sources_is_research_failed(self):
        candidate = profile_candidates.save_profile_candidate("grinder", "Mystery Grinder Y", "user-1", {})

        updated = profile_research.attach_draft_profile(candidate["candidate_key"], {"grinder_name": "Mystery Grinder Y"})

        self.assertEqual(updated["status"], "research_failed")
        self.assertFalse(updated["draft_validation"]["is_valid"])
        self.assertIn("aliases", updated["draft_validation"]["missing_fields"])


if __name__ == "__main__":
    unittest.main()
