import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import replace_v46


class ReplacementAuthorizationTest(unittest.TestCase):
    def test_exact_old_bytes_version_source_and_consumed_authorization(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = root / 'source'; data = root / 'data'
            source.mkdir(); (data / 'releases/46').mkdir(parents=True)
            artifact = b'original archive'
            (data / 'releases/46/android-v5.zip').write_bytes(artifact)
            manifest = dict(dataVersion=46, artifacts={'android':dict(path='releases/46/android-v5.zip',size=len(artifact),sha256=hashlib.sha256(artifact).hexdigest())})
            raw = json.dumps(manifest).encode()
            (data / 'manifest.json').write_bytes(raw); (data / 'releases/46/manifest.json').write_bytes(raw)
            def git(checkout, *args):
                if args == ('status', '--porcelain'): return ''
                return 'source-sha' if checkout == source else replace_v46.OLD_DATA_REVISION
            with patch.object(replace_v46, 'OLD_MANIFEST_SHA256', hashlib.sha256(raw).hexdigest()), patch.object(replace_v46, 'git', side_effect=git), patch.object(replace_v46.rules, 'load_source', return_value=(None,None,None,replace_v46.NEW_CONTENT_SHA256)), patch.object(replace_v46.rules, 'compiler_revision', return_value=replace_v46.COMPILER_REVISION):
                self.assertEqual(manifest, replace_v46.authorize(source, data, 'source-sha'))
                with self.assertRaisesRegex(ValueError, 'Exact committed'): replace_v46.authorize(source, data, 'wrong-source')
                with patch.object(replace_v46, 'OLD_DATA_REVISION', 'consumed-sha'):
                    # Simulate observed remote revision differing from the pinned old SHA.
                    with patch.object(replace_v46, 'git', side_effect=lambda checkout,*args: '' if args==('status','--porcelain') else ('source-sha' if checkout==source else 'old-sha')):
                        with self.assertRaisesRegex(ValueError, 'consumed'): replace_v46.authorize(source,data,'source-sha')
                with patch.object(replace_v46.rules, 'load_source', return_value=(None,None,None,'wrong-content')):
                    with self.assertRaisesRegex(ValueError, 'new content'): replace_v46.authorize(source,data,'source-sha')
                with patch.object(replace_v46.rules, 'compiler_revision', return_value='wrong-compiler'):
                    with self.assertRaisesRegex(ValueError, 'compiler'): replace_v46.authorize(source,data,'source-sha')
                (data / 'releases/46/android-v5.zip').write_bytes(b'corrupted')
                with self.assertRaisesRegex(ValueError, 'artifact'): replace_v46.authorize(source,data,'source-sha')
                (data / 'manifest.json').write_bytes(raw+b' ')
                with self.assertRaisesRegex(ValueError, 'manifest checksum'): replace_v46.authorize(source,data,'source-sha')
                manifest['dataVersion']=47;raw=json.dumps(manifest).encode();(data/'manifest.json').write_bytes(raw)
                with patch.object(replace_v46,'OLD_MANIFEST_SHA256',hashlib.sha256(raw).hexdigest()):
                    with self.assertRaisesRegex(ValueError,'restricted to V46'):replace_v46.authorize(source,data,'source-sha')
