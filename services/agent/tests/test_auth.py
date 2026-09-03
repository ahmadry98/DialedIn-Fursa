import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.agent import app as agent_app
from services.agent.auth import AuthenticatedUser, current_user
from services.agent.config import AgentSettings


class AuthApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.original_settings = agent_app.settings
        agent_app.settings = AgentSettings(
            local_upload_dir=Path(self.tmp.name) / "raw-videos",
            local_media_upload_dir=Path(self.tmp.name) / "uploads",
            media_storage_mode="local",
            media_upload_prefix="test-media",
        )
        self.client = TestClient(agent_app.app)

    def tearDown(self):
        agent_app.app.dependency_overrides.clear()
        agent_app.settings = self.original_settings
        self.tmp.cleanup()

    def test_me_uses_demo_identity_when_auth_is_disabled(self):
        with patch.dict(os.environ, {"DIALEDIN_AUTH_ENABLED": "false"}):
            response = self.client.get("/me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user_id"], "demo-user")
        self.assertEqual(response.json()["tier"], "free")

    def test_me_requires_bearer_token_when_auth_is_enabled(self):
        with patch.dict(
            os.environ,
            {
                "DIALEDIN_AUTH_ENABLED": "true",
                "DIALEDIN_COGNITO_USER_POOL_ID": "us-east-1_test",
                "DIALEDIN_COGNITO_APP_CLIENT_ID": "mobile-client",
            },
        ):
            response = self.client.get("/me")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"]["code"], "authentication_required")

    def test_upload_path_uses_verified_identity_not_request_user_id(self):
        agent_app.app.dependency_overrides[current_user] = lambda: AuthenticatedUser(
            user_id="verified-sub",
            email="person@example.com",
        )

        response = self.client.post(
            "/media/upload-url",
            json={
                "filename": "shot.m4a",
                "content_type": "audio/mp4",
                "media_kind": "shot_audio",
                "user_id": "attacker-controlled-id",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("/verified-sub/shot_audio/", response.json()["media_key"])
        self.assertNotIn("attacker-controlled-id", response.json()["media_key"])
