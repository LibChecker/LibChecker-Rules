import json
import tempfile
import unittest
import zipfile
from copy import deepcopy
from pathlib import Path

from chart.tools.build_bundle import build_bundle, read_rules, validate_calculation


class BuildChartBundleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.chart_dir = Path(__file__).resolve().parents[1]

    def test_source_rules_are_valid(self) -> None:
        rules = read_rules(self.chart_dir)

        self.assertEqual(
            ["official.flutter"],
            [rule["id"] for rule in rules],
        )

    def test_bundle_is_deterministic_and_contains_only_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_manifest = build_bundle(self.chart_dir, Path(first), 1)
            second_manifest = build_bundle(self.chart_dir, Path(second), 1)

            self.assertEqual(first_manifest, second_manifest)
            with zipfile.ZipFile(Path(first) / "chart.bundle") as archive:
                self.assertEqual(
                    ["catalog.json", "icons/flutter.svg"],
                    archive.namelist(),
                )
                catalog = json.loads(archive.read("catalog.json"))
            self.assertEqual(1, catalog["schemaVersion"])
            self.assertEqual(1, len(catalog["definitions"]))

    def test_native_library_rule_rejects_incompatible_operator(self) -> None:
        flutter_rule = next(
            rule for rule in read_rules(self.chart_dir) if rule["id"] == "official.flutter"
        )
        invalid_rule = deepcopy(flutter_rule)
        invalid_rule["calculation"]["predicate"]["operator"] = "equal"

        with self.assertRaisesRegex(ValueError, "must use contains"):
            validate_calculation(invalid_rule, invalid_rule["id"])

    def test_flutter_rule_preserves_brand_colors(self) -> None:
        flutter_rule = next(
            rule for rule in read_rules(self.chart_dir) if rule["id"] == "official.flutter"
        )

        self.assertEqual("original", flutter_rule["icon"]["renderMode"])


if __name__ == "__main__":
    unittest.main()
