#!/usr/bin/env python3
"""One consumed authorization for the unpublished 2026-10-11 V46 replacement."""
import argparse
import hashlib
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
import rules
from publish_rules import git

OPERATION = 'v46-replacement-20261011'
OLD_MANIFEST_SHA256 = 'c355180bc06ee37290ee5e04e31f52e0572cfcd83bc615c6ed7c84c1dd47b212'
OLD_DATA_REVISION = '9a13eaa0ba18363d75d25b76ce34b67065dfb867'
NEW_CONTENT_SHA256 = 'b7b7d500ad48af2898f2e42724e8032f933cc0d61d5fc628a8acb725fbc89bda'
COMPILER_REVISION = 'd09fc13240cd92fca9c7b5abb2baf4f3a9c4122db1f1e67e110e336383b4e0c2'


def require(value, message):
    if not value:
        raise ValueError(message)


def authorize(source, distribution, revision):
    require(git(source, 'rev-parse', 'HEAD') == revision, 'Exact committed source revision required')
    require(not git(source, 'status', '--porcelain'), 'Clean committed source required')
    require(git(distribution, 'rev-parse', 'HEAD') == OLD_DATA_REVISION, 'Old data revision changed or authorization consumed')
    raw = (distribution / 'manifest.json').read_bytes()
    require(hashlib.sha256(raw).hexdigest() == OLD_MANIFEST_SHA256, 'Old manifest checksum mismatch')
    previous = rules.read(distribution / 'manifest.json')
    require(previous['dataVersion'] == 46, 'Replacement restricted to V46')
    require((distribution / 'releases/46/manifest.json').read_bytes() == raw, 'Old release manifest differs')
    for artifact in previous['artifacts'].values():
        data = (distribution / rules.safe_path(artifact['path'])).read_bytes()
        require(len(data) == artifact['size'] and hashlib.sha256(data).hexdigest() == artifact['sha256'], 'Old artifact checksum mismatch')
    require(rules.load_source(source)[3] == NEW_CONTENT_SHA256, 'Authorized new content mismatch')
    require(rules.compiler_revision(source) == COMPILER_REVISION, 'Authorized compiler mismatch')
    return previous


def replace(source, remote, revision):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); data = root / 'data'; legacy = root / 'legacy'; output = root / 'output'
        subprocess.run(['git', 'clone', '--quiet', '--no-local', '--branch', 'rules-data', remote, str(data)], check=True)
        previous = authorize(source, data, revision)
        git(data, 'config', 'user.name', 'github-actions[bot]'); git(data, 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
        git(data, 'worktree', 'add', '-b', 'replacement-compat', str(legacy), 'origin/v4')
        require(git(legacy, 'rev-parse', 'HEAD') == revision, 'Remote source changed; publish only the pinned source')
        require(rules.load_source(legacy)[3] == NEW_CONTENT_SHA256 and rules.compiler_revision(legacy) == COMPILER_REVISION, 'Remote canonical/compiler mismatch')
        # Explicit version in a fresh output, never weakening rules.build monotonicity.
        manifest = rules.build(source, output, version=46, revision=revision)
        require(manifest['ruleCount'] == 3041, 'Expected 3041 matchers')
        with zipfile.ZipFile(output / manifest['artifacts']['legacy']['path']) as archive:
            expected = set(archive.namelist())
            for path in legacy.glob('*-libs/**/*.json'):
                if str(path.relative_to(legacy)) not in expected: path.unlink()
            for name in archive.namelist():
                dest = legacy / rules.safe_path(name); dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(archive.read(name))
        count_dirs = {'nativeLibraries':'native-libs','activities':'activities-libs','services':'services-libs','receivers':'receivers-libs','providers':'providers-libs','intentActions':'actions-libs','staticLibraries':'static-libs','chartRules':'chart/rules'}
        counts = {key:len(list((legacy / directory).rglob('*.json'))) for key, directory in count_dirs.items()}
        (legacy / 'rule-counts.json').write_bytes(rules.encoded(dict(rulesVersion=46, **counts)))
        shutil.copytree(output / 'releases/46', data / 'releases/46', dirs_exist_ok=True)
        shutil.copyfile(output / 'manifest.json', data / 'manifest.json')
        audit = dict(operation=OPERATION, oldDataRevision=OLD_DATA_REVISION, oldManifestSha256=OLD_MANIFEST_SHA256, oldManifest=previous, newManifest=manifest, sourceRevision=revision, reason='User confirms no user release shipped and authorizes one-time V46 replacement; existing V46 clients do not auto-refresh.')
        (data / 'replacement-audits').mkdir(exist_ok=True)
        (data / 'replacement-audits' / (OPERATION + '.json')).write_bytes(rules.encoded(audit))
        for checkout, message in [(legacy, 'Update v4 compatibility for one-time V46 replacement'), (data, 'Replace unpublished V46 once with audited old and new hashes')]:
            git(checkout, 'add', '--all')
            if checkout == legacy:
                # Preserve case-distinct legacy filenames on macOS as exact Git blobs.
                with zipfile.ZipFile(output / manifest['artifacts']['legacy']['path']) as archive:
                    names = archive.namelist()
                    for name in names:
                        if sum(other.casefold() == name.casefold() for other in names) > 1:
                            blob = subprocess.check_output(['git', '-C', str(legacy), 'hash-object', '-w', '--stdin'], input=archive.read(name)).decode().strip()
                            git(legacy, 'update-index', '--add', '--cacheinfo', '100644,' + blob + ',' + name)
            git(checkout, 'commit', '-m', message)
        # Both branches advance together, or neither does. Ordinary FF rules reject races.
        git(data, 'push', '--atomic', 'origin', 'HEAD:refs/heads/rules-data', 'replacement-compat:refs/heads/v4')
        print('Atomically replaced V46 data and compatibility for ' + revision)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=rules.ROOT)
    parser.add_argument('--remote', required=True)
    parser.add_argument('--source-revision', required=True)
    args = parser.parse_args()
    replace(args.source, args.remote, args.source_revision)
