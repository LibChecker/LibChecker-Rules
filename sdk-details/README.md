# SDK details

This directory contains remotely configurable SDK detection definitions and
generated enrichment data consumed by LibChecker's library details dialog.

`catalog.json` is generated from each `sdks/*/definition.json`. Definitions
associate stable library UUIDs with bounded detection probes, optional remote
lookups, and presentation fields. Existing rule detail JSON files remain
independent from SDK details configuration.

Definitions are data, not executable code. The client accepts only the
versioned operators and hard limits represented by the schemas under
`schemas/`. Version 1 supports the Flutter binary probe. Version 2 adds bounded
plain semantic-version capture, literal-prefixed semantic-version capture, and
whole-entry SHA-256 capture for AndroidX metadata. Unknown operators, unsafe
paths, oversized input, and unsupported schema versions are rejected without
affecting the normal library detail UI. Remote documents are fetched lazily and
are not bundled into the app or persisted as an offline version map.
Client support for a new definition schema, reader, or capture type must ship
before remote definitions start using it.

AndroidX definitions are generated from the reviewed artifact-to-rule mapping
in `tools/generate_androidx_definitions.py`. Most definitions read the official
`META-INF/<group>_<artifact>.version` entry packaged by AndroidX. Media3 reads
its literal-prefixed version string from bounded DEX entries. AndroidX Test,
which does not publish the standard version entry, uses a provider-maintained
Kotlin module fingerprint lookup.

Providers are optional. An SDK that embeds its version directly in an APK only
needs a definition. SDKs that require an external version index may expose a
`provider.py` with `SDK_ID`, `update()`, and `validate()` for the generic runner.

Run validation and updates from the repository root:

```shell
python sdk-details/tools/test.py
python sdk-details/tools/validate.py --write
python sdk-details/tools/generate_androidx_definitions.py --check
python sdk-details/tools/update.py --check
python sdk-details/tools/update.py --all
```

## Stable fingerprint indexes (staged migration)

`python sdk-details/tools/build_indexes.py` generates fixed public `data/index.json`
files and candidate definitions under `candidates/`. Run with `--check` to detect
stale output. Fixed-index definitions use `index_path` plus `entries_field: "entries"`;
clients match captured values locally against `expected_field`, then project
`items_field` releases. Never interpolate local fingerprints into request URLs or logs.

Flutter's active `sdks/flutter/definition.json` uses schema 2 and the fixed index,
so compatible clients resolve it directly without fetching a candidate definition.
Keep its candidate copy available for clients holding a cached legacy definition.
Per-engine files remain provider inputs for rebuilding the index.
AndroidX Test remains staged until its compatible reader has shipped. The base
rules publisher does not activate SDK candidates. Publish SDK definition changes
on the descriptions branch and synchronize its mirrors; rebuilding the rule database
alone does not publish them.

## Binary header probes (definition v3)

An `archive_entry` identifies exact APK paths and may specify one inner archive
member with `container: {"format": "unityfs", "entry": "..."}`. The
`binary_header` reader tries up to eight layouts. Each layout gives a prefix
offset for an `ascii_z` capture and up to 24 integer comparisons. Integers can
be constants, the entry's logical `size`, `end` (the byte immediately after the
NUL), or unsigned `u8`, `u32le`, `u32be`, or `u64be` loads at a prefix
offset or `end`. One addition per operand is supported. Every check must pass.
The capture's optional `formats` match the entire string. `#` is a nonempty
run of decimal digits, `[abc]` matches one of the listed letters, and ASCII
letters, digits, dots, underscores, and hyphens are literals. Omitting formats
or giving an empty list accepts printable ASCII. Keep per-file and per-probe
byte budgets as small as the source permits.

A definition can declare `native_library_names` for exact native library
basename matching. The catalog generator copies the one to sixteen distinct
names from the definition into its catalog entry. Each basename must belong
to a single SDK across the catalog. A match selects the
definition to probe; its binary checks determine the displayed value. The Unity
candidate matches only by library UUID.

A presentation field with `require_unique: true` appears only for a single
distinct result. Each capture contributing to that output needs a
`max_results` of at least two. Lookup outputs cannot use this constraint.

The Unity candidate uses this protocol to read Player SerializedFiles, including
the first segment and an exact member inside a UnityFS archive. Its Android
platform ID, supported format ranges, version masks, and header layout are all
declared in the definition. Once the compatible client ships, move the candidate
to `sdks/unity/definition.json`, regenerate the catalog with
`tools/validate.py --write`, and publish both to the descriptions branch.
