"""Model slots: one place decides which model answers each call. No network, no real CLI."""
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import claude_vision  # noqa: E402
import model_api  # noqa: E402
import model_slots  # noqa: E402


class ValidateTest(unittest.TestCase):
    def test_default_slots_keep_the_author_backend(self):
        for slot in model_slots.TEXT_SLOTS:
            self.assertEqual(model_slots.slot_config({}, slot)['adapter'], 'codex_cli')
            self.assertFalse(model_slots.second_model({}, slot))

    def test_unknown_slot_and_adapter_are_rejected(self):
        with self.assertRaises(ValueError):
            model_slots.slot_config({}, 'nope')
        with self.assertRaises(ValueError):
            model_slots.validate('critique', {'adapter': 'telepathy'})

    def test_api_slot_needs_a_model_an_https_url_and_a_known_preset(self):
        with self.assertRaises(ValueError):
            model_slots.validate('critique', {'adapter': 'openai_api', 'preset': 'deepseek'})
        with self.assertRaises(ValueError):
            model_slots.validate('critique', {'adapter': 'openai_api', 'model': 'x', 'base_url': 'http://example.com/v1'})
        with self.assertRaises(ValueError):
            model_slots.validate('critique', {'adapter': 'openai_api', 'model': 'x', 'preset': 'nope'})
        value = model_slots.validate('critique', {'adapter': 'openai_api', 'preset': 'deepseek', 'model': 'deepseek-flash'})
        self.assertEqual(value['base_url'], 'https://api.deepseek.com/v1')
        self.assertEqual(value['preset'], 'deepseek')

    def test_loopback_http_is_allowed_for_a_local_endpoint(self):
        value = model_slots.validate('critique', {'adapter': 'openai_api', 'model': 'local',
                                                  'base_url': 'http://127.0.0.1:8080/v1'})
        self.assertEqual(value['base_url'], 'http://127.0.0.1:8080/v1')

    def test_cli_slot_needs_a_command_and_a_valid_prompt_mode(self):
        with self.assertRaises(ValueError):
            model_slots.validate('critique', {'adapter': 'cli', 'command': []})
        with self.assertRaises(ValueError):
            model_slots.validate('critique', {'adapter': 'cli', 'command': ['x'], 'prompt_mode': 'file'})
        self.assertEqual(model_slots.validate('critique', {'adapter': 'cli', 'command': ['x']})['command'], ['x'])

    def test_only_image_generation_takes_the_host_adapter(self):
        self.assertEqual(model_slots.slot_config({}, 'image_generation')['adapter'], 'host')
        with self.assertRaises(ValueError):
            model_slots.validate('critique', {'adapter': 'host'})

    def test_legacy_settings_still_select_the_claude_cli(self):
        cfg = {'visual_backend': 'claude', 'critique_backend': 'claude', 'claude_model': 'sonnet',
               'claude_cli': '/usr/local/bin/claude'}
        self.assertEqual(model_slots.slot_config(cfg, 'visual_review')['model'], 'sonnet')
        self.assertEqual(model_slots.slot_config(cfg, 'advisor')['adapter'], 'claude_cli')
        self.assertEqual(model_slots.slot_config(cfg, 'advisor')['executable'], '/usr/local/bin/claude')
        self.assertEqual(model_slots.slot_config(cfg, 'content_review')['adapter'], 'codex_cli')
        self.assertTrue(model_slots.second_model(cfg, 'visual_review'))

    def test_an_explicit_slot_wins_over_the_legacy_key(self):
        cfg = {'visual_backend': 'claude', 'model_slots': {'visual_review': {'adapter': 'openai_api', 'preset': 'gemini',
                                                                            'model': 'gemini-4-pro'}}}
        value = model_slots.slot_config(cfg, 'visual_review')
        self.assertEqual(value['adapter'], 'openai_api')
        self.assertEqual(value['model'], 'gemini-4-pro')


class ResolveTest(unittest.TestCase):
    def test_api_key_from_the_named_environment_variable(self):
        cfg = {'model_slots': {'critique': {'adapter': 'openai_api', 'preset': 'qwen', 'model': 'qwen3-max'}}}
        with mock.patch.dict(os.environ, {'DASHSCOPE_API_KEY': 'sk-test'}, clear=False):
            value = model_slots.resolve(cfg, 'critique')
        self.assertEqual(value['api_key'], 'sk-test')
        self.assertEqual(value['base_url'], 'https://dashscope.aliyuncs.com/compatible-mode/v1')

    def test_missing_key_is_reported_not_raised_as_a_key_error(self):
        cfg = {'model_slots': {'critique': {'adapter': 'openai_api', 'model': 'x',
                                            'base_url': 'https://example.com/v1', 'key_env': 'NO_SUCH_KEY_HERE'}}}
        with self.assertRaises(model_slots.SlotUnavailable):
            model_slots.resolve(cfg, 'critique')
        self.assertFalse(model_slots.available(cfg, 'critique'))

    def test_key_file_must_be_private(self):
        with tempfile.TemporaryDirectory() as temp:
            key = Path(temp) / 'k.key'
            key.write_text('sk-live\n')
            key.chmod(0o644)
            cfg = {'model_slots': {'critique': {'adapter': 'openai_api', 'model': 'x',
                                                'base_url': 'https://example.com/v1', 'key_file': str(key)}}}
            with self.assertRaises(model_slots.SlotUnavailable):
                model_slots.resolve(cfg, 'critique')
            key.chmod(0o600)
            self.assertEqual(model_slots.resolve(cfg, 'critique')['api_key'], 'sk-live')

    def test_a_cli_slot_needs_an_installed_command(self):
        cfg = {'model_slots': {'critique': {'adapter': 'cli', 'command': ['definitely-not-installed-xyz']}}}
        with self.assertRaises(model_slots.SlotUnavailable):
            model_slots.resolve(cfg, 'critique')
        ok = {'model_slots': {'critique': {'adapter': 'cli', 'command': [sys.executable, '-c', 'print(1)']}}}
        self.assertTrue(model_slots.available(ok, 'critique'))

    def test_describe_never_shows_a_key(self):
        cfg = {'model_slots': {'critique': {'adapter': 'openai_api', 'preset': 'deepseek', 'model': 'm',
                                            'api_key': 'sk-secret-value'}}}
        text = json.dumps(model_slots.describe(cfg))
        self.assertNotIn('sk-secret-value', text)
        self.assertIn('deepseek', text)


class AuthorSlotTest(unittest.TestCase):
    def test_no_author_slot_keeps_the_operator_decision(self):
        self.assertIsNone(model_slots.author_profile({}))

    def test_an_api_author_slot_builds_a_model_profile(self):
        cfg = {'model_slots': {'author': {'adapter': 'openai_api', 'preset': 'deepseek', 'model': 'deepseek-flash',
                                          'api_key': 'sk-live', 'effort': 'high'}}}
        profile = model_slots.author_profile(cfg)
        self.assertEqual(profile['base_url'], 'https://api.deepseek.com/v1')
        self.assertEqual(profile['wire_api'], 'chat_completions')
        self.assertEqual(profile['model'], 'deepseek-flash')
        self.assertEqual(profile['reasoning_effort'], 'high')

    def test_a_codex_author_slot_with_a_provider_becomes_config_overrides(self):
        cfg = {'model_slots': {'author': {'adapter': 'codex_cli', 'model': 'deepseek-flash',
                                          'provider': {'id': 'deepseek', 'base_url': 'https://api.deepseek.com/v1',
                                                       'wire': 'chat_completions', 'key_env': 'DEEPSEEK_API_KEY'}}}}
        rows = model_slots.codex_overrides(cfg, 'author')
        self.assertEqual(len(rows), 1)
        args = rows[0]['args']
        self.assertIn('model="deepseek-flash"', args)
        self.assertIn('model_provider="deepseek"', args)
        self.assertIn('model_providers.deepseek.env_key="DEEPSEEK_API_KEY"', args)
        self.assertEqual(rows[0]['env_keys'], ['DEEPSEEK_API_KEY'])

    def test_overrides_are_empty_without_a_provider(self):
        self.assertEqual(model_slots.codex_overrides({}, 'author'), [])


class ApiPayloadTest(unittest.TestCase):
    def test_chat_payload_carries_images_and_an_embedded_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            image = Path(temp) / 'p.png'
            image.write_bytes(b'\x89PNG\r\n\x1a\n' + b'0' * 16)
            value = {'adapter': 'openai_api', 'model': 'm', 'base_url': 'https://x.test/v1'}
            body = model_api._payload(value, 'Review this page.', [image], {'type': 'object'})
        self.assertEqual(body['model'], 'm')
        parts = body['messages'][0]['content']
        self.assertIn('JSON Schema', parts[0]['text'])
        self.assertTrue(parts[1]['image_url']['url'].startswith('data:image/png;base64,'))

    def test_responses_payload_uses_input_items(self):
        value = {'adapter': 'openai_api', 'model': 'm', 'base_url': 'https://x.test/v1', 'wire': 'responses'}
        body = model_api._payload(value, 'Hi', [], None)
        self.assertEqual(body['input'][0]['content'][0], {'type': 'input_text', 'text': 'Hi'})
        self.assertNotIn('messages', body)

    def test_json_extraction_survives_fences_and_prose(self):
        self.assertEqual(model_api._extract_json('ok\n```json\n{"a": {"b": 1}}\n```\ndone'), {'a': {'b': 1}})
        self.assertEqual(model_api._extract_json('{"s": "a { brace"}'), {'s': 'a { brace'})
        self.assertIsNone(model_api._extract_json('no json here'))

    def test_chat_reply_text_and_usage_are_read(self):
        data = {'choices': [{'message': {'content': 'hello'}}], 'usage': {'prompt_tokens': 3, 'completion_tokens': 4}}
        text, usage = model_api._text_and_usage({'wire': 'chat_completions'}, data)
        self.assertEqual((text, usage['input_tokens'], usage['output_tokens']), ('hello', 3, 4))

    def test_an_http_error_is_reported_with_its_status(self):
        value = {'adapter': 'openai_api', 'model': 'm', 'base_url': 'http://127.0.0.1:9/v1', 'api_key': 'k'}
        with self.assertRaises(model_api.ApiUnavailable):
            model_api.ask(value, 'hi', timeout=3)


class DispatchTest(unittest.TestCase):
    def test_openai_slot_calls_the_api_client(self):
        cfg = {'model_slots': {'critique': {'adapter': 'openai_api', 'preset': 'deepseek', 'model': 'm',
                                            'api_key': 'k'}}}
        with mock.patch.object(model_api, 'ask', return_value={'text': 'ok', 'structured': {'v': 1}, 'model': 'm',
                                                               'adapter': 'openai_api', 'seconds': 0.1}) as call:
            answer = claude_vision.ask(cfg, 'prompt', schema={'type': 'object'}, slot='critique')
        self.assertEqual(answer['structured'], {'v': 1})
        self.assertEqual(call.call_args[0][0]['model'], 'm')

    def test_a_failing_api_slot_raises_the_reviewers_fallback_error(self):
        cfg = {'model_slots': {'critique': {'adapter': 'openai_api', 'preset': 'deepseek', 'model': 'm',
                                            'api_key': 'k'}}}
        with mock.patch.object(model_api, 'ask', side_effect=model_api.ApiUnavailable('HTTP 401')):
            with self.assertRaises(claude_vision.ClaudeUnavailable):
                claude_vision.ask(cfg, 'prompt', slot='critique')

    def test_a_cli_slot_runs_the_command_and_parses_its_json(self):
        script = ('import json,sys;'
                  'print(json.dumps({"text": sys.argv[1], "ok": True}))')
        cfg = {'model_slots': {'advisor': {'adapter': 'cli',
                                           'command': [sys.executable, '-c', script, '{prompt}'],
                                           'model': 'local-test'}}}
        answer = claude_vision.ask(cfg, 'hello', schema={'type': 'object'}, slot='advisor')
        self.assertEqual(answer['structured']['ok'], True)
        self.assertTrue(answer['structured']['text'].startswith('hello'))
        self.assertEqual(answer['adapter'], 'cli')

    def test_a_cli_slot_can_read_the_prompt_on_stdin(self):
        script = 'import json,sys;print(json.dumps({"len": len(sys.stdin.read())}))'
        cfg = {'model_slots': {'advisor': {'adapter': 'cli', 'command': [sys.executable, '-c', script],
                                           'prompt_mode': 'stdin'}}}
        answer = claude_vision.ask(cfg, 'abcd', slot='advisor')
        self.assertEqual(answer['structured'], {'len': 4})

    def test_a_claude_slot_keeps_the_cli_route(self):
        cfg = {'model_slots': {'visual_review': {'adapter': 'claude_cli', 'model': 'opus', 'executable': sys.executable}},
               'claude_review': True}
        self.assertTrue(claude_vision.available(cfg, 'visual_review'))

    def test_available_is_false_for_the_author_backend_and_customer_funded_tasks(self):
        self.assertFalse(claude_vision.available({}, 'visual_review'))
        self.assertFalse(claude_vision.available({'_customer_funded': True,
                                                  'model_slots': {'visual_review': {'adapter': 'claude_cli',
                                                                                    'executable': sys.executable}}},
                                                 'visual_review'))

    def test_legacy_call_without_a_slot_is_unchanged(self):
        with mock.patch.object(claude_vision, 'cli', return_value=None):
            with self.assertRaises(claude_vision.ClaudeUnavailable):
                claude_vision.ask({}, 'prompt')


if __name__ == '__main__':
    unittest.main()
