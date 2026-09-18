#!/usr/bin/env python3
"""CI-only publisher; local tests use a bare local Git remote. No external services."""
import argparse
import hashlib
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

import rules


def git(root, *args):
    return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()


def commit_push(root, message, branch):
    git(root,'add','--all')
    if not git(root,'status','--porcelain'):return
    git(root,'commit','-m',message)
    git(root,'push','origin',f'HEAD:refs/heads/{branch}')


def publish(source, remote, legacy_branch='v4', data_branch='rules-data', bootstrap_source_revision=None):
    if git(source,'status','--porcelain','--untracked-files=normal'):
        raise ValueError('Release source must be committed and clean')
    revision=git(source,'rev-parse','HEAD')
    with tempfile.TemporaryDirectory() as tmp:
        tmp=Path(tmp);distribution=tmp/'distribution';old=tmp/'legacy';output=tmp/'output'
        subprocess.run(['git','clone','--quiet','--no-local','--no-checkout',remote,str(distribution)],check=True)
        git(distribution,'config','user.name','github-actions[bot]')
        git(distribution,'config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
        refs=git(distribution,'for-each-ref','--format=%(refname)','refs/remotes/origin/')
        if f'refs/remotes/origin/{data_branch}' in refs.splitlines():
            git(distribution,'checkout','-b',data_branch,f'origin/{data_branch}')
        else:
            git(distribution,'checkout','--orphan',data_branch)
            git(distribution,'rm','-rf','--ignore-unmatch','.')
        previous=distribution/'manifest.json'
        if not previous.exists() and bootstrap_source_revision!=revision:
            raise ValueError('First publication requires --bootstrap-source-revision matching the clean pinned source checkout')
        # Recover an interrupted upload without reusing its version for other bytes.
        staged_manifests=sorted((distribution/'releases').glob('*/manifest.json'),key=lambda p:int(p.parent.name))
        staged=staged_manifests[-1] if staged_manifests else None
        with redirect_stdout(io.StringIO()):
            manifest=rules.build(source,output,previous=previous if previous.exists() else None,revision=revision)
        if manifest is None:
            print('Content/compiler unchanged; no release');return
        version=manifest['dataVersion']
        if staged and int(staged.parent.name)>=version:
            staged_value=rules.read(staged)
            # A rerun of exactly the same source resumes. A newer source advances.
            if (staged_value['contentSha256']==manifest['contentSha256'] and staged_value['compilerRevision']==manifest['compilerRevision']):
                shutil.rmtree(output)
                with redirect_stdout(io.StringIO()):manifest=rules.build(source,output,int(staged.parent.name),previous if previous.exists() else None,staged_value['sourceRevision'])
                version=manifest['dataVersion']
            elif staged_value!=manifest:
                shutil.rmtree(output)
                with redirect_stdout(io.StringIO()):manifest=rules.build(source,output,int(staged.parent.name)+1,previous if previous.exists() else None,revision)
                version=manifest['dataVersion']
        for path in (output/f'releases/{version}').iterdir():
            destination=distribution/f'releases/{version}'/path.name
            if destination.exists() and destination.read_bytes()!=path.read_bytes():raise ValueError('Immutable release conflict')
            destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,destination)
        commit_push(distribution,f'Publish immutable rules data {version}',data_branch)
        # Legacy path updates happen before advancing the v5 manifest. Old clients
        # continue using their existing branch and URLs throughout the migration.
        subprocess.run(['git','clone','--quiet','--no-local','--branch',legacy_branch,'--single-branch',remote,str(old)],check=True)
        git(old,'config','user.name','github-actions[bot]');git(old,'config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
        if (rules.load_source(old)[3]!=manifest['contentSha256'] or rules.compiler_revision(old)!=manifest['compilerRevision']):
            raise ValueError('v4 canonical/compiler inputs changed; retry from latest source')
        with zipfile.ZipFile(output/manifest['artifacts']['legacy']['path']) as archive:
            expected=set(archive.namelist())
            for path in old.glob('*-libs/**/*.json'):
                if str(path.relative_to(old)) not in expected:path.unlink()
            for name in archive.namelist():
                rules.safe_path(name);dest=old/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(archive.read(name))
        count_dirs={'nativeLibraries':'native-libs','activities':'activities-libs','services':'services-libs','receivers':'receivers-libs','providers':'providers-libs','intentActions':'actions-libs','staticLibraries':'static-libs','chartRules':'chart/rules'}
        counts={key:len(list((old/directory).rglob('*.json'))) for key,directory in count_dirs.items()}
        (old/'rule-counts.json').write_bytes(rules.encoded(dict(rulesVersion=version,**counts)))
        commit_push(old,f'Update v4 compatibility for rules data {version}',legacy_branch)
        shutil.copyfile(output/'manifest.json',distribution/'manifest.json')
        commit_push(distribution,f'Activate rules data {version}',data_branch)
        print(f'Published dataVersion {version}')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=rules.ROOT);p.add_argument('--remote',required=True);p.add_argument('--legacy-branch',default='v4');p.add_argument('--bootstrap-source-revision');a=p.parse_args()
    publish(a.source,a.remote,a.legacy_branch,bootstrap_source_revision=a.bootstrap_source_revision)
