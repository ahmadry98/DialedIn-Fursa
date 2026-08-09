import os
import sys
import unittest
from pathlib import Path

os.environ["DIALEDIN_PROFILE_STORAGE"] = "json"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from machine_profiles import get_machine_profile, get_machine_profile_by_slug, list_machine_profiles


class MachineProfilesTest(unittest.TestCase):
    def test_exact_match_returns_profile(self):
        profile = get_machine_profile("Rancilio Silvia")

        self.assertEqual(profile["machine_name"], "Rancilio Silvia")
        self.assertEqual(profile["specs"]["portafilter_mm"], 58)
        self.assertFalse(profile["specs"]["has_preinfusion"])

    def test_alias_match_resolves_bes870(self):
        profile = get_machine_profile("BES870")

        self.assertEqual(profile["machine_name"], "Breville Barista Express")
        self.assertEqual(profile["specs"]["portafilter_mm"], 54)
        self.assertTrue(profile["specs"]["has_preinfusion"])

    def test_alias_match_normalizes_delonghi_apostrophe(self):
        profile = get_machine_profile("De'Longhi EC685")

        self.assertEqual(profile["machine_name"], "DeLonghi Dedica")
        self.assertEqual(profile["specs"]["portafilter_mm"], 51)

    def test_new_aliases_resolve_popular_machines(self):
        cases = {
            "BES920": "Breville Dual Boiler",
            "MaraX": "Lelit Mara X",
            "Bianca V3": "Lelit Bianca V3",
            "Rocket Appartamento TCA": "Rocket Appartamento",
            "Steel Uno PID": "Ascaso Steel UNO PID / DUO PID",
            "Linea Mini R": "La Marzocco Linea Mini",
            "Synchronika": "ECM Synchronika",
            "Profitec GO": "Profitec GO",
        }

        for alias, expected_name in cases.items():
            with self.subTest(alias=alias):
                self.assertEqual(get_machine_profile(alias)["machine_name"], expected_name)

    def test_anita_profile_has_reviewed_technical_details(self):
        profile = get_machine_profile("PL042TEMD")

        self.assertEqual(profile["machine_name"], "LELIT Anita PL042TEMD")
        self.assertEqual(profile["specs"]["portafilter_mm"], 57)
        self.assertEqual(profile["specs"]["group_system"], "LELIT57")
        self.assertTrue(profile["specs"]["has_built_in_grinder"])
        self.assertEqual(profile["specs"]["built_in_grinder_burr_mm"], 38)
        self.assertTrue(profile["specs"]["termopid"])
        self.assertFalse(profile["specs"]["has_preinfusion"])
        self.assertTrue(profile["sources"]["technical_features"])

    def test_dialedin_slug_resolves_mobile_machine_profile(self):
        profile = get_machine_profile_by_slug("rancilio-silvia")

        self.assertEqual(profile["machine_name"], "Rancilio Silvia")
        self.assertEqual(profile["dialedin_slug"], "rancilio-silvia")

    def test_unknown_machine_returns_generic_profile(self):
        profile = get_machine_profile("Mystery Steam Box 3000")

        self.assertEqual(profile["machine_name"], "Generic Espresso Machine")
        self.assertIsNone(profile["specs"]["portafilter_mm"])

    def test_profiles_include_required_fields(self):
        top_level = {
            "machine_name",
            "aliases",
            "specs",
            "brew_defaults",
            "grind_adjustment_notes",
            "sources",
        }
        specs = {"portafilter_mm", "pump_type", "pressure_type", "has_preinfusion"}
        brew_defaults = {
            "target_total_shot_seconds",
            "typical_startup_delay_seconds",
            "target_visible_flow_seconds",
        }
        sources = {"aliases", "portafilter_mm", "pump_type", "pressure_type", "has_preinfusion"}

        for profile in list_machine_profiles():
            self.assertTrue(top_level.issubset(profile), profile["machine_name"])
            self.assertTrue(specs.issubset(profile["specs"]), profile["machine_name"])
            self.assertTrue(brew_defaults.issubset(profile["brew_defaults"]), profile["machine_name"])
            self.assertTrue(sources.issubset(profile["sources"]), profile["machine_name"])


if __name__ == "__main__":
    unittest.main()
