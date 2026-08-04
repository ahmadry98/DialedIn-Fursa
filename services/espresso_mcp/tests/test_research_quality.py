import unittest

from services.espresso_mcp import research_quality


class ResearchQualityTest(unittest.TestCase):
    def test_machine_quality_ready_when_score_is_above_threshold(self):
        draft = {
            "machine_name": "LELIT Elizabeth PL92T",
            "aliases": ["LELIT Elizabeth"],
            "specs": {
                "portafilter_mm": 58,
                "pump_type": "vibration",
                "pressure_type": "coffee pressure manometer; exact pump pressure not verified",
                "has_preinfusion": True,
                "has_built_in_grinder": False,
            },
            "grind_adjustment_notes": "Use verified machine features only.",
            "sources": {
                "aliases": ["https://www.lelit.com/manuals/elizabeth"],
                "portafilter_mm": ["https://assets.breville.com/Lelit/PESEL01/LELIT-Elizabeth-PL92T-120-EN.pdf"],
                "pump_type": ["https://assets.breville.com/Lelit/PESEL01/LELIT-Elizabeth-PL92T-120-EN.pdf"],
                "pressure_type": ["https://www.lelit.com/manuals/elizabeth"],
                "has_preinfusion": ["https://www.lelit.com/manuals/elizabeth"],
                "has_built_in_grinder": ["https://www.lelit.com/manuals/elizabeth"],
            },
        }
        evidence = {
            "sources": [
                {"url": "https://assets.breville.com/Lelit/PESEL01/LELIT-Elizabeth-PL92T-120-EN.pdf", "source_type": "pdf"}
            ],
            "text": "LELIT58 dual boiler preinfusion manometer technical data",
        }

        quality = research_quality.evaluate_research_quality("machine", draft, evidence)

        self.assertGreater(quality["score"], 55)
        self.assertEqual(quality["status"], "draft_ready")

    def test_machine_quality_fails_without_sources(self):
        draft = {
            "machine_name": "Fake Machine",
            "aliases": [],
            "specs": {
                "portafilter_mm": None,
                "pump_type": "unknown",
                "pressure_type": "unknown",
                "has_preinfusion": None,
                "has_built_in_grinder": None,
            },
            "sources": {
                "aliases": [],
                "portafilter_mm": [],
                "pump_type": [],
                "pressure_type": [],
                "has_preinfusion": [],
                "has_built_in_grinder": [],
            },
        }

        quality = research_quality.evaluate_research_quality("machine", draft, {})

        self.assertEqual(quality["status"], "research_failed")
        self.assertLessEqual(quality["score"], 55)

    def test_status_for_quality_requires_score_above_threshold(self):
        validation = {"is_valid": True}
        quality = {"score": 55, "status": "draft_needs_review"}

        self.assertEqual(research_quality.status_for_quality(validation, quality), "draft_needs_review")


if __name__ == "__main__":
    unittest.main()
