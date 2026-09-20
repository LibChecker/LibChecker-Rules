import copy
import json
import re
import tempfile
from unittest.mock import patch
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import build_indexes
import validate


class IndexTest(unittest.TestCase):
    def test_real_indexes_and_staged_definitions(self):
        build_indexes.build(check=True)
        for sdk,(_,key) in build_indexes.SOURCES.items():
            candidate=build_indexes.ROOT/'candidates'/sdk/'definition.json'
            definition=json.loads(candidate.read_text())
            validate.validate_definition(candidate,definition)
            schema=json.loads((build_indexes.ROOT/'schemas/definition-v2.schema.json').read_text())['$defs']['lookup']
            self.assertNotIn('path_template',schema['required'])
            self.assertRegex(definition['lookups'][0]['index_path'],schema['properties']['index_path']['pattern'])
            index=json.loads((build_indexes.ROOT/'sdks'/sdk/'data/index.json').read_text())
            self.assertTrue(index['entries'])
            value=index['entries'][0][key]
            lookup=definition['lookups'][0]
            self.assertNotIn(value,lookup['index_path'])
            self.assertNotIn('{value}',lookup['index_path'])
            matches=[entry for entry in index['entries'] if entry[lookup['expected_field']]==value]
            self.assertTrue(matches[0][lookup['items_field']])
            active=json.loads((build_indexes.ROOT/'sdks'/sdk/'definition.json').read_text())
            self.assertIn('path_template',active['lookups'][0])
            bad=copy.deepcopy(definition);bad['lookups'][0]['index_path']='sdk-details/{value}.json'
            with self.assertRaises(ValueError):validate.validate_definition(candidate,bad)

    def test_refresh_repairs_index_after_provider_data_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            sdk=root/'sdks/flutter';(sdk/'data/engine').mkdir(parents=True)
            (sdk/'definition.json').write_text(json.dumps({'lookups':[]}))
            (sdk/'data/engine/first.json').write_text(json.dumps({'engine':'first','releases':[]}))
            original_outputs=build_indexes.outputs
            with patch.object(build_indexes,'SOURCES',{'flutter':('engine','engine')}), patch.object(build_indexes,'outputs',lambda:original_outputs(root)):
                build_indexes.build()
                build_indexes.build(check=True)
                (sdk/'data/engine/second.json').write_text(json.dumps({'engine':'second','releases':[]}))
                with self.assertRaisesRegex(ValueError,'Stale SDK index'):
                    build_indexes.build(check=True)
                build_indexes.build()
                build_indexes.build(check=True)
                index=sdk/'data/index.json';before=index.read_bytes()
                self.assertEqual(['first','second'],[entry['engine'] for entry in json.loads(before)['entries']])
                build_indexes.build()
                self.assertEqual(before,index.read_bytes())
