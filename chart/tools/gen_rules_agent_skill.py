from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CHART_DIR = SCRIPT_DIR.parent
REPO_ROOT = CHART_DIR.parent
OUTPUT_DIR = REPO_ROOT / "skills" / "libchecker-chart-rules"

HEADER = """\
---
name: libchecker-chart-rules
description: Writing and validating LibChecker chart statistics rules. Provides JSON schema reference, evidence types, condition syntax, and bundle generation workflow for declarative chart rules.
author: LibChecker, Absinthe
license: Apache-2.0
user-invocable: true
---

"""


def main() -> None:
  readme = CHART_DIR / "README.md"
  content = readme.read_text(encoding="utf-8")
  content = content.replace("\n\nEnglish | [简体中文](README.zh-Hans.md)", "")

  OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
  skill_file = OUTPUT_DIR / "SKILL.md"
  skill_file.write_text(HEADER + content, encoding="utf-8")


if __name__ == "__main__":
  main()
