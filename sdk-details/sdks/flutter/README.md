# Flutter SDK details provider

Files in `data/engine/` map an engine revision found in `libflutter.so` to official
Flutter releases. A single engine can belong to multiple Flutter patch
releases, so consumers must treat `releases` as a candidate list rather than an
exact version.

The daily workflow reads the official Linux, macOS, and Windows release
indexes. For a framework revision that is not already represented in
`engine/`, it resolves `bin/internal/engine.version` from the Flutter
repository, then merges the release into the matching engine file. Existing
engine files are retained so releases that disappear from upstream indexes are
not lost.

Run the generator locally with:

```shell
python sdk-details/tools/test.py
python sdk-details/tools/update.py --sdk flutter
python sdk-details/tools/update.py --check
```

The generator validates existing history before network access, resolves only
previously unseen framework revisions, limits remote response sizes, writes
changed files atomically, and leaves unchanged mappings untouched. The scheduled
generic SDK details workflow serializes runs and commits only generated data
under `sdk-details/`.

Each generated file uses this schema:

```json
{
  "engine": "40-character engine revision",
  "releases": [
    {
      "flutter": "3.44.6",
      "dart": "3.12.2",
      "channel": "stable",
      "framework": "40-character framework revision",
      "release_date": "2026-07-09T18:35:32.476978Z"
    }
  ]
}
```
