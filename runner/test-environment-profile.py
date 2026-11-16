"""Environment boundaries; no production queue, credentials or model calls."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import sys
import unittest
from unittest.mock import patch

from environment_profile import validate
import runner

spec = importlib.util.spec_from_file_location('environment_tool', Path(__file__).parents[1] / 'tools/environment.py')
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class Environments(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.worker = self.root / 'runner'
        self.worker.mkdir()
        self.cfg = {'deployment_environment': 'local', 'site': 'http://127.0.0.1:3000',
                    'token': 'x' * 64, 'python': sys.executable,
                    'plugin': str(self.worker / 'runtime/v1/pptx-agent'),
                    'blank': str(self.root / 'blank.pptx'),
                    'state_directory': str(self.worker / 'state/local')}

    def test_explicit_loopback_http_and_https(self):
        for site in ('http://127.0.0.1:3000', 'https://localhost:443', 'http://[::1]:3000'):
            with self.subTest(site=site):
                self.assertEqual(validate({**self.cfg, 'site': site}, self.worker), 'local')

    def test_local_rejects_hosted_queue_and_ambiguous_urls(self):
        for site in ('https://rickppt.aaarickmorty.chatgpt.site', 'http://127.0.0.1.example',
                     'http://user@localhost:3000', 'http://localhost:3000/api',
                     'http://localhost?token=secret', 'file:///tmp/test', 'http://[::1]:0'):
            with self.subTest(site=site), self.assertRaises(ValueError):
                validate({**self.cfg, 'site': site}, self.worker)

    def test_marker_refuses_unlabelled_and_server_settings(self):
        (self.worker / 'deployment.local.json').write_text('{"environment":"local"}')
        for profile in (None, 'server', 'typo'):
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                validate({**self.cfg, 'deployment_environment': profile}, self.worker)

    def test_paths_cannot_reuse_another_checkout_or_symlink(self):
        outside = self.root / 'other-worker'
        outside.mkdir()
        (self.worker / 'linked').symlink_to(outside, target_is_directory=True)
        for key in ('state_directory', 'plugin'):
            for value in (str(outside), str(self.worker / 'linked/data'), 'relative'):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    validate({**self.cfg, key: value}, self.worker)

    def test_mutable_plugin_and_shared_state_root_refused(self):
        for override in ({'plugin': str(self.root / 'pptx-agent')}, {'state_directory': str(self.worker)}):
            with self.assertRaises(ValueError):
                validate({**self.cfg, **override}, self.worker)

    def test_server_requires_linux_and_hosted_https(self):
        cfg = {**self.cfg, 'deployment_environment': 'server', 'site': 'https://production.example'}
        self.assertEqual(validate(cfg, self.worker, platform='linux'), 'server')
        with self.assertRaises(ValueError):
            validate(cfg, self.worker, platform='darwin')
        for site in ('http://production.example', 'https://localhost'):
            with self.assertRaises(ValueError):
                validate({**cfg, 'site': site}, self.worker, platform='linux')

    def test_legacy_keeps_https_without_profile_or_new_path_fields(self):
        self.assertEqual(validate({'site': 'https://legacy.example'}, self.worker), 'legacy')
        with self.assertRaises(ValueError):
            validate({'site': 'http://localhost:3000'}, self.worker)

    def test_settings_applies_guard_after_environment_overrides(self):
        settings = self.worker / 'settings.local.json'
        settings.write_text(json.dumps(self.cfg))
        with patch.object(runner, 'ROOT', self.worker), patch.dict(os.environ, {
            'PPTX_RUNNER_SETTINGS': str(settings), 'PPTX_RUNNER_STATE_DIRECTORY': str(self.root / 'production')
        }, clear=True), self.assertRaisesRegex(ValueError, 'state_directory'):
            runner.settings()

    def test_pinned_checkout_refuses_foreign_settings(self):
        (self.worker / 'deployment.local.json').write_text('{"environment":"local"}')
        settings = self.root / 'foreign.local.json'
        settings.write_text(json.dumps({**self.cfg, 'deployment_environment': 'server'}))
        with patch.object(runner, 'ROOT', self.worker), patch.dict(os.environ, {
            'PPTX_RUNNER_SETTINGS': str(settings)
        }, clear=True), self.assertRaisesRegex(ValueError, 'environment'):
            runner.settings()

    def initialize(self):
        source = self.root / 'pptx-agent'
        (source / '.codex-plugin').mkdir(parents=True)
        (source / 'skills/pptx/assets').mkdir(parents=True)
        (source / '.codex-plugin/plugin.json').write_text('{"version":"test-v1"}')
        (source / 'skills/pptx/assets/blank.pptx').write_bytes(b'fixture')
        return tool.initialize_local(self.root, Path(sys.executable))

    def test_initialization_private_independent_and_idempotence_safe(self):
        cfg = self.initialize()
        self.assertEqual(cfg['site'], 'http://127.0.0.1:3000')
        self.assertIn('WORKER_TOKEN=' + cfg['token'], (self.root / 'website/.dev.vars').read_text())
        for path in ('runner/settings.local.json', 'runner/deployment.local.json', 'website/.dev.vars'):
            self.assertEqual((self.root / path).stat().st_mode & 0o777, 0o600)
        before = (self.worker / 'settings.local.json').read_bytes()
        with self.assertRaises(ValueError):
            tool.initialize_local(self.root, Path(sys.executable))
        self.assertEqual((self.worker / 'settings.local.json').read_bytes(), before)
        _, report = tool.inspect(self.root, 'local')
        self.assertNotIn(cfg['token'], json.dumps(report))

    def test_launcher_clears_inherited_worker_overrides_and_keeps_ac_policy(self):
        with patch.dict(os.environ, {'PPTX_RUNNER_SETTINGS': '/production',
                                     'PPTX_RUNNER_MODEL_PROFILE': '/production/key',
                                     'PPTX_AUTHOR_CONTEXT_MODE': 'split',
                                     'PPTX_WORKER_AC_ONLY': '0', 'HTTP_PROXY': 'keep-for-models'}, clear=True):
            command, env = tool.local_launch(self.root, self.cfg, True)
        self.assertNotIn('PPTX_RUNNER_SETTINGS', env)
        self.assertNotIn('PPTX_RUNNER_MODEL_PROFILE', env)
        self.assertNotIn('PPTX_AUTHOR_CONTEXT_MODE', env)
        self.assertEqual(env['PPTX_WORKER_AC_ONLY'], '1')
        self.assertIn('127.0.0.1', env['NO_PROXY'])
        self.assertEqual(env['HTTP_PROXY'], 'keep-for-models')
        self.assertIn('--reload', command)

    def test_real_local_transport_ignores_proxy_without_claiming_any_job(self):
        from resilience import request
        seen = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                seen.append((self.path, self.headers.get('Authorization')))
                self.rfile.read(int(self.headers.get('Content-Length', '0')))
                body = b'{"ok":true}'
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass
        server = HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            cfg = {**self.cfg, 'site': 'http://127.0.0.1:' + str(server.server_port)}
            with patch.dict(os.environ, {'http_proxy': 'http://127.0.0.1:1', 'all_proxy': 'http://127.0.0.1:1', 'NO_PROXY': '', 'no_proxy': ''}):
                self.assertEqual(request(cfg, '/test-only?action=heartbeat'), {'ok': True})
            self.assertEqual(seen, [('/test-only?action=heartbeat', 'Bearer ' + cfg['token'])])
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    unittest.main()
