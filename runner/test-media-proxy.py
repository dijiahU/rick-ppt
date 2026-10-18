"""Task client integration: prepare without blocking, then consume host replies."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import runner


class ClientTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.queue = self.root / 'media-requests'
        self.queue.mkdir()
        self.script = self.root / 'web-media-proxy.py'
        shutil.copyfile(Path(__file__).with_name('web-media-proxy.py'), self.script)

    def call(self, *args, check=True):
        return subprocess.run([sys.executable, str(self.script), *args], capture_output=True,
                              text=True, timeout=3, check=check)

    def test_submit_returns_before_host_and_batch_status_preserves_each_result(self):
        ids = []
        for purpose in ('later page photo', 'later page detail'):
            value = json.loads(self.call('https://example.test/file.png', '--source-page',
                'https://example.test/work', '--purpose', purpose, '--submit-only').stdout)
            self.assertEqual(value['status'], 'pending')
            ids.append(value['id'])
        pending = json.loads(self.call('--status', *ids).stdout)['requests']
        self.assertEqual([x['status'] for x in pending], ['pending', 'pending'])
        for ident, purpose in zip(ids, ('later page photo', 'later page detail')):
            request = json.loads((self.queue / (ident + '.request.json')).read_text())
            self.assertEqual(request['purpose'], purpose)
        (self.queue / (ids[0] + '.reply.json')).write_text(json.dumps(
            {'ok': True, 'path': 'assets/web-first-media.png', 'purpose': 'later page photo'}))
        (self.queue / (ids[1] + '.reply.json')).write_text(json.dumps(
            {'ok': False, 'error_code': 'not_media', 'error': 'Use a direct file URL'}))
        ready = json.loads(self.call('--status', *ids).stdout)['requests']
        self.assertEqual([x['status'] for x in ready], ['ready', 'failed'])
        self.assertEqual(ready[0]['purpose'], 'later page photo')
        self.assertEqual(ready[1]['error_code'], 'not_media')
        self.assertEqual(len(list(self.queue.glob('*.request.json'))), 2)

    def test_status_rejects_paths_and_symlink_replies(self):
        self.assertNotEqual(self.call('--status', '../private', check=False).returncode, 0)
        outside = self.root / 'private.txt'
        outside.write_text('private-material-must-not-be-output')
        (self.queue / ('a' * 32 + '.reply.json')).symlink_to(outside)
        result = self.call('--status', 'a' * 32, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(outside.read_text(), result.stdout)

    def test_local_and_api_bootstrap_and_refresh_preserve_prepared_material(self):
        seed=self.root/'blank.pptx';seed.write_bytes(b'bootstrap-only-native-seed')
        for profile in (None, {'model':'external-test-model','base_url':'https://example.test/v1',
                'api_key':'unit-private-not-propagated','wire_api':'responses','auxiliary_tools':'existing_backend'}):
            cfg={'blank':str(seed),'plugin':str(self.root/'plugin')}
            if profile:cfg['_model_profile']=profile
            with patch.object(runner,'prepare_fonts'):
                job=runner.prepare(cfg)
                self.addCleanup(shutil.rmtree,job)
                caps=json.loads((job/'capabilities.json').read_text())
                self.assertEqual(caps['material_prefetch']['page_authoring'],'single-main-author-in-order')
                self.assertTrue((job/'prefetch-proxy.py').is_file())
                self.assertTrue((job/'prefetch-requests').is_dir())
                self.assertNotIn('unit-private-not-propagated',json.dumps(caps))
                (job/'PREFETCH.md').write_text('retained-old-guide')
                (job/'material-prefetch/evidence.txt').write_text('retained-prepared-evidence')
                runner.refresh_support(cfg,job)
            self.assertEqual((job/'material-prefetch/evidence.txt').read_text(),'retained-prepared-evidence')
            backups=list((job/'support-versions').glob('*/PREFETCH.md'))
            self.assertEqual(len(backups),1)
            self.assertEqual(backups[0].read_text(),'retained-old-guide')
            self.assertEqual((job/'PREFETCH.md').read_bytes(),Path(__file__).with_name('PREFETCH.md').read_bytes())


if __name__ == '__main__':
    unittest.main()
