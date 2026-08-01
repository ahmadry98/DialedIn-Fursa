import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.espresso_mcp import profile_candidates, profile_research_worker


class ProfileResearchWorkerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.original_path = profile_candidates.CANDIDATES_PATH
        profile_candidates.CANDIDATES_PATH = Path(self.tmp.name) / "profile_candidates.json"
        profile_candidates.CANDIDATES_PATH.write_text("[]\n", encoding="utf-8")

    def tearDown(self):
        profile_candidates.CANDIDATES_PATH = self.original_path
        self.tmp.cleanup()

    def test_dry_run_builds_prompt_without_bedrock(self):
        candidate = profile_candidates.save_profile_candidate("grinder", "Kingrinder K6", "user-1", {"grind_setting": "25"})

        results = profile_research_worker.run_worker(candidate_key=candidate["candidate_key"], dry_run=True, web_evidence=False)

        self.assertEqual(results[0]["status"], "dry_run")
        self.assertIn("Expected schema", results[0]["prompt"])
        self.assertFalse(results[0]["evidence_found"])

    def test_dry_run_reads_evidence_file(self):
        candidate = profile_candidates.save_profile_candidate("machine", "Lelit Victoria", "user-1", {})
        evidence_dir = Path(self.tmp.name) / "evidence"
        evidence_dir.mkdir()
        (evidence_dir / "machine-lelit-victoria.md").write_text("Official page says 58mm portafilter.", encoding="utf-8")

        results = profile_research_worker.run_worker(
            candidate_key=candidate["candidate_key"],
            evidence_dir=evidence_dir,
            dry_run=True,
            web_evidence=False,
        )

        self.assertTrue(results[0]["evidence_found"])
        self.assertIn("Official page says 58mm", results[0]["prompt"])

    def test_dry_run_collects_web_evidence(self):
        candidate = profile_candidates.save_profile_candidate("machine", "Lelit Victoria", "user-1", {})
        fake_evidence = {
            "sources": [
                {
                    "url": "https://example.com/lelit-victoria",
                    "title": "Lelit Victoria",
                    "snippet": "58mm portafilter",
                    "query": "Lelit Victoria specs",
                }
            ],
            "text": "URL: https://example.com/lelit-victoria\nPage text excerpt: 58mm portafilter",
        }

        with patch.object(profile_research_worker.profile_web_evidence, "collect_web_evidence", return_value=fake_evidence):
            results = profile_research_worker.run_worker(candidate_key=candidate["candidate_key"], dry_run=True)

        self.assertTrue(results[0]["evidence_found"])
        self.assertEqual(results[0]["evidence_sources"][0]["url"], "https://example.com/lelit-victoria")
        self.assertIn("58mm portafilter", results[0]["prompt"])
        updated = profile_candidates.load_profile_candidates()[0]
        self.assertEqual(updated["research_evidence"]["sources"][0]["url"], "https://example.com/lelit-victoria")


    def test_polyai_style_model_id_is_normalized(self):
        self.assertEqual(
            profile_research_worker.normalize_bedrock_model_id("bedrock/openai.gpt-oss-20b-1:0"),
            "openai.gpt-oss-20b-1:0",
        )
        self.assertEqual(
            profile_research_worker.additional_model_request_fields("bedrock/openai.gpt-oss-20b-1:0"),
            {"reasoning_effort": "low"},
        )

    def test_parse_json_response_tolerates_fences(self):
        parsed = profile_research_worker.parse_json_response('```json\n{"grinder_name":"Kingrinder K6"}\n```')

        self.assertEqual(parsed["grinder_name"], "Kingrinder K6")

    def test_bedrock_response_attaches_draft(self):
        candidate = profile_candidates.save_profile_candidate("grinder", "Kingrinder K6", "user-1", {})
        fake_response = {
            "output": {
                "message": {
                    "content": [
                        {
                            "text": '{"grinder_name":"Kingrinder K6","aliases":["kingrinder k6"],"setting_type":"numeric_integer","lower_is_finer":true,"small_step":1,"medium_step":2,"large_step":3,"min_setting":0,"max_setting":240,"espresso_range":[30,60],"data_confidence":"C","notes":"Draft only.","source_urls":["https://example.com"]}'
                        }
                    ]
                }
            }
        }

        captured = {}

        class FakeClient:
            def converse(self, **kwargs):
                captured.update(kwargs)
                return fake_response

        fake_boto3 = types.SimpleNamespace(client=lambda *_args, **_kwargs: FakeClient())
        with patch.dict(sys.modules, {"boto3": fake_boto3}):
            results = profile_research_worker.run_worker(
                candidate_key=candidate["candidate_key"],
                model_id="bedrock/openai.gpt-oss-20b-1:0",
                region="us-east-1",
                web_evidence=False,
            )

        self.assertEqual(captured["modelId"], "openai.gpt-oss-20b-1:0")
        self.assertEqual(captured["additionalModelRequestFields"], {"reasoning_effort": "low"})
        self.assertEqual(results[0]["status"], "draft_ready")
        updated = profile_candidates.load_profile_candidates()[0]
        self.assertEqual(updated["draft_profile"]["grinder_name"], "Kingrinder K6")


if __name__ == "__main__":
    unittest.main()
