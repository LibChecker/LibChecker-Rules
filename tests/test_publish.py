from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import publish_rules


class PublishTest(unittest.TestCase):
    def test_local_remote_legacy_update_noop_and_interrupted_retry(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()):
            tmp=Path(tmp);source=tmp/'source';source.mkdir();remote=tmp/'remote.git'
            for directory in ('libraries','icons','docs'):
                shutil.copytree(ROOT/directory,source/directory)
            (source/'tools').mkdir()
            for name in ('rules.py','android_vectors.py','vector_import.py'):
                shutil.copyfile(ROOT/'tools'/name,source/'tools'/name)
            git=lambda *args: publish_rules.git(source,*args)
            git('init','-b','v4');git('config','gc.auto','0');git('config','user.name','Test');git('config','user.email','test@example.invalid')
            git('add','.');git('commit','-m','Initial canonical source')
            subprocess.run(['git','clone','--quiet','--no-local','--bare',str(source),str(remote)],check=True)
            with self.assertRaisesRegex(ValueError,'First publication requires'):
                publish_rules.publish(source,str(remote))
            publish_rules.publish(source,str(remote),bootstrap_source_revision=git('rev-parse','HEAD'))
            show=lambda ref:json.loads(subprocess.check_output(['git','--git-dir',str(remote),'show',ref],text=True))
            first=show('rules-data:manifest.json')
            self.assertEqual(45,first['dataVersion'])
            tree=subprocess.check_output(['git','--git-dir',str(remote),'ls-tree','--name-only','rules-data'],text=True).splitlines()
            self.assertEqual(['manifest.json','releases'],tree)
            self.assertEqual(45,show('v4:cloud/md5/v4')['version'])
            self.assertEqual(45,show('v4:rule-counts.json')['rulesVersion'])
            self.assertEqual(first,show('rules-data:releases/45/manifest.json'))
            self.assertEqual(git('rev-parse','HEAD'),first['sourceRevision'])
            publish_rules.publish(source,str(remote),bootstrap_source_revision=git('rev-parse','HEAD'))
            self.assertEqual(first,show('rules-data:manifest.json'))
            git('fetch',str(remote),'v4');git('merge','--ff-only','FETCH_HEAD')
            file=source/'libraries/AEF9680F-4A43-4EDC-A5B8-8119D23BCD21.json'
            value=json.loads(file.read_text());value['matchers'][0]['label']='Updated label';file.write_text(json.dumps(value))
            git('add','.');git('commit','-m','Change label');git('push',str(remote),'HEAD:refs/heads/v4')
            original=publish_rules.commit_push
            def interrupted(root,message,branch):
                if branch=='v4':raise RuntimeError('simulated interruption')
                original(root,message,branch)
            with patch.object(publish_rules,'commit_push',interrupted),self.assertRaises(RuntimeError):publish_rules.publish(source,str(remote),bootstrap_source_revision=git('rev-parse','HEAD'))
            self.assertEqual(first,show('rules-data:manifest.json'))
            staged=show('rules-data:releases/46/manifest.json')
            publish_rules.publish(source,str(remote),bootstrap_source_revision=git('rev-parse','HEAD'))
            self.assertEqual(staged,show('rules-data:manifest.json'))
            self.assertEqual(46,show('v4:cloud/md5/v4')['version'])
            self.assertEqual(first,show('rules-data:releases/45/manifest.json'))
            # A newer remote source must not be overwritten by an older build.
            git('fetch',str(remote),'v4');git('merge','--ff-only','FETCH_HEAD')
            value['matchers'][0]['label']='Unpublished local change';file.write_text(json.dumps(value))
            git('add','.');git('commit','-m','Local source ahead of remote')
            with self.assertRaisesRegex(ValueError,'inputs changed'):publish_rules.publish(source,str(remote),bootstrap_source_revision=git('rev-parse','HEAD'))
            self.assertEqual(staged,show('rules-data:manifest.json'))


if __name__=='__main__':unittest.main()
