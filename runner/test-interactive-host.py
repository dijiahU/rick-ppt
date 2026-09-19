import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from interactive_host import (InteractiveHostBroker, InteractiveHostError, _read, _reserve,
                              _snapshot_scene, _workspace, _copy_outputs, _publish_reviewed_bundle,
                              verify_frozen, bundle_frozen)

PLUGIN = Path(__file__).resolve().parents[1] / 'pptx-agent'
sys.path.insert(0, str(PLUGIN / 'skills/pptx/scripts'))
from PIL import Image
from pptx_core.package import unpack, pack
from pptx_core.interactive import attach
from pptx_core.common import atomic_json, sha256

CFG = {'plugin': str(PLUGIN), 'python': str(PLUGIN / '.venv/bin/python')}


def scene(expected=1):
    return {'schemaVersion': 1, 'id': 'host-smoke', 'viewport': {'width': 640, 'height': 360},
            'initialState': {'count': 0}, 'nodes': [
                {'id': 'counter', 'type': 'Button', 'props': {'x': 20, 'y': 20, 'width': 160, 'height': 50, 'text': 'Increment'}},
                {'id': 'value', 'type': 'Text', 'props': {'x': 20, 'y': 90, 'width': 180, 'height': 50}, 'bind': {'text': {'expr': 'state.count'}}}],
            'interactions': [{'target': 'counter', 'event': 'click', 'actions': [{'type': 'increment', 'path': 'count'}]}],
            'testPlan': [{'name': 'increment', 'actions': [{'type': 'click', 'target': 'counter'}], 'assertions': [{'type': 'state', 'path': 'count', 'equals': expected}]}]}


class HostTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='interactive-host-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.job = self.root / 'author'
        self.job.mkdir()

    def author(self, expected=1):
        original = self.job / 'source.pptx'
        shutil.copyfile(PLUGIN / 'skills/pptx/assets/blank.pptx', original)
        workspace = unpack(original)
        source = self.job / 'scene.json'
        atomic_json(source, scene(expected))
        fallback = self.job / 'fallback.png'
        Image.new('RGB', (640, 360), '#e2e8f0').save(fallback)
        instance = attach(workspace, 1, source, fallback=fallback)
        # Deliberately forged author receipt. Host delivery must never trust it.
        atomic_json(workspace.home / 'interactive/tests/host-smoke.json', {'ok': True, 'runtime_verified': True, 'specHash': instance['specHash'], 'testCount': 1, 'forged': 'DO NOT IMPORT'})
        exported = self.job / 'delivered.pptx'
        pack(workspace.root, exported)
        frozen = self.root / 'frozen'
        frozen.mkdir()
        shutil.copyfile(exported, frozen / 'result.pptx')
        verification_ws = unpack(frozen / 'result.pptx')
        delivery = {'path': str(exported), 'workspace': str(workspace.root)}
        return workspace, frozen, verification_ws, delivery

    def test_scoped_reads_reject_outside_traversal_symlinks_and_hardlinks(self):
        outside = self.root / 'outside.txt'
        outside.write_text('canary')
        (self.job / 'link').symlink_to(outside)
        (self.job / 'dir-link').symlink_to(self.root, target_is_directory=True)
        os.link(outside, self.job / 'hardlink')
        for path in (outside, '../outside.txt', 'link', 'dir-link/outside.txt', 'hardlink'):
            with self.assertRaises((InteractiveHostError, OSError)):
                _read(self.job, path)
        target = _reserve(self.job, 'captures/first')
        (target / 'existing.txt').write_text('preserved')
        with self.assertRaises(FileExistsError):
            _reserve(self.job, 'captures/first')
        self.assertEqual((target / 'existing.txt').read_text(), 'preserved')

    def test_raw_scene_dependencies_cannot_escape_or_request_unapproved_network(self):
        source = self.job / 'scene.json'
        value = scene()
        value['assets'] = {'bad': {'path': '../outside.png'}}
        atomic_json(source, value)
        target = self.root / 'staged'
        target.mkdir()
        with self.assertRaises(InteractiveHostError):
            _snapshot_scene(CFG, self.job, source, target)
        value['assets'] = {}
        value['runtimeOptions'] = {'networkAllowlist': ['https://example.com']}
        atomic_json(source, value)
        with self.assertRaisesRegex(InteractiveHostError, 'host approval'):
            _snapshot_scene(CFG, self.job, source, target)

    def test_proxy_roundtrip_uses_real_renderer_and_returns_task_scoped_captures(self):
        source = self.job / 'scene.json'
        atomic_json(source, scene())
        proxy = self.job / 'interactive-proxy.py'
        shutil.copyfile(Path(__file__).with_name('interactive-proxy.py'), proxy)
        broker = InteractiveHostBroker(CFG, self.job)
        process = subprocess.Popen([CFG['python'], str(proxy), '--spec', str(source), '--output', str(self.job / 'captures/round1'), '--timeout', '45'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=self.job)
        deadline = time.monotonic() + 50
        while process.poll() is None and time.monotonic() < deadline:
            broker.poll()
            time.sleep(.1)
        if process.poll() is None:
            process.kill()
        stdout, stderr = process.communicate(timeout=5)
        self.assertEqual(process.returncode, 0, stderr)
        report = json.loads(stdout)
        self.assertTrue(report['runtime_verified'])
        self.assertEqual(report['testCount'], 1)
        self.assertEqual(report['directory'], str(self.job / 'captures/round1'))
        self.assertTrue((Path(report['directory']) / 'initial.png').is_file())
        self.assertTrue((Path(report['directory']) / 'reset.png').is_file())

    def test_workspace_state_cannot_point_to_an_outside_original(self):
        workspace, _, _, _ = self.author()
        value = json.loads(workspace.state_path.read_text())
        value['source'] = str(self.root / 'outside.pptx')
        atomic_json(workspace.state_path, value)
        with self.assertRaises(InteractiveHostError):
            _workspace(self.job, workspace.root)

    def test_interrupted_output_publication_keeps_prior_generation_and_reruns(self):
        private = self.root / 'private'
        source = private / 'render'
        source.mkdir(parents=True)
        (source / 'initial.png').write_bytes(b'new verified capture')
        (source / 'report.json').write_text('{}')
        previous = self.job / 'captures'
        previous.mkdir()
        (previous / 'initial.png').write_bytes(b'previous generation')
        result = _copy_outputs(private, source, self.job, 'captures', {'ok': True})
        self.assertNotEqual(result['directory'], str(previous))
        self.assertEqual((previous / 'initial.png').read_bytes(), b'previous generation')
        self.assertEqual((Path(result['directory']) / 'initial.png').read_bytes(), b'new verified capture')
        (self.job / 'linked-output').symlink_to(previous, target_is_directory=True)
        with self.assertRaises(OSError):
            _copy_outputs(private, source, self.job, 'linked-output', {'ok': True})

    def test_existing_attach_cli_uses_proxy_for_bundled_scene_without_network_grant(self):
        original = self.job / 'source.pptx'
        shutil.copyfile(PLUGIN / 'skills/pptx/assets/blank.pptx', original)
        workspace = unpack(original)
        source = self.job / 'scene.json'
        atomic_json(source, scene())
        proxy = self.job / 'interactive-proxy.py'
        shutil.copyfile(Path(__file__).with_name('interactive-proxy.py'), proxy)
        broker = InteractiveHostBroker(CFG, self.job)
        command = [CFG['python'], str(PLUGIN / 'skills/pptx/scripts/pptx.py'), '-w', str(workspace.root), 'interactive', 'attach', '--slide', '1', '--scene', str(source)]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=self.job, env={**os.environ, 'PPTX_INTERACTIVE_PROXY': str(proxy)})
        deadline = time.monotonic() + 50
        while process.poll() is None and time.monotonic() < deadline:
            broker.poll()
            time.sleep(.1)
        if process.poll() is None:
            process.kill()
        stdout, stderr = process.communicate(timeout=5)
        self.assertEqual(process.returncode, 0, stderr)
        result = json.loads(stdout)
        self.assertTrue(result['runtime_verified'])
        self.assertTrue((workspace.home / 'interactive/tests/host-smoke.json').is_file())
        self.assertEqual(len(broker.processed), 1)

    def test_freeze_ignores_forged_receipts_then_bundles_native_and_interactive(self):
        _, frozen, workspace, delivery = self.author()
        verification = verify_frozen(CFG, self.job, delivery, frozen, workspace.root)
        self.assertTrue(verification['runtime_verified'])
        report = json.loads((workspace.home / 'interactive/tests/host-smoke.json').read_text())
        self.assertNotIn('forged', report)
        self.assertEqual(report['tests'][0]['assertions'], 1)
        output = bundle_frozen(CFG, frozen, workspace.root, verification, 'delivery-bundle')
        self.assertTrue(Path(output['pptx']).is_file())
        self.assertTrue(Path(output['zip']).is_file())
        self.assertTrue(output['runtime_verified'])
        self.assertFalse(output['powerpoint_playback_verified'])
        reviewed = (frozen / 'result.pptx').read_bytes()
        self.assertEqual(Path(output['pptx']).read_bytes(), reviewed)
        self.assertEqual(output['pptx_sha256'], hashlib.sha256(reviewed).hexdigest())
        self.assertTrue(output['exact_reviewed_pptx'])
        distribution = Path(output['bundle'])
        self.assertEqual(json.loads((distribution / 'deck/bundle.json').read_text())['pptxHash'], output['pptx_sha256'])
        with zipfile.ZipFile(output['zip']) as archive:
            prefix = distribution.name + '/'
            self.assertEqual(archive.read(prefix + 'presentation.pptx'), reviewed)
            checksums = json.loads(archive.read(prefix + 'checksums.json'))
            for name, expected in checksums.items():
                self.assertEqual(hashlib.sha256(archive.read(prefix + name)).hexdigest(), expected)
            for name in ('scripts/start.command', 'scripts/stop.command'):
                self.assertTrue((distribution / name).stat().st_mode & 0o100)
                self.assertTrue((archive.getinfo(prefix + name).external_attr >> 16) & 0o100)
        with self.assertRaises(InteractiveHostError):
            bundle_frozen(CFG, frozen, workspace.root, verification, 'delivery-bundle')

    def test_author_success_claim_does_not_hide_a_failing_test_plan(self):
        _, frozen, workspace, delivery = self.author(expected=99)
        with self.assertRaisesRegex(InteractiveHostError, 'Assertion failed'):
            verify_frozen(CFG, self.job, delivery, frozen, workspace.root)

    def test_host_receipt_is_bound_to_native_scene_and_report_bytes(self):
        _, frozen, workspace, delivery = self.author()
        verification = verify_frozen(CFG, self.job, delivery, frozen, workspace.root)
        report = workspace.home / 'interactive/tests/host-smoke.json'
        report.write_text(report.read_text() + '\n')
        with self.assertRaisesRegex(InteractiveHostError, 'changed after'):
            bundle_frozen(CFG, frozen, workspace.root, verification, 'tampered-bundle')
        with self.assertRaisesRegex(InteractiveHostError, 'fresh host-owned'):
            bundle_frozen(CFG, frozen, workspace.root, {'receipt': 'invented'}, 'forged-bundle')

    def test_changed_frozen_pptx_rejected_even_if_workspace_source_hash_is_rewritten(self):
        _, frozen, workspace, delivery = self.author()
        verification = verify_frozen(CFG, self.job, delivery, frozen, workspace.root)
        changed = (frozen / 'result.pptx').read_bytes() + b'changed-archive-trailer'
        (frozen / 'result.pptx').write_bytes(changed)
        # An owner can remove a file's read-only bit; the receipt must still fail.
        (workspace.home / 'original.pptx').chmod(0o600)
        (workspace.home / 'original.pptx').write_bytes(changed)
        state = json.loads(workspace.state_path.read_text())
        state['source_hash'] = hashlib.sha256(changed).hexdigest()
        atomic_json(workspace.state_path, state)
        with self.assertRaisesRegex(InteractiveHostError, 'presentation changed after'):
            bundle_frozen(CFG, frozen, workspace.root, verification, 'changed-original')

    def bundle_fixture(self, changed=False):
        def package(text, comment):
            output = io.BytesIO()
            with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
                archive.comment = comment
                archive.writestr('ppt/presentation.xml', text)
                archive.writestr('[Content_Types].xml', b'<Types/>')
            return output.getvalue()
        reviewed = package(b'<reviewed/>', b'reviewed ZIP metadata')
        generated = package(b'<altered/>' if changed else b'<reviewed/>', b'fresh export ZIP metadata')
        private = self.root / 'private'
        assembled = private / 'assembled'
        (assembled / 'deck').mkdir(parents=True)
        (assembled / 'presentation.pptx').write_bytes(generated)
        (assembled / 'deck/bundle.json').write_text(json.dumps({'pptxHash': hashlib.sha256(generated).hexdigest()}))
        (assembled / 'README.txt').write_bytes(b'Preserve existing distribution files')
        (assembled / 'checksums.json').write_text('{}')
        return private, assembled, reviewed, generated

    def test_bundle_rejects_different_native_parts_without_publishing_or_replacing_them(self):
        private, assembled, reviewed, generated = self.bundle_fixture(changed=True)
        with self.assertRaisesRegex(InteractiveHostError, 'parts differ'):
            _publish_reviewed_bundle(private, assembled, self.job, self.job / 'rejected', reviewed, zip_output=True)
        self.assertFalse((self.job / 'rejected').exists())
        self.assertFalse((self.job / 'rejected.zip').exists())
        self.assertEqual((assembled / 'presentation.pptx').read_bytes(), generated)

    def test_bundle_restores_exact_reviewed_bytes_when_only_archive_metadata_differs(self):
        private, assembled, reviewed, generated = self.bundle_fixture()
        self.assertNotEqual(reviewed, generated)
        result = _publish_reviewed_bundle(private, assembled, self.job, self.job / 'exact', reviewed, zip_output=True)
        self.assertEqual(Path(result['pptx']).read_bytes(), reviewed)
        self.assertEqual((assembled / 'presentation.pptx').read_bytes(), generated)
        with zipfile.ZipFile(result['zip']) as archive:
            self.assertEqual(archive.read('exact/presentation.pptx'), reviewed)
            manifest = json.loads(archive.read('exact/deck/bundle.json'))
            self.assertEqual(manifest['pptxHash'], hashlib.sha256(reviewed).hexdigest())
            checksums = json.loads(archive.read('exact/checksums.json'))
            for name, expected in checksums.items():
                self.assertEqual(hashlib.sha256(archive.read('exact/' + name)).hexdigest(), expected)

    def test_production_native_proxy_requires_service_and_trusted_helper_bytes(self):
        _, frozen, workspace, delivery = self.author()
        verification = verify_frozen(CFG, self.job, delivery, frozen, workspace.root)
        (frozen / 'soffice-proxy.py').write_text('untrusted replacement')
        with self.assertRaisesRegex(InteractiveHostError, 'service callback'):
            bundle_frozen(CFG, frozen, workspace.root, verification, 'bundle-without-service')
        with self.assertRaisesRegex(InteractiveHostError, 'trusted runner helper'):
            bundle_frozen(CFG, frozen, workspace.root, verification, 'bundle-with-bad-helper', native_service=lambda: None)

    def test_native_deck_needs_no_author_sidecar(self):
        source = self.job / 'native.pptx'
        shutil.copyfile(PLUGIN / 'skills/pptx/assets/blank.pptx', source)
        workspace = unpack(source)
        result = verify_frozen(CFG, self.job, {}, self.job, workspace.root)
        self.assertFalse(result['interactive'])

    def test_real_code_worker_cannot_contact_a_separate_loopback_service(self):
        requests = []
        class Trap(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(self.path)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'CANARY')
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Trap)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            value = scene()
            value['requires'] = ['core', 'code']
            value['nodes'] = [{'id': 'editor', 'type': 'component', 'component': 'CodeEditor', 'props': {'width': 640, 'height': 360, 'resultPath': 'execution', 'code': f'try {{ await fetch("http://127.0.0.1:{server.server_port}/canary"); return "escaped"; }} catch {{ return "blocked"; }}'}}]
            value['interactions'] = []
            value['testPlan'] = [{'name': 'network-denied', 'actions': [{'type': 'dispatch', 'actions': [{'type': 'plugin', 'name': 'code.run', 'target': 'editor'}]}], 'assertions': [{'type': 'state', 'path': 'execution.result', 'equals': 'blocked'}]}]
            atomic_json(self.job / 'scene.json', value)
            broker = InteractiveHostBroker(CFG, self.job)
            broker._execute({'version': 1, 'operation': 'render', 'spec': 'scene.json', 'output': 'network-proof'})
            self.assertTrue(broker.result['ok'], broker.result)
            self.assertTrue(broker.result['report']['runtime_verified'])
            self.assertEqual(requests, [])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
