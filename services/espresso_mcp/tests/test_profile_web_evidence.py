import unittest
from unittest.mock import patch

from services.espresso_mcp import profile_web_evidence


class ProfileWebEvidenceTest(unittest.TestCase):
    def test_build_queries_prefers_machine_specs_and_manuals(self):
        queries = profile_web_evidence.build_queries("machine", "Lelit Victoria")

        self.assertIn("official specifications", queries[0])
        self.assertIn("manual pdf", queries[1])

    def test_duckduckgo_parser_extracts_results(self):
        body = """
        <a rel=\"nofollow\" class=\"result__a\" href=\"/l/?uddg=https%3A%2F%2Fexample.com%2Fmanual.pdf\">Official Manual</a>
        <a class=\"result__snippet\">Machine manual snippet</a>
        """

        results = profile_web_evidence.DuckDuckGoResultParser.parse(body)

        self.assertEqual(results[0]["title"], "Official Manual")
        self.assertEqual(profile_web_evidence.normalize_url(results[0]["url"]), "https://example.com/manual.pdf")

    def test_collect_web_evidence_ranks_and_fetches(self):
        search_results = [
            {"url": "https://reddit.com/r/espresso/test", "title": "Reddit", "snippet": "skip"},
            {"url": "https://manufacturer.example/victoria", "title": "Lelit Victoria official specs", "snippet": "58mm portafilter"},
        ]

        with patch.object(profile_web_evidence, "search_web", return_value=search_results), patch.object(
            profile_web_evidence, "fetch_page_text", return_value="Official page text says 58mm portafilter and vibration pump."
        ):
            evidence = profile_web_evidence.collect_web_evidence(
                {"type": "machine", "name_entered": "Lelit Victoria"}, max_results=1
            )

        self.assertEqual(len(evidence["sources"]), 1)
        self.assertEqual(evidence["sources"][0]["url"], "https://manufacturer.example/victoria")
        self.assertIn("vibration pump", evidence["text"])


if __name__ == "__main__":
    unittest.main()
