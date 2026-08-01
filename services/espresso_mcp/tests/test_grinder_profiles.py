import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from grinder_profiles import get_grinder_profile, suggest_grind_setting, validate_grind_setting


class GrinderProfilesTest(unittest.TestCase):
    def test_alias_match_resolves_varia_vs6(self):
        profile = get_grinder_profile("varia grinder vs6")

        self.assertEqual(profile["grinder_name"], "Varia VS6")

    def test_unknown_grinder_returns_generic_profile(self):
        profile = get_grinder_profile("Some Unknown Grinder")

        self.assertEqual(profile["grinder_name"], "Generic Numeric Grinder")

    def test_new_aliases_resolve_popular_grinders(self):
        cases = {
            "niche": "Niche Zero",
            "bes870": "Breville Barista Express Built-in Grinder",
            "sage smart grinder pro": "Breville Smart Grinder Pro",
            "df64 gen2": "Turin DF64 Gen 2",
            "064s": "Timemore Sculptor 064S",
        }

        for alias, expected_name in cases.items():
            with self.subTest(alias=alias):
                self.assertEqual(get_grinder_profile(alias)["grinder_name"], expected_name)

    def test_profiles_include_step_estimates(self):
        from grinder_profiles import _load_profiles

        for profile in _load_profiles():
            with self.subTest(grinder=profile["grinder_name"]):
                self.assertIn("seconds_per_small_step_estimate", profile)
                self.assertGreater(profile["seconds_per_small_step_estimate"], 0)
                self.assertIn("max_recommended_small_steps", profile)
                self.assertGreaterEqual(profile["max_recommended_small_steps"], 1)

    def test_validate_known_grinder_range(self):
        self.assertIsNone(validate_grind_setting("Varia VS6", "1.8"))
        self.assertIn("accepts settings", validate_grind_setting("Varia VS6", "7"))

    def test_validate_integer_grinder_rejects_decimal(self):
        self.assertIn("whole-number", validate_grind_setting("Baratza Encore ESP", "12.5"))

    def test_validate_unknown_grinder_allows_numeric(self):
        self.assertIsNone(validate_grind_setting("My Custom Grinder", "12.5"))
        self.assertEqual(validate_grind_setting("My Custom Grinder", "fine-ish"), "Use a numeric grind setting.")

    def test_varia_vs6_finer_setting_uses_seconds_per_step_estimate(self):
        result = suggest_grind_setting("Varia VS6", "1.8", "grind_finer", 17, (25, 35))

        self.assertEqual(result["suggested_setting"], 1.5)
        self.assertEqual(result["adjustment_size"], "medium")
        self.assertEqual(result["estimated_small_steps"], 3)
        self.assertEqual(result["seconds_gap"], 8)

    def test_varia_vs6_coarser_setting_raises_number(self):
        result = suggest_grind_setting("Varia VS6", "1.8", "grind_coarser", 42, (25, 35))

        self.assertEqual(result["suggested_setting"], 2.1)
        self.assertEqual(result["estimated_small_steps"], 3)

    def test_non_numeric_setting_does_not_guess(self):
        result = suggest_grind_setting("Varia VS6", "between 1 and 2", "grind_finer", 17, (25, 35))

        self.assertIsNone(result["suggested_setting"])


if __name__ == "__main__":
    unittest.main()
