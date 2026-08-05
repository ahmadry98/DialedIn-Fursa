import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.agent import app as agent_app
from services.agent.config import AgentSettings


class StorageApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.original_settings = agent_app.settings
        agent_app.settings = AgentSettings(
            app_name="DialedIN Agent",
            local_upload_dir=Path(self.tmp.name) / "raw-videos",
            local_media_upload_dir=Path(self.tmp.name) / "uploads",
            media_storage_mode="local",
            media_upload_prefix="test-media",
            profile_research_autorun=False,
            chat_llm_extraction_enabled=False,
        )
        self.client = TestClient(agent_app.app)

    def tearDown(self):
        agent_app.settings = self.original_settings
        self.tmp.cleanup()

    def test_local_upload_url_put_and_register(self):
        response = self.client.post(
            "/media/upload-url",
            json={
                "filename": "shot.MOV",
                "content_type": "video/quicktime",
                "media_kind": "shot_video",
                "user_id": "user-1",
            },
        )

        self.assertEqual(response.status_code, 200)
        upload = response.json()
        self.assertEqual(upload["storage_mode"], "local")
        self.assertEqual(upload["method"], "PUT")
        self.assertTrue(upload["media_key"].endswith("shot.MOV"))

        put_response = self.client.put(upload["upload_url"], content=b"video-bytes")
        self.assertEqual(put_response.status_code, 200)
        self.assertEqual(Path(upload["media_key"]).read_bytes(), b"video-bytes")

        register_response = self.client.post(
            "/media/register",
            json={
                "media_key": upload["media_key"],
                "media_kind": "shot_video",
                "storage_mode": "local",
                "content_type": "video/quicktime",
            },
        )
        self.assertEqual(register_response.status_code, 200)
        registered = register_response.json()
        self.assertEqual(registered["video_s3_key"], upload["media_key"])

    def test_s3_upload_url_uses_presigned_put(self):
        agent_app.settings = AgentSettings(
            app_name="DialedIN Agent",
            media_storage_mode="s3",
            media_upload_bucket="dialedin-test-bucket",
            media_upload_prefix="uploads",
            aws_region="us-east-1",
        )
        self.client = TestClient(agent_app.app)

        class FakeS3Client:
            def generate_presigned_url(self, operation, Params, ExpiresIn):
                self.operation = operation
                self.params = Params
                self.expires = ExpiresIn
                return "https://example.com/upload"

        class FakeSession:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def client(self, service_name):
                self.service_name = service_name
                return fake_client

        fake_client = FakeS3Client()
        with patch("boto3.Session", FakeSession):
            response = self.client.post(
                "/media/upload-url",
                json={
                    "filename": "shot.mov",
                    "content_type": "video/quicktime",
                    "media_kind": "shot_video",
                    "user_id": "user-1",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["upload_url"], "https://example.com/upload")
        self.assertEqual(payload["storage_mode"], "s3")
        self.assertEqual(fake_client.operation, "put_object")
        self.assertEqual(fake_client.params["Bucket"], "dialedin-test-bucket")
        self.assertEqual(fake_client.params["ContentType"], "video/quicktime")


if __name__ == "__main__":
    unittest.main()
