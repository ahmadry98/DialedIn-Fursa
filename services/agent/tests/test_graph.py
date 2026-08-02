import sys
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.agent import graph
from services.agent.schemas import AnalyzeShotRequest, AnalyzeShotResponse, ChatMessage, ChatRequest, ShotContext


class CoachGraphTest(unittest.TestCase):
    def test_graph_asks_next_missing_field(self):
        response = graph.run_chat_graph(
            ChatRequest(messages=[ChatMessage(role="user", content="hi")]),
            fake_analyze,
        )

        self.assertEqual(response.next_field, "machine")
        self.assertIn("machine", response.response.lower())
        self.assertIsNone(response.analysis_result)

    def test_graph_runs_analysis_when_context_is_complete(self):
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="17 seconds")],
            shot_context=ShotContext(
                machine="Rancilio Silvia",
                grinder="DF54",
                dose_g=18,
                grind_setting="15",
                roast_level="medium",
                taste="sour",
            ),
        )

        response = graph.run_chat_graph(request, fake_analyze)

        self.assertIsNone(response.next_field)
        self.assertEqual(response.missing_fields, [])
        self.assertIsNotNone(response.analysis_result)
        self.assertIn("Next", response.response)

    def test_graph_uses_llm_extraction_when_enabled(self):
        request = ChatRequest(
            messages=[
                ChatMessage(
                    role="user",
                    content="I use a Silvia with DF54, 18 in, setting 15, medium roast, sour, 17 seconds",
                )
            ]
        )
        extracted = {
            "machine": "Rancilio Silvia",
            "grinder": "DF54",
            "dose_g": 18,
            "grind_setting": "15",
            "roast_level": "medium",
            "taste": "sour",
            "total_shot_seconds": 17,
        }

        with patch.object(graph, "get_settings") as fake_settings, patch.object(
            graph.llm_extraction, "extract_context_with_bedrock", return_value=extracted
        ):
            fake_settings.return_value.chat_llm_extraction_enabled = True
            fake_settings.return_value.chat_llm_model_id = "anthropic.claude-haiku-4-5-20251001-v1:0"
            fake_settings.return_value.aws_region = "us-east-1"
            response = graph.run_chat_graph(request, fake_analyze)

        self.assertIsNotNone(response.analysis_result)
        self.assertEqual(response.shot_context.machine, "Rancilio Silvia")
        self.assertEqual(response.shot_context.grinder, "DF54")
        self.assertEqual(response.shot_context.total_shot_seconds, 17)


def fake_analyze(request: AnalyzeShotRequest) -> AnalyzeShotResponse:
    return AnalyzeShotResponse(
        timing={
            "source_path": "manual",
            "machine_start_time": None,
            "machine_stop_time": None,
            "total_shot_seconds": request.total_shot_seconds,
            "start_confidence": 1,
            "stop_confidence": 1,
            "audio_method": "manual_total_time",
            "requires_manual_confirmation": False,
            "warnings": [],
        },
        machine_profile={"machine_name": request.machine},
        recommendation={
            "recommendation": "grind_finer",
            "adjustment": "set grinder finer",
            "reason": "Shot was fast.",
            "confidence": "medium",
            "keep_fixed": ["dose_g"],
            "needs_more_info": [],
            "target_range_seconds": [25, 32],
            "exact_grind_setting": {"setting_label": "14"},
        },
        missing_fields=[],
        profile_candidates=[],
        saved_result={"status": "saved"},
        previous_comparison={"status": "none"},
        message="ok",
    )


if __name__ == "__main__":
    unittest.main()
