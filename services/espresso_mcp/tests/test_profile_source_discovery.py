import unittest

from services.espresso_mcp import profile_source_discovery


class ProfileSourceDiscoveryTest(unittest.TestCase):
    def test_build_prompt_asks_for_json_source_leads(self):
        prompt = profile_source_discovery.build_source_discovery_prompt(
            {"type": "machine", "name_entered": "Quick Mill Silvano Evo", "latest_context": {}}
        )

        self.assertIn("Return ONLY valid JSON", prompt)
        self.assertIn("official_domains", prompt)
        self.assertIn("Quick Mill Silvano Evo", prompt)
        self.assertIn("Do not extract the final profile", prompt)

    def test_normalize_discovery_packet_sanitizes_domains_urls_and_confidence(self):
        packet = profile_source_discovery.normalize_discovery_packet(
            {
                "manufacturer": " Fellow ",
                "official_domains": ["https://www.fellowproducts.com/", "bad value"],
                "product_urls": ["https://fellowproducts.com/products/opus#reviews", "not-a-url"],
                "manual_urls": ["https://help.fellowproducts.com/hc/en-us/articles/123"],
                "support_urls": [],
                "search_queries": [" Fellow Opus official manual ", "x"],
                "confidence": "certain",
                "notes": "  maybe  ",
            }
        )

        self.assertEqual(packet["manufacturer"], "Fellow")
        self.assertEqual(packet["official_domains"], ["fellowproducts.com"])
        self.assertEqual(packet["product_urls"], ["https://fellowproducts.com/products/opus"])
        self.assertEqual(packet["manual_urls"], ["https://help.fellowproducts.com/hc/en-us/articles/123"])
        self.assertEqual(packet["search_queries"], ["Fellow Opus official manual"])
        self.assertEqual(packet["confidence"], "low")
        self.assertEqual(packet["notes"], "maybe")

    def test_discovery_domains_includes_url_hosts(self):
        domains = profile_source_discovery.discovery_domains(
            {
                "official_domains": ["quick-mill.com"],
                "product_urls": ["https://www.quick-mill.com/products/silvano/"],
                "manual_urls": ["https://manuals.quick-mill.com/silvano.pdf"],
                "support_urls": [],
            }
        )

        self.assertIn("quick-mill.com", domains)
        self.assertIn("manuals.quick-mill.com", domains)


if __name__ == "__main__":
    unittest.main()
