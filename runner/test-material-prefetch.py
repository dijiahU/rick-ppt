"""Real queue/files/PNG/concurrency checks, with a bounded fake hosted backend."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import patch
from PIL import Image

import material_prefetch as m


def png(color='royalblue'):
    stream = io.BytesIO()
    Image.new('RGB', (24, 18), color).save(stream, format='PNG')
    return stream.getvalue()


class FakeTools:
    entered = []
    lock = threading.Lock()
    release = None
    barrier = None
    generation_count = 1
    unsafe_file = False
    calls = []

    def __init__(self, cfg, job, *, importer, tick):
        self.cfg, self.job, self.tick = cfg, job, tick
        self.calls = []

    def handle(self, value):
        with self.lock:
            self.entered.append((threading.get_ident(), self.job, self.cfg, value))
        if self.barrier:
            self.barrier.wait(timeout=3)
        while self.release is not None and not self.release.is_set():
            self.tick()
            time.sleep(.005)
        self.tick()
        output = {'text': 'Inspected the original diagram at https://example.org/original; '
                          'blue indicates the input, only this page was inspected.',
                  'model': 'fake-hosted-tool', 'files': []}
        if value['tool'] == 'pptx_generate_image':
            for index in range(self.generation_count):
                body = png('royalblue' if index % 2 == 0 else 'coral')
                name = 'generated-exec-' + str(index).zfill(8) + '-0000-0000-0000-000000000000.png'
                (self.job / 'assets' / name).write_bytes(body)
                output['files'].append({'file': '../outside.png' if self.unsafe_file else name,
                                        'sha256': hashlib.sha256(body).hexdigest()})
        self.calls.append({'seconds': .01, 'tool': value['tool']})
        return {'success': True, 'contentItems': [{'type': 'inputText', 'text': json.dumps(output)}]}


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.job = Path(self.temp.name).resolve()
        (self.job / 'assets').mkdir()
        self.write('assets/index.json', {'images': []})
        self.write('request.json', {'brief': 'Two original editable pages', 'pages': 2})
        self.outline = {'title': 'Example', 'purpose': 'Explain', 'style': 'Quiet editorial',
                        'slides': [{'id': 'one', 'title': 'First', 'summary': 'Inputs'},
                                   {'id': 'two', 'title': 'Second', 'summary': 'Outputs'}]}
        self.write('outline.json', self.outline)
        self.plan = {'version': 3, 'task': {'research': 'topic_research'},
                     'design_direction': 'One coherent narrative',
                     'pages': [{'id': ident, 'form': 'original_illustration', 'assets': [
                         {'route': 'generate', 'kind': 'illustrative', 'status': 'planned', 'file': None,
                          'origin': 'A conceptual example'}]} for ident in ('one', 'two')]}
        self.write('decision-plan.json', self.plan)
        self.write('capabilities.json', {'web_search': {'mode': 'live'}, 'image_generation': {'mode': 'built-in'}})
        FakeTools.entered = []
        FakeTools.release = None
        FakeTools.barrier = None
        FakeTools.generation_count = 1
        FakeTools.unsafe_file = False
        self.backend = patch.object(m, 'AuxiliaryTools', FakeTools)
        self.backend.start()
        self.addCleanup(self.backend.stop)
        self.brokers = []
        self.addCleanup(self.cleanup_brokers)

    def cleanup_brokers(self):
        if FakeTools.release:
            FakeTools.release.set()
        for broker in self.brokers:
            broker.close()
        for broker in self.brokers:
            for future, _ in broker.pending.values():
                try:
                    future.result(timeout=3)
                except Exception:
                    pass

    def write(self, path, value):
        (self.job / path).write_text(json.dumps(value))

    def broker(self, **kwargs):
        broker = m.MaterialPrefetchBroker({'_model_profile': {'api_key': 'DO-NOT-COPY'},
                                           'token': 'PRIVATE', 'default_model': 'fake-default'}, self.job, **kwargs)
        self.brokers.append(broker)
        return broker

    def request(self, kind='search', page='one', **extra):
        return {'kind': kind, 'request': 'Inspect the original relevant example',
                'purpose': 'Prepare evidence for the next page', 'page_ids': [page], **extra}

    def ready(self, broker, ident):
        until = time.monotonic() + 3
        while time.monotonic() < until:
            broker.poll()
            result = broker.get(ident)
            if result['state'] not in ('queued', 'running'):
                return result
            time.sleep(.005)
        self.fail('Fake hosted work did not finish')

    def cli(self, *args):
        shutil.copyfile(Path(__file__).with_name('prefetch-proxy.py'), self.job / 'prefetch-proxy.py')
        result = subprocess.run([sys.executable, str(self.job / 'prefetch-proxy.py'), *args],
                                text=True, capture_output=True, timeout=3)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_two_workers_overlap_while_owner_keeps_authoring(self):
        broker = self.broker()
        FakeTools.barrier = threading.Barrier(2)
        FakeTools.release = threading.Event()
        first = broker.submit(self.request())['id']
        second = broker.submit(self.request(page='two'))['id']
        start = time.monotonic()
        broker.poll()
        self.assertLess(time.monotonic() - start, .5)
        until = time.monotonic() + 2
        while len(FakeTools.entered) < 2 and time.monotonic() < until:
            time.sleep(.005)
        self.assertEqual(len(FakeTools.entered), 2)
        # The main author can write a page while both auxiliaries are blocked.
        (self.job / 'author-page-marker.txt').write_text('page one is still being authored')
        self.assertEqual(broker.get(first)['state'], 'running')
        self.assertEqual(broker.get(second)['state'], 'running')
        self.assertNotEqual(FakeTools.entered[0][0], threading.get_ident())
        self.assertNotEqual(FakeTools.entered[0][0], FakeTools.entered[1][0])
        self.assertNotEqual(FakeTools.entered[0][1], FakeTools.entered[1][1])
        for _, stage, cfg, _ in FakeTools.entered:
            self.assertFalse(stage.is_relative_to(self.job))
            self.assertNotIn('DO-NOT-COPY', json.dumps(cfg))
            self.assertNotIn('PRIVATE', json.dumps(cfg))
        FakeTools.release.set()
        self.assertEqual(self.ready(broker, first)['state'], 'ready')
        self.assertEqual(self.ready(broker, second)['state'], 'ready')

    def test_result_preserves_source_and_is_not_author_acceptance(self):
        broker = self.broker()
        ident = broker.submit(self.request())['id']
        result = self.ready(broker, ident)
        self.assertEqual(result['state'], 'ready')
        self.assertIn('https://example.org/original', result['result']['text'])
        self.assertIn('only this page', result['result']['text'])
        self.assertEqual(result['result']['author_inspection'], 'not_yet_inspected_or_selected')
        self.assertEqual(m.digest(result['result']), result['result_sha256'])

    def test_duplicate_and_restart_reuse_ready_without_new_work(self):
        broker = self.broker()
        ident = broker.submit(self.request())['id']
        self.assertEqual(broker.submit(self.request())['id'], ident)
        self.assertEqual(self.ready(broker, ident)['state'], 'ready')
        broker.close()
        resumed = self.broker()
        self.assertEqual(resumed.get(ident)['state'], 'ready')
        self.assertEqual(resumed.submit(self.request())['id'], ident)
        resumed.poll()
        self.assertEqual(len(FakeTools.entered), 1)

    def test_running_restart_is_interrupted_and_requires_explicit_retry(self):
        broker = self.broker()
        FakeTools.release = threading.Event()
        ident = broker.submit(self.request())['id']
        broker.poll()
        broker.close()
        resumed = self.broker()
        self.assertEqual(resumed.get(ident)['state'], 'interrupted')
        self.assertEqual(resumed.submit(self.request())['id'], ident)
        resumed.poll()
        self.assertFalse(resumed.pending)
        retry = resumed.submit(self.request(retry_of=ident))['id']
        self.assertNotEqual(retry, ident)
        FakeTools.release.set()
        self.assertEqual(self.ready(resumed, retry)['state'], 'ready')

    def test_only_target_page_changes_stale_the_result(self):
        broker = self.broker()
        ident = broker.submit(self.request())['id']
        self.assertEqual(self.ready(broker, ident)['state'], 'ready')
        self.outline['slides'][1]['summary'] = 'Unrelated updated page'
        self.write('outline.json', self.outline)
        self.plan['pages'][1]['form'] = 'diagram'
        self.write('decision-plan.json', self.plan)
        self.assertEqual(broker.get(ident)['state'], 'ready')
        self.outline['slides'][0]['summary'] = 'Actual target content changed'
        self.write('outline.json', self.outline)
        self.assertEqual(broker.get(ident)['state'], 'stale')

    def test_style_selection_and_real_input_revision_invalidate_but_chat_does_not(self):
        revision = [0]
        broker = self.broker(input_revision=lambda: revision[0])
        ident = broker.submit(self.request())['id']
        self.ready(broker, ident)
        self.write('conversation-inputs-chat.json', {'kind': 'chat', 'text': 'How is it going?'})
        self.assertEqual(broker.get(ident)['state'], 'ready')
        revision[0] = 1
        self.assertEqual(broker.get(ident)['state'], 'stale')
        new = broker.submit(self.request())['id']
        self.ready(broker, new)
        self.plan['pages'][0]['assets'][0]['route'] = 'supplied'
        self.write('decision-plan.json', self.plan)
        self.assertEqual(broker.get(new)['state'], 'stale')

    def test_supplied_only_and_unselected_generation_are_rejected_before_work(self):
        broker = self.broker()
        self.plan['task']['research'] = 'supplied_only'
        self.write('decision-plan.json', self.plan)
        with self.assertRaises(ValueError):
            broker.submit(self.request())
        self.plan['pages'][0]['assets'] = [{'route': 'none'}]
        self.write('decision-plan.json', self.plan)
        with self.assertRaises(ValueError):
            broker.submit(self.request('generate'))
        self.assertFalse(FakeTools.entered)

    def test_generation_copies_references_and_publishes_only_from_owner(self):
        (self.job / 'assets/reference.png').write_bytes(png())
        images = {}
        broker = self.broker(images=images)
        original_publish = m.AssetImporter._publish
        thread_ids = []
        def publish(importer, *args):
            thread_ids.append(threading.get_ident())
            return original_publish(importer, *args)
        with patch.object(m.AssetImporter, '_publish', publish):
            ident = broker.submit(self.request('generate', reference_files=['assets/reference.png']))['id']
            result = self.ready(broker, ident)
        self.assertEqual(result['state'], 'ready')
        self.assertIs(broker.images, images)
        self.assertEqual(len(images), 1)
        self.assertEqual(thread_ids, [threading.get_ident()])
        item = result['result']['files'][0]
        self.assertFalse(Path(item['path']).is_absolute())
        self.assertEqual(hashlib.sha256((self.job / item['path']).read_bytes()).hexdigest(), item['sha256'])
        self.assertEqual(self.ready(broker, ident)['state'], 'ready')
        stage = FakeTools.entered[0][1]
        self.assertFalse(stage.exists())
        self.assertEqual(self.outline, json.loads((self.job / 'outline.json').read_text()))

    def test_generation_respects_shared_global_quota_without_partial_import(self):
        images = {str(index): {'file': str(index) + '.png'} for index in range(11)}
        broker = self.broker(images=images)
        FakeTools.generation_count = 2
        ident = broker.submit(self.request('generate'))['id']
        self.assertEqual(self.ready(broker, ident)['state'], 'failed')
        self.assertEqual(len(images), 11)
        self.assertEqual(list((self.job / 'assets').glob('generated-prefetch-*')), [])
        images['last'] = {'file': 'last.png'}
        with self.assertRaises(ValueError):
            broker.submit(self.request('generate', page='two'))

    def test_path_boundaries_and_unsafe_backend_output_are_rejected(self):
        broker = self.broker()
        outside = self.job / 'outside.png'
        outside.write_bytes(png())
        (self.job / 'assets/escape.png').symlink_to(outside)
        for name in ('assets/../../outside.png', 'assets/escape.png', str(outside)):
            with self.assertRaises((ValueError, OSError)):
                broker.submit(self.request('generate', reference_files=[name]))
        FakeTools.unsafe_file = True
        ident = broker.submit(self.request('generate'))['id']
        self.assertEqual(self.ready(broker, ident)['state'], 'failed')
        self.assertEqual(list((self.job / 'assets').glob('generated-prefetch-*')), [])

    def test_cancel_and_close_are_quick_and_keep_completed_results(self):
        broker = self.broker()
        finished = broker.submit(self.request())['id']
        self.ready(broker, finished)
        FakeTools.release = threading.Event()
        ident = broker.submit(self.request(page='two'))['id']
        broker.poll()
        self.assertEqual(broker.cancel(ident)['state'], 'cancelled')
        start = time.monotonic()
        broker.close()
        self.assertLess(time.monotonic() - start, .5)
        self.assertEqual(broker.get(finished)['state'], 'ready')

    def test_lease_loss_cancels_the_background_without_drain(self):
        alive = [True]
        def check():
            if not alive[0]:
                raise RuntimeError('Lease gone')
        broker = self.broker(lease_check=check)
        FakeTools.release = threading.Event()
        ident = broker.submit(self.request())['id']
        broker.poll()
        alive[0] = False
        start = time.monotonic()
        with self.assertRaises(RuntimeError):
            broker.poll()
        self.assertLess(time.monotonic() - start, .5)
        self.assertEqual(broker.get(ident)['state'], 'interrupted')
        self.assertTrue(broker.closed)

    def test_cli_batch_alias_and_immediate_status_get_and_staleness(self):
        broker = self.broker()
        self.write('batch.json', [self.request(), self.request()])
        submitted = self.cli('submit', '--batch', 'batch.json')['requests']
        first, alias = [item['id'] for item in submitted]
        self.assertEqual(self.cli('get', first)['request']['state'], 'queued')
        broker.poll()
        ready = self.ready(broker, first)
        self.assertEqual(ready['state'], 'ready')
        canonical = ready['id']
        self.assertEqual(self.cli('get', alias)['request']['id'], canonical)
        self.assertEqual(len(FakeTools.entered), 1)
        self.assertEqual(self.cli('status', first)['requests'][0]['state'], 'ready')
        self.outline['slides'][0]['summary'] = 'Changed before host next poll'
        self.write('outline.json', self.outline)
        self.assertEqual(self.cli('get', first)['request']['state'], 'stale')

    def test_partial_input_write_is_temporarily_unavailable_then_reusable(self):
        broker = self.broker()
        ident = broker.submit(self.request())['id']
        self.ready(broker, ident)
        (self.job / 'outline.json').write_text('{"slides":')
        broker.poll()
        pending = broker.get(ident)
        self.assertEqual(pending['state'], 'interrupted')
        self.assertTrue(pending['verification_pending'])
        self.assertNotIn('result', pending)
        self.assertEqual(broker.records[ident]['state'], 'ready')
        self.assertEqual(self.cli('get', ident)['request']['state'], 'interrupted')
        self.write('outline.json', self.outline)
        self.assertEqual(broker.get(ident)['state'], 'ready')
        self.assertEqual(self.cli('get', ident)['request']['state'], 'ready')

    def test_status_index_is_compact_and_timing_calls_are_retained(self):
        broker = self.broker()
        ident = broker.submit(self.request())['id']
        result = self.ready(broker, ident)
        index = json.loads((self.job / 'material-prefetch/index.json').read_text())
        summary = index['requests'][0]
        self.assertNotIn('basis', summary)
        self.assertNotIn('request', summary['payload'])
        self.assertLess(len(json.dumps(index)), 2000)
        self.assertIn('started_at', result)
        self.assertIn('completed_at', result)
        self.assertGreaterEqual(result['seconds'], 0)
        self.assertEqual(len(result['calls']), 1)
        self.assertEqual(result['calls'], result['result']['calls'])

    def test_safe_tool_failure_is_preserved_and_does_not_automatically_retry(self):
        broker = self.broker()
        def failure(helper, value):
            helper.calls.append({'tool': 'pptx_search_sources', 'seconds': .01})
            return {'success': False, 'contentItems': [{'type': 'inputText',
                    'text': 'Retained tool failed: TransportError; keep the unmet requirement explicit'}]}
        with patch.object(FakeTools, 'handle', failure):
            ident = broker.submit(self.request())['id']
            result = self.ready(broker, ident)
        self.assertEqual(result['state'], 'failed')
        self.assertIn('TransportError', result['error'])
        self.assertEqual(len(result['calls']), 1)
        self.assertEqual(broker.submit(self.request())['id'], ident)
        broker.poll()
        self.assertFalse(broker.pending)

    def test_absent_research_branch_cannot_bypass_supplied_only(self):
        broker = self.broker()
        (self.job / 'decision-plan.json').unlink()
        with self.assertRaises(ValueError):
            broker.submit(self.request())
        self.assertFalse(FakeTools.entered)

    def test_queued_cancel_is_applied_before_any_hosted_work_starts(self):
        broker = self.broker()
        ident = self.cli('submit', '--page-id', 'one', '--purpose', 'prepare next page',
                         '--search', 'inspect this original diagram')['requests'][0]['id']
        self.cli('cancel', ident)
        broker.poll()
        self.assertEqual(self.cli('get', ident)['request']['state'], 'cancelled')
        self.assertFalse(FakeTools.entered)

    def test_active_generation_reserves_the_last_shared_slot(self):
        images = {str(index): {'file': str(index) + '.png'} for index in range(11)}
        broker = self.broker(images=images)
        first = broker.submit(self.request('generate'))['id']
        second = broker.submit(self.request('generate', page='two'))['id']
        self.assertEqual(self.ready(broker, first)['state'], 'ready')
        broker.poll()
        self.assertEqual(broker.get(second)['state'], 'failed')
        self.assertEqual(len(FakeTools.entered), 1)
        self.assertEqual(len(images), 12)

    def test_restored_provider_pngs_are_not_counted_again_by_real_importer(self):
        generated_root = self.job / 'generated-test-source'
        thread = str(uuid.uuid4())
        source = generated_root / thread
        source.mkdir(parents=True)
        records = []
        names = []
        for index in range(6):
            name = 'exec-' + str(uuid.uuid4()) + '.png'
            names.append(name)
            body = png('royalblue' if index % 2 else 'coral')
            (source / name).write_bytes(body)
            destination = 'generated-' + name
            (self.job / 'assets' / destination).write_bytes(body)
            records.append({'file': destination, 'sha256': hashlib.sha256(body).hexdigest(),
                            'source': 'built-in image generation'})
        self.write('assets/index.json', {'images': records})
        images = {}
        broker = self.broker(images=images)
        self.assertEqual(set(images), set(names))
        importer = m.AssetImporter(self.job, generated_root=generated_root)
        importer.imported = images
        importer.thread = thread
        importer.import_images()
        self.assertEqual(len(images), 6)
        self.assertEqual(len({record['file'] for record in images.values()}), 6)
        # All six remaining genuine slots remain usable after the resumed import.
        for _ in range(6):
            (source / ('exec-' + str(uuid.uuid4()) + '.png')).write_bytes(png('green'))
        importer.import_images()
        self.assertEqual(len(images), 12)
        saved = json.loads((self.job / 'assets/index.json').read_text())['images']
        self.assertEqual(len(saved), 12)
        self.assertEqual(len({record['file'] for record in saved}), 12)
        self.assertIs(broker.images, images)

    def test_prefetched_png_restore_deduplicates_by_file_and_uses_stable_key(self):
        ident = 'a' * 32
        name = 'generated-prefetch-' + ident + '-0.png'
        body = png()
        (self.job / 'assets' / name).write_bytes(body)
        record = {'file': name, 'sha256': hashlib.sha256(body).hexdigest(),
                  'source': 'built-in image generation', 'prefetch_request_id': ident}
        self.write('assets/index.json', {'images': [record, {**record, 'additional_note': 'same file'}]})
        # A legacy restoration alias must also migrate in the shared object.
        images = {'restored:' + name: record, 'duplicate-alias': {**record, 'extra': True}}
        self.broker(images=images)
        self.assertEqual(set(images), {'prefetch:' + ident + ':0'})
        self.assertEqual(len({value['file'] for value in images.values()}), 1)

    def test_large_finished_queue_history_does_not_starve_submit_or_cancel(self):
        broker = self.broker()
        canonical = broker.submit(self.request())['id']
        for index in range(256):
            ident = format(index, '032x')
            broker._publish('prefetch-requests/' + ident + '.request.json',
                            m.encoded({'action': 'submit', 'payload': self.request()}))
        broker.poll(start_new=False)
        self.assertEqual(len(list((self.job / 'prefetch-requests').glob('*.reply.json'))), 256)
        self.assertEqual(len(broker.records), 1)
        new_ident, cancel_ident = 'e' * 32, 'f' * 32
        broker._publish('prefetch-requests/' + new_ident + '.request.json',
                        m.encoded({'action': 'submit', 'payload': self.request(page='two')}))
        broker._publish('prefetch-requests/' + cancel_ident + '.request.json',
                        m.encoded({'action': 'cancel', 'id': new_ident}))
        broker.poll(start_new=False)
        self.assertTrue(json.loads((self.job / 'prefetch-requests' / (new_ident + '.reply.json')).read_text())['ok'])
        self.assertTrue(json.loads((self.job / 'prefetch-requests' / (cancel_ident + '.reply.json')).read_text())['ok'])
        self.assertEqual(broker.get(new_ident)['state'], 'cancelled')
        self.assertEqual(broker.get(canonical)['state'], 'queued')
        self.assertEqual(len(list((self.job / 'prefetch-requests').glob('*.request.json'))), 258)
        self.assertFalse(FakeTools.entered)

    def test_combined_request_limit_is_checked_before_backend_and_boundary_succeeds(self):
        from auxiliary_tools import AuxiliaryTools as ActualAuxiliaryTools
        import auxiliary_tools
        broker = self.broker()
        with self.assertRaisesRegex(ValueError, 'plus purpose'):
            broker.submit(self.request(request='x' * 8000))
        self.assertFalse(broker.records)
        self.assertFalse(FakeTools.entered)

        class ShortServer:
            def __init__(self, **kwargs):
                self.usage = {('thread', 'turn'): {'input_tokens': 7}}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def start_thread(self):
                return {'thread': {'id': 'thread'}}
            def start_turn(self, *args):
                return {'id': 'turn'}
            def wait_turn(self, *args, **kwargs):
                return {'status': 'completed'}
            def result_text(self, *args):
                return 'Inspected original https://example.org/source; restricted to this page.'

        purpose = 'p' * 800
        request = 'q' * (8000 - len('\nPurpose: ') - len(purpose))
        payload = self.request(request=request, purpose=purpose)
        with patch.object(m, 'AuxiliaryTools', ActualAuxiliaryTools), patch.object(auxiliary_tools, 'AppServer', ShortServer):
            ident = broker.submit(payload)['id']
            result = self.ready(broker, ident)
        self.assertEqual(result['state'], 'ready')
        self.assertEqual(result['result']['purpose'], purpose)
        self.assertEqual(result['calls'][0]['usage']['input_tokens'], 7)

    def test_result_and_generated_file_tampering_never_returns_ready(self):
        broker = self.broker()
        ident = broker.submit(self.request('generate'))['id']
        ready = self.ready(broker, ident)
        (self.job / ready['result']['files'][0]['path']).write_bytes(png('black'))
        self.assertEqual(broker.get(ident)['state'], 'failed')
        other = broker.submit(self.request(page='two'))['id']
        self.ready(broker, other)
        path = self.job / 'material-prefetch' / (other + '.result.json')
        result = json.loads(path.read_text())
        result['text'] = 'Forged prepared evidence'
        path.write_text(json.dumps(result))
        self.assertEqual(broker.get(other)['state'], 'failed')


if __name__ == '__main__':
    unittest.main()
