import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.agent import account_cleanup
from services.agent.config import AgentSettings
from services.espresso_mcp import storage as shot_storage


class AccountCleanupTest(unittest.TestCase):
    def test_deletes_local_media_and_memory_history(self):
        with TemporaryDirectory() as tmp:
            settings = AgentSettings(
                local_media_upload_dir=Path(tmp),
                media_storage_mode="local",
                media_upload_prefix="dialchat-media",
            )
            media_dir = Path(tmp) / "dialchat-media" / "user-1" / "shot_audio"
            media_dir.mkdir(parents=True)
            (media_dir / "shot.m4a").write_bytes(b"audio")
            shot_storage.SHOT_HISTORY["user-1"] = [{"shot": 1}]

            with (
                patch.object(account_cleanup, "_shot_table_name", return_value=None),
                patch.object(account_cleanup, "_delete_dynamodb_partition", return_value=0),
            ):
                result = account_cleanup.delete_user_data("user-1", settings)

            self.assertFalse((Path(tmp) / "dialchat-media" / "user-1").exists())
            self.assertNotIn("user-1", shot_storage.SHOT_HISTORY)
            self.assertEqual(result["media_objects"], 1)

    def test_rejects_empty_user_id(self):
        with self.assertRaises(ValueError):
            account_cleanup.delete_user_data("", AgentSettings())


if __name__ == "__main__":
    unittest.main()

