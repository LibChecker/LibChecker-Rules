# LibChecker-Rules

[![Rules version](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FLibChecker%2FLibChecker-Rules%2FHEAD%2Frule-counts.json&query=%24.rulesVersion&label=Rules&color=6f42c1&style=flat&cacheSeconds=3600)](cloud/md5/v4)
[![Native libraries](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FLibChecker%2FLibChecker-Rules%2FHEAD%2Frule-counts.json&query=%24.nativeLibraries&label=Native%20libraries&color=0969da&style=flat&cacheSeconds=3600)](native-libs/)
[![Activities](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FLibChecker%2FLibChecker-Rules%2FHEAD%2Frule-counts.json&query=%24.activities&label=Activities&color=1a7f37&style=flat&cacheSeconds=3600)](activities-libs/)
[![Services](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FLibChecker%2FLibChecker-Rules%2FHEAD%2Frule-counts.json&query=%24.services&label=Services&color=bf8700&style=flat&cacheSeconds=3600)](services-libs/)
[![Receivers](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FLibChecker%2FLibChecker-Rules%2FHEAD%2Frule-counts.json&query=%24.receivers&label=Receivers&color=cf222e&style=flat&cacheSeconds=3600)](receivers-libs/)
[![Providers](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FLibChecker%2FLibChecker-Rules%2FHEAD%2Frule-counts.json&query=%24.providers&label=Providers&color=8250df&style=flat&cacheSeconds=3600)](providers-libs/)
[![Intent actions](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FLibChecker%2FLibChecker-Rules%2FHEAD%2Frule-counts.json&query=%24.intentActions&label=Intent%20actions&color=1b7c83&style=flat&cacheSeconds=3600)](actions-libs/)
[![Static libraries](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FLibChecker%2FLibChecker-Rules%2FHEAD%2Frule-counts.json&query=%24.staticLibraries&label=Static%20libraries&color=57606a&style=flat&cacheSeconds=3600)](static-libs/)
[![Chart rules](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FLibChecker%2FLibChecker-Rules%2FHEAD%2Frule-counts.json&query=%24.chartRules&label=Chart%20rules&color=bf3989&style=flat&cacheSeconds=3600)](chart/rules/)

English | [简体中文](README.zh-Hans.md)

This repository maintains the rules and metadata used by [LibChecker](https://github.com/LibChecker/LibChecker). It covers Android component and native library identification, Flutter engine version mappings, and declarative statistics for the chart page.

## Repository contents

| Path | Contents |
| --- | --- |
| `native-libs/`, `activities-libs/`, `services-libs/`, `receivers-libs/`, `providers-libs/`, `actions-libs/`, `static-libs/` | Identify libraries and SDKs from native libraries, Android components, and intent actions. |
| [`flutter_hash/`](flutter_hash/README.md) | Maps engine revisions found in `libflutter.so` to possible Flutter releases. |
| [`chart/`](chart/README.md) | Contains chart rules, SVG icons, JSON Schemas, tests, and generated bundles. |
| `configuration/`, `cloud/` | Contains versioned configuration and rule data consumed by LibChecker. |

## Contributing

### Library identification rules

If a library identification rule is missing or incorrect, open the [issue chooser](https://github.com/LibChecker/LibChecker-Rules/issues/new/choose) and select **Submit new rule** or **Bug report**. Follow the template and provide the filename, library name, development team, description, and a primary source. Include the app name and version when a sample is available for verification. Icons must use the SVG format.

### Chart rules

Chart rules have their own schema, tests, and release process. New rules normally start in the preview channel and move to the stable channel after verification. Read the complete contribution guide before submitting a rule:

- [English contribution guide](chart/README.md)
- [简体中文贡献指南](chart/README.zh-Hans.md)

If your AI agent supports Skills, install the chart rule Skill from this repository:

```shell
npx skills add LibChecker/LibChecker-Rules
```

See the [chart rule Skill guide](skills/libchecker-chart-rules/README.md) for installation and usage details.

## License

This repository is licensed under the [Apache License 2.0](LICENSE).

## Canonical base rules (v5)

Edit `libraries/<UUID>.json` and `icons/`; legacy per-name JSON and DB are compatibility
outputs. The [v5 contract](docs/rules-v5-contract.md) documents editor fields,
matching, SVG validation, manifests, migration audit and staged rollout.

```sh
python3 tools/rules.py check
python3 -m unittest discover -s tests -v
python3 tools/rules.py build --output /tmp/libchecker-rules
```

Python compilation uses only the standard library; cross-language tests also need
Node.js and a JDK. `import-icon` validates an SVG and automatically appends its icon
index. Generated artifacts share one source revision and dataVersion; normal source
changes publish through the serialized own-repository workflow after merge to v4.
SDK details and chart pipelines remain independent.
