from pathlib import Path
import shutil

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

REFERENCE_FILES = [("rules/flutter.json", "rules/flutter.json"), ("rules/reactivex.json", "rules/reactivex.json"),
  ("rules/itgsa.json", "rules/itgsa.json"), ("schema/v1/chart-rule.schema.json", "schema/v1/chart-rule.schema.json"),
  ("schema/v1/manifest.schema.json", "schema/v1/manifest.schema.json"), ]


def main() -> None:
  readme = CHART_DIR / "README.md"
  content = readme.read_text(encoding="utf-8")
  content = content.replace("\n\nEnglish | [简体中文](README.zh-Hans.md)", "")

  OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
  skill_file = OUTPUT_DIR / "SKILL.md"
  skill_file.write_text(HEADER + content, encoding="utf-8")

  # references
  refs_dir = OUTPUT_DIR / "references"
  if refs_dir.exists():
    shutil.rmtree(refs_dir)
  refs_dir.mkdir(parents=True)

  for src_rel, dst_rel in REFERENCE_FILES:
    src = CHART_DIR / src_rel
    dst = refs_dir / dst_rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


if __name__ == "__main__":
  main()
