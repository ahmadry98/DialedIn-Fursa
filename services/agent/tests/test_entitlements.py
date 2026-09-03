import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.agent import entitlements
from services.agent.config import AgentSettings


class EntitlementsTest(unittest.TestCase):
    def setUp(self):
        entitlements.reset_memory_store()
        self.settings = AgentSettings(
            quota_enabled=True,
            usage_storage="memory",
            free_monthly_analysis_limit=3,
            pro_monthly_analysis_limit=100,
        )

    def tearDown(self):
        entitlements.reset_memory_store()

    def test_free_account_stops_after_three_analyses(self):
        for expected_remaining in (2, 1, 0):
            status = entitlements.consume_analysis("free-user", self.settings)
            self.assertEqual(status.remaining, expected_remaining)

        with self.assertRaises(entitlements.QuotaExceeded) as raised:
            entitlements.consume_analysis("free-user", self.settings)

        self.assertEqual(raised.exception.status.used, 3)
        self.assertEqual(raised.exception.status.limit, 3)

    def test_active_pro_entitlement_uses_pro_limit(self):
        expires_at = int((datetime.now(UTC) + timedelta(days=365)).timestamp())
        entitlements.set_memory_entitlement("pro-user", expires_at)

        status = entitlements.consume_analysis("pro-user", self.settings)

        self.assertEqual(status.tier, "pro")
        self.assertEqual(status.limit, 100)
        self.assertEqual(status.remaining, 99)

    def test_expired_pro_entitlement_falls_back_to_free(self):
        expires_at = int((datetime.now(UTC) - timedelta(seconds=1)).timestamp())
        entitlements.set_memory_entitlement("expired-user", expires_at)

        status = entitlements.usage_status("expired-user", self.settings)

        self.assertEqual(status.tier, "free")
        self.assertEqual(status.limit, 3)

    def test_disabled_quota_does_not_consume(self):
        settings = AgentSettings(quota_enabled=False, usage_storage="memory")

        first = entitlements.consume_analysis("demo-user", settings)
        second = entitlements.consume_analysis("demo-user", settings)

        self.assertEqual(first.used, 0)
        self.assertEqual(second.used, 0)

    def test_revenuecat_event_grants_pro_and_is_idempotent(self):
        expiration = int((datetime.now(UTC) + timedelta(days=365)).timestamp())
        event = {
            "id": "event-1",
            "app_user_id": "paid-user",
            "type": "INITIAL_PURCHASE",
            "entitlement_ids": ["pro"],
            "expiration_at_ms": expiration * 1000,
        }

        self.assertTrue(entitlements.apply_revenuecat_event(event, self.settings))
        self.assertFalse(entitlements.apply_revenuecat_event(event, self.settings))
        self.assertEqual(entitlements.usage_status("paid-user", self.settings).tier, "pro")

    def test_revenuecat_expiration_removes_pro(self):
        entitlements.set_memory_entitlement("expired-paid-user", int((datetime.now(UTC) + timedelta(days=1)).timestamp()))
        event = {
            "id": "event-expired",
            "app_user_id": "expired-paid-user",
            "type": "EXPIRATION",
            "entitlement_ids": [],
            "expiration_at_ms": None,
        }

        self.assertTrue(entitlements.apply_revenuecat_event(event, self.settings))
        self.assertEqual(entitlements.usage_status("expired-paid-user", self.settings).tier, "free")


if __name__ == "__main__":
    unittest.main()

