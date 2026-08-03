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


    def test_graph_does_not_store_small_talk_as_machine(self):
        response = graph.run_chat_graph(
            ChatRequest(
                messages=[
                    ChatMessage(role="user", content="hello"),
                    ChatMessage(role="assistant", content="What machine are you using?"),
                    ChatMessage(role="user", content="how are toy ?"),
                    ChatMessage(role="assistant", content="What grinder are you using?"),
                    ChatMessage(role="user", content="how are you?"),
                ],
                shot_context=ShotContext(machine="how are toy?", video_s3_key="866F409F.png"),
            ),
            fake_analyze,
        )

        self.assertIsNone(response.shot_context.machine)
        self.assertIsNone(response.shot_context.video_s3_key)
        self.assertEqual(response.next_field, "machine")
        self.assertIn("ready to help", response.response.lower())
        self.assertIn("machine", response.response.lower())


    def test_graph_rejects_non_equipment_machine_reply(self):
        response = graph.run_chat_graph(
            ChatRequest(messages=[ChatMessage(role="user", content="height")], shot_context=ShotContext()),
            fake_analyze,
        )

        self.assertIsNone(response.shot_context.machine)
        self.assertEqual(response.next_field, "machine")
        self.assertIn("machine", response.response.lower())

    def test_graph_accepts_known_machine_reply(self):
        response = graph.run_chat_graph(
            ChatRequest(messages=[ChatMessage(role="user", content="Rancilio Silvia")], shot_context=ShotContext()),
            fake_analyze,
        )

        self.assertEqual(response.shot_context.machine, "Rancilio Silvia")
        self.assertEqual(response.next_field, "grinder")

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


    def test_graph_ignores_llm_plain_number_timing_when_asking_for_dose(self):
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="17")],
            shot_context=ShotContext(
                machine="Lelit Anita",
                grinder="Lelit Anita built-in grinder",
                uses_built_in_grinder=True,
            ),
        )
        extracted = {"dose_g": 17, "total_shot_seconds": 17}

        with patch.object(graph, "get_settings") as fake_settings, patch.object(
            graph.llm_extraction, "extract_context_with_bedrock", return_value=extracted
        ):
            fake_settings.return_value.chat_llm_extraction_enabled = True
            fake_settings.return_value.chat_llm_model_id = "anthropic.claude-haiku-4-5-20251001-v1:0"
            fake_settings.return_value.aws_region = "us-east-1"
            response = graph.run_chat_graph(request, fake_analyze)

        self.assertEqual(response.shot_context.dose_g, 17)
        self.assertIsNone(response.shot_context.total_shot_seconds)
        self.assertEqual(response.next_field, "grind_setting")
        self.assertIsNone(response.analysis_result)

    def test_graph_accepts_plain_number_timing_only_when_asking_for_timing(self):
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="17")],
            shot_context=ShotContext(
                machine="Lelit Anita",
                grinder="Lelit Anita built-in grinder",
                uses_built_in_grinder=True,
                dose_g=17,
                grind_setting="1.9",
                roast_level="dark",
                taste="balanced",
            ),
        )
        extracted = {"total_shot_seconds": 17}

        with patch.object(graph, "get_settings") as fake_settings, patch.object(
            graph.llm_extraction, "extract_context_with_bedrock", return_value=extracted
        ):
            fake_settings.return_value.chat_llm_extraction_enabled = True
            fake_settings.return_value.chat_llm_model_id = "anthropic.claude-haiku-4-5-20251001-v1:0"
            fake_settings.return_value.aws_region = "us-east-1"
            response = graph.run_chat_graph(request, fake_analyze)

        self.assertEqual(response.shot_context.total_shot_seconds, 17)
        self.assertIsNotNone(response.analysis_result)

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
        self.assertEqual(response.shot_context.grinder, "Turin DF54")
        self.assertEqual(response.shot_context.total_shot_seconds, 17)



    def test_graph_low_confidence_image_guess_asks_for_name(self):
        request = ChatRequest(
            messages=[
                ChatMessage(
                    role="user",
                    content="machine photo",
                    image_base64="ZmFrZQ==",
                    image_media_type="image/jpeg",
                    image_kind="machine",
                )
            ]
        )
        guess = {"gear_type": "machine", "name": None, "confidence": "low", "reason": "Unclear photo."}

        with patch.object(graph, "get_settings") as fake_settings, patch.object(
            graph.image_identification, "identify_gear_image_with_bedrock", return_value=guess
        ):
            fake_settings.return_value.chat_llm_extraction_enabled = True
            fake_settings.return_value.chat_llm_model_id = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
            fake_settings.return_value.aws_region = "us-east-1"
            response = graph.run_chat_graph(request, fake_analyze)

        self.assertIsNone(response.shot_context.pending_gear_name)
        self.assertEqual(response.next_field, "machine")
        self.assertIn("could not identify the machine confidently", response.response.lower())

    def test_graph_canonicalizes_image_guess_alias(self):
        request = ChatRequest(
            messages=[
                ChatMessage(
                    role="user",
                    content="machine photo",
                    image_base64="ZmFrZQ==",
                    image_media_type="image/jpeg",
                    image_kind="machine",
                )
            ]
        )
        guess = {"gear_type": "machine", "name": "lelit anita", "confidence": "high", "reason": "Logo visible."}

        with patch.object(graph, "get_settings") as fake_settings, patch.object(
            graph.image_identification, "identify_gear_image_with_bedrock", return_value=guess
        ):
            fake_settings.return_value.chat_llm_extraction_enabled = True
            fake_settings.return_value.chat_llm_model_id = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
            fake_settings.return_value.aws_region = "us-east-1"
            response = graph.run_chat_graph(request, fake_analyze)

        self.assertEqual(response.shot_context.pending_gear_name, "LELIT Anita PL042TEMD")
        self.assertEqual(response.image_guess["name"], "LELIT Anita PL042TEMD")

    def test_graph_identifies_machine_image_and_requires_text_confirmation(self):
        request = ChatRequest(
            messages=[
                ChatMessage(
                    role="user",
                    content="machine photo",
                    image_base64="ZmFrZQ==",
                    image_media_type="image/jpeg",
                    image_kind="machine",
                )
            ]
        )
        guess = {
            "gear_type": "machine",
            "name": "Rancilio Silvia",
            "confidence": "medium",
            "reason": "Boxy single-boiler machine shape.",
        }

        with patch.object(graph, "get_settings") as fake_settings, patch.object(
            graph.image_identification, "identify_gear_image_with_bedrock", return_value=guess
        ), patch.object(graph.llm_extraction, "extract_context_with_bedrock") as fake_text_extraction:
            fake_settings.return_value.chat_llm_extraction_enabled = True
            fake_settings.return_value.chat_llm_model_id = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
            fake_settings.return_value.aws_region = "us-east-1"
            response = graph.run_chat_graph(request, fake_analyze)

        fake_text_extraction.assert_not_called()
        self.assertEqual(response.next_field, "confirm_machine")
        self.assertEqual(response.shot_context.pending_gear_name, "Rancilio Silvia")
        self.assertIsNone(response.shot_context.video_s3_key)
        self.assertIsNone(response.shot_context.total_shot_seconds)
        self.assertEqual(response.image_guess["name"], "Rancilio Silvia")
        self.assertIn("is that your machine", response.response.lower())


    def test_graph_rejected_image_guess_asks_natural_followup(self):
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="no")],
            shot_context=ShotContext(
                pending_gear_type="machine",
                pending_gear_name="Lelit Victoria",
                pending_gear_confidence="high",
            ),
        )

        response = graph.run_chat_graph(request, fake_analyze)

        self.assertIsNone(response.shot_context.pending_gear_name)
        self.assertIsNone(response.shot_context.machine)
        self.assertEqual(response.next_field, "machine")
        self.assertEqual(response.response, "No problem. What machine is it?")

    def test_graph_corrects_rejected_image_guess(self):
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="no it is Rancilio Silvia")],
            shot_context=ShotContext(
                pending_gear_type="machine",
                pending_gear_name="Breville Bambino",
                pending_gear_confidence="low",
            ),
        )

        response = graph.run_chat_graph(request, fake_analyze)

        self.assertEqual(response.shot_context.machine, "Rancilio Silvia")
        self.assertIsNone(response.shot_context.pending_gear_name)
        self.assertEqual(response.next_field, "grinder")
        self.assertIn("grinder", response.response.lower())

    def test_graph_corrects_rejected_image_guess_with_comma(self):
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="no, lelit anita")],
            shot_context=ShotContext(
                pending_gear_type="machine",
                pending_gear_name="Lelit Victoria",
                pending_gear_confidence="high",
            ),
        )

        response = graph.run_chat_graph(request, fake_analyze)

        self.assertEqual(response.shot_context.machine, "LELIT Anita PL042TEMD")
        self.assertFalse(response.shot_context.machine.startswith(","))
        self.assertEqual(response.next_field, "grinder")

    def test_graph_accepts_confirmed_image_guess(self):
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="yes")],
            shot_context=ShotContext(
                pending_gear_type="grinder",
                pending_gear_name="DF54",
                pending_gear_confidence="medium",
            ),
        )

        response = graph.run_chat_graph(request, fake_analyze)

        self.assertEqual(response.shot_context.grinder, "Turin DF54")
        self.assertIsNone(response.shot_context.pending_gear_name)
        self.assertEqual(response.next_field, "machine")



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
