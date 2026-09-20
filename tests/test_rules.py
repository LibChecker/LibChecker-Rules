import base64
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import rules

class RulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows,cls.common,cls.legacy,cls.digest=rules.load_source()

    def test_source_details_and_exact_lookup(self):
        for row in self.rows:
            self.assertEqual(row['id'],rules.find_rule(self.rows,row['name'],row['type']))
            if row['detailPath']:
                detail=json.loads(self.common[row['detailPath']])
                self.assertEqual(row['uuid'],detail['uuid'])
                self.assertTrue(detail['data'])

    def test_reproducible_build_and_versioning(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            a,b=Path(tmp)/'a',Path(tmp)/'b'
            first=rules.build(ROOT,a,45)
            second=rules.build(ROOT,b,45)
            self.assertEqual(first,second)
            for kind,item in first['artifacts'].items():
                raw=(a/item['path']).read_bytes()
                self.assertEqual(raw,(b/item['path']).read_bytes())
                self.assertEqual(item['sha256'],hashlib.sha256(raw).hexdigest())
                self.assertEqual(item['size'],len(raw))
            self.assertIsNone(rules.build(ROOT,a,46,a/'manifest.json'))
            changed=copy.deepcopy(first);changed['contentSha256']='0'*64
            prior=Path(tmp)/'previous.json';prior.write_bytes(rules.encoded(changed))
            with self.assertRaises(ValueError):rules.build(ROOT,b,45,prior)
            new=rules.build(ROOT,a,None,prior)
            self.assertEqual(46,new['dataVersion'])
            changed=copy.deepcopy(new);changed['compilerRevision']='0'*64;prior.write_bytes(rules.encoded(changed))
            self.assertEqual(47,rules.build(ROOT,a,None,prior)['dataVersion'])
            with self.assertRaises(ValueError):rules.build(ROOT,a,45,revision='a'*40)
            with zipfile.ZipFile(a/first['artifacts']['android']['path']) as android,zipfile.ZipFile(a/first['artifacts']['portable']['path']) as portable:
                self.assertEqual({'rules.db','metadata.json'},set(android.namelist()))
                self.assertEqual(android.read('metadata.json'),portable.read('metadata.json'))
                self.assertIn('matching-fixtures.json',portable.namelist())
                self.assertIn('icons/index.json',portable.namelist())
                self.assertTrue(any(name.startswith('details/') for name in portable.namelist()))
                self.assertTrue(any(name.endswith('.svg') for name in portable.namelist()))
                self.assertFalse(any(name.endswith('.xml') for name in portable.namelist()))
                db_path=Path(tmp)/'read.db';db_path.write_bytes(android.read('rules.db'))
                with contextlib.closing(sqlite3.connect(db_path)) as db:
                    self.assertEqual(5,db.execute('PRAGMA user_version').fetchone()[0])
                    columns=[row[1] for row in db.execute('PRAGMA table_info(rules_table)')]
                    self.assertEqual(['_id','name','label','type','iconIndex','isRegexRule','regexName','priority','labelEn'],columns)
                    self.assertEqual(4096,db.execute('PRAGMA page_size').fetchone()[0])
                    expected=[(r['id'],r['name'],r['label'],r['type'],r['iconIndex'],int(r['isRegexRule']),r['regexName'],r['priority'],rules.english_label(r,self.common)) for r in sorted(self.rows,key=lambda r:r['id'])]
                    self.assertEqual(expected,db.execute('select * from rules_table order by _id').fetchall())
                    self.assertEqual([r['id'] for r in self.rows],[r[0] for r in db.execute('select _id from rules_table order by priority,_id')])
                    self.assertEqual(self.rows,json.loads(portable.read('core.json'))['rules'])
                    self.assertEqual('ok',db.execute('PRAGMA integrity_check').fetchone()[0])
                    self.assertEqual(len(self.rows),db.execute('select count(*) from rules_table').fetchone()[0])

    def test_english_labels_use_effective_matcher_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);shutil.copytree(ROOT/'libraries',root/'libraries');shutil.copytree(ROOT/'icons',root/'icons')
            path=root/'libraries/AEF9680F-4A43-4EDC-A5B8-8119D23BCD21.json'
            lib=rules.read(path)
            def localized(label):return [{'locale':'en','data':{'label':label}}]
            lib['data']=localized('Library English')
            source=copy.deepcopy(lib['matchers'][0]);lib['matchers']=[]
            scenarios=[('inherited',True,None,'Original','Library English'),
                       ('override',True,localized('Specific English'),'Original','Specific English'),
                       ('missing',True,[{'locale':'zh-Hans','data':{'label':'中文'}}],'Original',None),
                       ('same',True,localized('Same'),'Same',None),
                       ('blank',True,localized('  '),'Original',None),
                       ('no-detail',False,None,'Original',None)]
            expected={}
            for offset,(name,has_detail,override,label,result) in enumerate(scenarios):
                m=copy.deepcopy(source);m.update(id=100000+offset,name='test.'+name,label=label,hasDetail=has_detail,legacyPath=None,examples={'positive':[],'negative':[]})
                m.pop('detailData',None)
                if override is not None:m['detailData']=override
                lib['matchers'].append(m);expected[m['id']]=result
            path.write_bytes(rules.encoded(lib))
            rows,details,_,_=rules.load_source(root)
            db_path=root/'check.db';db_path.write_bytes(rules.database(rows,True,details))
            with contextlib.closing(sqlite3.connect(db_path)) as db:
                actual=dict(db.execute('select _id,labelEn from rules_table where _id>=100000'))
                self.assertEqual(expected,actual)
            db_path.write_bytes(rules.database(rows,False,details))
            with contextlib.closing(sqlite3.connect(db_path)) as db:
                self.assertEqual(7,len(db.execute('PRAGMA table_info(rules_table)').fetchall()))

    def test_compact_database_keeps_priority_independent_of_id(self):
        rows=copy.deepcopy(self.rows[:2])
        rows[0]['priority']=100
        rows[1]['priority']=1
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'rules.db';path.write_bytes(rules.database(rows,True))
            with contextlib.closing(sqlite3.connect(path)) as db:
                self.assertEqual([rows[1]['id'],rows[0]['id']],[r[0] for r in db.execute('select _id from rules_table order by priority,_id')])
                self.assertEqual(sorted(r['id'] for r in rows),[r[0] for r in db.execute('select _id from rules_table order by _id')])

    def test_validation_boundaries_and_editor_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);shutil.copytree(ROOT/'libraries',root/'libraries');shutil.copytree(ROOT/'icons',root/'icons')
            result=subprocess.run([sys.executable,str(ROOT/'tools/rules.py'),'--root',str(root),'check'],capture_output=True,text=True)
            self.assertEqual(0,result.returncode,result.stderr)
            path=next((root/'libraries').glob('*.json'));original=rules.read(path)
            candidate=copy.deepcopy(original);candidate['matchers'][0]['mode']='bad';path.write_bytes(rules.encoded(candidate))
            result=subprocess.run([sys.executable,str(ROOT/'tools/rules.py'),'--root',str(root),'check'],capture_output=True,text=True)
            self.assertEqual(1,result.returncode);self.assertIn('Invalid mode',result.stderr)
            path.write_bytes(rules.encoded(original))
            extra=root/'icons/ic_lib_test_new.svg';extra.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M0 0"/></svg>')
            before=rules.read(root/'icons/index.json')
            with contextlib.redirect_stdout(io.StringIO()):rules.sync_icons(root)
            after=rules.read(root/'icons/index.json')
            self.assertTrue(all(after[k]==v for k,v in before.items()))
            self.assertEqual('ic_lib_test_new',after[str(max(map(int,before))+1)]['iconId'])
            rules.load_source(root)
            incoming=root/'input.svg';incoming.write_text('<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/></svg>')
            with contextlib.redirect_stdout(io.StringIO()):rules.import_icon(root,incoming,'ic_lib_imported',True)
            self.assertTrue((root/'icons/ic_lib_imported.svg').exists())
            self.assertIn(dict(iconId='ic_lib_imported',isSimpleColorIcon=True),rules.read(root/'icons/index.json').values())
            snapshot=(root/'icons/index.json').read_bytes()
            incoming.write_text('<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>')
            with self.assertRaises(ValueError):rules.import_icon(root,incoming,'ic_lib_invalid')
            self.assertEqual(snapshot,(root/'icons/index.json').read_bytes())
            self.assertFalse((root/'icons/ic_lib_invalid.svg').exists())
            self.assertFalse((root/'.rules-edit.lock').exists())
            after['20']['iconId']='ic_lib_test_new';(root/'icons/index.json').write_bytes(rules.encoded(after))
            with self.assertRaises(ValueError):rules.load_source(root)

    def test_vector_import_preserves_indexes_and_rejects_mismatched_svg(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp);shutil.copytree(ROOT/'libraries',root/'libraries');shutil.copytree(ROOT/'icons',root/'icons')
            xml=root/'input.xml'
            raw=b'<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24"><path android:fillColor="#FF0000" android:pathData="M0,0L1,1"/></vector>'
            xml.write_bytes(raw);before=rules.read(root/'icons/index.json')
            rules.import_icon(root,xml,'ic_lib_new_vector',True,vector=True)
            after=rules.read(root/'icons/index.json')
            self.assertTrue(all(after[key]==value for key,value in before.items()))
            new_index=str(max(map(int,before))+1)
            self.assertEqual({'iconId':'ic_lib_new_vector','isSimpleColorIcon':True},after[new_index])
            self.assertEqual(raw,(root/'icons/android/ic_lib_new_vector.xml').read_bytes())
            xml.write_bytes(raw.replace(b'#FF0000',b'#00FF00'))
            rules.import_icon(root,xml,'ic_lib_new_vector',vector=True)
            self.assertEqual(after,rules.read(root/'icons/index.json'))
            self.assertIn(b'#00FF00'.lower(),(root/'icons/ic_lib_new_vector.svg').read_bytes().lower())
            (root/'icons/ic_lib_new_vector.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
            with self.assertRaisesRegex(ValueError,'derived from Android XML'):rules.load_source(root)
            rules.import_icon(root,xml,'ic_lib_new_vector',vector=True)
            snapshot=(root/'icons/index.json').read_bytes()
            xml.write_bytes(raw.replace(b'#FF0000',b'@color/missing'))
            with self.assertRaises(ValueError):rules.import_icon(root,xml,'ic_lib_invalid_vector',vector=True)
            self.assertEqual(snapshot,(root/'icons/index.json').read_bytes())
            self.assertFalse((root/'icons/android/ic_lib_invalid_vector.xml').exists())
            self.assertFalse((root/'.rules-edit.lock').exists())

    def test_regex_and_svg_rejections(self):
        for pattern in ['(?i)abc','(?=x)x',r'(a)\1',r'\p{L}',r'\w+',r'\s+',r'a++','[',r'\#',r'\!',r'foo{bar}',r'foo]',r'[a&&b]']:
            with self.subTest(pattern=pattern),self.assertRaises(ValueError):rules.valid_regex(pattern)
        for body in ['<script/>','<path onload="bad"/>','<path fill="url(https://evil)"/>','<defs><clipPath id="a"><path clip-path="url(#a)"/></clipPath></defs>','<path fill="url(#absent)"/>','<path href="file:///etc/passwd"/>']:
            with self.subTest(body=body),self.assertRaises(ValueError):rules.validate_svg(('<svg xmlns="http://www.w3.org/2000/svg">'+body+'</svg>').encode())
        for path in ['../bad','/tmp/bad','a/../b','a\\b','a//b']:
            with self.assertRaises(ValueError):rules.safe_path(path)

    def test_python_java_javascript_parity(self):
        fixtures=rules.read(ROOT/'tests/matching-fixtures.json')['cases']
        # Include every production regex with real exact names and conservative witnesses.
        patterns=[r for r in self.rows if r['isRegexRule']]
        inputs=['', 'libpython3.so','libSnpeDspV66CalculatorStub.so','libsnpe_dsp_v66_domains_v3_skel.so','😀','库12','bar\n']
        vectors=[]
        for r in patterns:
            witness=r['name'].replace('(.*)','sample').replace(r'\.','.')
            for value in inputs+[witness]:vectors.append([r['name'],value,rules.regex_matches(r['name'],value)])
        for case in fixtures:
            self.assertEqual(case['expected'],rules.find_rule(case['rules'],case['input'],case['type'],case.get('useRegex',True)))
            for r in case['rules']:
                if r['isRegexRule']:vectors.append([r['name'],case['input'],rules.regex_matches(r['name'],case['input'])])
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);data=tmp/'data.json';data.write_text(json.dumps(dict(vectors=vectors,fixtures=fixtures),ensure_ascii=False))
            subprocess.run(['node',str(ROOT/'tests/matching.mjs'),str(data)],check=True)
            tsv=tmp/'vectors.tsv'
            tsv.write_text('\n'.join('\t'.join([base64.b64encode(p.encode()).decode(),base64.b64encode(v.encode()).decode(),str(e).lower()]) for p,v,e in vectors))
            subprocess.run(['javac','-d',str(tmp),str(ROOT/'tests/Matching.java')],check=True)
            subprocess.run(['java','-cp',str(tmp),'Matching',str(tsv)],check=True)

if __name__=='__main__':unittest.main()
