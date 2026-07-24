import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import validate


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
        self.assertEqual("flutter", catalog["entries"][0]["sdk_id"])


if __name__ == "__main__":
    unittest.main()
