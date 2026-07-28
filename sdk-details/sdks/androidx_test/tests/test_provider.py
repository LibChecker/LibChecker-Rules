import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import provider


class AndroidXTestProviderTest(unittest.TestCase):
    def test_parses_official_group_index(self):
        content = (
            b"<androidx.test>"
            b'<core versions="1.6.1,1.7.0-alpha01,1.7.0"/>'
            b"</androidx.test>"
        )

        self.assertEqual(
            ["1.6.1", "1.7.0-alpha01", "1.7.0"],
            provider.parse_versions(content),
        )

    def test_fingerprints_kotlin_modules_in_classes_jar(self):
        content = self.aar(
            {
                "META-INF/androidx.test.core.kotlin_module": b"module",
                "androidx/test/core/Example.class": b"class",
            }
        )

        fingerprints = provider.fingerprint_aar(content)

        self.assertEqual(1, len(fingerprints))
        self.assertEqual(
            "META-INF/androidx.test.core.kotlin_module",
            fingerprints[0][0],
        )
        self.assertRegex(fingerprints[0][1], r"^[a-f0-9]{64}$")

    def test_keeps_colliding_versions_as_candidates(self):
        digest = "a" * 64
        entry = "META-INF/androidx.test.core.kotlin_module"

        mappings = provider.build_mappings(
            {
                "1.6.1": [(entry, digest)],
                "1.7.0": [(entry, digest)],
            }
        )

        self.assertEqual(
            ["1.7.0", "1.6.1"],
            [
                release["version"]
                for release in mappings[digest]["releases"]
            ],
        )

    def test_sorts_stable_before_prerelease_candidates(self):
        digest = "a" * 64
        entry = "META-INF/androidx.test.core.kotlin_module"

        mappings = provider.build_mappings(
            {
                "1.7.0-beta01": [(entry, digest)],
                "1.7.0": [(entry, digest)],
                "1.7.0-rc01": [(entry, digest)],
            }
        )

        self.assertEqual(
            ["1.7.0", "1.7.0-rc01", "1.7.0-beta01"],
            [
                release["version"]
                for release in mappings[digest]["releases"]
            ],
        )

    def test_preserves_historical_mapping(self):
        old_digest = "a" * 64
        new_digest = "b" * 64
        entry = "META-INF/androidx.test.core.kotlin_module"
        existing = {
            old_digest: {
                "sha256": old_digest,
                "releases": [
                    {
                        "artifact": "core",
                        "version": "1.5.0",
                        "entry": entry,
                    }
                ],
            }
        }

        mappings = provider.build_mappings(
            {"1.7.0": [(entry, new_digest)]},
            existing,
        )

        self.assertEqual({old_digest, new_digest}, set(mappings))

    def test_write_skips_unchanged_mapping(self):
        digest = "a" * 64
        mappings = provider.build_mappings(
            {
                "1.7.0": [
                    ("META-INF/androidx.test.core.kotlin_module", digest)
                ]
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            self.assertEqual(1, provider.write_mappings(mappings, output))
            self.assertEqual(0, provider.write_mappings(mappings, output))
            written = json.loads((output / f"{digest}.json").read_text())
            self.assertEqual(digest, written["sha256"])

    @staticmethod
    def aar(entries):
        classes_buffer = io.BytesIO()
        with zipfile.ZipFile(classes_buffer, "w") as classes:
            for name, content in entries.items():
                classes.writestr(name, content)
        aar_buffer = io.BytesIO()
        with zipfile.ZipFile(aar_buffer, "w") as aar:
            aar.writestr("classes.jar", classes_buffer.getvalue())
        return aar_buffer.getvalue()


if __name__ == "__main__":
    unittest.main()
