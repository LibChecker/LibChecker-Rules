import copy
import json
import sys
import tempfile
from unittest import mock
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

    def test_unity_definition_and_archive_contract(self):
        path = validate.SDK_DETAILS_DIR / "candidates/unity/definition.json"
        # Continue checking the contract after promoting the definition.
        if not path.exists():
            path = validate.SDKS_DIR / "unity/definition.json"
        definition = validate.load_json(path)
        sdk_id, uuids = validate.validate_definition(path, definition)
        self.assertEqual("unity", sdk_id)
        self.assertEqual([validate.load_json(validate.ROOT / "native-libs/libunity.so.json")["uuid"]], uuids)
        for probe in definition["probes"]:
            modern = next(layout for layout in probe["reader"]["layouts"] if layout["offset"] == 48)
            checks = [(c["left"], c["op"], c["right"]) for c in modern["checks"]]
            self.assertIn(("u8@40", "eq", "0"), checks)
            self.assertIn(("end+4", "le", "48+u64be@16"), checks)
            self.assertIn(("48+u64be@16", "le", "u64be@32"), checks)
        for field_path, value in (
            (("schema_version",), 2),
            (("native_library_names",), []),
            (("native_library_names",), ["lib*.so"]),
            (("native_library_names",), ["lib..a.so"]),
            (("native_library_names",), ["liba.SO"]),
            (("native_library_names",), ["a" * 126 + ".so"]),
            (("native_library_names",), ["one.so", "one.so"]),
            (("native_library_names",), ["../one.so"]),
            (("native_library_names",), [f"lib{i}.so" for i in range(17)]),
            (("probes", 0, "source", "file_name"), "libunity.so"),
            (("probes", 0, "source", "archive_paths"), ["/root"]),
            (("probes", 2, "source", "container", "entry"), "../other"),
            (("probes", 2, "source", "container", "format"), "unknown"),
            (("probes", 0, "reader", "layouts", 0, "checks", 0, "op"), "eval"),
            (("probes", 0, "reader", "layouts", 0, "checks", 0, "left"), "u32le@512"),
            (("probes", 0, "reader", "layouts", 0, "checks", 0, "right"), "size+end+8"),
            (("probes", 0, "reader", "layouts", 0, "checks", 0, "right"), "9223372036854775808"),
            (("probes", 0, "captures", 0, "formats"), ["##", "[a-z]"]),
            (("probes", 1, "reader", "operator"), "ascii_strings"),
            (("probes", 0, "captures", 0, "type"), "semver"),
            (("probes", 1, "captures", 0, "max_results"), 1),
        ):
            with self.subTest(field=field_path):
                changed = copy.deepcopy(definition)
                parent = changed
                for key in field_path[:-1]:
                    parent = parent[key]
                parent[field_path[-1]] = value
                with self.assertRaises(ValueError):
                    validate.validate_definition(path, changed)

    def test_promoted_definition_exports_native_library_names(self):
        definition = validate.SDK_DETAILS_DIR / "candidates/unity/definition.json"
        if not definition.exists():
            definition = validate.SDKS_DIR / "unity/definition.json"
        unity = validate.load_json(definition)
        self.assertEqual(["libyuanshen.so"], unity["native_library_names"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdks = root / "sdk-details/sdks"
            promoted = sdks / "unity/definition.json"
            promoted.parent.mkdir(parents=True)
            promoted.write_text(json.dumps(unity), encoding="utf-8")
            with (
                mock.patch.object(validate, "ROOT", root),
                mock.patch.object(validate, "SDKS_DIR", sdks),
                mock.patch.object(validate, "collect_rule_uuids", return_value=set(unity["target_uuids"])),
                mock.patch.object(validate, "collect_jetpack_rule_uuids", return_value=set()),
            ):
                entry, = validate.build_catalog()["entries"]
            self.assertEqual(unity["native_library_names"], entry["native_library_names"])

    def test_rejects_native_library_name_owned_by_two_sdks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdks = root / "sdk-details/sdks"
            rules = root / "native-libs"
            rules.mkdir()
            for sdk_id in ("flutter", "unity"):
                rule = validate.load_json(validate.ROOT / f"native-libs/lib{sdk_id}.so.json")
                (rules / f"lib{sdk_id}.so.json").write_text(json.dumps(rule), encoding="utf-8")
                source = validate.SDKS_DIR / sdk_id / "definition.json"
                if not source.exists():
                    source = validate.SDK_DETAILS_DIR / "candidates" / sdk_id / "definition.json"
                definition = validate.load_json(source)
                definition.update(schema_version=3, target_uuids=[rule["uuid"]], native_library_names=["libshared.so"])
                target = sdks / sdk_id / "definition.json"
                target.parent.mkdir(parents=True)
                target.write_text(json.dumps(definition), encoding="utf-8")
            with mock.patch.object(validate, "ROOT", root), mock.patch.object(validate, "SDKS_DIR", sdks):
                with self.assertRaisesRegex(ValueError, r"libshared\.so belongs to both flutter and unity"):
                    validate.build_catalog()

    def test_schema_three_accepts_an_existing_package_probe(self):
        definition = generate_androidx_definitions.build_definition(
            generate_androidx_definitions.ANDROIDX_DEFINITIONS[0]
        )
        definition["native_library_names"] = ["lib+one.so"]
        with self.assertRaises(ValueError):
            validate.validate_definition(validate.SDKS_DIR / definition["sdk_id"] / "definition.json", definition)
        definition["schema_version"] = 3
        path = validate.SDKS_DIR / definition["sdk_id"] / "definition.json"
        validate.validate_definition(path, definition)

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
