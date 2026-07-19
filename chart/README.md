# Chart rules

This directory contains the declarative statistics shown on LibChecker's chart
page. Contributors provide data and conditions; the APK owns all APK, DEX,
manifest, and native-file traversal. Rules cannot execute scripts or arbitrary
code.

## Repository layout

- `schema/v1/`: JSON schemas for source rules and generated manifests.
- `rules/`: one reviewed statistic definition per JSON file.
- `icons/`: SVG assets referenced by online rules.
- `tools/build_bundle.py`: validator and deterministic bundle generator.
- `cloud/v1/`: generated files consumed by LibChecker.

The rule filename should match the final segment of its stable ID. IDs use the
`official.` prefix and must never be reused for a different statistic. Increase
`revision` whenever a published rule's detection or presentation changes.

## Rule envelope

Every source rule contains:

- `id`, `revision`, and `source: official`.
- `title.translations` with at least `en` and `zh-Hans`.
- `details.description.translations` with at least `en` and `zh-Hans`, plus
  one HTTPS `details.referenceUrl` for the in-app introduction dialog.
- `icon.asset`, plus an optional render mode and tint role.
- `calculation`, using one of the calculation types below.
- optional chart metadata such as `fingerprint`.
- optional `releaseChannel`, which defaults to `stable`.

Do not use `zh` or `zh-CN`. Simplified Chinese translations must use
`zh-Hans`. English is the runtime fallback locale.

`releaseChannel` controls publication without changing APK behavior:

- `stable` rules are included in preview and stable bundles.
- `preview-only` rules are included only in preview bundles.

The builder removes this source-only field from the generated catalog. Mark
experimental rules `preview-only`; never rely on manually deleting them before
a stable release.

## Calculation types

### Predicate

Use `kind: predicate` for one binary question. A predicate supplies localized
`matchedTitle` and `unmatchedTitle`, then either one complete evidence/operator/
value tuple or one recursive `condition`.

### Facets

Use `kind: facets` when an app may match several named capabilities at once.
The facets object supplies localized matched/unmatched titles and an ordered
`items` array. Each item contains:

- a rule-local, stable, unique `id`;
- a localized `title` used as the app-row chip;
- exactly one `condition`.

An app enters the matched group when at least one facet matches. Every matching
facet is displayed in rule order. Do not duplicate the facet conditions in a
separate root `any`: that creates two sources of truth. A rule may define at
most eight facets, and facet titles may contain at most 40 characters.

Facets describe overlapping capabilities. Do not use them for mutually
exclusive buckets or numeric distributions; those require dedicated
calculation types.

## Conditions and evidence

Conditions are restricted to `all`, `any`, `not`, or one typed evidence leaf.
The validator limits condition depth, node count, child count, query count, and
string length.

Schema v1 currently supports:

- numeric comparison of `target_sdk`;
- exact library-name membership through `native_library`;
- `dex_class` queries using an exact or prefix class name, string constants,
  and method references;
- `manifest_receiver_action` membership.

Name, string, and method constraints inside one DEX class query must be
satisfied by the same class. Use separate queries when constraints may be found
in different classes. Use `any` when either DEX or manifest evidence is an
accepted detection path.

Rules can compose only evidence implemented by the current APK. A genuinely
new source such as a DEX field definition, DEX field reference, resource-table
entry, or native symbol requires one generic APK evidence provider first. Do
not work around this boundary with executable code, reflection, file paths, or
network URLs.

## Icons

Online icons live under `icons/` and are referenced by a repository-relative
asset path; rules must not contain an external icon URL. Built-in statistics
continue to use APK drawable resources.

SVG files must:

- use a `0 0 1024 1024` viewBox;
- place the intended artwork in an approximately `800 x 800` center boundary;
- remain below 64 KiB;
- avoid scripts, styles, text, linked images, entities, external references,
  and `url(...)` content.

Use `renderMode: original` only when brand colors are meaningful. Otherwise use
`monochrome` and let LibChecker apply its theme tint.

## Details and references

Every online rule provides a short, neutral introduction in
`details.description`. Describe the technology or capability itself; do not
claim that the current app matches because LibChecker appends the actual
analysis result at runtime. Faceted rules automatically list the matched facet
titles below the introduction.

`details.referenceUrl` must use HTTPS and should point to the primary project,
standards body, or platform documentation. Do not use tracking links, URL
shorteners, affiliate links, or unreviewed third-party summaries.

## Validation and bundle generation

Run from the repository root:

```shell
python3 -m unittest chart.tools.test_build_bundle
python3 chart/tools/build_bundle.py --bundle-version 10 --channel stable --minimum-app-version-code 2731
```

Set `minimum-app-version-code` to the exact first compatible APK version before
publishing. Use `0` only when every supported published APK already implements
the rule's calculation and evidence types. Bundle versions must increase
independently on each published branch.

The preview build includes stable and preview-only rules. A stable build uses
`--channel stable`; its tests must prove that preview-only rules are absent.
Generated `chart.bundle` output is deterministic, checksummed, size-limited,
and committed together with `manifest.json`.

## Contribution checklist

1. Add or update one source JSON, its localized details and primary reference,
   and its SVG asset.
2. Use only supported evidence and the narrowest condition that avoids false
   positives.
3. Add `en` and `zh-Hans` for every title and facet.
4. Add focused builder tests for detection data, ordering, channels, and icon
   rendering mode.
5. Run the unit tests and generate the preview bundle with a higher version.
6. Test the rule from the preview branch in a compatible LibChecker APK.
7. Only after the preview result is verified, generate the stable bundle and
   confirm that every `preview-only` rule is excluded.

If a bad bundle is published, restore the last known-good generated bundle and
manifest with a higher bundle version. Compatible APKs retain their cached
bundle when a download, checksum, schema, or minimum-version check fails.
