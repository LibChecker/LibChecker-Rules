import sys
import unittest
from pathlib import Path


SDK_DETAILS_DIR = Path(__file__).resolve().parents[1]


def main():
    suite = unittest.TestSuite()
    test_directories = sorted(
        path for path in SDK_DETAILS_DIR.rglob("tests") if path.is_dir()
    )
    for directory in test_directories:
        suite.addTests(
            unittest.defaultTestLoader.discover(
                start_dir=str(directory),
                pattern="test_*.py",
                top_level_dir=str(directory),
            )
        )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.testsRun == 0:
        raise RuntimeError("No SDK details tests were discovered")
    if not result.wasSuccessful():
        sys.exit(1)


if __name__ == "__main__":
    main()
