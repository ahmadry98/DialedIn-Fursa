import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.agent import app as agent_app
from services.agent import agent_runner
from services.espresso_mcp import app as espresso_tools
from services.espresso_mcp import profile_candidates


class ConversationApiTest(unittest.TestCase):
    def setUp(self):
        espresso_tools.SHOT_HISTORY.clear()
        agent_app.settings = agent_app.settings.__class__(
            app_name=agent_app.settings.app_name,
            local_upload_dir=agent_app.settings.local_upload_dir,
            require_confirm_below_confidence=agent_app.settings.require_confirm_below_confidence,
            profile_research_autorun=False,
            profile_research_autorun_limit=1,
            chat_llm_extraction_enabled=False,
            chat_llm_model_id="anthropic.claude-haiku-4-5-20251001-v1:0",
            aws_region="us-east-1",
        )
        self.candidate_tmp = TemporaryDirectory()
        self.original_candidates_path = profile_candidates.CANDIDATES_PATH
        profile_candidates.CANDIDATES_PATH = Path(self.candidate_tmp.name) / "profile_candidates.json"
        profile_candidates.CANDIDATES_PATH.write_text("[]\n", encoding="utf-8")
        agent_runner.METRICS.update(
            {
                "shot_analysis_requests_total": 0,
                "chat_requests_total": 0,
                "last_missing_fields_count": 0,
            }
        )
        self.client = TestClient(agent_app.app)

    def tearDown(self):
        profile_candidates.CANDIDATES_PATH = self.original_candidates_path
        self.candidate_tmp.cleanup()

    def post_chat(self, message, context=None):
        body = {"messages": [{"role": "user", "content": message}]}
        if context is not None:
            body["shot_context"] = context
        response = self.client.post("/chat", json=body)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_chat_greeting_starts_with_machine_question(self):
        payload = self.post_chat("hi")

        self.assertEqual(payload["next_field"], "machine")
        self.assertIn("machine", payload["response"].lower())
        self.assertFalse(payload["needs_shot_analysis"])

    def test_chat_collects_context_and_runs_analysis(self):
        context = self.post_chat("Breville Barista Express")["shot_context"]
        self.assertEqual(context["machine"], "Breville Barista Express")

        context = self.post_chat("Baratza Encore ESP", context)["shot_context"]
        context = self.post_chat("18g", context)["shot_context"]
        context = self.post_chat("grind setting 12", context)["shot_context"]
        context = self.post_chat("medium", context)["shot_context"]
        context = self.post_chat("sour and watery", context)["shot_context"]
        payload = self.post_chat("17 seconds", context)

        self.assertIsNone(payload["next_field"])
        self.assertEqual(payload["missing_fields"], [])
        self.assertIsNotNone(payload["analysis_result"])
        self.assertIn("17", payload["response"])
        self.assertEqual(payload["analysis_result"]["recommendation"]["recommendation"], "grind_finer")

    def test_chat_allows_unknown_roast(self):
        context = self.post_chat("Rancilio Silvia")["shot_context"]
        context = self.post_chat("DF54", context)["shot_context"]
        context = self.post_chat("idk", context)["shot_context"]
        context = self.post_chat("15", context)["shot_context"]

        payload = self.post_chat("I don't know", context)
        self.assertTrue(payload["shot_context"]["roast_unknown"])
        self.assertEqual(payload["next_field"], "taste")

    def test_chat_analyzes_without_dose_or_roast_when_unknown(self):
        context = {
            "user_id": "demo-user",
            "machine": "Rancilio Silvia",
            "grinder": "DF54",
            "dose_unknown": True,
            "grind_setting": "15",
            "roast_unknown": True,
            "taste": "sour",
        }

        payload = self.post_chat("17 seconds", context)

        self.assertIsNone(payload["next_field"])
        self.assertEqual(payload["missing_fields"], [])
        self.assertIsNotNone(payload["analysis_result"])

    def test_chat_builtin_grinder_skips_grinder_question(self):
        context = self.post_chat("Meraki")["shot_context"]
        payload = self.post_chat("built-in", context)

        self.assertTrue(payload["shot_context"]["uses_built_in_grinder"])
        self.assertEqual(payload["next_field"], "dose_g")
        self.assertNotIn("grinder", payload["missing_fields"])
        self.assertIn("grind_setting", payload["missing_fields"])

    def test_chat_unknown_dose_then_asks_grind_setting(self):
        context = self.post_chat("Lelit Anita")["shot_context"]
        context = self.post_chat("built-in", context)["shot_context"]
        payload = self.post_chat("idk", context)

        self.assertTrue(payload["shot_context"]["dose_unknown"])
        self.assertEqual(payload["next_field"], "grind_setting")
        self.assertIn("grind setting", payload["response"].lower())

    def test_chat_unknown_roast_then_asks_taste(self):
        context = {
            "user_id": "demo-user",
            "machine": "LELIT Anita PL042TEMD",
            "grinder": "LELIT Anita PL042TEMD built-in grinder",
            "uses_built_in_grinder": True,
            "dose_unknown": True,
            "grind_setting": "2.1",
        }

        payload = self.post_chat("I do not know", context)

        self.assertTrue(payload["shot_context"]["roast_unknown"])
        self.assertEqual(payload["next_field"], "taste")
        self.assertIn("taste", payload["response"].lower())

    def test_chat_accepts_video_path_as_timing_source(self):
        context = {
            "user_id": "demo-user",
            "machine": "Rancilio Silvia",
            "grinder": "DF54",
            "dose_g": 18,
            "grind_setting": "15",
            "roast_level": "medium",
        }

        payload = self.post_chat("data/raw-videos/shot_007.mp4", context)

        self.assertEqual(payload["shot_context"]["video_s3_key"], "data/raw-videos/shot_007.mp4")
        self.assertEqual(payload["next_field"], "taste")
        self.assertIsNone(payload["analysis_result"])


if __name__ == "__main__":
    unittest.main()
