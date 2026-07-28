import subprocess
import sys
from pathlib import Path


SDK_DETAILS_DIR = Path(__file__).resolve().parents[1]


def main():
    test_directories = sorted(
        path for path in SDK_DETAILS_DIR.rglob("tests") if path.is_dir()
    )
    if not test_directories:
        raise RuntimeError("No SDK details test directories were discovered")
    test_files = [
        path
        for directory in test_directories
        for path in directory.glob("test_*.py")
    ]
    if not test_files:
        raise RuntimeError("No SDK details tests were discovered")

    failed = False
    for directory in test_directories:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-v",
                "-s",
                str(directory),
                "-p",
                "test_*.py",
            ],
            check=False,
        )
        failed = failed or result.returncode != 0
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
