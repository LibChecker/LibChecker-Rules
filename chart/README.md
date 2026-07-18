# Chart rules

This directory contains declarative statistics shown by LibChecker's chart
page. Source files are reviewed in `rules/` and `icons/`; generated download
artifacts are committed under `cloud/`.

## Layout

- `schema/v1/`: JSON schemas for rules and the generated manifest.
- `rules/`: one reviewed statistic definition per JSON file.
- `icons/`: SVG icons referenced by external rules.
- `tools/build_bundle.py`: deterministic bundle and manifest generator.
- `cloud/v1/`: generated files consumed by LibChecker.

Run the checks from the repository root:

```shell
python3 -m unittest chart.tools.test_build_bundle
python3 chart/tools/build_bundle.py --bundle-version 9
```

The APK never executes code from this repository. Rules can only select
evidence and operators implemented by the installed LibChecker version.

Schema v1 currently supports numeric comparisons on `target_sdk` and exact
library-name membership through `native_library` plus `contains`.
