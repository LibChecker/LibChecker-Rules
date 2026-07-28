import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import validate
import generate_androidx_definitions


class ValidateTest(unittest.TestCase):
    def test_rejects_remote_path_escape(self):
        for value in (
            "../sdk-details/config.json",
            "sdk-details/../secret.json",
            "https://example.com/config.json",
            "sdk-details\\config.json",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate.validate_remote_path(value, "test path")

    def test_catalog_is_deterministic(self):
        first = validate.serialized_catalog()
        second = validate.serialized_catalog()
        self.assertEqual(first, second)
        catalog = json.loads(first)
        self.assertEqual(1, catalog["schema_version"])
        sdk_ids = {entry["sdk_id"] for entry in catalog["entries"]}
        self.assertTrue(
            {
                "flutter",
                *[
                    item["sdk_id"]
                    for item in generate_androidx_definitions.ANDROIDX_DEFINITIONS
                ],
            }.issubset(sdk_ids)
        )

    def test_every_jetpack_rule_has_exactly_one_remote_definition(self):
        catalog = json.loads(validate.serialized_catalog())
        owners = {}
        for entry in catalog["entries"]:
            for library_uuid in entry["library_uuids"]:
                self.assertNotIn(library_uuid, owners)
                owners[library_uuid] = entry["sdk_id"]

        jetpack_uuids = validate.collect_jetpack_rule_uuids()
        self.assertEqual(32, len(jetpack_uuids))
        self.assertTrue(jetpack_uuids.issubset(owners))

    def test_generated_androidx_definitions_are_current(self):
        generate_androidx_definitions.check()

    def test_rejects_prefix_on_non_prefixed_capture(self):
        definition = generate_androidx_definitions.build_definition(
            generate_androidx_definitions.ANDROIDX_DEFINITIONS[0]
        )
        definition["probes"][0]["captures"][0]["prefix"] = "unexpected"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / definition["sdk_id"] / "definition.json"
            path.parent.mkdir()
            with self.assertRaises(ValueError):
                validate.validate_definition(path, definition)


if __name__ == "__main__":
    unittest.main()
