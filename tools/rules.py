#!/usr/bin/env python3
"""Validate canonical rules and compile deterministic v4/v5 data releases (stdlib)."""
import argparse
from contextlib import closing
import os
import shutil
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sqlite3
import subprocess
import tempfile
import uuid
import xml.etree.ElementTree as ET
import zipfile
from android_vectors import validate_vector

ROOT = Path(__file__).resolve().parents[1]
LINE_ENDINGS = '\n\r\x85\u2028\u2029'
TAGS = {'svg','g','path','defs','clipPath','linearGradient','radialGradient','stop'}
ATTRS = {'width','height','viewBox','fill','fill-opacity','stroke','stroke-width','stroke-opacity','stroke-linecap','stroke-linejoin','stroke-miterlimit','fill-rule','clip-rule','d','transform','id','clip-path','x1','x2','y1','y2','cx','cy','r','fx','fy','gradientUnits','gradientTransform','spreadMethod','offset','stop-color','stop-opacity','opacity'}
LEGACY_SQL = '''CREATE TABLE rules_table(_id INTEGER NOT NULL PRIMARY KEY, name TEXT NOT NULL, label TEXT NOT NULL, type INTEGER NOT NULL, iconIndex INTEGER NOT NULL, isRegexRule INTEGER NOT NULL, regexName TEXT)'''
V5_SQL = LEGACY_SQL[:-1]+', priority INTEGER NOT NULL)'

def fail(condition, message):
    if not condition: raise ValueError(message)

def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',',':'))+'\n').encode()

def read(path):
    def unique(pairs):
        result={}
        for key,value in pairs:
            fail(key not in result, f'{path}: duplicate JSON key {key}')
            result[key]=value
        return result
    return json.loads(path.read_text(), object_pairs_hook=unique, parse_constant=lambda value: fail(False,f'Invalid JSON constant {value}'))

def safe_path(value):
    fail(isinstance(value,str) and value and '\\' not in value and '\x00' not in value, f'Invalid path {value!r}')
    p=PurePosixPath(value)
    fail(not p.is_absolute() and '..' not in p.parts and str(p)==value, f'Unsafe path {value!r}')
    return value

def valid_regex(pattern):
    fail(len(pattern)<=1024, 'Regex too long')
    fail(not any(ord(c)>65535 or c in LINE_ENDINGS for c in pattern), 'Unsupported regex literal')
    # Only punctuation escapes and ASCII digit shorthand are portable here.
    fail(not re.search(r'\\(?:[A-Za-ce-z0-9])',pattern), f'Unsupported regex escape: {pattern}')
    fail(not re.search(r'\(\?(?!:)|[*+?}]\+',pattern), f'Unsupported regex construct: {pattern}')
    in_class=False
    index=0
    while index<len(pattern):
        char=pattern[index]
        if char=='\\':
            index+=1
            fail(index<len(pattern),'Trailing regex escape')
            allowed='d^$\\.*+?()[]{}|/' + ('-' if in_class else '')
            fail(pattern[index] in allowed, f'Nonportable regex escape: {pattern}')
        elif char=='[':
            fail(not in_class,'Nested character classes are not portable')
            in_class=True
        elif char==']':
            fail(in_class,'Unmatched character class end')
            in_class=False
        elif char=='&' and in_class:
            fail(index+1>=len(pattern) or pattern[index+1]!='&','Character class intersection is not portable')
        elif char=='{' and not in_class:
            quantifier=re.match(r'\{[0-9]+(?:,[0-9]*)?\}',pattern[index:])
            fail(quantifier is not None,'Nonportable literal brace')
            index+=len(quantifier[0])-1
        elif char=='}' and not in_class:fail(False,'Unmatched quantifier end')
        index+=1
    try: return re.compile(pattern, re.ASCII)
    except re.error as exc: raise ValueError(f'Invalid regex {pattern}: {exc}') from exc

def regex_matches(pattern, value):
    return not any(c in value for c in LINE_ENDINGS) and re.fullmatch(pattern,value,re.ASCII) is not None

def find_rule(rules, value, typ, use_regex=True):
    for rule in rules:
        if rule['type']==typ and rule['name']==value: return rule['id']
    if use_regex:
        for rule in sorted(rules,key=lambda r:(r['priority'],r['id'])):
            if rule['type']==typ and rule['isRegexRule'] and regex_matches(rule['name'],value): return rule['id']
    return None

def validate_svg(raw):
    fail(len(raw)<=256*1024, 'SVG exceeds 256 KiB')
    text=raw.decode('utf-8')
    fail(not re.search(r'<!|<\?',text), 'SVG declarations/entities forbidden')
    root=ET.fromstring(text)
    fail(root.tag=='{http://www.w3.org/2000/svg}svg','SVG root/namespace required')
    ids=set(); refs=[]; count=0
    def visit(node, depth, in_definition=False):
        in_definition = in_definition or node.tag.rsplit('}',1)[-1] in ('defs','clipPath','linearGradient','radialGradient')
        nonlocal count
        count+=1
        fail(depth<=32 and count<=4096,'SVG structure limit')
        fail(node.tag in {'{http://www.w3.org/2000/svg}'+t for t in TAGS},f'Unsupported SVG element {node.tag}')
        fail(not (node.text or '').strip() and not (node.tail or '').strip(),'SVG text forbidden')
        for key,value in node.attrib.items():
            fail(key in ATTRS, f'Unsupported SVG attribute {key}')
            fail(not any(c in value for c in ('<','>','&','\\')), 'Unsafe SVG value')
            if key=='id':
                fail(re.fullmatch(r'[A-Za-z_][\w.-]*',value) is not None and value not in ids,'Invalid/duplicate SVG id'); ids.add(value)
            if 'url' in value.lower():
                match=re.fullmatch(r'url\(#([A-Za-z_][\w.-]*)\)',value)
                fail(match is not None and key in ('fill','stroke','clip-path'), 'External/invalid SVG reference')
                refs.append(match[1])
            else:
                fail(not re.search(r'javascript:|data:|https?:|file:|//',value,re.I),'External SVG value')
            # Paint servers cannot reference another paint server; prevents cycles.
            if in_definition:
                fail('url' not in value.lower(),'Recursive SVG definition')
        for child in node: visit(child,depth+1,in_definition)
    visit(root,1)
    fail(set(refs)<=ids,'Unresolved SVG reference')

def locale_data(data):
    fail(isinstance(data,list),'data must be a locale array')
    seen=set()
    for item in data:
        fail(isinstance(item,dict) and isinstance(item.get('locale'),str) and item['locale'] and isinstance(item.get('data'),dict),'Invalid locale entry')
        fail(item['locale'] not in seen,'Duplicate locale');seen.add(item['locale'])
        for key,value in item['data'].items():
            if key=='rule_contributors': fail(isinstance(value,list) and all(isinstance(x,str) for x in value),'Invalid contributors')
            elif key in ('label','dev_team','description','source_link'): fail(isinstance(value,str),f'Invalid detail {key}')

def load_source(root=ROOT):
    icon_index=read(root/'icons/index.json'); by_icon={}
    for index,entry in icon_index.items():
        fail(re.fullmatch(r'-?\d+',index) is not None and int(index)>=-1,'Invalid icon index')
        icon=entry['iconId'];fail(type(entry['isSimpleColorIcon']) is bool,'Invalid icon color flag')
        fail(icon is None and index=='-1' or isinstance(icon,str) and re.fullmatch(r'ic_lib_[a-z0-9_]+',icon),f'Invalid iconId {icon}')
        fail(icon not in by_icon,'Duplicate icon mapping');by_icon[icon]=(int(index),entry['isSimpleColorIcon'])
    fail(None in by_icon,'Missing placeholder icon')
    frozen=read(ROOT/'docs/migration-audit.json')['legacyIconIndex']
    fail(all(icon_index.get(k)==v for k,v in frozen.items()),'Legacy icon assignments are immutable')
    icons={}
    for p in sorted((root/'icons').glob('*.svg')):
        validate_svg(p.read_bytes());icons[f'icons/{p.name}']=p.read_bytes()
    fail(all(icon is None or f'icons/{icon}.svg' in icons for icon in by_icon),'Missing SVG')
    vectors={}
    for path in sorted((root/'icons/android').glob('*.xml')):
        fail(path.stem in by_icon,'Vector has no stable icon mapping')
        raw=path.read_bytes();generated=validate_vector(raw,path.stem)
        fail(icons.get(f'icons/{path.stem}.svg')==generated,f'SVG must be derived from Android XML: {path.stem}')
        vectors[f'icons/android/{path.name}']=raw
    libraries=[];rules=[];details={};legacy={};ids=set();names=set()
    def add_legacy(path,payload):
        safe_path(path)
        fail(path.split('/')[0] in ('native-libs','services-libs','activities-libs','receivers-libs','providers-libs','dex-libs','static-libs','permissions-libs','metadata-libs','actions-libs') and path.endswith('.json'),'Invalid legacy detail path')
        value=encoded(payload)
        fail(path not in legacy or legacy[path]==value,f'Conflicting legacy details: {path}')
        legacy[path]=value
    for p in sorted((root/'libraries').glob('*.json')):
        lib=read(p);uid=lib['uuid']
        fail(str(uuid.UUID(uid)).upper()==uid and p.stem==uid,f'UUID/filename mismatch: {p}')
        fail(lib['schemaVersion']==5 and lib['iconId'] in by_icon,'Invalid library header')
        locale_data(lib['data']);fail(isinstance(lib['matchers'],list),'matchers must be array')
        for m in lib['matchers']:
            fail(type(m['id']) is int and 0<m['id']<=2147483647 and m['id'] not in ids,'Invalid/duplicate matcher ID');ids.add(m['id'])
            fail(type(m['type']) is int and m['type'] in range(10),'Invalid rule type')
            fail(isinstance(m['name'],str) and 0<len(m['name'])<=1024 and '\x00' not in m['name'],'Invalid name')
            key=(m['type'],m['name']);fail(key not in names,f'Duplicate matcher {key}');names.add(key)
            fail(type(m['priority']) is int and 0<=m['priority']<=2147483647,'Invalid priority')
            fail(m['mode'] in ('exact','regex') and isinstance(m['label'],str) and m['label'],'Invalid mode/label')
            fail(m['regexName'] is None or isinstance(m['regexName'],str) and m['regexName'],'Invalid regexName')
            if m['mode']=='regex': valid_regex(m['name'])
            fail(m['iconId'] in by_icon,'Unknown matcher icon')
            index,simple=by_icon[m['iconId']]
            fail(type(m['hasDetail']) is bool,'hasDetail must be boolean')
            fail(m['hasDetail'] or 'detailData' not in m,'Missing detail has override')
            path=None
            if m['hasDetail']:
                data=m.get('detailData',lib['data']);locale_data(data);fail(bool(data),'Empty active detail')
                path=f'details/{uid}/{m["id"]}.json';payload=dict(uuid=uid,data=data);details[path]=encoded(payload)
                if m['legacyPath'] is not None: add_legacy(m['legacyPath'],payload)
            else: fail(m['legacyPath'] is None,'Missing detail has legacy path')
            examples=m['examples'];fail(set(examples)=={'positive','negative'},'Invalid examples')
            for kind,values in examples.items():
                fail(isinstance(values,list) and all(isinstance(v,str) for v in values),'Invalid examples')
                for value in values:
                    matches=regex_matches(m['name'],value) if m['mode']=='regex' else m['name']==value
                    fail(matches==(kind=='positive'),f'Failing {kind} example for {m["id"]}')
            rules.append(dict(id=m['id'],uuid=uid,name=m['name'],label=m['label'],type=m['type'],iconIndex=index,iconId=m['iconId'],isSimpleColorIcon=simple,isRegexRule=m['mode']=='regex',regexName=m['regexName'],priority=m['priority'],detailPath=path))
        for orphan in lib['unreferencedDescriptions']:
            fail(orphan['payload']['uuid']==uid,'Orphan UUID mismatch');locale_data(orphan['payload']['data']);add_legacy(orphan['path'],orphan['payload'])
        libraries.append(lib)
    fail(bool(rules),'No rules')
    rules.sort(key=lambda r:(r['priority'],r['id']))
    fixtures=read(ROOT/'tests/matching-fixtures.json')
    for case in fixtures['cases']:
        for r in case['rules']:
            if r['isRegexRule']: valid_regex(r['name'])
        fail(find_rule(case['rules'],case['input'],case['type'],case.get('useRegex',True))==case['expected'],f'Invalid fixture {case["name"]}')
    digest=hashlib.sha256(encoded(dict(libraries=libraries,icons=icon_index,fixtures=fixtures)))
    for path,raw in sorted({**icons,**vectors}.items()):digest.update(path.encode()+b'\0'+raw)
    common={**icons,**details,'icons/index.json':encoded(icon_index),'matching-fixtures.json':encoded(fixtures)}
    return rules,common,legacy,digest.hexdigest()

def database(rules, v5):
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'rules.db'
        with closing(sqlite3.connect(path)) as db, db:
            db.execute('PRAGMA page_size=4096');db.execute(V5_SQL if v5 else LEGACY_SQL)
            if v5: db.execute('PRAGMA user_version=5')
            for r in sorted(rules,key=lambda r:r['id']):
                row=[r['id'],r['name'],r['label'],r['type'],r['iconIndex'],int(r['isRegexRule']),r['regexName']]
                if v5:row.append(r['priority'])
                db.execute('INSERT INTO rules_table VALUES ('+','.join('?' for _ in row)+')',row)
        return path.read_bytes()

def zip_bytes(files):
    import io
    output=io.BytesIO()
    # Stored entries avoid zlib version differences and make release bytes reproducible.
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_STORED) as archive:
        for name,raw in sorted(files.items()):
            safe_path(name);info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.create_system=3;info.external_attr=0o100644<<16
            archive.writestr(info,raw)
    return output.getvalue()

def compiler_revision(root=ROOT):
    digest=hashlib.sha256()
    for name in ('rules.py','android_vectors.py','vector_import.py'):
        digest.update(name.encode()+b'\0'+(root/'tools'/name).read_bytes())
    return digest.hexdigest()


def build(root, output, version=None, previous=None, revision=None):
    rules,common,legacy,content=load_source(root)
    previous=read(previous) if previous else None
    compiler=compiler_revision()
    if previous and previous['contentSha256']==content and previous['compilerRevision']==compiler:
        print('Content unchanged; no release');return None
    last=previous['dataVersion'] if previous else 44
    version=last+1 if version is None else version
    fail(type(version) is int and last<version<=2147483647,'dataVersion must increase')
    revision=revision or subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    fail(re.fullmatch('[0-9a-f]{40}',revision) is not None,'sourceRevision must be a full Git SHA')
    metadata=dict(schemaVersion=5,dataVersion=version,sourceRevision=revision,compilerRevision=compiler,contentSha256=content,ruleCount=len(rules),minimumReader=dict(android=5,portable=5))
    common['metadata.json']=encoded(metadata)
    payloads={'android':{'metadata.json':encoded(metadata),'rules.db':database(rules,True)},'portable':{**common,'core.json':encoded(dict(schemaVersion=5,rules=rules))},'legacy':{**legacy,'cloud/rules/v4/rules.db':database(rules,False),'cloud/md5/v4':encoded(dict(version=version,count=len(rules)))}}
    manifest={**metadata,'artifacts':{}}
    outputs={}
    for kind,files in payloads.items():
        schema=4 if kind=='legacy' else 5
        path=f'releases/{version}/{kind}-v{schema}.zip';raw=zip_bytes(files)
        manifest['artifacts'][kind]=dict(path=path,sha256=hashlib.sha256(raw).hexdigest(),size=len(raw),schemaVersion=schema,minimumReaderVersion=schema)
        outputs[path]=raw
    outputs[f'releases/{version}/manifest.json']=encoded(manifest)
    for path,raw in outputs.items():
        dest=output/path
        fail(not dest.exists() or dest.read_bytes()==raw,f'Refusing to overwrite immutable artifact {dest}')
    for path,raw in outputs.items():
        dest=output/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    output.mkdir(parents=True,exist_ok=True)
    staged=output/'manifest.json.tmp';staged.write_bytes(encoded(manifest));staged.replace(output/'manifest.json')
    print(json.dumps(manifest,indent=2));return manifest

def sync_icons(root):
    path=root/'icons/index.json'
    index=read(path)
    known={v['iconId'] for v in index.values()}
    next_index=max(map(int,index))+1
    for svg in sorted((root/'icons').glob('ic_lib_*.svg')):
        validate_svg(svg.read_bytes())
        if svg.stem not in known:
            index[str(next_index)]=dict(iconId=svg.stem,isSimpleColorIcon=False)
            next_index+=1
    temporary=path.with_suffix('.json.tmp')
    temporary.write_bytes(encoded(index));temporary.replace(path)
    print(f'Icon mappings: {len(index)} (existing assignments preserved)')

def import_icon(root, source, icon_id, simple=False, vector=False):
    fail(re.fullmatch(r'ic_lib_[a-z0-9_]+',icon_id) is not None,'Invalid icon ID')
    source_raw=source.read_bytes()
    if vector:source_raw=source_raw.replace(b'\r\n',b'\n')
    raw=validate_vector(source_raw,icon_id) if vector else source_raw
    validate_svg(raw)
    target=root/'icons'/f'{icon_id}.svg'
    lock=root/'.rules-edit.lock'
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    try:
        fail(vector or not target.exists(),'Icon already exists; use editor replacement flow')
        with tempfile.TemporaryDirectory(dir=root) as tmp:
            staged=Path(tmp)
            shutil.copytree(root/'icons',staged/'icons')
            shutil.copytree(root/'libraries',staged/'libraries')
            (staged/'icons'/target.name).write_bytes(raw)
            if vector:
                (staged/'icons/android').mkdir(exist_ok=True)
                (staged/f'icons/android/{icon_id}.xml').write_bytes(source_raw)
            old_index=read(root/'icons/index.json')
            existing=next((entry for entry in old_index.values() if entry['iconId']==icon_id),None)
            sync_icons(staged)
            index_path=staged/'icons/index.json';index=read(index_path)
            for entry in index.values():
                if entry['iconId']==icon_id:
                    entry['isSimpleColorIcon']=existing['isSimpleColorIcon'] if existing else simple
            index_path.write_bytes(encoded(index));load_source(staged)
            names=([f'icons/android/{icon_id}.xml'] if vector else [])+[f'icons/{icon_id}.svg','icons/index.json']
            backups={name:(root/name).read_bytes() if (root/name).exists() else None for name in names}
            published=[]
            try:
                for name in names:
                    destination=root/name;destination.parent.mkdir(parents=True,exist_ok=True)
                    (staged/name).replace(destination);published.append(name)
            except OSError:
                for name in reversed(published):
                    if backups[name] is None:(root/name).unlink()
                    else:(root/name).write_bytes(backups[name])
                raise
    finally:
        os.close(fd);lock.unlink()
    print(f'Imported {icon_id}')

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('check');sub.add_parser('sync-icons');b=sub.add_parser('build');b.add_argument('--output',type=Path,required=True);b.add_argument('--data-version',type=int);b.add_argument('--previous-manifest',type=Path);b.add_argument('--source-revision')
    i=sub.add_parser('import-icon');i.add_argument('--file',type=Path,required=True);i.add_argument('--icon-id',required=True);i.add_argument('--simple-color',action='store_true')
    v=sub.add_parser('import-vector');v.add_argument('--file',type=Path,required=True);v.add_argument('--icon-id',required=True);v.add_argument('--simple-color',action='store_true')
    a=p.parse_args()
    try:
        if a.command=='import-vector': import_icon(a.root,a.file,a.icon_id,a.simple_color,vector=True)
        elif a.command=='import-icon': import_icon(a.root,a.file,a.icon_id,a.simple_color)
        elif a.command=='sync-icons': sync_icons(a.root)
        elif a.command=='check':
            rows,_,_,digest=load_source(a.root);print(f'Validated {len(rows)} matchers; contentSha256={digest}')
        else: build(a.root,a.output,a.data_version,a.previous_manifest,a.source_revision)
    except (ValueError,KeyError,TypeError,OSError,ET.ParseError) as exc:p.exit(1,f'Rules validation failed: {exc}\n')

if __name__=='__main__':main()
