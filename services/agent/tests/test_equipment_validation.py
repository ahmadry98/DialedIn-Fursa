import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.agent import equipment_validation


class EquipmentValidationTest(unittest.TestCase):
    def test_machine_prompt_requires_specific_model_not_brand_only(self):
        prompt = equipment_validation._build_prompt(name="Nuova Simonelli", gear_type="machine")

        self.assertIn("specific equipment model", prompt)
        self.assertIn("not just a brand", prompt)
        self.assertIn("Rancilio Silvia", prompt)

    def test_grinder_prompt_requires_specific_model_not_brand_only(self):
        prompt = equipment_validation._build_prompt(name="Varia", gear_type="grinder")

        self.assertIn("specific equipment model", prompt)
        self.assertIn("not just a brand", prompt)
        self.assertIn("Varia VS3", prompt)

    def test_brand_only_name_can_be_rejected_by_llm_validation(self):
        with patch.object(equipment_validation, "_validate_with_bedrock") as fake_validate:
            fake_validate.return_value = {
                "is_equipment": False,
                "confidence": "high",
                "corrected_name": None,
                "reason": "Nuova Simonelli is a brand; the model is needed.",
            }

            result = equipment_validation.validate_equipment_name(
                name="Nuova Simonelli",
                gear_type="machine",
                model_id="test-model",
                region="us-east-1",
            )

        self.assertFalse(result["is_equipment"])
        self.assertIn("model", result["reason"].lower())


if __name__ == "__main__":
    unittest.main()
