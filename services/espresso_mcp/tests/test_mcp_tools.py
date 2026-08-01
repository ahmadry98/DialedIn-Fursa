import asyncio
import math
import sys
import unittest
import wave
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mcp import types

from services.espresso_mcp import app


def write_synthetic_wav(path: Path, sample_rate: int = 16000) -> None:
    duration = 12.0
    samples = np.zeros(int(duration * sample_rate), dtype=np.float32)
    timeline = np.arange(samples.size) / sample_rate
    quiet = 0.01 * np.sin(2 * math.pi * 100 * timeline)
    pump = 0.35 * np.sin(2 * math.pi * 120 * timeline)
    samples += quiet.astype(np.float32)
    active = (timeline >= 2.0) & (timeline <= 10.0)
    samples[active] += pump[active].astype(np.float32)
    pcm = np.clip(samples, -1, 1)
    pcm = (pcm * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm.tobytes())


class EspressoMcpToolsTest(unittest.TestCase):
    def setUp(self):
        app.SHOT_HISTORY.clear()

    def test_registered_tool_names(self):
        self.assertEqual(
            app.get_registered_tool_names(),
            [
                "extract_audio_track",
                "detect_machine_audio_window",
                "calculate_total_shot_time",
                "analyze_audio_timing",
                "recommend_grind_adjustment",
                "get_machine_profile",
                "save_shot_result",
                "compare_previous_shots",
                "capture_unknown_gear",
                "list_profile_candidates",
                "prepare_profile_research",
                "attach_draft_profile",
            ],
        )

    def test_mcp_server_and_tool_schemas_are_available(self):
        self.assertIsNotNone(app.mcp)
        schemas = app.get_tool_schemas()

        self.assertEqual(len(schemas), len(app.TOOL_NAMES))
        self.assertEqual(schemas[0]["name"], "extract_audio_track")
        self.assertIn("input_schema", schemas[0])

    def test_mcp_list_and_call_tool_handlers(self):
        listed = asyncio.run(app.list_mcp_tools())
        called = asyncio.run(
            app.call_mcp_tool(
                None,
                types.CallToolRequestParams(
                    name="calculate_total_shot_time",
                    arguments={"machine_start_time": 4, "machine_stop_time": 29},
                ),
            )
        )

        self.assertEqual(len(listed.tools), len(app.TOOL_NAMES))
        self.assertEqual(called.structured_content["total_shot_seconds"], 25.0)
        self.assertFalse(called.is_error)

    def test_calculate_total_shot_time(self):
        result = app.calculate_total_shot_time(4.2, 29.7)

        self.assertEqual(result["machine_start_time"], 4.2)
        self.assertEqual(result["machine_stop_time"], 29.7)
        self.assertEqual(result["total_shot_seconds"], 25.5)

    def test_get_machine_profile_alias(self):
        profile = app.get_machine_profile("BES870")

        self.assertEqual(profile["machine_name"], "Breville Barista Express")
        self.assertEqual(profile["specs"]["portafilter_mm"], 54)

    def test_recommend_grind_adjustment_adds_machine_profile(self):
        result = app.recommend_grind_adjustment(
            {
                "machine": "Linea Micra",
                "total_shot_seconds": 22,
                "taste": "sour",
                "timing_confidence": 0.9,
            }
        )

        self.assertEqual(result["recommendation"], "grind_finer")
        self.assertEqual(result["target_range_seconds"], (25.0, 32.0))

    def test_save_and_compare_previous_shots(self):
        saved = app.save_shot_result("user-1", {"total_shot_seconds": 22})
        comparison = app.compare_previous_shots("user-1", {"total_shot_seconds": 27})

        self.assertEqual(saved["status"], "saved")
        self.assertEqual(saved["shot_count"], 1)
        self.assertTrue(comparison["has_previous"])
        self.assertEqual(comparison["total_shot_delta_seconds"], 5.0)

    def test_compare_previous_shots_without_history(self):
        comparison = app.compare_previous_shots("user-1", {"total_shot_seconds": 27})

        self.assertFalse(comparison["has_previous"])
        self.assertIn("No previous shots", comparison["message"])

    def test_audio_tools_from_wav(self):
        with TemporaryDirectory() as tmp:
            wav_path = Path(tmp) / "shot.wav"
            write_synthetic_wav(wav_path)

            extracted = app.extract_audio_track(str(wav_path))
            timing = app.detect_machine_audio_window(extracted["audio_s3_key"])
            analyzed = app.analyze_audio_timing(str(wav_path))

        self.assertEqual(extracted["status"], "ok")
        self.assertIsNotNone(timing["machine_start_time"])
        self.assertAlmostEqual(timing["total_shot_seconds"], 8.0, delta=0.75)
        self.assertAlmostEqual(analyzed["total_shot_seconds"], 8.0, delta=0.75)
        self.assertIn("requires_manual_confirmation", analyzed)


if __name__ == "__main__":
    unittest.main()
