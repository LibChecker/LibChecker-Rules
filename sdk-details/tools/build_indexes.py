"""Build stable public SDK indexes and staged definitions; never activate catalog."""
import argparse
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCES={'flutter':('engine','engine'),'androidx_test':('fingerprint','sha256')}


def outputs(root=ROOT):
    result={}
    for sdk,(directory,key) in SOURCES.items():
        sdk_dir=root/'sdks'/sdk
        entries=[]
        for path in sorted((sdk_dir/'data'/directory).glob('*.json')):
            entry=json.loads(path.read_text())
            if entry.get(key)!=path.stem:raise ValueError(f'Index key mismatch: {path}')
            entries.append(entry)
        if not entries:raise ValueError(f'No index entries for {sdk}')
        result[sdk_dir/'data/index.json']=dict(schema_version=1,sdk_id=sdk,entries=entries)
        candidate=json.loads((sdk_dir/'definition.json').read_text())
        candidate['schema_version']=2
        for lookup in candidate['lookups']:
            lookup.pop('path_template',None)
            lookup['index_path']=f'sdk-details/sdks/{sdk}/data/index.json'
            lookup['entries_field']='entries'
        result[root/'candidates'/sdk/'definition.json']=candidate
    return {p:json.dumps(value,ensure_ascii=False,indent=2)+'\n' for p,value in result.items()}


def build(check=False):
    for path,text in outputs().items():
        if check:
            if not path.exists() or path.read_text()!=text:raise ValueError(f'Stale SDK index: {path}')
        else:
            path.parent.mkdir(parents=True,exist_ok=True)
            temporary=path.with_suffix('.json.tmp');temporary.write_text(text);temporary.replace(path)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args();build(a.check)
