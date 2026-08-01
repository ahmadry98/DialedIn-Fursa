import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import visual_analysis


class VisualAnalysisTest(unittest.TestCase):
    def test_should_try_visual_fallback_for_manual_confirmation(self):
        self.assertTrue(visual_analysis.should_try_visual_fallback(True))

    def test_should_try_visual_fallback_for_talking_audio(self):
        self.assertTrue(
            visual_analysis.should_try_visual_fallback(False, audio_quality="talking")
        )

    def test_visual_timing_placeholder_is_structured(self):
        result = visual_analysis.analyze_visual_timing(Path("shot_001.mp4"))

        self.assertFalse(result.available)
        self.assertEqual(result.method, "not_implemented")
        self.assertIsNone(result.machine_start_time)
        self.assertEqual(result.confidence, 0.0)
        self.assertTrue(result.warnings)


if __name__ == "__main__":
    unittest.main()
