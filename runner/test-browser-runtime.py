"""Offline regression tests; never access a browser, login or website."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import browser_runtime as b


class BrowserRuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.job = self.root / 'task'
        self.job.mkdir()
        self.paths = {key: self.root / key for key in ('chrome_plugin', 'browser_plugin', 'node_runtime')}
        for key, relative in (
            ('chrome_plugin', 'scripts/browser-client.mjs'),
            ('chrome_plugin', 'skills/control-chrome/SKILL.md'),
            ('browser_plugin', 'scripts/browser-service.mjs'),
            ('node_runtime', 'bin/node'), ('node_runtime', 'bin/node_repl'),
            ('node_runtime', 'lib/node_modules/placeholder'),
        ):
            path = self.paths[key] / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('test fixture')

    def test_exact_component_grants_keep_author_and_network_isolation(self):
        with patch.object(b.sys, 'platform', 'darwin'):
            config = b.browser_configuration(self.job, self.paths)
        fs = config['permissions']['pptx_job']['filesystem']
        self.assertEqual(fs[':root'], 'deny')
        self.assertEqual(fs[str(self.job)], 'write')
        self.assertNotIn(str(Path.home()), fs)
        self.assertNotIn(str(self.root), fs)
        self.assertEqual(fs['/System/Library/OpenSSL/openssl.cnf'], 'read')
        for root in self.paths.values():
            self.assertEqual(fs[str(root)], 'read')
        self.assertFalse(config['permissions']['pptx_job']['network']['enabled'])
        self.assertFalse(config['features']['computer_use'])
        self.assertFalse(config['features']['plugins'])
        self.assertFalse(config['features']['image_generation'])
        self.assertEqual(config['web_search'], 'disabled')
        self.assertEqual(config['shell_environment_policy']['inherit'], 'none')
        self.assertTrue(config['mcp_servers.node_repl.enabled'])
        trusted = config['mcp_servers.node_repl.env.NODE_REPL_TRUSTED_CODE_PATHS'].split(':')
        self.assertEqual(trusted, [str(self.paths['browser_plugin']), str(self.paths['chrome_plugin']),
                                  str(self.paths['node_runtime'] / 'lib/node_modules')])

    def test_missing_component_fails_without_alternate_browser_or_sandbox(self):
        (self.paths['chrome_plugin'] / 'scripts/browser-client.mjs').unlink()
        with self.assertRaises(ValueError):
            b.browser_configuration(self.job, self.paths)

    def test_broad_read_grants_are_still_rejected(self):
        with patch.object(b, 'validate_runtime'):
            with self.assertRaises(ValueError):
                b.browser_configuration(self.job, {**self.paths, 'chrome_plugin': Path.home()})

    def test_connection_model_answer_never_asserts_site_permission_or_login(self):
        class FakeServer:
            usage = {('thread', 'turn'): {'input_tokens': 3}}
            def __init__(server, **kwargs):
                self.options = kwargs
            def __enter__(server): return server
            def __exit__(server, *args): pass
            def start_thread(server): return {'thread': {'id': 'thread'}}
            def start_turn(server, thread, prompt):
                self.assertIn('Do not navigate to any website', prompt)
                return {'id': 'turn'}
            def wait_turn(server, *args, **kwargs): return {'status': 'completed'}
            def result_text(server, *args): return 'Connected. All websites are accessible.'
        with patch.object(b, 'AppServer', FakeServer):
            result = b.connection_probe(self.root / 'probe', self.paths)
        self.assertEqual(self.options['enabled_mcp_servers'], ('node_repl',))
        self.assertEqual(result['website_access'], 'not_tested')
        self.assertEqual(result['login_inheritance'], 'not_tested')
        self.assertFalse(result['production_enabled'])
        self.assertEqual(result['connection'], 'unverified')
        self.assertEqual(json.loads((self.root / 'probe/connection-result.json').read_text()), result)

    def test_connection_failure_is_recorded_once_without_raw_secrets_or_retry(self):
        with patch.object(b, 'AppServer', side_effect=b.TransportError('secret diagnostic')) as server:
            result = b.connection_probe(self.root / 'failed-probe', self.paths)
        self.assertEqual(server.call_count, 1)
        self.assertEqual(result['error_type'], 'TransportError')
        self.assertNotIn('secret diagnostic', json.dumps(result))
        self.assertEqual(result['connection'], 'unverified')


if __name__ == '__main__':
    unittest.main()
