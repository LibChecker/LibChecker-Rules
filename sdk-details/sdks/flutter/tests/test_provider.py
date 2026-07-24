import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import provider


class FetcherTest(unittest.TestCase):
    def test_builds_engine_files_and_reuses_historical_framework_mapping(self):
        engine_a = "a" * 40
        engine_b = "b" * 40
        framework_old = "1" * 40
        framework_new_same_engine = "2" * 40
        framework_new_engine = "3" * 40
        existing = {
            engine_a: {
                "engine": engine_a,
                "releases": [
                    {
                        "flutter": "1.0.0",
                        "dart": "2.0.0",
                        "channel": "stable",
                        "framework": framework_old,
                        "release_date": "2020-01-01T00:00:00Z",
                    }
                ],
            }
        }
        official = {
            framework_old: self.release(framework_old, "1.0.0", "2.0.1"),
            framework_new_same_engine: self.release(
                framework_new_same_engine, "1.0.1", "2.0.1"
            ),
            framework_new_engine: self.release(
                framework_new_engine, "2.0.0", "3.0.0"
            ),
        }
        resolved = {
            framework_new_same_engine: engine_a,
            framework_new_engine: engine_b,
        }
        calls = []

        def resolver(framework):
            calls.append(framework)
            return resolved[framework]

        mappings = provider.build_mappings(
            official,
            existing,
            {framework_old: engine_a},
            resolver=resolver,
        )

        self.assertCountEqual(
            calls, [framework_new_same_engine, framework_new_engine]
        )
        self.assertEqual(2, len(mappings[engine_a]["releases"]))
        self.assertEqual("2.0.1", mappings[engine_a]["releases"][1]["dart"])
        self.assertEqual("2.0.0", mappings[engine_b]["releases"][0]["flutter"])

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            provider.write_mappings(mappings, output)
            written = json.loads((output / f"{engine_a}.json").read_text())
            self.assertEqual(engine_a, written["engine"])
            self.assertEqual(2, len(written["releases"]))

    def test_rejects_mismatched_engine_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            engine_dir = Path(directory)
            (engine_dir / f"{'a' * 40}.json").write_text(
                json.dumps({"engine": "b" * 40, "releases": []})
            )
            with self.assertRaises(ValueError):
                provider.load_existing_mappings(engine_dir)

    def test_preserves_historical_release_missing_from_official_index(self):
        engine = "a" * 40
        historical_framework = "1" * 40
        current_framework = "2" * 40
        existing = {
            engine: {
                "engine": engine,
                "releases": [
                    {
                        "flutter": "1.0.0",
                        "dart": "2.0.0",
                        "channel": "stable",
                        "framework": historical_framework,
                        "release_date": "2020-01-01T00:00:00Z",
                    }
                ],
            }
        }

        mappings = provider.build_mappings(
            {current_framework: self.release(current_framework, "2.0.0", "3.0.0")},
            existing,
            {historical_framework: engine},
            resolver=lambda _: engine,
        )

        self.assertEqual(
            {historical_framework, current_framework},
            {release["framework"] for release in mappings[engine]["releases"]},
        )

    def test_write_skips_unchanged_mapping(self):
        engine = "a" * 40
        framework = "1" * 40
        mappings = {
            engine: {
                "engine": engine,
                "releases": [
                    {
                        "flutter": "1.0.0",
                        "dart": None,
                        "channel": "stable",
                        "framework": framework,
                        "release_date": None,
                    }
                ],
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            self.assertEqual(1, provider.write_mappings(mappings, output))
            self.assertEqual(0, provider.write_mappings(mappings, output))

    def test_rejects_duplicate_framework_across_engines(self):
        framework = "1" * 40
        mappings = {
            engine: {
                "engine": engine,
                "releases": [
                    {
                        "flutter": version,
                        "dart": None,
                        "channel": "stable",
                        "framework": framework,
                        "release_date": None,
                    }
                ],
            }
            for engine, version in (("a" * 40, "1.0.0"), ("b" * 40, "2.0.0"))
        }
        with self.assertRaises(ValueError):
            provider.validate_mappings(mappings)

    @staticmethod
    def release(framework, version, dart):
        return {
            "hash": framework,
            "version": version,
            "dart_sdk_version": dart,
            "channel": "stable",
            "release_date": f"2026-01-0{version[0]}T00:00:00Z",
        }


if __name__ == "__main__":
    unittest.main()
