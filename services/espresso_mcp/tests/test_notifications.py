import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.espresso_mcp import notifications


class NotificationsTest(unittest.TestCase):
    def candidate(self, gear_type="machine"):
        return {
            "candidate_key": f"{gear_type}:quick mill silvano evo",
            "type": gear_type,
            "name_entered": "Quick Mill Silvano Evo" if gear_type == "machine" else "Fellow Opus",
            "status": "needs_research",
            "seen_count": 1,
            "created_at": "2026-08-11T10:00:00Z",
            "latest_context": {"machine": "Quick Mill Silvano Evo", "grinder": "Fellow Opus"},
        }

    def test_candidate_email_body_mentions_auto_research_and_admin_link(self):
        with patch.dict(os.environ, {"PROFILE_CANDIDATE_ADMIN_URL": "http://ai-dev.dialedin.me/admin"}):
            body = notifications._candidate_email_body(self.candidate())

        self.assertIn("Research should already be queued/running automatically", body)
        self.assertIn("Type: machine", body)
        self.assertIn("Admin review: http://ai-dev.dialedin.me/admin", body)
        self.assertIn("- grinder: Fellow Opus", body)

    def test_build_message_uses_support_sender_by_default(self):
        message = notifications._build_candidate_message(self.candidate("grinder"))

        self.assertEqual(message["From"], "support@dialedin.me")
        self.assertEqual(message["To"], "support@dialedin.me")
        self.assertEqual(message["Subject"], "DialedIN new grinder candidate: Fellow Opus")

    def test_notify_uses_ses_when_enabled(self):
        calls = []

        class FakeClient:
            def send_email(self, **kwargs):
                calls.append(kwargs)

        fake_boto3 = types.SimpleNamespace(client=lambda service, region_name=None: FakeClient())
        with patch.dict(sys.modules, {"boto3": fake_boto3}), patch.dict(
            os.environ,
            {
                "PROFILE_CANDIDATE_EMAIL_ENABLED": "true",
                "PROFILE_CANDIDATE_EMAIL_PROVIDER": "ses",
                "PROFILE_CANDIDATE_EMAIL_FROM": "support@dialedin.me",
                "PROFILE_CANDIDATE_EMAIL_TO": "support@dialedin.me",
            },
            clear=False,
        ):
            sent = notifications.notify_new_profile_candidate(self.candidate("grinder"))

        self.assertTrue(sent)
        self.assertEqual(calls[0]["FromEmailAddress"], "support@dialedin.me")
        self.assertEqual(calls[0]["Destination"]["ToAddresses"], ["support@dialedin.me"])
        self.assertIn("new grinder candidate", calls[0]["Content"]["Simple"]["Subject"]["Data"])

    def test_notify_disabled_by_default(self):
        with patch.dict(os.environ, {"PROFILE_CANDIDATE_EMAIL_ENABLED": "false"}, clear=False):
            self.assertFalse(notifications.notify_new_profile_candidate(self.candidate()))


if __name__ == "__main__":
    unittest.main()
