import math
import sys
import unittest
import wave
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.agent import app as agent_app
from services.agent import agent_runner, observability
from services.espresso_mcp import app as espresso_tools
from services.espresso_mcp import grinder_profiles, machine_profiles, profile_candidates


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
        observability.reset()
        self.client = TestClient(agent_app.app)

    def tearDown(self):
        profile_candidates.CANDIDATES_PATH = self.original_candidates_path
        self.candidate_tmp.cleanup()

    def test_health(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["tool_count"], 12)

    def test_metrics_initial_and_after_chat(self):
        self.assertEqual(self.client.get("/metrics").json()["chat_requests_total"], 0)

        self.client.post("/chat", json={"messages": [{"role": "user", "content": "hello"}]})

        self.assertEqual(self.client.get("/metrics").json()["chat_requests_total"], 1)

    def test_prometheus_metrics_endpoint(self):
        response = self.client.get("/metrics.prometheus")

        self.assertEqual(response.status_code, 200)
        self.assertIn("dialedin_chat_requests_total", response.text)
        self.assertIn("dialedin_shot_analysis_requests_total", response.text)
        self.assertIn("dialedin_last_missing_fields_count", response.text)

    def test_prometheus_metrics_after_manual_analysis(self):
        response = self.client.post(
            "/analyze-shot",
            json={
                "machine": "Rancilio Silvia",
                "grinder": "Varia VS3",
                "dose_g": 18,
                "grind_setting": "3.4",
                "roast_level": "medium",
                "taste": "balanced",
                "total_shot_seconds": 26,
            },
        )
        self.assertEqual(response.status_code, 200)

        metrics = self.client.get("/metrics.prometheus").text
        self.assertIn('dialedin_audio_analysis_requests_total{source="manual"} 1', metrics)
        self.assertIn("dialedin_audio_total_shot_seconds_latest", metrics)
        self.assertIn("dialedin_audio_timing_confidence_latest", metrics)

    def test_chat_asks_for_shot_context(self):
        response = self.client.post(
            "/chat",
            json={"messages": [{"role": "user", "content": "Can you dial in my espresso?"}]},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["needs_shot_analysis"])
        self.assertIn("machine", payload["response"].lower())
        self.assertIn("Never invent timestamps", payload["system_prompt"])


    def test_profile_candidate_admin_list_and_update(self):
        candidate = profile_candidates.save_profile_candidate("machine", "Admin Machine", "user-admin", {"machine": "Admin Machine"})
        response = self.client.get("/profile-candidates")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["candidates"][0]["candidate_key"], candidate["candidate_key"])

        update = self.client.patch(
            f"/profile-candidates/{candidate['candidate_key']}",
            json={
                "draft_profile": {"machine_name": "Admin Machine", "aliases": ["admin"]},
                "review_notes": ["verified source urls"],
                "status": "draft_needs_review",
            },
        )

        self.assertEqual(update.status_code, 200)
        updated = update.json()["candidate"]
        self.assertEqual(updated["status"], "draft_needs_review")
        self.assertEqual(updated["draft_profile"]["machine_name"], "Admin Machine")
        self.assertEqual(updated["review_notes"], ["verified source urls"])

    def test_profile_candidate_admin_deletes_candidate(self):
        candidate = profile_candidates.save_profile_candidate("machine", "Delete Me", "user-admin", {})

        response = self.client.delete(f"/profile-candidates/{candidate['candidate_key']}")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["deleted"])
        self.assertEqual(profile_candidates.load_profile_candidates(), [])

    def test_profile_candidate_admin_reruns_research_for_one_candidate(self):
        candidate = profile_candidates.save_profile_candidate("grinder", "Admin Grinder", "user-admin", {})
        calls = []

        def fake_worker(**kwargs):
            calls.append(kwargs)
            return [{"candidate_key": kwargs["candidate_key"], "status": "draft_ready"}]

        original_worker = agent_app.profile_research_worker.run_worker
        agent_app.profile_research_worker.run_worker = fake_worker
        try:
            response = self.client.post(f"/profile-candidates/{candidate['candidate_key']}/research")
        finally:
            agent_app.profile_research_worker.run_worker = original_worker

        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, [{"candidate_key": candidate["candidate_key"]}])
        self.assertEqual(response.json()["results"][0]["status"], "draft_ready")

    def test_profile_candidate_admin_promotes_reviewed_machine(self):
        with TemporaryDirectory() as tmp:
            original_machine_path = machine_profiles.PROFILE_PATH
            original_grinder_path = grinder_profiles.PROFILE_PATH
            machine_profiles.PROFILE_PATH = Path(tmp) / "machine_profiles.json"
            grinder_profiles.PROFILE_PATH = Path(tmp) / "grinder_profiles.json"
            machine_profiles.PROFILE_PATH.write_text('[{"machine_name":"Generic Espresso Machine","aliases":[]}]\n', encoding="utf-8")
            grinder_profiles.PROFILE_PATH.write_text('[{"grinder_name":"Generic Numeric Grinder","aliases":[]}]\n', encoding="utf-8")
            machine_profiles.load_machine_profiles.cache_clear()
            try:
                candidate = profile_candidates.save_profile_candidate("machine", "Admin Promote", "user-admin", {})
                self.client.patch(
                    f"/profile-candidates/{candidate['candidate_key']}",
                    json={
                        "draft_profile": {
                            "machine_name": "Admin Promote",
                            "aliases": ["admin promote"],
                            "image": {
                                "media_key": "dialchat-media/admin/machine_photo/admin-promote.jpg",
                                "storage_mode": "s3",
                                "status": "reviewed",
                            },
                        },
                        "review_notes": ["ready"],
                        "status": "draft_ready",
                    },
                )

                response = self.client.post(f"/profile-candidates/{candidate['candidate_key']}/promote")
            finally:
                machine_profiles.PROFILE_PATH = original_machine_path
                grinder_profiles.PROFILE_PATH = original_grinder_path
                machine_profiles.load_machine_profiles.cache_clear()

        self.assertEqual(response.status_code, 200)
        self.assertIn(response.json()["status"], {"inserted", "updated"})
        self.assertEqual(profile_candidates.load_profile_candidates(), [])

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

    def test_analyze_shot_without_yield_is_allowed(self):
        response = self.client.post(
            "/analyze-shot",
            json={
                "user_id": "user-no-yield",
                "total_shot_seconds": 29,
                "timing_confidence": 0.9,
                "machine": "BES870",
                "grinder": "Baratza Encore ESP",
                "dose_g": 18,
                "grind_setting": "12",
                "roast_level": "medium",
                "taste": "balanced",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertNotIn("yield_g", payload["missing_fields"])
        self.assertEqual(payload["recommendation"]["recommendation"], "keep_settings")

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

    def test_autorun_profile_research_runs_when_enabled(self):
        agent_app.settings = agent_app.settings.__class__(
            app_name=agent_app.settings.app_name,
            local_upload_dir=agent_app.settings.local_upload_dir,
            require_confirm_below_confidence=agent_app.settings.require_confirm_below_confidence,
            profile_research_autorun=True,
            profile_research_autorun_limit=1,
            chat_llm_extraction_enabled=False,
            chat_llm_model_id="anthropic.claude-haiku-4-5-20251001-v1:0",
            aws_region="us-east-1",
        )
        calls = []

        def fake_worker(**kwargs):
            calls.append(kwargs)

        original_worker = agent_app.profile_research_worker.run_worker
        agent_app.profile_research_worker.run_worker = fake_worker
        try:
            response = self.client.post(
                "/analyze-shot",
                json={
                    "user_id": "user-autorun",
                    "total_shot_seconds": 29,
                    "timing_confidence": 0.9,
                    "machine": "Autorun Unknown Machine",
                    "grinder": "Autorun Unknown Grinder",
                    "dose_g": 18,
                    "grind_setting": "12",
                    "roast_level": "medium",
                    "taste": "balanced",
                },
            )
        finally:
            agent_app.profile_research_worker.run_worker = original_worker

        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, [{"limit": 1}])

    def test_autorun_profile_research_does_not_run_when_disabled(self):
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
        calls = []

        def fake_worker(**kwargs):
            calls.append(kwargs)

        original_worker = agent_app.profile_research_worker.run_worker
        agent_app.profile_research_worker.run_worker = fake_worker
        try:
            response = self.client.post(
                "/analyze-shot",
                json={
                    "user_id": "user-no-autorun",
                    "total_shot_seconds": 29,
                    "timing_confidence": 0.9,
                    "machine": "No Autorun Unknown Machine",
                    "grinder": "No Autorun Unknown Grinder",
                    "dose_g": 18,
                    "grind_setting": "12",
                    "roast_level": "medium",
                    "taste": "balanced",
                },
            )
        finally:
            agent_app.profile_research_worker.run_worker = original_worker

        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, [])

    def test_analyze_shot_captures_unknown_gear_candidates(self):
        response = self.client.post(
            "/analyze-shot",
            json={
                "user_id": "user-unknown",
                "total_shot_seconds": 29,
                "timing_confidence": 0.9,
                "machine": "Mystery Machine X",
                "grinder": "Mystery Grinder Y",
                "dose_g": 18,
                "grind_setting": "12",
                "roast_level": "medium",
                "taste": "balanced",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["machine_profile"]["machine_name"], "Generic Espresso Machine")
        self.assertEqual(len(payload["profile_candidates"]), 2)
        self.assertEqual({candidate["type"] for candidate in payload["profile_candidates"]}, {"machine", "grinder"})

    def test_analyze_shot_uses_canonical_grinder_for_likely_typo(self):
        response = self.client.post(
            "/analyze-shot",
            json={
                "user_id": "user-typo",
                "total_shot_seconds": 17,
                "timing_confidence": 0.9,
                "machine": "Rancilio Silvia",
                "grinder": "Varia V3",
                "dose_g": 18,
                "grind_setting": "3.4",
                "roast_level": "medium",
                "taste": "balanced",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["profile_candidates"], [])
        exact = payload["recommendation"]["exact_grind_setting"]
        self.assertEqual(exact["grinder_profile"]["grinder_name"], "Varia VS3")

    def test_built_in_grinder_does_not_capture_separate_grinder_candidate(self):
        response = self.client.post(
            "/analyze-shot",
            json={
                "user_id": "user-built-in",
                "total_shot_seconds": 17,
                "timing_confidence": 0.9,
                "machine": "Mystery Built In Machine",
                "uses_built_in_grinder": True,
                "dose_g": 18,
                "grind_setting": "14",
                "roast_level": "medium",
                "taste": "sour",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertNotIn("grinder", payload["missing_fields"])
        self.assertEqual(len(payload["profile_candidates"]), 1)
        self.assertEqual(payload["profile_candidates"][0]["type"], "machine")
        exact = payload["recommendation"]["exact_grind_setting"]
        self.assertEqual(exact["grinder_profile"]["grinder_name"], "Generic Numeric Grinder")
        self.assertIsNone(exact["suggested_setting"])
        self.assertIn("small steps finer", payload["recommendation"]["adjustment"])

    def test_analyze_shot_rejects_invalid_known_grinder_setting(self):
        response = self.client.post(
            "/analyze-shot",
            json={
                "user_id": "user-bad-grind",
                "total_shot_seconds": 29,
                "timing_confidence": 0.9,
                "machine": "BES870",
                "grinder": "Baratza Encore ESP",
                "dose_g": 18,
                "grind_setting": "12.5",
                "roast_level": "medium",
                "taste": "balanced",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("whole-number", response.json()["detail"])

    def test_analyze_shot_requires_timing_or_video(self):
        response = self.client.post("/analyze-shot", json={"user_id": "user-3"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("Either video_s3_key or total_shot_seconds", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
