import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.agent import image_identification


class ImageIdentificationTest(unittest.TestCase):
    def test_media_format_maps_supported_images(self):
        self.assertEqual(image_identification.media_format("image/png"), "png")
        self.assertEqual(image_identification.media_format("image/webp"), "webp")
        self.assertEqual(image_identification.media_format("image/jpeg"), "jpeg")

    def test_sanitize_guess_keeps_safe_shape(self):
        guess = image_identification.sanitize_guess(
            {"gear_type": "machine", "name": " Rancilio Silvia ", "confidence": "HIGH", "reason": "looks like it"},
            fallback_type="machine",
        )

        self.assertEqual(guess["gear_type"], "machine")
        self.assertEqual(guess["name"], "Rancilio Silvia")
        self.assertEqual(guess["confidence"], "high")

    def test_strip_data_url_prefix(self):
        self.assertEqual(image_identification.strip_data_url_prefix("data:image/jpeg;base64,abc"), "abc")
        self.assertEqual(image_identification.strip_data_url_prefix("abc"), "abc")

    def test_build_user_prompt_includes_known_candidates_and_visual_rules(self):
        prompt = image_identification.build_user_prompt("machine")

        self.assertIn("Known equipment candidates", prompt)
        self.assertIn("Rancilio Silvia", prompt)
        self.assertIn("Varia VS3", prompt)
        self.assertIn("return null with low confidence", prompt)


if __name__ == "__main__":
    unittest.main()
