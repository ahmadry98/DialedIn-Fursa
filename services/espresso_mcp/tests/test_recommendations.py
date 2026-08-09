import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from recommendations import recommend_grind_adjustment


class RecommendationRulesTest(unittest.TestCase):
    def test_fast_sour_shot_recommends_finer(self):
        result = recommend_grind_adjustment(
            {
                "total_shot_seconds": 17,
                "taste": "sour and watery",
                "timing_confidence": 0.9,
                "dose_g": 18,
                "yield_g": 36,
                "grinder": "Varia VS6",
                "grind_setting": "1.8",
                "machine_profile": {"target_total_shot_seconds": [25, 32]},
            }
        )

        self.assertEqual(result["recommendation"], "grind_finer")
        self.assertEqual(result["adjustment"], "try grind setting 1.5 next (about 3 small steps finer)")
        self.assertEqual(result["exact_grind_setting"]["suggested_setting"], 1.5)
        self.assertEqual(result["confidence"], "high")
        self.assertIn("dose_g", result["keep_fixed"])

    def test_very_fast_shot_uses_large_exact_grinder_step(self):
        result = recommend_grind_adjustment(
            {
                "total_shot_seconds": 14,
                "taste": "sour",
                "timing_confidence": 0.9,
                "dose_g": 18,
                "yield_g": 36,
                "grinder": "Varia VS6",
                "grind_setting": "1.8",
                "machine_profile": {"target_total_shot_seconds": [25, 32]},
            }
        )

        self.assertEqual(result["recommendation"], "grind_finer")
        self.assertEqual(result["exact_grind_setting"]["adjustment_size"], "large")
        self.assertEqual(result["exact_grind_setting"]["suggested_setting"], 1.4)
        self.assertEqual(result["adjustment"], "try grind setting 1.4 next (about 4 small steps finer)")
        self.assertTrue(any("11s outside" in item for item in result["calculation_explanation"]))
        self.assertTrue(any("about 2.8s per small grind step" in item for item in result["calculation_explanation"]))
        self.assertTrue(any("Known grinder profile used: Varia VS6" in item for item in result["confidence_reasons"]))

    def test_fast_channeling_shot_recommends_puck_prep_first(self):
        result = recommend_grind_adjustment(
            {
                "total_shot_seconds": 16,
                "taste": "spraying and channeling",
                "timing_confidence": 0.8,
            }
        )

        self.assertEqual(result["recommendation"], "improve_puck_prep")
        self.assertIn("puck prep", result["adjustment"])

    def test_slow_bitter_shot_recommends_coarser(self):
        result = recommend_grind_adjustment(
            {
                "total_shot_seconds": 42,
                "taste": "bitter and dry",
                "timing_confidence": 0.8,
                "grinder": "Varia VS6",
                "grind_setting": "1.8",
            }
        )

        self.assertEqual(result["recommendation"], "grind_coarser")
        self.assertEqual(result["adjustment"], "try grind setting 2.2 next (about 4 small steps coarser)")

    def test_generic_grinder_uses_relative_steps_not_exact_setting(self):
        result = recommend_grind_adjustment(
            {
                "total_shot_seconds": 53.7,
                "taste": "balanced",
                "timing_confidence": 0.96,
                "grinder": "LELIT Anita PL042TEMD built-in grinder",
                "grind_setting": "2.1",
                "machine_profile": {"target_total_shot_seconds": [25, 32]},
            }
        )

        self.assertEqual(result["recommendation"], "grind_coarser")
        self.assertEqual(result["adjustment"], "move about 6 small steps coarser from your current setting")
        self.assertEqual(result["confidence"], "medium")
        self.assertIsNone(result["exact_grind_setting"]["suggested_setting"])
        self.assertIsNone(result["exact_grind_setting"]["setting_label"])
        self.assertTrue(any("exact scale is unknown" in item for item in result["calculation_explanation"]))
        self.assertTrue(any("relative step move instead of an exact setting" in item for item in result["confidence_reasons"]))

    def test_known_grinder_limit_uses_safe_capped_message(self):
        result = recommend_grind_adjustment(
            {
                "total_shot_seconds": 12,
                "taste": "sour",
                "timing_confidence": 0.9,
                "grinder": "Varia VS6",
                "grind_setting": "0.1",
                "machine_profile": {"target_total_shot_seconds": [25, 32]},
            }
        )

        self.assertEqual(result["recommendation"], "grind_finer")
        self.assertEqual(result["confidence"], "medium")
        self.assertTrue(result["exact_grind_setting"]["was_clamped"])
        self.assertIn("as far finer as your grinder allows", result["adjustment"])
        self.assertTrue(any("capped" in item for item in result["calculation_explanation"]))

    def test_normal_sour_shot_recommends_more_extraction(self):
        result = recommend_grind_adjustment(
            {
                "total_shot_seconds": 28,
                "taste": "still sour",
                "timing_confidence": 0.7,
            }
        )

        self.assertEqual(result["recommendation"], "increase_extraction")
        self.assertIn("longer yield", result["adjustment"])

    def test_normal_balanced_shot_recommends_keep_settings(self):
        result = recommend_grind_adjustment(
            {
                "total_shot_seconds": 29,
                "taste": "balanced and sweet",
                "timing_confidence": 0.7,
                "machine": "Gaggia Classic Pro",
                "grinder": "DF54",
                "dose_g": 18,
                "yield_g": 36,
                "grind_setting": "15",
                "roast_level": "medium",
            }
        )

        self.assertEqual(result["recommendation"], "keep_settings")
        self.assertEqual(result["confidence"], "high")
        self.assertEqual(result["needs_more_info"], [])

    def test_yield_is_optional_context(self):
        result = recommend_grind_adjustment(
            {
                "total_shot_seconds": 29,
                "taste": "balanced and sweet",
                "timing_confidence": 0.7,
                "machine": "Gaggia Classic Pro",
                "grinder": "DF54",
                "dose_g": 18,
                "grind_setting": "15",
                "roast_level": "medium",
            }
        )

        self.assertEqual(result["recommendation"], "keep_settings")
        self.assertNotIn("yield_g", result["needs_more_info"])

    def test_low_confidence_timing_requires_confirmation(self):
        result = recommend_grind_adjustment(
            {
                "total_shot_seconds": 17,
                "taste": "sour",
                "timing_confidence": 0.2,
            }
        )

        self.assertEqual(result["recommendation"], "confirm_timing")
        self.assertEqual(result["confidence"], "low")

    def test_custom_machine_target_range_is_supported(self):
        result = recommend_grind_adjustment(
            {
                "total_shot_seconds": 23,
                "taste": "balanced",
                "timing_confidence": 0.8,
                "machine_profile": {"target_total_shot_seconds": [25, 32]},
            }
        )

        self.assertEqual(result["recommendation"], "grind_finer")
        self.assertEqual(result["target_range_seconds"], (25.0, 32.0))


if __name__ == "__main__":
    unittest.main()
