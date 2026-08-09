import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.espresso_mcp import profile_repository


class ProfileRepositoryTest(unittest.TestCase):
    def test_json_backend_loads_and_saves_profiles_when_forced(self):
        with TemporaryDirectory() as tmp, patch.dict(os.environ, {"DIALEDIN_PROFILE_STORAGE": "json"}, clear=True):
            path = Path(tmp) / "profiles.json"
            path.write_text(json.dumps([{"machine_name": "A"}]) + "\n", encoding="utf-8")

            profiles = profile_repository.load_profiles("machine", path)
            profiles.append({"machine_name": "Generic Espresso Machine"})
            profile_repository.save_profiles("machine", profiles, path)

            self.assertEqual(json.loads(path.read_text())[1]["machine_name"], "Generic Espresso Machine")

    def test_upsert_profile_inserts_before_generic(self):
        with TemporaryDirectory() as tmp, patch.dict(os.environ, {"DIALEDIN_PROFILE_STORAGE": "json"}, clear=True):
            path = Path(tmp) / "profiles.json"
            path.write_text(json.dumps([{"machine_name": "Generic Espresso Machine", "aliases": []}]) + "\n", encoding="utf-8")

            result = profile_repository.upsert_profile(
                profile_type="machine",
                json_path=path,
                draft={"machine_name": "Meraki", "aliases": ["meraki"]},
                name_field="machine_name",
                generic_name="Generic Espresso Machine",
                normalize=lambda value: str(value).lower(),
            )

            profiles = json.loads(path.read_text())
            self.assertEqual(result["status"], "inserted")
            self.assertEqual(profiles[0]["machine_name"], "Meraki")
            self.assertEqual(profiles[1]["machine_name"], "Generic Espresso Machine")


    def test_dynamodb_is_default_when_table_is_configured(self):
        with patch.dict(os.environ, {"DIALEDIN_PROFILE_TABLE": "profiles"}, clear=True):
            self.assertEqual(profile_repository._storage_mode(), "dynamodb")

    def test_json_can_be_forced_for_local_fixtures(self):
        with patch.dict(
            os.environ,
            {"DIALEDIN_PROFILE_STORAGE": "json", "DIALEDIN_PROFILE_TABLE": "profiles"},
            clear=True,
        ):
            self.assertEqual(profile_repository._storage_mode(), "json")

    def test_dynamodb_backend_writes_json_string_items(self):
        class FakeBatch:
            def __init__(self):
                self.items = []

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def put_item(self, Item):
                self.items.append(Item)

        class FakeTable:
            def __init__(self):
                self.batch = FakeBatch()

            def batch_writer(self):
                return self.batch

        fake_table = FakeTable()
        with patch.dict(os.environ, {"DIALEDIN_PROFILE_STORAGE": "dynamodb", "DIALEDIN_PROFILE_TABLE": "profiles"}), patch.object(
            profile_repository, "_dynamodb_table", return_value=fake_table
        ):
            profile_repository.save_profiles("grinder", [{"grinder_name": "Varia VS3", "aliases": ["vs3"]}], Path("unused.json"))

        self.assertEqual(fake_table.batch.items[0]["profile_type"], "grinder")
        self.assertEqual(fake_table.batch.items[0]["profile_id"], "varia-vs3")
        self.assertEqual(json.loads(fake_table.batch.items[0]["profile_json"])["grinder_name"], "Varia VS3")


if __name__ == "__main__":
    unittest.main()
