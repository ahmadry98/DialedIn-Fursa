import math
import sys
import unittest
import wave
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.agent.app import app
from services.agent import agent_runner
from services.espresso_mcp import app as espresso_tools


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


class AgentApiTest(unittest.TestCase):
    def setUp(self):
        espresso_tools.SHOT_HISTORY.clear()
        agent_runner.METRICS.update(
            {
                "shot_analysis_requests_total": 0,
                "chat_requests_total": 0,
                "last_missing_fields_count": 0,
            }
        )
        self.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["tool_count"], 8)

    def test_metrics_initial_and_after_chat(self):
        self.assertEqual(self.client.get("/metrics").json()["chat_requests_total"], 0)

        self.client.post("/chat", json={"messages": [{"role": "user", "content": "hello"}]})

        self.assertEqual(self.client.get("/metrics").json()["chat_requests_total"], 1)

    def test_chat_asks_for_shot_context(self):
        response = self.client.post(
            "/chat",
            json={"messages": [{"role": "user", "content": "Can you dial in my espresso?"}]},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["needs_shot_analysis"])
        self.assertIn("shot video", payload["response"])
        self.assertIn("Never invent timestamps", payload["system_prompt"])

    def test_analyze_shot_with_manual_total_time(self):
        response = self.client.post(
            "/analyze-shot",
            json={
                "user_id": "user-1",
                "total_shot_seconds": 17,
                "timing_confidence": 0.9,
                "machine": "BES870",
                "grinder": "Baratza Encore ESP",
                "dose_g": 18,
                "yield_g": 36,
                "grind_setting": "12",
                "roast_level": "medium",
                "taste": "sour and watery",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["recommendation"]["recommendation"], "grind_finer")
        self.assertEqual(payload["machine_profile"]["machine_name"], "Breville Barista Express")
        self.assertEqual(payload["missing_fields"], [])
        self.assertEqual(payload["saved_result"]["status"], "saved")

    def test_analyze_shot_with_wav_path(self):
        with TemporaryDirectory() as tmp:
            wav_path = Path(tmp) / "shot.wav"
            write_synthetic_wav(wav_path)
            response = self.client.post(
                "/analyze-shot",
                json={
                    "user_id": "user-2",
                    "video_s3_key": str(wav_path),
                    "machine": "Rancilio Silvia",
                    "grinder": "DF54",
                    "dose_g": 18,
                    "yield_g": 36,
                    "grind_setting": "15",
                    "roast_level": "medium",
                    "taste": "sour",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertAlmostEqual(payload["timing"]["total_shot_seconds"], 8.0, delta=0.75)
        self.assertEqual(payload["recommendation"]["recommendation"], "grind_finer")

    def test_analyze_shot_requires_timing_or_video(self):
        response = self.client.post("/analyze-shot", json={"user_id": "user-3"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("Either video_s3_key or total_shot_seconds", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
