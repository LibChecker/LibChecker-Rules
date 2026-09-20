#!/usr/bin/env python3
"""One-time migration of the DB, all descriptions and Bundle icon resources."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid
from vector_import import convert_vector_xml_to_svg, parse_icon_res_map

DIRS = {0:'native-libs',1:'services-libs',2:'activities-libs',3:'receivers-libs',4:'providers-libs',5:'dex-libs',6:'static-libs',7:'permissions-libs',8:'metadata-libs',9:'actions-libs'}

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')

def migrate(root, bundle):
    if any((root/'libraries').glob('*.json')):
        raise ValueError('Refusing to overwrite canonical source')
    icon_map, simple = parse_icon_res_map((bundle/'library/src/main/java/com/absinthe/rulesbundle/IconResMap.kt').read_text())
    icons = {str(i):{'iconId':name,'isSimpleColorIcon':i in simple} for i,name in icon_map.items()}
    icons['-1']={'iconId':None,'isSimpleColorIcon':-1 in simple}
    write(root/'icons/index.json', icons)
    for name in sorted(set(icon_map.values())):
        xml=(bundle/f'library/src/main/res/drawable/{name}.xml').read_text()
        (root/'icons/android').mkdir(exist_ok=True)
        (root/f'icons/android/{name}.xml').write_text(xml)
        svg=convert_vector_xml_to_svg(xml,name)
        if not svg: raise ValueError(name)
        (root/f'icons/{name}.svg').write_text(svg+'\n')
    payloads={str(p.relative_to(root)):json.loads(p.read_text()) for d in DIRS.values() for p in sorted((root/d).rglob('*.json'))}
    libraries={}
    def library(uid, data, icon):
        return libraries.setdefault(uid,dict(schemaVersion=5,uuid=uid,iconId=icon,data=data,matchers=[],unreferencedDescriptions=[]))
    used=set(); missing=[]; divergent=set(); case_aliases=[]
    folded={p.casefold():p for p in payloads}
    conn=sqlite3.connect(root/'cloud/rules/v4/rules.db')
    rows=conn.execute('select * from rules_table order by _id').fetchall()
    for id,name,label,typ,index,regex,rname in rows:
        filename=f'regex/{rname}' if regex and rname else (name.replace('.','/') if typ in (1,2,3,4,5,6) else name)
        path=f'{DIRS[typ]}/{filename}.json'
        if path not in payloads and path.casefold() in folded:
            actual=folded[path.casefold()]; case_aliases.append(dict(expectedPath=path,sourcePath=actual)); path=actual
        payload=payloads.get(path)
        uid=payload['uuid'] if payload else str(uuid.uuid5(uuid.NAMESPACE_URL,f'libchecker:legacy:{typ}:{name}')).upper()
        icon=icons[str(index)]['iconId']
        lib=library(uid,payload['data'] if payload else [],icon)
        m=dict(id=id,type=typ,name=name,mode='regex' if regex else 'exact',priority=id,label=label,iconId=icon,regexName=rname,hasDetail=payload is not None,legacyPath=path if payload else None,examples=dict(positive=[] if regex else [name],negative=[]))
        if payload:
            used.add(path)
            if payload['data']!=lib['data']:
                m['detailData']=payload['data']; divergent.add(uid)
        else: missing.append(dict(id=id,type=typ,name=name,expectedPath=path))
        lib['matchers'].append(m)
    for path,payload in payloads.items():
        if path not in used:
            library(payload['uuid'],payload['data'],None)['unreferencedDescriptions'].append(dict(path=path,payload=payload))
    for uid,lib in sorted(libraries.items()): write(root/f'libraries/{uid}.json',lib)
    audit=dict(legacyDbSha256=hashlib.sha256((root/'cloud/rules/v4/rules.db').read_bytes()).hexdigest(),ruleCount=len(rows),descriptionFileCount=len(payloads),libraryCount=len(libraries),divergentDetailUUIDs=sorted(divergent),missingDescriptions=missing,unreferencedDescriptions=sorted(set(payloads)-used),iconCount=len(set(icon_map.values())),caseAliases=case_aliases,legacyIconIndex=icons)
    write(root/'docs/migration-audit.json',audit)
    print(json.dumps({k:v for k,v in audit.items() if not isinstance(v,list)}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);a=p.parse_args();migrate(a.root,a.bundle)
