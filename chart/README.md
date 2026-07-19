# Chart rule contribution guide

English | [简体中文](README.zh-Hans.md)

This directory contains the declarative statistics shown on LibChecker's chart
page. A rule describes the data that LibChecker should inspect, the condition
that produces a match, and the labels and icon shown to the user.

Rules cannot execute scripts or arbitrary code. LibChecker owns all APK, DEX,
manifest, and native-file traversal. A rule can only use evidence and operators
that the installed app already implements.

## Before you start

Answer these questions before writing JSON:

1. What does the chart measure, and why is it useful to LibChecker users?
2. Which installed-app evidence proves a match?
3. Can an app produce one yes/no result, or can it match several capabilities?
4. Is there a primary HTTPS source that explains the technology or capability?
5. Can you test the rule against both matching and non-matching APKs?

Schema v1 supports only the evidence listed in [Evidence reference](#evidence-reference).
If your rule needs another source, such as a DEX field, resource-table entry,
native symbol, certificate property, or arbitrary file content, propose a
generic evidence provider in the LibChecker app first. Do not encode a
workaround in the rule.

New rules should normally start with `"releaseChannel": "preview-only"`. Move
them to `stable` only after the preview bundle has been tested with a compatible
LibChecker build.

## Contribution workflow

1. Fork the repository and create a topic branch.
2. Choose the closest example in `rules/`:
   - [`flutter.json`](rules/flutter.json) for exact native-library detection.
   - [`reactivex.json`](rules/reactivex.json) for exact APK entries with a DEX
     fallback.
   - [`itgsa.json`](rules/itgsa.json) for facets, recursive conditions, DEX
     queries, and manifest receiver actions.
   - The [predicate example](#predicate-calculations) below for a numeric
     comparison.
3. Add one UTF-8 JSON file under `rules/`. Use four-space indentation and name
   the file after the final segment of the rule ID.
4. Add the referenced SVG under `icons/`.
5. Update the tests that enumerate rule IDs, icons, catalog size, and stable
   channel contents. Add focused assertions for the new detection data.
6. Run the unit tests and build a preview bundle in a temporary directory.
7. Test the preview rule with known matching and non-matching apps.
8. Regenerate `cloud/v1/chart.bundle` and `cloud/v1/manifest.json` with the
   bundle version and minimum app version agreed for the target branch.
9. Submit the source rule, icon, tests, generated bundle, and manifest in one
   pull request. Include your evidence source and manual test results in the PR
   description.

Run commands from the repository root:

```shell
python3 -m unittest chart.tools.test_build_bundle
python3 chart/tools/build_bundle.py \
  --bundle-version 12 \
  --channel preview \
  --minimum-app-version-code 2731 \
  --output-dir /tmp/libchecker-chart-preview
```

The numbers above are examples. Read `chart/cloud/v1/manifest.json` and the
target branch before choosing a bundle version or minimum app version.

## Repository layout

| Path | Purpose |
| --- | --- |
| `rules/` | Reviewed source definitions, one JSON file per statistic. |
| `icons/` | SVG assets referenced by source rules. |
| `schema/v1/chart-rule.schema.json` | Machine-readable schema for source rules. |
| `schema/v1/manifest.schema.json` | Machine-readable schema for the generated manifest. |
| `tools/build_bundle.py` | Validator and deterministic bundle generator. |
| `tools/test_build_bundle.py` | Source validation and bundle regression tests. |
| `cloud/v1/chart.bundle` | Generated catalog and icons consumed by LibChecker. |
| `cloud/v1/manifest.json` | Generated version, compatibility, size, and checksum metadata. |

## Minimal rule

This is a complete single-predicate rule:

```json
{
    "id": "official.example-sdk",
    "revision": 1,
    "source": "official",
    "releaseChannel": "preview-only",
    "title": {
        "translations": {
            "en": "Example SDK",
            "zh-Hans": "示例 SDK"
        }
    },
    "details": {
        "description": {
            "translations": {
                "en": "Example SDK provides a documented capability for Android apps.",
                "zh-Hans": "示例 SDK 为 Android 应用提供一项有公开文档的能力。"
            }
        },
        "referenceUrl": "https://example.com/android-sdk"
    },
    "icon": {
        "asset": "icons/example-sdk.svg",
        "renderMode": "monochrome",
        "tintRole": "on_surface"
    },
    "calculation": {
        "kind": "predicate",
        "predicate": {
            "evidence": "native_library",
            "operator": "contains",
            "value": {
                "string": "libexample.so"
            },
            "matchedTitle": {
                "translations": {
                    "en": "Example SDK apps",
                    "zh-Hans": "示例 SDK 应用"
                }
            },
            "unmatchedTitle": {
                "translations": {
                    "en": "Other apps",
                    "zh-Hans": "其他应用"
                }
            }
        }
    },
    "fingerprint": "artifact"
}
```

## Top-level fields

The source schema does not allow unknown fields. The following fields are
available to official online rules.

| Field | Required | Type or allowed values | Meaning |
| --- | --- | --- | --- |
| `id` | Yes | String matching `official.<name>` | Permanent identity of the statistic. |
| `revision` | Yes | Integer, minimum `1` | Version of this rule definition. |
| `source` | Yes | `official` | Online rules in this repository are official rules. |
| `title` | Yes | Translated text | Chart title shown by LibChecker. |
| `details` | Yes | Object | In-app description and primary reference URL. |
| `icon` | Yes | Object | Bundled SVG and its rendering behavior. |
| `calculation` | Yes | `predicate` or `facets` | How apps are classified. |
| `releaseChannel` | No | `stable` or `preview-only` | Controls which generated bundle includes the rule. Defaults to `stable`. |
| `availability` | No | `always` | Availability gate. Schema v1 online rules only support `always`. |
| `requiresFeatureInitialization` | No | Boolean | Hides the chart until feature initialization finishes. Defaults to `false`. |
| `controls` | No | Empty array only | Online controls are not supported in schema v1. |
| `dashboard` | No | `none` | Online dashboard integrations are not supported in schema v1. |
| `fingerprint` | No | `standard`, `features`, or `artifact` | Selects the app-data fingerprint used to invalidate cached chart results. |

JSON Schema `default` values document client defaults. The bundle builder does
not insert missing optional fields into the generated catalog.

### `id`

The ID must match:

```text
^official\.[a-z0-9]+(?:[.-][a-z0-9]+)*$
```

Examples:

- Valid: `official.flutter`, `official.android-api-level`,
  `official.vendor.capability`.
- Invalid: `flutter`, `official.Flutter`, `official_target_sdk`.

Use a specific, technology-neutral ID. Once a rule has been published, never
reuse its ID for a different statistic. The source filename should match the
last ID segment, such as `official.flutter` in `flutter.json`.

### `revision`

Start a new rule at revision `1`. Increase the revision whenever a published
rule changes its matching logic, titles, description, icon, calculation type,
or other presentation metadata. A change to repository documentation alone
does not require a rule revision.

The revision belongs to one rule. It is independent of the generated bundle's
`bundleVersion`.

### `source`

Every rule submitted to this repository must use:

```json
"source": "official"
```

The builder rejects other values.

## Translated text

`title`, `details.description`, predicate group titles, and facet titles use
the same wrapper:

```json
{
    "translations": {
        "en": "English text",
        "zh-Hans": "简体中文文本"
    }
}
```

### Translated-text parameters

| Parameter | Type | Required | Allowed values and limits | Meaning |
| --- | --- | --- | --- | --- |
| `translations` | Object | Yes | 2 to 16 locale entries; must include `en` and `zh-Hans` | Maps locale tags to the text shown by LibChecker. |
| `translations.<locale>` | String | Yes for each declared locale | Non-empty; 80 characters for chart and group titles, 40 for facet titles, 1,500 for descriptions | Localized value for one BCP 47-style locale tag. |

| Locale key | Allowed | Meaning |
| --- | --- | --- |
| `en` | Required | English text and runtime fallback. |
| `zh-Hans` | Required | Simplified Chinese text. |
| `zh`, `zh-CN` | Rejected | These tags are intentionally not accepted; use `zh-Hans`. |
| Other schema-compatible tags | Optional | Additional translations, for example `pt-BR` or `es-419`, up to 16 locales total. |

Rules for translations:

- `en` and `zh-Hans` are required. English is the runtime fallback.
- Use `zh-Hans` for Simplified Chinese. `zh` and `zh-CN` are rejected.
- A translated object must contain 2 to 16 locales.
- Locale keys use BCP 47-style tags accepted by the schema, such as `en`,
  `zh-Hans`, `pt-BR`, or `es-419`.
- Each translation must be a non-empty string.
- `title`, `matchedTitle`, and `unmatchedTitle` allow up to 80 characters.
- A facet `title` allows up to 40 characters because it is displayed as a chip.
- `details.description` allows up to 1,500 characters.
- Keep equivalent meaning across locales. Do not add claims to one language
  that are absent from another.

Use short labels for chart and group titles. The matched and unmatched titles
name the two result groups, for example `Flutter apps` and `Other apps`.

## Details and reference URL

`details` is required:

```json
"details": {
    "description": {
        "translations": {
            "en": "A neutral introduction to the technology.",
            "zh-Hans": "对该技术的中性介绍。"
        }
    },
    "referenceUrl": "https://project.example/documentation"
}
```

### Details parameters

| Parameter | Type | Required | Allowed values and limits | Meaning |
| --- | --- | --- | --- | --- |
| `details.description` | Translated text | Yes | `en` and `zh-Hans`; 1 to 1,500 characters per locale | Neutral in-app introduction to the technology or capability. |
| `details.referenceUrl` | String | Yes | HTTPS URL, valid host, no credentials or whitespace, maximum 512 characters | Primary source opened from the introduction dialog. |

Write a short, neutral description of the technology or capability. Do not say
that the currently selected app matches the rule. LibChecker appends the actual
analysis result at runtime. Faceted rules also list the matched facet titles.

`referenceUrl` must:

- use HTTPS;
- contain a valid host;
- contain no username, password, or whitespace;
- be no longer than 512 characters;
- point to a primary project, standards body, vendor, or platform document.

Do not use tracking links, URL shorteners, affiliate links, search results, or
an unreviewed third-party summary.

## Icons

Every online rule references one repository asset:

```json
"icon": {
    "asset": "icons/example-sdk.svg",
    "renderMode": "monochrome",
    "tintRole": "on_surface"
}
```

### Icon fields

| Field | Required | Allowed values | Meaning |
| --- | --- | --- | --- |
| `asset` | Yes | `icons/<safe-name>.svg` | Repository-relative path included in the bundle. |
| `renderMode` | No | `monochrome`, `original` | Whether LibChecker applies a theme tint. Defaults to `monochrome`. |
| `tintRole` | No | `on_surface`, `on_surface_variant`, `primary`, `secondary`, `tertiary` | Theme color used for a monochrome icon. Defaults to `on_surface`. |

Use `original` only when the original brand colors carry meaning. LibChecker
does not apply `tintRole` to an `original` icon. Use `monochrome` for a shape
that should adapt to the active theme.

### SVG requirements

An SVG must:

- use a `0 0 1024 1024` viewBox;
- keep the artwork approximately within a centered `800 x 800` area so that
  icons have consistent optical size;
- remain below 64 KiB;
- be valid UTF-8;
- contain no scripts, styles, text nodes, linked images, entities, external
  references, or `url(...)` content.

The validator rejects `<!doctype`, `<!entity`, `<?xml-stylesheet`, `<script`,
`<foreignObject`, `<image`, `<style`, `<text`, `href=`, `xlink:`, and `url(`.
Convert text to paths and inline any required fill colors.

## Choosing a calculation type

Use `predicate` when every app belongs to one of two groups. Use `facets` when
one app can match several named capabilities and the UI should show each match
as a chip.

| Question | Use |
| --- | --- |
| Does the app target SDK 35 or newer? | `predicate` |
| Does the app contain `libflutter.so`? | `predicate` |
| Which ITGSA capabilities does the app implement? | `facets` |

### Calculation parameters

| Parameter | Type | Required | Possible values | Meaning |
| --- | --- | --- | --- | --- |
| `calculation.kind` | String | Yes | `predicate`, `facets` | Selects the calculation object that must accompany it. |
| `calculation.predicate` | Object | Required when `kind` is `predicate` | See [Predicate calculations](#predicate-calculations) | Produces matched and unmatched groups from one condition. |
| `calculation.facets` | Object | Required when `kind` is `facets` | See [Facet calculations](#facet-calculations) | Produces matched and unmatched groups plus per-app capability chips. |

Only the object selected by `kind` is allowed. Online rules cannot use the
client's built-in `native` calculation type.

Facets are for overlapping capabilities. Do not use them for mutually
exclusive buckets or numeric distributions. Schema v1 has no online
calculation type for those cases.

## Predicate calculations

A predicate requires `matchedTitle`, `unmatchedTitle`, and exactly one complete
condition. For a single evidence leaf, put `evidence`, `operator`, and `value`
directly in `predicate`:

| Parameter | Type | Required | Possible values and limits | Meaning |
| --- | --- | --- | --- | --- |
| `predicate.matchedTitle` | Translated text | Yes | 1 to 80 characters per locale | Label for apps whose condition evaluates to true. |
| `predicate.unmatchedTitle` | Translated text | Yes | 1 to 80 characters per locale | Label for apps whose condition evaluates to false. |
| `predicate.evidence` | String | Required for direct-leaf form | `target_sdk`, `native_library`, `archive_entry`, `dex_class`, `manifest_receiver_action`, `manifest_attribute` | Evidence provider used by the leaf. |
| `predicate.operator` | String | Required for direct-leaf form | Depends on `evidence` | Comparison applied to the evidence. |
| `predicate.value` | Object | Required for direct-leaf form | Exactly one value variant compatible with `evidence` | Expected value for the comparison. |
| `predicate.condition` | Condition | Required for recursive form | One leaf, `all`, `any`, or `not` | Recursive condition used instead of the three direct-leaf fields. |

```json
"calculation": {
    "kind": "predicate",
    "predicate": {
        "evidence": "target_sdk",
        "operator": "greater_than_or_equal",
        "value": {
            "integer": 35
        },
        "matchedTitle": {
            "translations": {
                "en": "Target SDK 35 or newer",
                "zh-Hans": "Target SDK 35 及以上"
            }
        },
        "unmatchedTitle": {
            "translations": {
                "en": "Target SDK 34 or older",
                "zh-Hans": "Target SDK 34 及以下"
            }
        }
    }
}
```

For logical composition, replace the direct leaf fields with one `condition`:

```json
"predicate": {
    "condition": {
        "any": [
            {
                "evidence": "native_library",
                "operator": "contains",
                "value": {
                    "string": "libexample.so"
                }
            },
            {
                "evidence": "manifest_receiver_action",
                "operator": "contains_any",
                "value": {
                    "strings": [
                        "com.example.ACTION_READY"
                    ]
                }
            }
        ]
    },
    "matchedTitle": {
        "translations": {
            "en": "Example apps",
            "zh-Hans": "示例应用"
        }
    },
    "unmatchedTitle": {
        "translations": {
            "en": "Other apps",
            "zh-Hans": "其他应用"
        }
    }
}
```

Do not provide both the direct fields and `condition`. Partial direct tuples
are also rejected.

## Facet calculations

A facet calculation contains 1 to 8 ordered items:

| Parameter | Type | Required | Possible values and limits | Meaning |
| --- | --- | --- | --- | --- |
| `facets.matchedTitle` | Translated text | Yes | 1 to 80 characters per locale | Chart label for apps matching at least one facet. |
| `facets.unmatchedTitle` | Translated text | Yes | 1 to 80 characters per locale | Chart label for apps matching no facets. |
| `facets.items` | Array | Yes | 1 to 8 facet objects | Ordered capability definitions. |
| `items[].id` | String | Yes | Lowercase rule-local ID matching the documented pattern; unique within the rule | Stable internal identity of a facet. |
| `items[].title` | Translated text | Yes | 1 to 40 characters per locale | Chip shown for a matching app. |
| `items[].condition` | Condition | Yes | One leaf, `all`, `any`, or `not` | Determines whether this facet matches an app. |

```json
"calculation": {
    "kind": "facets",
    "facets": {
        "matchedTitle": {
            "translations": {
                "en": "Example capability apps",
                "zh-Hans": "示例能力应用"
            }
        },
        "unmatchedTitle": {
            "translations": {
                "en": "Other apps",
                "zh-Hans": "其他应用"
            }
        },
        "items": [
            {
                "id": "service-kit",
                "title": {
                    "translations": {
                        "en": "Service Kit",
                        "zh-Hans": "服务套件"
                    }
                },
                "condition": {
                    "evidence": "native_library",
                    "operator": "contains",
                    "value": {
                        "string": "libexample_service.so"
                    }
                }
            }
        ]
    }
}
```

Each item requires:

- a rule-local `id` matching
  `^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$`;
- a unique, stable ID within the rule;
- a translated `title` of at most 40 characters per locale;
- exactly one `condition`.

An app enters the matched chart group when at least one facet matches. All
matching facet titles are shown as chips in the order declared by `items`.
Do not duplicate facet conditions in a separate root `any` expression.

## Conditions

A condition is either one typed evidence leaf or one logical operator.
Additional properties are rejected.

### Condition object parameters

| Parameter | Type | Required | Possible values and limits | Meaning |
| --- | --- | --- | --- | --- |
| `evidence` | String | Required for a leaf | `target_sdk`, `native_library`, `archive_entry`, `dex_class`, `manifest_receiver_action`, `manifest_attribute` | Selects the app data to inspect. |
| `operator` | String | Required for a leaf | `equal`, `greater_than_or_equal`, `less_than_or_equal`, `contains`, `contains_any`; compatibility depends on `evidence` | Selects the comparison. |
| `value` | Object | Required for a leaf | Exactly one of `integer`, `string`, `strings`, `dexClasses`, `manifestAttribute` | Supplies the expected value. |
| `all` | Array of conditions | Required for an `all` node | 1 to 16 children | True when every child is true. |
| `any` | Array of conditions | Required for an `any` node | 1 to 16 children | True when at least one child is true. |
| `not` | Condition | Required for a `not` node | One child object | Inverts the child result. |

Exactly one operation is allowed. A leaf must contain all of `evidence`,
`operator`, and `value`; a logical node must contain only `all`, `any`, or
`not`.

### Value object parameters

| Parameter | Type | Used by | Allowed values and limits | Meaning |
| --- | --- | --- | --- | --- |
| `integer` | Integer | `target_sdk` | Any JSON integer | Numeric comparison target. |
| `string` | String | `native_library` | 1 to 160 safe filename characters | Exact native-library filename. |
| `strings` | Array of strings | `archive_entry`, `manifest_receiver_action` | 1 to 16 values, each 1 to 160 safe characters for its evidence type | Exact archive entries or receiver actions; any listed value may match. |
| `dexClasses` | Array of DEX class queries | `dex_class` | 1 to 16 queries | Class queries; any query may match. |
| `manifestAttribute` | Manifest attribute query | `manifest_attribute` | One `application` element, one safe `android:` attribute name, and one Boolean | Exact application-manifest Boolean attribute and expected value. |

One value object must contain exactly one of these parameters.

### Evidence leaf

```json
{
    "evidence": "native_library",
    "operator": "contains",
    "value": {
        "string": "libflutter.so"
    }
}
```

All three fields are required and must use a compatible combination from the
evidence table below.

### Logical operators

| Operator | Value | Result |
| --- | --- | --- |
| `all` | Array of 1 to 16 conditions | Matches when every child matches. |
| `any` | Array of 1 to 16 conditions | Matches when at least one child matches. |
| `not` | One condition object | Inverts the child result. |

Example:

```json
{
    "all": [
        {
            "evidence": "target_sdk",
            "operator": "greater_than_or_equal",
            "value": {
                "integer": 35
            }
        },
        {
            "not": {
                "evidence": "native_library",
                "operator": "contains",
                "value": {
                    "string": "liblegacy.so"
                }
            }
        }
    ]
}
```

### Condition limits

- Maximum nesting depth: 8, with the root condition at depth 1.
- Maximum condition nodes: 64 per predicate calculation. A facet rule shares
  the same 64-node budget across all facet conditions.
- Maximum children in one `all` or `any`: 16.
- A condition object must define exactly one operation. It cannot mix a leaf
  with `all`, `any`, or `not`.

Prefer the narrowest condition that is supported by reliable evidence. A long
condition is not necessarily a more accurate condition.

## Evidence reference

| Evidence | Operator | Value object | Match behavior |
| --- | --- | --- | --- |
| `target_sdk` | `equal`, `greater_than_or_equal`, `less_than_or_equal` | `{ "integer": <integer> }` | Compares the app's target SDK value. |
| `native_library` | `contains` | `{ "string": "<library-name>" }` | Matches an exact native-library filename. |
| `archive_entry` | `contains_any` | `{ "strings": ["<entry-name>", ...] }` | Matches when any exact entry exists in the base or split APKs. |
| `dex_class` | `contains_any` | `{ "dexClasses": [<query>, ...] }` | Matches when any query matches one DEX class. |
| `manifest_receiver_action` | `contains_any` | `{ "strings": ["<action>", ...] }` | Matches when any listed action is declared by a manifest receiver. |
| `manifest_attribute` | `equal` | `{ "manifestAttribute": { "element": "application", "name": "android:<name>", "boolean": <Boolean> } }` | Matches an explicitly declared application-manifest Boolean attribute. |

### `target_sdk`

The integer is compared with the target API recorded for the installed app.
The schema does not impose an API-level range, but the value should represent a
real Android API level.

```json
{
    "evidence": "target_sdk",
    "operator": "less_than_or_equal",
    "value": {
        "integer": 34
    }
}
```

Use `fingerprint: standard` or omit `fingerprint` for a rule that only depends
on target SDK metadata.

### `native_library`

The value is an exact `.so` filename, not a path and not a regular expression.
LibChecker checks extracted libraries and libraries packaged in the APK.

```json
{
    "evidence": "native_library",
    "operator": "contains",
    "value": {
        "string": "libflutter.so"
    }
}
```

The string must be 1 to 160 characters and may contain ASCII letters, digits,
periods, underscores, plus signs, and hyphens. Use `fingerprint: artifact`.

### `archive_entry`

This evidence checks exact ZIP entry names across the base and split APKs. It
does not read file contents and does not support prefixes, globs, or regular
expressions.

```json
{
    "evidence": "archive_entry",
    "operator": "contains_any",
    "value": {
        "strings": [
            "META-INF/example.properties"
        ]
    }
}
```

The list must contain 1 to 16 entry names. Each name must be 1 to 160
characters, use only ASCII letters, digits, periods, underscores, plus signs,
hyphens, and slashes, and must not end in a slash or contain `.` or `..` path
segments. Use `fingerprint: artifact`.

### `manifest_receiver_action`

This evidence reads actions from manifest-declared broadcast receivers across
the base and split APKs. It matches when at least one supplied action is found.

```json
{
    "evidence": "manifest_receiver_action",
    "operator": "contains_any",
    "value": {
        "strings": [
            "com.example.ACTION_TRIM",
            "com.example.ACTION_KILL"
        ]
    }
}
```

The list must contain 1 to 16 strings. Each action must be 1 to 160 characters
and may contain ASCII letters, digits, underscores, periods, and hyphens. Use
`fingerprint: artifact`.

### `manifest_attribute`

This evidence reads an explicitly declared Boolean attribute from the APK's
`application` manifest element. A missing attribute does not match, even when
the Android platform supplies the same value as a runtime default.

```json
{
    "evidence": "manifest_attribute",
    "operator": "equal",
    "value": {
        "manifestAttribute": {
            "element": "application",
            "name": "android:enableOnBackInvokedCallback",
            "boolean": true
        }
    }
}
```

The attribute name must use the `android:` namespace followed by an ASCII
letter and up to 79 ASCII letters, digits, or underscores. Schema v1 supports
only the `application` element and Boolean values. Resource-backed Boolean
attributes are compared after resource resolution. Use `fingerprint: artifact`.

### `dex_class`

`dex_class` accepts 1 to 16 class queries. The outer `dexClasses` list is OR:
the evidence matches when any query matches any class in the app's base or
split APKs.

```json
{
    "evidence": "dex_class",
    "operator": "contains_any",
    "value": {
        "dexClasses": [
            {
                "name": {
                    "operator": "starts_with",
                    "value": "Lcom/example/sdk/"
                },
                "stringConstants": [
                    "com.example.ACTION_READY"
                ],
                "methodReferences": [
                    {
                        "definingClass": "Landroid/content/IntentFilter;",
                        "name": "addAction",
                        "parameterTypes": [
                            "Ljava/lang/String;"
                        ]
                    }
                ]
            }
        ]
    }
}
```

Each query may contain `name`, `stringConstants`, `methodReferences`, or a
combination of them. At least one field is required.

#### DEX class query parameters

| Parameter | Type | Required | Allowed values and limits | Meaning |
| --- | --- | --- | --- | --- |
| `name` | Object | No | `operator` plus `value` | Restricts the class descriptor. |
| `stringConstants` | Array of strings | No | 1 to 16 strings, each 1 to 160 characters without control characters | Matches if the class references any listed string. |
| `methodReferences` | Array of method-reference objects | No | 1 to 16 references | Matches if the class references any listed method. |

At least one query parameter is required. If several parameters are present,
all parameter categories must match the same class.

The fields inside one query are AND categories and must be satisfied by the
same DEX class:

- `name`, when present, must match that class.
- `stringConstants`, when present, succeeds if the class references any string
  in the list.
- `methodReferences`, when present, succeeds if the class references any method
  in the list.

For example, a query containing both `stringConstants` and `methodReferences`
requires one class that contains at least one listed string and at least one
listed method reference. The matching instructions do not have to appear in
the same method. Use separate entries in `dexClasses` when the evidence may be
found in different classes.

Use `fingerprint: artifact` for every DEX rule.

#### Class names

DEX class names use descriptors, not Java or Kotlin dotted names.

| Goal | Operator | Example |
| --- | --- | --- |
| Match one class | `equal` | `Lcom/example/sdk/EntryPoint;` |
| Match a package or nested prefix | `starts_with` | `Lcom/example/sdk/` |

| Name parameter | Type | Required | Possible values and limits | Meaning |
| --- | --- | --- | --- | --- |
| `name.operator` | String | Yes | `equal`, `starts_with` | Exact descriptor match or descriptor-prefix match. |
| `name.value` | String | Yes | DEX class descriptor pattern beginning with `L`; `equal` must end in `;` | Descriptor or prefix to match. |

`equal` requires the trailing semicolon. `starts_with` may omit it and usually
uses a trailing slash for a package prefix. Values begin with `L` and may use
letters, digits, underscores, dollar signs, slashes, and hyphens.

#### String constants

`stringConstants` contains 1 to 16 strings, each 1 to 160 characters. Control
characters are rejected. These strings are literal DEX string references, not
regular expressions or substrings.

#### Method references

A method reference requires `definingClass` and `name`:

```json
{
    "definingClass": "Landroid/content/IntentFilter;",
    "name": "<init>",
    "parameterTypes": [
        "Ljava/lang/String;"
    ]
}
```

| Field | Required | Constraint |
| --- | --- | --- |
| `definingClass` | Yes | Full DEX class descriptor ending in `;`, up to the schema limit. |
| `name` | Yes | DEX method name, 1 to 80 characters. `<init>` and `<clinit>` are accepted. |
| `parameterTypes` | No | Exact parameter descriptor list, at most 16 entries. |

Omit `parameterTypes` to match any overload with the same defining class and
method name. Provide it to require an exact parameter list. An empty array
matches a zero-parameter method.

Primitive descriptors are `Z` (boolean), `B` (byte), `S` (short), `C` (char),
`I` (int), `J` (long), `F` (float), and `D` (double). Prefix a descriptor with
`[` for each array dimension. Object types use full descriptors such as
`Ljava/lang/String;`.

## Optional metadata

### `releaseChannel`

- `stable` is the default and is included in both preview and stable bundles.
- `preview-only` is included only when the builder uses `--channel preview`.

The builder removes `releaseChannel` from the generated catalog. It is a
repository publication control, not runtime chart metadata.

### `availability`

Schema v1 online rules only accept `always`, which is also the default. Omit
this field unless a future schema adds a supported online availability gate.

### `requiresFeatureInitialization`

When `true`, LibChecker hides the chart until its feature initialization has
finished. Current online evidence types do not require feature data, so new
online rules should normally omit this field or use `false`.

### `controls`

Schema v1 allows no online chart controls. Omit this field. An explicit empty
array is valid but adds no behavior.

### `dashboard`

Schema v1 online rules only accept `none`, which is the default. Omit it.

### `fingerprint`

The fingerprint controls when LibChecker discards cached chart results after
installed-app data changes. It does not grant access to additional evidence.

| Value | Use |
| --- | --- |
| `standard` | Metadata-based rules such as `target_sdk`. This is the default. |
| `artifact` | Rules that inspect native libraries, archive entries, DEX, or manifest contents. |
| `features` | Rules that depend on LibChecker's initialized feature data. No schema v1 online evidence currently needs it. |

Choose the fingerprint that covers every evidence leaf in the rule. A rule
that combines target SDK with DEX evidence should use `artifact`.

## Validation and tests

Run:

```shell
python3 -m unittest chart.tools.test_build_bundle
```

The JSON Schema defines the complete object shape and field constraints. The
Python builder performs additional semantic validation. It rejects incompatible
evidence/operator/value combinations, unsafe URLs, unsafe icon paths and SVG
content, duplicate IDs, duplicate facet IDs, and complexity-limit violations.

When adding a rule, update the existing assertions in
`chart/tools/test_build_bundle.py`:

1. Add the ID in sorted order to `test_source_rules_are_valid`.
2. Add a new icon path in sorted archive order and update the expected catalog
   count in `test_bundle_is_deterministic_and_contains_only_expected_files`.
3. Update `test_stable_bundle_excludes_preview_only_rules` according to the
   rule's release channel.
4. Add one focused test that asserts the important detection values, condition
   ordering, icon render mode, details URL, or another property that reviewers
   should not accidentally change.
5. Add negative validation tests when you introduce a new schema capability or
   validator branch.

Do not weaken limits or delete regression assertions only to make a new rule
pass.

## Bundle generation

For a local preview, write to a temporary directory so that validation does not
modify tracked generated files:

```shell
python3 chart/tools/build_bundle.py \
  --bundle-version 12 \
  --channel preview \
  --minimum-app-version-code 2731 \
  --output-dir /tmp/libchecker-chart-preview
```

For the final branch artifact, omit `--output-dir` to write to `chart/cloud/v1/`:

```shell
python3 chart/tools/build_bundle.py \
  --bundle-version 12 \
  --channel preview \
  --minimum-app-version-code 2731
```

Builder arguments:

| Argument | Required | Meaning |
| --- | --- | --- |
| `--bundle-version` | Yes | Positive, monotonically increasing publication version for the target branch. |
| `--channel` | No | `preview` by default, or `stable`. Preview includes both release channels; stable excludes `preview-only`. |
| `--minimum-app-version-code` | No | First LibChecker version code that can safely load every rule in the bundle. Defaults to `0`, which should only be published when all supported clients are compatible. |
| `--output-dir` | No | Destination directory. Defaults to `chart/cloud/v1/`. |

If the rule uses only evidence and calculation features already supported by
the published app, retain the branch's compatible minimum app version. If it
depends on a new client capability, coordinate the app change first and set the
exact first compatible version code. Do not guess this number.

The builder:

- validates every source rule and referenced SVG;
- sorts rules by ID and icons by path;
- writes a deterministic ZIP containing `catalog.json` and referenced icons;
- limits the bundle to 64 rules and 2 MiB;
- computes `bundleSha256` and `bundleSize`;
- writes `manifest.json` with schema, publication, and compatibility metadata.

Commit `chart.bundle` and `manifest.json` together. A checksum or size from one
generation cannot be paired with a bundle from another generation.

## Manual verification

Automated validation proves that a rule is well-formed. It does not prove that
the evidence identifies the intended apps.

Before requesting stable publication:

1. Install a compatible LibChecker build that reads the preview branch.
2. Check at least one known matching app and one known non-matching app.
3. For facets, verify every facet independently and confirm that an app matching
   several facets shows all expected chips in rule order.
4. Check the chart title, group titles, description, reference link, icon size,
   colors, light theme, and dark theme.
5. Record the app versions or sample APKs used for testing in the PR description.
6. Rebuild with `--channel stable` and inspect the catalog before publishing.
   Every `preview-only` rule must be absent.

## Pull request checklist

- [ ] The rule solves one clearly described statistic.
- [ ] The ID and filename are stable and follow the naming rules.
- [ ] A new rule starts at revision `1`; an edited published rule increments its revision.
- [ ] All text includes equivalent `en` and `zh-Hans` translations.
- [ ] The description is neutral and the HTTPS reference is primary.
- [ ] The calculation uses only supported evidence and compatible operators.
- [ ] DEX queries use descriptors and preserve same-class matching semantics.
- [ ] The SVG passes the safety and viewBox requirements.
- [ ] The release channel and fingerprint match the rule's maturity and evidence.
- [ ] Focused tests cover the important matching data and channel behavior.
- [ ] Unit tests pass.
- [ ] Matching and non-matching apps were checked with a compatible LibChecker build.
- [ ] The generated bundle and manifest were rebuilt and committed together.

## Recovery after a bad publication

Do not reuse an older bundle version. Restore the last known-good source rules
and generated contents, then publish them with a higher `bundleVersion`.
Compatible LibChecker clients retain their cached bundle when a download,
checksum, schema, or minimum-version check fails.
