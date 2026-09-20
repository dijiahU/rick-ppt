"""Offline proxy boundary tests: no sockets, credentials or external requests."""
import io
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from chat_proxy import ChatProxy, MAX_BODY, UpstreamError, provider_session
from model_backend import KEY_ENV

PROFILE = {'model': 'test-flash', 'base_url': 'https://provider.invalid/v1',
           'api_key': 'unit-test-placeholder', 'wire_api': 'chat_completions'}


def completed():
    return {'model': 'test-flash', 'choices': [{'message': {'content': 'done'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 2, 'completion_tokens': 1, 'total_tokens': 3}}


class ProxyTests(unittest.TestCase):
    def test_upstream_key_stays_off_argv_and_observations(self):
        proxy = ChatProxy(PROFILE)
        reply = SimpleNamespace(returncode=0, stdout=json.dumps(completed()) + '\n200', stderr='')
        with patch('chat_proxy.subprocess.run', return_value=reply) as run:
            result = proxy.complete({'model': 'test-flash', 'input': 'private test prompt', 'stream': True,
                                     'max_output_tokens': 100000})
        args, kwargs = run.call_args
        self.assertNotIn(PROFILE['api_key'], repr(args))
        self.assertNotIn('private test prompt', repr(args))
        self.assertIn(PROFILE['api_key'], kwargs['input'])
        data_line = next(line for line in kwargs['input'].splitlines() if line.startswith('data = '))
        sent = json.loads(json.loads(data_line[len('data = '):]))
        self.assertFalse(sent['enable_thinking'])
        self.assertFalse(sent['stream'])
        self.assertEqual(sent['max_tokens'], 16384)
        self.assertEqual(result['output'][0]['content'][0]['text'], 'done')
        self.assertNotIn(PROFILE['api_key'], json.dumps(proxy.calls))
        self.assertNotIn('private test prompt', json.dumps(proxy.calls))

    def test_profile_model_cannot_be_overridden_by_request(self):
        with patch('chat_proxy.subprocess.run') as run, self.assertRaises(ValueError):
            ChatProxy(PROFILE).complete({'model': 'other', 'input': 'hi'})
        run.assert_not_called()

    def test_provider_errors_do_not_echo_raw_response(self):
        proxy = ChatProxy(PROFILE)
        response = SimpleNamespace(returncode=0, stdout='private upstream details\n429', stderr='')
        with patch('chat_proxy.subprocess.run', return_value=response), self.assertRaises(UpstreamError) as caught:
            proxy.complete({'model': 'test-flash', 'input': 'hello'})
        self.assertEqual(caught.exception.status, 429)
        self.assertNotIn('private', str(caught.exception))
        self.assertNotIn('private', json.dumps(proxy.calls))

    def test_transport_errors_do_not_echo_stderr(self):
        response = SimpleNamespace(returncode=28, stdout='', stderr='sensitive proxy settings')
        with patch('chat_proxy.subprocess.run', return_value=response), self.assertRaises(UpstreamError) as caught:
            ChatProxy(PROFILE).complete({'model': 'test-flash', 'input': 'hello'})
        self.assertEqual(caught.exception.status, 502)
        self.assertNotIn('sensitive', str(caught.exception))

    def test_provider_session_exposes_only_ephemeral_key(self):
        fake = SimpleNamespace(url='http://127.0.0.1:32123/v1', token='temporary-local-token', calls=[])
        cm = Mock()
        cm.__enter__ = Mock(return_value=fake)
        cm.__exit__ = Mock(return_value=False)
        with patch('chat_proxy.ChatProxy', return_value=cm):
            with provider_session(PROFILE) as (config, env, calls):
                self.assertEqual(env, {KEY_ENV: fake.token})
                self.assertEqual(config['model_providers']['pptx_external']['base_url'], fake.url)
                self.assertEqual(config['model_providers']['pptx_external']['wire_api'], 'responses')
                self.assertNotIn(PROFILE['api_key'], json.dumps([config, env, calls]))
        cm.__exit__.assert_called_once()

    def test_default_and_direct_responses_keep_existing_path(self):
        with patch('chat_proxy.ChatProxy') as factory:
            with provider_session(None) as result:
                self.assertEqual(result, ({}, None, []))
            direct = {**PROFILE, 'wire_api': 'responses'}
            with provider_session(direct) as (_, env, calls):
                self.assertEqual(env[KEY_ENV], PROFILE['api_key'])
                self.assertEqual(calls, [])
            factory.assert_not_called()

    def handler(self, body=None, *, auth=True, path='/v1/responses', headers=None):
        captured = {}
        def server_factory(address, handler_class):
            self.assertEqual(address, ('127.0.0.1', 0))
            captured['class'] = handler_class
            return SimpleNamespace(server_port=12345, serve_forever=lambda: None)
        proxy = ChatProxy(PROFILE)
        with patch('chat_proxy.ThreadingHTTPServer', side_effect=server_factory), patch('chat_proxy.threading.Thread'):
            proxy.__enter__()
        handler = object.__new__(captured['class'])
        raw = json.dumps(body or {'model': 'test-flash', 'input': 'hello'}).encode()
        handler.path = path
        handler.headers = {'Content-Length': str(len(raw)), 'Authorization': 'Bearer ' + (proxy.token if auth else 'bad')}
        handler.headers.update(headers or {})
        handler.rfile, handler.wfile = io.BytesIO(raw), io.BytesIO()
        handler.send_response = lambda status: captured.update(status=status)
        handler.send_header = lambda name, value: captured.setdefault('headers', {}).update({name: value})
        handler.end_headers = lambda: None
        return proxy, handler, captured

    def test_auth_failure_before_body_or_upstream(self):
        proxy, handler, result = self.handler(auth=False)
        with patch.object(proxy, 'complete') as complete:
            handler.do_POST()
        self.assertEqual(result['status'], 401)
        self.assertEqual(handler.rfile.tell(), 0)
        complete.assert_not_called()

    def test_route_and_limits_before_upstream(self):
        for options, status in [({'path': '/v1/chat/completions'}, 404),
                                ({'headers': {'Content-Length': str(MAX_BODY + 1)}}, 400),
                                ({'headers': {'Content-Encoding': 'gzip'}}, 400)]:
            with self.subTest(options=options):
                proxy, handler, result = self.handler(**options)
                with patch.object(proxy, 'complete') as complete:
                    handler.do_POST()
                self.assertEqual(result['status'], status)
                complete.assert_not_called()

    def test_stream_framing_and_completion(self):
        from chat_protocol import chat_to_response
        response = chat_to_response(completed())
        proxy, handler, result = self.handler(body={'model': 'test-flash', 'input': 'hello', 'stream': True})
        with patch.object(proxy, 'complete', return_value=response):
            handler.do_POST()
        raw = handler.wfile.getvalue()
        self.assertEqual(result['status'], 200)
        self.assertEqual(result['headers']['Content-Type'], 'text/event-stream')
        self.assertEqual(int(result['headers']['Content-Length']), len(raw))
        frames = [frame for frame in raw.decode().split('\n\n') if frame]
        parsed = [json.loads(frame.split('\ndata: ', 1)[1]) for frame in frames]
        self.assertEqual(parsed[0]['type'], 'response.created')
        self.assertEqual(parsed[-1]['type'], 'response.completed')
        self.assertEqual(parsed[-1]['response'], response)

    def test_unexpected_failure_returns_generic_error(self):
        proxy, handler, result = self.handler()
        with patch.object(proxy, 'complete', side_effect=RuntimeError('private runtime detail')):
            handler.do_POST()
        self.assertEqual(result['status'], 502)
        self.assertNotIn(b'private runtime detail', handler.wfile.getvalue())
        self.assertNotIn('private runtime detail', json.dumps(proxy.calls))


if __name__ == '__main__':
    unittest.main()
