"""Real local TLS/keep-alive and retry-safety checks; no live jobs or tokens."""
import io
import json
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

import site_transport
from resilience import request, WorkerHTTPError


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
        path = urlsplit(self.path).path
        with self.server.record_lock:
            self.server.records.append((self.client_address[1], path, dict(self.headers), body))
            count = sum(row[1] == path for row in self.server.records)
        if path == '/lost':
            self.close_connection = True
            self.connection.shutdown(socket.SHUT_RDWR)
            return
        status = 503 if path == '/retry' and count == 1 else 401 if path == '/unauthorized' else 302 if path == '/redirect' else 200
        data = b'x' * 100 if path in ('/large', '/stream') else b'not json' if path == '/bad-json' else b'{"ok":true}'
        self.send_response(status)
        if path == '/redirect':
            self.send_header('Location', '/ok')
        if path in ('/stream', '/slow'):
            self.send_header('Connection', 'close')
            self.close_connection = True
        else:
            self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        try:
            if path == '/slow':
                for _ in range(10):
                    self.wfile.write(b'x'); self.wfile.flush(); time.sleep(0.025)
            else:
                self.wfile.write(data)
        except OSError:
            pass


class PooledTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='pptx-https-test-')
        root = Path(cls.temporary.name)
        cls.cert, cls.key = root / 'cert.pem', root / 'key.pem'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                        '-subj', '/CN=localhost', '-addext', 'subjectAltName=IP:127.0.0.1,DNS:localhost',
                        '-keyout', str(cls.key), '-out', str(cls.cert)], check=True, capture_output=True)
        cls.context = ssl.create_default_context(cafile=str(cls.cert))
        server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_context.load_cert_chain(str(cls.cert), str(cls.key))
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.server.socket = server_context.wrap_socket(cls.server.socket, server_side=True)
        cls.server.records = []
        cls.server.record_lock = threading.Lock()
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.site = f'https://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        site_transport.close_connections()
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(timeout=2)
        cls.temporary.cleanup()

    def setUp(self):
        site_transport.close_connections()
        with self.server.record_lock:
            self.server.records.clear()
        self.tls_patch = patch.object(site_transport, '_tls', self.context)
        self.tls_patch.start()
        self.addCleanup(self.tls_patch.stop)
        self.addCleanup(site_transport.close_connections)
        self.cfg = {'site': self.site, 'token': 'SYNTHETIC_PRIVATE_TOKEN', 'site_http_transport': 'pooled'}

    def exchange(self, path='/ok', **options):
        return site_transport.exchange(self.site, path, {'Content-Type': 'application/json'}, b'{}', **options)

    def test_keepalive_reuses_socket_but_refreshes_credentials(self):
        self.assertEqual(request(self.cfg, '/ok?action=poll', lease='first'), {'ok': True})
        self.cfg['token'] = 'NEW_SYNTHETIC_TOKEN'
        self.assertEqual(request(self.cfg, '/ok?action=poll', lease='second'), {'ok': True})
        first, second = self.server.records
        self.assertEqual(first[0], second[0])
        self.assertEqual(first[2]['X-Job-Lease'], 'first')
        self.assertEqual(second[2]['X-Job-Lease'], 'second')
        self.assertEqual(second[2]['Authorization'], 'Bearer NEW_SYNTHETIC_TOKEN')

    def test_lost_claim_response_is_not_replayed(self):
        with self.assertRaises(WorkerHTTPError) as caught:
            request(self.cfg, '/lost')
        self.assertTrue(caught.exception.retryable)
        self.assertEqual(len(self.server.records), 1)
        self.assertNotIn('SYNTHETIC_PRIVATE_TOKEN', str(caught.exception))
        request(self.cfg, '/ok')
        self.assertNotEqual(self.server.records[0][0], self.server.records[1][0])

    def test_only_existing_safe_lease_operations_retry(self):
        output = io.StringIO()
        with patch('resilience.time.sleep'), redirect_stdout(output):
            self.assertEqual(request(self.cfg, '/retry?action=complete', lease='same-lease'), {'ok': True})
        self.assertEqual(len(self.server.records), 2)
        self.assertEqual(self.server.records[0][3], self.server.records[1][3])
        self.assertEqual(self.server.records[0][2]['X-Job-Lease'], self.server.records[1][2]['X-Job-Lease'])
        self.assertNotIn('SYNTHETIC_PRIVATE_TOKEN', output.getvalue())

    def test_claim_transient_status_is_not_replayed(self):
        with self.assertRaises(WorkerHTTPError) as caught:
            request(self.cfg, '/retry')
        self.assertTrue(caught.exception.retryable)
        self.assertEqual(len(self.server.records), 1)

    def test_rejected_credentials_are_terminal(self):
        with self.assertRaises(WorkerHTTPError) as caught:
            request(self.cfg, '/unauthorized?action=complete', lease='rejected')
        self.assertEqual(caught.exception.status, 401)
        self.assertFalse(caught.exception.retryable)
        self.assertEqual(len(self.server.records), 1)

    def test_redirects_are_never_followed_with_worker_token(self):
        with self.assertRaises(WorkerHTTPError) as caught:
            request(self.cfg, '/redirect')
        self.assertEqual(caught.exception.status, 302)
        self.assertFalse(caught.exception.retryable)
        self.assertEqual(len(self.server.records), 1)

    def test_both_declared_and_streaming_response_sizes_are_bounded(self):
        for path in ('/large', '/stream'):
            with self.subTest(path=path), self.assertRaises(site_transport.ExchangeError) as caught:
                self.exchange(path, maximum=16)
            self.assertFalse(caught.exception.retryable)
            self.assertEqual(str(caught.exception), 'response too large')
            self.assertEqual(site_transport._local.connections, {})
        self.assertEqual(self.exchange()[0], 200)

    def test_body_deadline_is_checked_between_reads(self):
        with self.assertRaises(site_transport.ExchangeError) as caught:
            self.exchange('/slow', timeout=0.12)
        self.assertTrue(caught.exception.retryable)
        self.assertEqual(str(caught.exception), 'transport timeout')
        self.assertEqual(site_transport._local.connections, {})

    def test_tls_verification_cannot_be_skipped_in_configuration(self):
        with patch.object(site_transport, '_tls', ssl.create_default_context()):
            with self.assertRaises(site_transport.ExchangeError) as caught:
                self.exchange()
        self.assertEqual(str(caught.exception), 'TLS certificate verification failed')
        self.assertFalse(caught.exception.retryable)
        self.assertEqual(self.server.records, [])

    def test_invalid_json_still_defers_to_caller_for_poll(self):
        with self.assertRaises(WorkerHTTPError) as caught:
            request(self.cfg, '/bad-json?action=poll')
        self.assertTrue(caught.exception.retryable)
        self.assertEqual(len(self.server.records), 1)

    def test_raw_responses_are_unchanged(self):
        self.assertEqual(request(self.cfg, '/large?action=attachment', raw=True, lease='synthetic'), b'x' * 100)

    def test_threads_do_not_share_an_inflight_connection(self):
        errors = []
        barrier = threading.Barrier(2)
        def run():
            try:
                barrier.wait(timeout=5)
                self.exchange(); self.exchange()
            except Exception as error:
                errors.append(error)
            finally:
                site_transport.close_connections()
        threads = [threading.Thread(target=run) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=5)
        self.assertFalse(errors)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        ports = [row[0] for row in self.server.records]
        self.assertEqual(len(set(ports)), 2)
        self.assertTrue(all(ports.count(port) == 2 for port in set(ports)))

    def test_idle_connection_is_retired(self):
        self.exchange()
        key, (connection, _) = next(iter(site_transport._local.connections.items()))
        site_transport._local.connections[key] = (connection, time.monotonic() - 46)
        self.exchange()
        self.assertNotEqual(self.server.records[0][0], self.server.records[1][0])

    def test_bad_proxy_never_falls_back_to_direct(self):
        for proxy in ('socks5://127.0.0.1:1', 'http://secret:password@localhost:1', 'http://127.0.0.1:1'):
            with self.subTest(proxy=proxy), self.assertRaises(site_transport.ExchangeError) as caught:
                self.exchange(proxy=proxy)
            self.assertNotIn('password', str(caught.exception))
        self.assertEqual(self.server.records, [])


if __name__ == '__main__':
    unittest.main()
