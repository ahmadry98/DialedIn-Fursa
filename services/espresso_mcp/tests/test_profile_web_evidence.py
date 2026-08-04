import unittest
from unittest.mock import patch

from services.espresso_mcp import profile_web_evidence


class ProfileWebEvidenceTest(unittest.TestCase):
    def test_build_queries_prefers_known_manufacturer_site(self):
        queries = profile_web_evidence.build_queries("machine", "Lelit Victoria")

        self.assertTrue(queries[0].startswith("site:lelit.com"))
        self.assertTrue(any("manual pdf" in query for query in queries))


    def test_x1_anniversary_queries_prefer_illy_site(self):
        queries = profile_web_evidence.build_queries("machine", "X1 Anniversary E.S.E. Pod & Ground Espresso Machine")

        self.assertTrue(queries[0].startswith("site:illy.com"))

    def test_x1_anniversary_direct_candidates_do_not_guess_x1tech(self):
        urls = [
            result["url"]
            for result in profile_web_evidence.build_direct_url_candidates(
                "machine", "X1 Anniversary E.S.E. Pod & Ground Espresso Machine"
            )
        ]

        self.assertTrue(any("illy.com" in url for url in urls))
        self.assertFalse(any("x1tech.com" in url for url in urls))

    def test_known_manufacturer_domain_scores_above_misleading_x1tech_domain(self):
        illy = {
            "url": "https://www.illy.com/en-us/coffee-machines/all-italian-espresso-machines/x1-anniversary-coffee-machine-ese-ground/coffee-machines-X1-Anniversary-ESE-and-Ground-us-p.html",
            "title": "X1 Anniversary E.S.E. and Ground Coffee Machine",
            "snippet": "Illy coffee machine official product page",
        }
        misleading = {
            "url": "https://www.x1tech.com/products/anniversary-pod-ground-espressomachine",
            "title": "X1 Anniversary Pod Ground Espresso Machine",
            "snippet": "Product page",
        }

        self.assertGreater(
            profile_web_evidence.score_result(illy, "machine", "X1 Anniversary E.S.E. Pod & Ground Espresso Machine"),
            profile_web_evidence.score_result(misleading, "machine", "X1 Anniversary E.S.E. Pod & Ground Espresso Machine"),
        )

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

    def test_direct_url_candidates_include_two_word_brand_domain(self):
        urls = [
            result["url"]
            for result in profile_web_evidence.build_direct_url_candidates("machine", "la pavoni new casa bar")
        ]

        self.assertIn("https://www.lapavoni.com/en/products/domestic-machines/new-casa-bar", urls)
        self.assertIn("https://www.lapavoni.com/en/products/domestic-machines/new-casabar", urls)
        self.assertIn("https://www.lapavoni.com/en/products/domestic-machines/new-casabar-pid-black", urls)



    def test_known_direct_asset_candidates_include_elizabeth_pdf(self):
        urls = [result["url"] for result in profile_web_evidence.known_direct_asset_candidates("LELIT Elizabeth")]

        self.assertIn("https://assets.breville.com/Lelit/PESEL01/LELIT-Elizabeth-PL92T-120-EN.pdf", urls)

    def test_source_family_key_deduplicates_regional_product_pages(self):
        self.assertEqual(
            profile_web_evidence.source_family_key("https://www.lelit.com/en/products/domestic-machines/elizabeth"),
            profile_web_evidence.source_family_key("https://www.lelit.com/en-ca/products/elizabeth"),
        )
        self.assertEqual(
            profile_web_evidence.source_family_key("https://www.lelit.com/products/elizabeth"),
            profile_web_evidence.source_family_key("https://www.lelit.com/product/elizabeth"),
        )

    def test_pdf_and_trusted_asset_domains_rank_high_for_lelit(self):
        pdf_result = {
            "url": "https://assets.breville.com/Lelit/PESEL01/LELIT-Elizabeth-PL92T-120-EN.pdf",
            "title": "LELIT Elizabeth PL92T technical manual",
            "snippet": "dual boiler preinfusion LELIT58",
        }
        duplicate_product = {
            "url": "https://www.lelit.com/en-ca/products/elizabeth",
            "title": "LELIT Elizabeth",
            "snippet": "Product page",
        }

        self.assertGreater(
            profile_web_evidence.score_result(pdf_result, "machine", "LELIT Elizabeth"),
            profile_web_evidence.score_result(duplicate_product, "machine", "LELIT Elizabeth"),
        )

    def test_collect_web_evidence_deduplicates_regional_pages_and_keeps_pdf(self):
        search_results = [
            {"url": "https://www.lelit.com/en/products/elizabeth", "title": "Elizabeth", "snippet": "LELIT58 group"},
            {"url": "https://www.lelit.com/en-ca/products/elizabeth", "title": "Elizabeth Canada", "snippet": "LELIT58 group"},
            {"url": "https://assets.breville.com/Lelit/PESEL01/LELIT-Elizabeth-PL92T-120-EN.pdf", "title": "Manual PDF", "snippet": "dual boiler preinfusion"},
        ]

        def fake_fetch(url, **_kwargs):
            if url.endswith(".pdf"):
                return "Technical data says dual boiler, LELIT58 group, preinfusion activation."
            return "Official product page says LELIT58 group."

        with patch.object(profile_web_evidence, "build_direct_url_candidates", return_value=[]), patch.object(
            profile_web_evidence, "search_web", return_value=search_results
        ), patch.object(profile_web_evidence, "fetch_page_text", side_effect=fake_fetch):
            evidence = profile_web_evidence.collect_web_evidence(
                {"type": "machine", "name_entered": "LELIT Elizabeth"}, max_results=3
            )

        urls = [source["url"] for source in evidence["sources"]]
        self.assertIn("https://www.lelit.com/en/products/elizabeth", urls)
        self.assertIn("https://assets.breville.com/Lelit/PESEL01/LELIT-Elizabeth-PL92T-120-EN.pdf", urls)
        self.assertNotIn("https://www.lelit.com/en-ca/products/elizabeth", urls)
        self.assertIn("dual boiler", evidence["text"])

    def test_extract_pdf_text_falls_back_when_dependency_missing(self):
        with patch.dict("sys.modules", {"pypdf": None}):
            text = profile_web_evidence.extract_pdf_text(b"not a real pdf")

        self.assertIn("pypdf is not installed", text)

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

    def test_collect_web_evidence_searches_even_with_many_direct_candidates(self):
        direct_results = [
            {
                "url": f"https://example{i}.com/product/no-match",
                "title": "Possible official page",
                "snippet": "Direct fallback",
                "source": "direct_fallback",
            }
            for i in range(20)
        ]
        search_results = [
            {
                "url": "https://www.lapavoni.com/en/products/domestic-machines/new-casabar-pid-black",
                "title": "La Pavoni New Casabar PID Black",
                "snippet": "Filter holder internal diameter 58 mm",
            }
        ]

        def fake_fetch(url, **_kwargs):
            if "lapavoni" in url:
                return "Official La Pavoni page says filter holder internal diameter 58 mm."
            return ""

        with patch.object(profile_web_evidence, "build_direct_url_candidates", return_value=direct_results), patch.object(
            profile_web_evidence, "search_web", return_value=search_results
        ), patch.object(profile_web_evidence, "fetch_page_text", side_effect=fake_fetch):
            evidence = profile_web_evidence.collect_web_evidence(
                {"type": "machine", "name_entered": "la pavoni new casa bar"}, max_results=1
            )

        self.assertEqual(evidence["sources"][0]["url"], search_results[0]["url"])
        self.assertIn("58 mm", evidence["text"])

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
