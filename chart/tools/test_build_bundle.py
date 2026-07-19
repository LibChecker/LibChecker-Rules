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
            ["official.flutter", "official.itgsa", "official.target-sdk-35-plus"],
            [rule["id"] for rule in rules],
        )

    def test_bundle_is_deterministic_and_contains_only_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_manifest = build_bundle(self.chart_dir, Path(first), 1)
            second_manifest = build_bundle(self.chart_dir, Path(second), 1)

            self.assertEqual(first_manifest, second_manifest)
            with zipfile.ZipFile(Path(first) / "chart.bundle") as archive:
                self.assertEqual(
                    [
                        "catalog.json",
                        "icons/android-15.svg",
                        "icons/flutter.svg",
                        "icons/itgsa.svg",
                    ],
                    archive.namelist(),
                )
                catalog = json.loads(archive.read("catalog.json"))
            self.assertEqual(1, catalog["schemaVersion"])
            self.assertEqual(3, len(catalog["definitions"]))
            self.assertTrue(
                all("releaseChannel" not in rule for rule in catalog["definitions"])
            )

    def test_stable_bundle_excludes_preview_only_rules(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            manifest = build_bundle(
                self.chart_dir,
                Path(output),
                10,
                channel="stable",
                minimum_app_version_code=123,
            )
            with zipfile.ZipFile(Path(output) / "chart.bundle") as archive:
                catalog = json.loads(archive.read("catalog.json"))

        self.assertEqual(
            ["official.flutter", "official.itgsa"],
            [rule["id"] for rule in catalog["definitions"]],
        )
        self.assertEqual(123, manifest["minimumAppVersionCode"])

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

    def test_itgsa_rule_keeps_all_detection_data_in_ordered_facets(self) -> None:
        itgsa_rule = next(
            rule for rule in read_rules(self.chart_dir) if rule["id"] == "official.itgsa"
        )
        facets = itgsa_rule["calculation"]["facets"]["items"]
        self.assertEqual(
            ["voip-service-kit", "fair-runtime-memory", "security-paste-view"],
            [facet["id"] for facet in facets],
        )

        voip_queries = facets[0]["condition"]["value"]["dexClasses"]
        self.assertEqual("Lcom/voip/service/", voip_queries[0]["name"]["value"])

        fair_conditions = facets[1]["condition"]["any"]
        self.assertEqual(
            {"dex_class", "manifest_receiver_action"},
            {condition["evidence"] for condition in fair_conditions},
        )
        fair_dex_condition = next(
            condition
            for condition in fair_conditions
            if condition["evidence"] == "dex_class"
        )
        fair_queries = fair_dex_condition["value"]["dexClasses"]
        self.assertEqual(
            {"itgsa.intent.action.TRIM", "itgsa.intent.action.KILL"},
            set(fair_queries[0]["stringConstants"]),
        )
        self.assertEqual(
            {"<init>", "addAction"},
            {
                reference["name"]
                for reference in fair_queries[0]["methodReferences"]
            },
        )

        security_queries = facets[2]["condition"]["value"]["dexClasses"]
        self.assertEqual(
            "Lcom/os/widget/SecurityPasteView;",
            security_queries[0]["name"]["value"],
        )

    def test_unknown_evidence_is_rejected(self) -> None:
        itgsa_rule = next(
            rule for rule in read_rules(self.chart_dir) if rule["id"] == "official.itgsa"
        )
        invalid_rule = deepcopy(itgsa_rule)
        invalid_rule["calculation"]["facets"]["items"][0]["condition"][
            "evidence"
        ] = "app_capability"

        with self.assertRaisesRegex(ValueError, "Unsupported rule evidence"):
            validate_calculation(invalid_rule, invalid_rule["id"])

    def test_duplicate_facet_ids_are_rejected(self) -> None:
        itgsa_rule = next(
            rule for rule in read_rules(self.chart_dir) if rule["id"] == "official.itgsa"
        )
        invalid_rule = deepcopy(itgsa_rule)
        invalid_rule["calculation"]["facets"]["items"][1]["id"] = (
            "voip-service-kit"
        )

        with self.assertRaisesRegex(ValueError, "Facet id is duplicated"):
            validate_calculation(invalid_rule, invalid_rule["id"])


if __name__ == "__main__":
    unittest.main()
