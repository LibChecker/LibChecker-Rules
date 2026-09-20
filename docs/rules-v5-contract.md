# Rules v5 contract

This repository is the only editable base-rule source. SDK details and chart rules
remain separate. Schema version is **5**, initial data version **45** (legacy 44). The earlier full-Android 45 was local only
and unpublished; the approved database-only bootstrap supersedes it.
All JSON is UTF-8. UUIDs retain their original uppercase spelling. Paths are relative,
POSIX, case-sensitive, with no leading slash or `..` components.

## Canonical source

`libraries/<uuid>.json` contains `schemaVersion: 5`, `uuid`, `iconId` (string or null),
`data` (the original locale entries, possibly empty), `matchers` (possibly empty),
and `unreferencedDescriptions` (original `{path,payload}` objects, never enabled).
Each locale entry is `{locale, data}`. Its data preserves `label`, `dev_team`,
`description`, `source_link`, `rule_contributors` and all existing extension fields.
Editors must preserve unrecognized metadata and all locale entries.

Each matcher has the following **required** fields:

- `id`: globally unique positive integer, imported from legacy `_id`; allocate above max.
- `type`: 0 native, 1 service, 2 activity, 3 receiver, 4 provider, 5 DEX,
  6 static, 7 permission, 8 metadata, 9 action.
- `name`: exact name or regex pattern; `mode`: `exact` or `regex`.
- `priority`: nonnegative integer, lower first; import uses legacy `_id`.
- `label`: original DB display label, independent of localized details.
- `iconId`: stable `ic_lib_*` string or null; explicit per-matcher value.
- `regexName`: original string or null, used only for compatibility paths.
- `hasDetail`: boolean; false means no details, even if library `data` exists.
- `legacyPath`: original detail path or null.
- `examples`: `{positive: [string], negative: [string]}`; empty arrays permitted for
  imported patterns without trustworthy examples, never invented witnesses.

Optional `detailData` overrides the entire library locale array for this matcher.
This retains divergent descriptions sharing a UUID. If `hasDetail` is false,
`detailData` must be absent. All active matching comes from `matchers`, never from
`unreferencedDescriptions`.

Real Flutter matcher (library `AEF9680F-4A43-4EDC-A5B8-8119D23BCD21`):

```json
{"id":71,"type":0,"name":"libflutter.so","mode":"exact","priority":71,"label":"Flutter","iconId":"ic_lib_flutter","regexName":null,"hasDetail":true,"legacyPath":"native-libs/libflutter.so.json","examples":{"positive":["libflutter.so"],"negative":[]}}
```

`icons/index.json` maps decimal legacy icon indexes to
`{iconId, isSimpleColorIcon}`; `-1` maps to a null icon. SVGs live in
`icons/<iconId>.svg`. Index assignments remain fixed for old Android consumers.

## Artifact files

A release contains `android-v5.zip`, `portable-v5.zip`, `legacy-v4.zip` and an
external `manifest.json`. ZIPs have **no enclosing directory**.
Android ZIP contains **exactly two entries**: `rules.db` and `metadata.json`.
It contains no descriptions, SVGs, icon index, XML resources, or test fixtures.
Portable ZIP includes `metadata.json`, `details/<uuid>/<id>.json`,
`icons/<iconId>.svg`, `icons/index.json`, and `matching-fixtures.json`.
The metadata bytes are identical in both packages.
Each detail JSON is `{uuid, data}` in the original locale format, not flattened.
Only matchers with `hasDetail: true` receive a detail file.

Portable additionally contains `core.json`:

```json
{"schemaVersion":5,"rules":[{"id":71,"uuid":"AEF9680F-4A43-4EDC-A5B8-8119D23BCD21","name":"libflutter.so","label":"Flutter","type":0,"iconIndex":20,"iconId":"ic_lib_flutter","isSimpleColorIcon":false,"isRegexRule":false,"regexName":null,"priority":71,"detailPath":"details/AEF9680F-4A43-4EDC-A5B8-8119D23BCD21/71.json"}]}
```

Android contains `rules.db` with `PRAGMA user_version=5` and
`rules_table(_id INTEGER PRIMARY KEY, name TEXT NOT NULL, label TEXT NOT NULL,
type INTEGER NOT NULL, iconIndex INTEGER NOT NULL, isRegexRule INTEGER NOT NULL,
regexName TEXT, priority INTEGER NOT NULL, labelEn TEXT)`.
These are the legacy seven columns plus `priority` and nullable `labelEn`, with
4096-byte pages. `label` always preserves the original matcher label. `labelEn`
comes only from the effective matcher detail locale `en` (whole `detailData`
override if present, otherwise library `data`), and only when `hasDetail` is true.
Missing/blank English or English identical to `label` is stored as NULL. No
translation is invented, and an override without English never borrows the library
English label. Readers show `label` for persisted Chinese detail language; all
other languages use `labelEn` with fallback to `label`. Older eight-column
databases remain readable by falling back to `label`. Canonical editing format,
portable fields and legacy seven-column data stay unchanged.
Rows retain their legacy integer IDs. Query regex rows with explicit
`ORDER BY priority, _id`. The Android DB has no `uuid`, `iconId`, `detailPath`, or
`isSimpleColorIcon` columns: these unused Android fields belong to canonical and
portable data, which retain them in full. Android details use existing cloud JSON
endpoints and the selected GitHub/GitLab root; SDK UUID comes from cloud detail JSON.
Android icons and their monochrome flags use Bundle drawable/IconResMap only.
Independent chart SVG support is unchanged. This compact layout replaces the
unpublished local 45 preview only; matching schema/user_version stays 5. Reader
validation accepts the original eight columns and this nine-column extension.

Legacy ZIP contains `cloud/rules/v4/rules.db` (original seven columns),
`cloud/md5/v4` (`{version,count}`), and legacy detail paths. Existing checked-in
legacy files are retained during migration; new source edits ship updated legacy
artifacts from the same compiler invocation. Orphan descriptions remain available
at old paths without becoming matches.

## Matching and SVG safety

Exact name equality is attempted first for **all rows**, including the literal
pattern string of regex rows (legacy behavior). Duplicate type/name is rejected.
Then, if enabled, regex rows are tried by `(priority,id)`; first whole-string match
wins. Python uses `re.fullmatch`; Java uses `Pattern.matcher(name).matches()`;
JS uses `new RegExp('^(?:' + pattern + ')$', 'u')` and also checks the matched
string length equals input length (JS `$` otherwise accepts a final newline).
No case folding or Unicode normalization. Unsupported types must be filtered,
not reinterpreted; tgbot capabilities are `[0,1,2,3,4,9]`.

Portable regex subset: literals, escaped punctuation, dot, ASCII character ranges,
negated classes, capturing/noncapturing groups, alternation, `? * + {m,n}`, `^ $`.
`\d` means ASCII digits only (Python compiles with `re.ASCII`). Reject other shorthand character classes, flags, lookarounds, backreferences, Unicode
properties, possessive quantifiers, and non-BMP pattern literals. Dot excludes
LF, CR, U+0085, U+2028, U+2029 in every runtime (consumers must normalize dot
semantics or reject these input characters for regex evaluation). Shared fixtures
include alternation, escaping, Unicode literals, exact precedence and ordering.

Library SVGs support bounded `svg/g/path/defs/clipPath/linearGradient/radialGradient/stop`
and local `url(#id)` paint/clip references. No scripts, events, stylesheets,
external URLs, href, entities, DTD, foreign elements, or recursive references.
Maximum 256 KiB per icon, 4096 elements, depth 32. Chart SVG policy is unchanged.

## Manifest, identity, and publication

`metadata.json` contains `schemaVersion`, `dataVersion`, `sourceRevision`,
`compilerRevision`, `contentSha256`, `ruleCount`, and
`minimumReader: {android:5, portable:5}`. External manifest repeats these fields
and adds `artifacts`, keyed `android`, `portable`, `legacy`. Each value has
`path` (`releases/<dataVersion>/<filename>`), `sha256` (lowercase hex), `size`
(bytes), `schemaVersion` (5 or 4), `minimumReaderVersion` (5 or 4).
`compilerRevision` hashes `rules.py`, `android_vectors.py`, and `vector_import.py`
(filename + NUL + bytes in that order); `sourceRevision` is a Git commit
SHA. For local uncommitted previews it identifies the base commit, while
`contentSha256` binds actual canonical source; production CI requires a clean tree.

`tools/rules.py check` validates canonical source. `build --output DIR
[--data-version N] [--previous-manifest PATH] [--source-revision SHA]` emits all
artifacts in one pass. Equal content hash AND compilerRevision with a previous manifest emits no release;
otherwise N must exceed previous dataVersion (default: previous + 1, or 45 when no manifest exists). Published versions remain
immutable. The unpublished local full-Android preview 45 is superseded only through
an explicit local bootstrap replacement; normal remote update rules are unchanged. Same release inputs yield identical
bytes. Rollback means building older canonical content with a **new higher** N.
Never overwrite a published version. Publish immutable files first, then update
mutable manifest; releases serialize and use only this repository's token.
No consumer should automatically activate v5 until its reader migration is deployed.

## Editor integration

Run `python3 /absolute/path/to/tools/rules.py --root TEMP_ROOT check` before saving.
TEMP_ROOT needs only `libraries/` and `icons/`; fixtures belong to compiler tooling.
Exit code 0 means valid; code 1 and a human-readable stderr message mean invalid.
For build: `python3 tools/rules.py --root SOURCE_ROOT build --output OUTPUT_ROOT
[--data-version N] [--previous-manifest PATH] [--source-revision FULL_GIT_SHA]`.
A temporary non-Git source root must pass `--source-revision`.

Android uses ICU Pattern: its default `\d` accepts Unicode digits, unlike the JVM.
V5 readers must lexically normalize unescaped `\d` to `[0-9]` outside character
classes and `0-9` inside them. Preserve escaped backslashes and the original name
for exact lookup. Do not apply a blind string replacement. Fixtures include all
three escape positions; v4 matching is unchanged.

New icons: `python3 tools/rules.py --root SOURCE_ROOT import-icon --file INPUT.svg
--icon-id ic_lib_name [--simple-color]` validates SVG and a staged complete source,
allocates the next never-reused index, and publishes SVG before replacing index.
Validation failure makes no source change. Commit errors roll back the new SVG;
an OS/process crash between the two renames can leave an unreferenced SVG only
(recover with `sync-icons`). `.rules-edit.lock` prevents concurrent icon imports;
remove a stale lock only after confirming its writer stopped. Existing icons are
replaced through the editor's staged single-file check. `sync-icons` is an offline
repair/batch operation; it appends indexes in filename order, never changes old ones.

## Distribution endpoints and release order

Publication targets this repository's `rules-data` branch:
`https://raw.githubusercontent.com/LibChecker/LibChecker-Rules/rules-data/manifest.json`.
Resolve `artifacts.*.path` against that same root. The identical immutable manifest
is stored at `releases/<dataVersion>/manifest.json`. **These endpoints have not
been published by this implementation task.** Local integration uses build output.

The serialized workflow triggers on `v4` canonical/tool changes or manual dispatch.
It uploads immutable version files, updates actual existing `v4` branch cloud DB,
version marker and all owned detail paths from the legacy archive, then advances
the mutable v5 manifest. Removed detail files are removed; explicitly retained
canonical orphan descriptions survive. It checks current remote v4 canonical and
compiler inputs against the built release before writing; racing pushes cause
rejection, never force-push. SDK/chart content is never changed by this publisher.
Interrupted releases resume the identical staged version or allocate a higher
version if its inputs changed. Only the repository's own GITHUB_TOKEN is needed.
Initial v5-capable consumer deployment is a separate release gate.

Machine-readable structural schemas are in `schemas/`; `tools/rules.py check` is
the authoritative semantic validator (UUID links, icons, regex subset, paths,
examples, locale uniqueness and SVG safety). Import audit lives in
`docs/migration-audit.json`; `python3 tools/audit_migration.py` proves the initial
migration against retained v4 input and is intentionally not a future-edit CI gate.
The 33 orphan paths in the earlier macOS scan include one case-only path alias;
canonical import has 32 genuinely unreferenced files, with all 2687 original JSON
payloads retained. Five aliases and every missing expected path are recorded.
Imported numeric icon IDs are frozen; new IDs are append-only. Old Bundle readers
that do not have a newly appended icon return their existing placeholder.

## SDK fingerprint privacy gate

SDK data is separate from base dataVersion. `sdk-details/tools/build_indexes.py`
builds fixed `data/index.json` files for Flutter and AndroidX Test and staged
`sdk-details/candidates/<sdk>/definition.json` files. A lookup uses `index_path`,
`entries_field: "entries"`, `input`, `expected_field`, `items_field`, and `outputs`.
Readers fetch the fixed index once, compare captured values to each entry's
`expected_field` locally, then project `items_field` releases through `outputs`.
Captured values never enter a URL or a log. Active definitions/catalog deliberately
retain their deployed format; candidates must only be activated after compatible
client release, with separate SDK deployment review. Base rule publication cannot
activate these candidates. The existing SDK scheduled job regenerates indexes
alongside provider output without changing the active definitions.

## Android resource synchronization (separate code release)

`icons/android/<iconId>.xml` preserves the original Android VectorDrawable sources.
`icons/index.json` is the common stable numeric map; existing assignments never move.
Bundle resource synchronization reads these two source paths at a pinned Rules commit,
copies validated XML, and generates its resource mapping automatically. XML/SVG and
resource mapping never enter the Android data ZIP. New rules reusing an existing
icon need only a data update. A new icon requires a Bundle resource release and an
App dependency update; older installed Bundles safely use their placeholder.
The existing XML-to-SVG converter derives portable web icons; no generic SVG-to-XML
conversion is introduced. SVG-only imports remain valid for web use and require a
separate Android vector source before that icon can ship as a Bundle drawable.

`python3 tools/rules.py --root SOURCE_ROOT import-vector --file INPUT.xml
--icon-id ic_lib_name [--simple-color]` supports adding, updating, or adding XML to
a web-only ID. It validates bounded standalone VectorDrawable XML, derives SVG with
the existing converter, and automatically appends an index for a new ID. Existing
index and color flags are preserved. It stages and checks all source under the same
`.rules-edit.lock`; ordinary I/O commit failures roll back. Multiple renames are not
crash-atomic: after an interrupted update, rerun the import before publishing.
When an XML exists, `check` requires its generated SVG to match byte-for-byte; edit
the vector rather than the generated SVG. Editor temporary roots must recursively
copy `icons/`, including `icons/android/`. External XML resources are forbidden
except the existing `?android:attr/colorControlNormal` root tint. Bounds are 256 KiB,
4096 elements and depth 32. Original vector XML stays available to the Android
resource compiler; web conversion retains its existing supported subset.

### First publication of the consumer-locked 45

A merge commit is not interchangeable with the frozen `sourceRevision`: metadata
would change ZIP bytes even if canonical content did not. The first publisher run
is therefore refused unless `--bootstrap-source-revision` equals its clean source
checkout HEAD. Merge the implementation, then manually dispatch **Publish rules
data** on `v4` with `bootstrap_source_revision` set to the exact 40-character
`sourceRevision` from the consumer-locked final manifest. Checkout uses that exact
commit; deterministic build reproduces the locked 45 metadata and bytes. Before
activation, the publisher still checks current v4 canonical/compiler inputs match;
if later data edits exist, restore/reconcile those inputs before first publication.
Do not substitute the merge HEAD, increment version, or loosen same-version hash
checks. Normal push publishing resumes once the first manifest exists. An equivalent
local publication command (only after separate release authorization) uses a clean
detached checkout of the pinned commit and `--bootstrap-source-revision FULL_SHA`.
No publication has been performed in this implementation task.
