import copy
import json
import re
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
