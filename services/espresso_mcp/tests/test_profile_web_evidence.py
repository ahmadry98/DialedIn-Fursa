import unittest
from unittest.mock import patch

from services.espresso_mcp import profile_web_evidence


class ProfileWebEvidenceTest(unittest.TestCase):
    def test_build_queries_prefers_machine_specs_and_manuals(self):
        queries = profile_web_evidence.build_queries("machine", "Lelit Victoria")

        self.assertIn("official specifications", queries[0])
        self.assertIn("manual pdf", queries[1])

    def test_slug_candidates_include_model_without_brand(self):
        slugs = profile_web_evidence.slug_candidates(["lelit", "anita", "pl042temd"])

        self.assertIn("lelit-anita-pl042temd", slugs)
        self.assertIn("anita-pl042temd", slugs)
        self.assertIn("pl042temd", slugs)

    def test_direct_url_candidates_include_lelit_product_page(self):
        urls = [
            result["url"]
            for result in profile_web_evidence.build_direct_url_candidates("machine", "Lelit Anita PL042TEMD")
        ]

        self.assertIn("https://www.lelit.com/product/anita-pl042temd/", urls)

    def test_duckduckgo_parser_extracts_results(self):
        body = """
        <a rel=\"nofollow\" class=\"result__a\" href=\"/l/?uddg=https%3A%2F%2Fexample.com%2Fmanual.pdf\">Official Manual</a>
        <a class=\"result__snippet\">Machine manual snippet</a>
        """

        results = profile_web_evidence.DuckDuckGoResultParser.parse(body)

        self.assertEqual(results[0]["title"], "Official Manual")
        self.assertEqual(profile_web_evidence.normalize_url(results[0]["url"]), "https://example.com/manual.pdf")

    def test_exact_direct_product_slug_scores_above_generated_suffix(self):
        exact = {
            "url": "https://www.lelit.com/product/anita-pl042temd/",
            "title": "Possible official Lelit Anita PL042TEMD page",
            "snippet": "Direct official URL fallback generated from the entered gear name.",
            "source": "direct_fallback",
        }
        generated = {
            **exact,
            "url": "https://www.lelit.com/product/anita-pl042temd-espresso-machine/",
        }

        self.assertGreater(
            profile_web_evidence.score_result(exact, "machine", "Lelit Anita PL042TEMD"),
            profile_web_evidence.score_result(generated, "machine", "Lelit Anita PL042TEMD"),
        )

    def test_collect_web_evidence_ranks_and_fetches(self):
        search_results = [
            {"url": "https://reddit.com/r/espresso/test", "title": "Reddit", "snippet": "skip"},
            {"url": "https://manufacturer.example/victoria", "title": "Lelit Victoria official specs", "snippet": "58mm portafilter"},
        ]

        with patch.object(profile_web_evidence, "build_direct_url_candidates", return_value=[]), patch.object(
            profile_web_evidence, "search_web", return_value=search_results
        ), patch.object(
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
