#!/usr/bin/env python3
"""One-time migration proof against the retained v4 baseline, not a future CI gate."""
import contextlib
import json
import sqlite3
import unittest
import rules
ROOT=rules.ROOT

class MigrationAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows,cls.common,cls.legacy,cls.digest=rules.load_source()

    def test_migration_no_loss(self):
        with contextlib.closing(sqlite3.connect(ROOT/'cloud/rules/v4/rules.db')) as db:
            original=db.execute('select * from rules_table order by _id').fetchall()
        actual=[(r['id'],r['name'],r['label'],r['type'],r['iconIndex'],int(r['isRegexRule']),r['regexName']) for r in sorted(self.rows,key=lambda r:r['id'])]
        self.assertEqual(original,actual)
        for p in ROOT.glob('*-libs/**/*.json'):
            self.assertEqual(json.loads(p.read_text()),json.loads(self.legacy[str(p.relative_to(ROOT))]))
        audit=rules.read(ROOT/'docs/migration-audit.json')
        self.assertEqual(119,len(audit['missingDescriptions']))
        self.assertEqual(17,len(audit['divergentDetailUUIDs']))
        self.assertEqual(32,len(audit['unreferencedDescriptions']))
        self.assertEqual(119,sum(r['detailPath'] is None for r in self.rows))
        for row in self.rows:
            self.assertEqual(row['id'],rules.find_rule(self.rows,row['name'],row['type']))
        self.assertEqual(2832,len(self.rows))

if __name__=='__main__':unittest.main()
