# SDK details

This directory contains remotely configurable SDK detection definitions and
generated enrichment data consumed by LibChecker's library details dialog.

`catalog.json` is generated from each `sdks/*/definition.json`. Definitions
associate stable library UUIDs with bounded detection probes, optional remote
lookups, and presentation fields. Existing rule detail JSON files remain
independent from SDK details configuration.

Definitions are data, not executable code. The client accepts only the
versioned operators and hard limits represented by `schemas/definition-v1.schema.json`;
unknown operators, unsafe paths, oversized input, and unsupported schema
versions are rejected without affecting the normal library detail UI. Remote
documents are fetched lazily and are not bundled into the app or persisted as
an offline version map.

Providers are optional. An SDK that embeds its version directly in an APK only
needs a definition. SDKs that require an external version index may expose a
`provider.py` with `SDK_ID`, `update()`, and `validate()` for the generic runner.

Run validation and updates from the repository root:

```shell
python sdk-details/tools/test.py
python sdk-details/tools/validate.py --write
python sdk-details/tools/update.py --check
python sdk-details/tools/update.py --all
```
