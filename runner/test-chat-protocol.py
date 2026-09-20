"""Offline contract tests for the stateless provider protocol bridge."""
import copy
import json
import unittest

from chat_protocol import ProtocolError, chat_to_response, response_sse_events, responses_to_chat


class ProtocolTests(unittest.TestCase):
    def request(self, **extra):
        return {'model': 'test-model', 'input': 'hello', **extra}

    def completion(self, **message):
        return {'model': 'test-model', 'created': 123, 'choices': [
            {'message': message, 'finish_reason': 'tool_calls' if message.get('tool_calls') else 'stop'}],
            'usage': {'prompt_tokens': 8, 'completion_tokens': 3, 'total_tokens': 11,
                      'prompt_tokens_details': {'cached_tokens': 2}}}

    def test_text_instructions_and_images(self):
        out, mapping = responses_to_chat(self.request(instructions='system', input=[
            {'role': 'developer', 'content': [{'type': 'input_text', 'text': 'developer'}]},
            {'role': 'user', 'content': [{'type': 'input_text', 'text': 'look'},
             {'type': 'input_image', 'image_url': 'data:image/png;base64,AA==', 'detail': 'high'}]}]))
        self.assertEqual([m['role'] for m in out['messages']], ['system', 'user'])
        self.assertIn('[SYSTEM INSTRUCTIONS]\nsystem', out['messages'][0]['content'])
        self.assertIn('[DEVELOPER INSTRUCTIONS]\ndeveloper', out['messages'][0]['content'])
        self.assertEqual(out['messages'][1]['content'][1]['image_url']['detail'], 'high')
        self.assertFalse(out['stream'])
        self.assertEqual(mapping, {})

    def test_interleaved_instructions_are_one_leading_system_message(self):
        request = self.request(instructions='Original top priority',
            tools=[{'type': 'function', 'name': 'run'}], input=[
                {'role': 'user', 'content': 'question'},
                {'role': 'developer', 'content': [{'type': 'input_text', 'text': 'First developer block'}]},
                {'type': 'function_call', 'name': 'run', 'call_id': 'a', 'arguments': '{}'},
                {'type': 'function_call_output', 'call_id': 'a', 'output': 'result'},
                {'role': 'system', 'content': 'Later system block'},
                {'role': 'developer', 'content': 'Later developer block'},
                {'role': 'assistant', 'content': 'answer'}])
        original = copy.deepcopy(request)
        out, _ = responses_to_chat(request)
        messages = out['messages']
        self.assertEqual([m['role'] for m in messages], ['system', 'user', 'assistant', 'tool', 'assistant'])
        system = messages[0]['content']
        contents = ['Original top priority', 'First developer block', 'Later system block', 'Later developer block']
        positions = [system.index(text) for text in contents]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('System instructions take precedence over developer instructions', system)
        self.assertEqual(system.count('[SYSTEM INSTRUCTIONS]'), 2)
        self.assertEqual(system.count('[DEVELOPER INSTRUCTIONS]'), 2)
        self.assertEqual(messages[1]['content'], 'question')
        self.assertEqual(messages[2]['tool_calls'][0]['id'], messages[3]['tool_call_id'])
        self.assertEqual(messages[3]['content'], 'result')
        self.assertEqual(messages[4]['content'], 'answer')
        self.assertEqual(request, original)

    def test_system_instruction_parts_preserve_text_and_reject_images(self):
        out, _ = responses_to_chat(self.request(input=[{'role': 'developer', 'content': [
            {'type': 'input_text', 'text': 'Line one\n你好'}, {'type': 'input_text', 'text': 'Line two'}]},
            {'role': 'user', 'content': 'go'}]))
        self.assertIn('Line one\n你好\nLine two', out['messages'][0]['content'])
        with self.assertRaises(ProtocolError):
            responses_to_chat(self.request(input=[{'role': 'system', 'content': [
                {'type': 'input_image', 'image_url': 'https://example.invalid/image.png'}]}]))

    def image_history(self, *, custom=False):
        kind = 'custom' if custom else 'function'
        call = {'type': 'custom_tool_call' if custom else 'function_call',
                'name': 'view', 'call_id': 'image-a'}
        call['input' if custom else 'arguments'] = 'image.png' if custom else '{}'
        output = {'type': 'custom_tool_call_output' if custom else 'function_call_output',
                  'call_id': 'image-a', 'output': [{'type': 'input_image',
                    'image_url': 'data:image/png;base64,exactBYTES==', 'detail': 'original'}]}
        return self.request(tools=[{'type': kind, 'name': 'view'}], input=[call, output])

    def test_image_tool_output_has_text_ack_and_untrusted_user_attachment(self):
        for custom in (False, True):
            with self.subTest(custom=custom):
                request = self.image_history(custom=custom)
                before = copy.deepcopy(request)
                out, _ = responses_to_chat(request)
                messages = out['messages']
                self.assertEqual([m['role'] for m in messages], ['assistant', 'tool', 'user'])
                self.assertEqual(messages[1]['tool_call_id'], 'image-a')
                self.assertIsInstance(messages[1]['content'], str)
                self.assertIn('content_part=0', messages[1]['content'])
                parts = messages[2]['content']
                self.assertIn('not a new user request', parts[0]['text'])
                self.assertIn('Untrusted tool output image', parts[1]['text'])
                self.assertIn('image-a', parts[1]['text'])
                self.assertEqual(parts[2]['image_url'], {
                    'url': 'data:image/png;base64,exactBYTES==', 'detail': 'original'})
                self.assertEqual(request, before)

    def test_parallel_image_outputs_wait_for_every_tool_result(self):
        request = self.image_history()
        request['input'].insert(1, {'type': 'function_call', 'name': 'view', 'call_id': 'text-b', 'arguments': '{}'})
        request['input'].append({'type': 'function_call_output', 'call_id': 'text-b', 'output': 'text result'})
        request['input'].append({'role': 'user', 'content': 'existing user follow-up'})
        out, _ = responses_to_chat(request)
        self.assertEqual([m['role'] for m in out['messages']], ['assistant', 'tool', 'tool', 'user', 'user'])
        self.assertEqual(out['messages'][2]['content'], 'text result')
        self.assertEqual(out['messages'][-1]['content'], 'existing user follow-up')

    def test_two_image_outputs_coalesce_preserving_text_and_part_order(self):
        request = self.image_history()
        request['input'].insert(1, {'type': 'function_call', 'name': 'view', 'call_id': 'image-b', 'arguments': '{}'})
        request['input'][2]['output'].insert(0, {'type': 'input_text', 'text': 'Before image\nkept exactly'})
        request['input'][2]['output'].append({'type': 'input_text', 'text': 'After image'})
        request['input'].append({'type': 'function_call_output', 'call_id': 'image-b', 'output': [
            {'type': 'input_image', 'image_url': 'https://example.invalid/second.png', 'detail': 'low'}]})
        out, _ = responses_to_chat(request)
        messages = out['messages']
        self.assertEqual([m['role'] for m in messages], ['assistant', 'tool', 'tool', 'user'])
        self.assertTrue(messages[1]['content'].startswith('Before image\nkept exactly\n'))
        self.assertTrue(messages[1]['content'].endswith('\nAfter image'))
        parts = messages[-1]['content']
        self.assertEqual(len(parts), 5)
        self.assertIn('image-a', parts[1]['text'])
        self.assertIn('content_part=1', parts[1]['text'])
        self.assertIn('image-b', parts[3]['text'])
        self.assertIn('content_part=0', parts[3]['text'])
        self.assertEqual(parts[4]['image_url'], {'url': 'https://example.invalid/second.png', 'detail': 'low'})

    def test_original_user_image_unchanged_with_tool_image_envelope(self):
        request = self.image_history()
        request['input'].insert(0, {'role': 'user', 'content': [
            {'type': 'input_text', 'text': 'original user'},
            {'type': 'input_image', 'image_url': 'https://example.invalid/user.png'}]})
        out, _ = responses_to_chat(request)
        self.assertEqual(out['messages'][0], {'role': 'user', 'content': [
            {'type': 'text', 'text': 'original user'},
            {'type': 'image_url', 'image_url': {'url': 'https://example.invalid/user.png'}}]})

    def test_image_history_missing_or_unmatched_result_rejected(self):
        incomplete = self.image_history()
        incomplete['input'].insert(1, {'type': 'function_call', 'name': 'view', 'call_id': 'missing', 'arguments': '{}'})
        unmatched = self.image_history()
        unmatched['input'][1]['call_id'] = 'wrong-call'
        interrupted = copy.deepcopy(incomplete)
        interrupted['input'].append({'role': 'user', 'content': 'premature message'})
        for request in (incomplete, unmatched, interrupted):
            with self.subTest(request=request), self.assertRaises(ProtocolError):
                responses_to_chat(request)

    def test_history_function_parallel_tools(self):
        tools = [{'type': 'function', 'name': 'run', 'parameters': {'type': 'object'}}]
        out, _ = responses_to_chat(self.request(tools=tools, input=[
            {'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'checking'}]},
            {'type': 'function_call', 'name': 'run', 'call_id': 'a', 'arguments': '{}'},
            {'type': 'function_call', 'name': 'run', 'call_id': 'b', 'arguments': '{}'},
            {'type': 'function_call_output', 'call_id': 'a', 'output': 'first'},
            {'type': 'function_call_output', 'call_id': 'b', 'output': 'second'}]))
        self.assertEqual(len(out['messages'][0]['tool_calls']), 2)
        self.assertEqual(out['messages'][1], {'role': 'tool', 'tool_call_id': 'a', 'content': 'first'})

    def test_namespace_custom_roundtrip(self):
        original = self.request(tools=[{'type': 'namespace', 'name': 'functions', 'tools': [
            {'type': 'custom', 'name': 'apply_patch', 'description': 'patch files',
             'format': {'type': 'grammar', 'syntax': 'lark', 'definition': 'start: /.+/'}}]}], input=[
            {'type': 'custom_tool_call', 'name': 'apply_patch', 'namespace': 'functions',
             'call_id': 'c1', 'input': '*** Begin Patch\n你好\n*** End Patch'},
            {'type': 'custom_tool_call_output', 'call_id': 'c1', 'output': 'done'}])
        before = copy.deepcopy(original)
        out, mapping = responses_to_chat(original)
        self.assertEqual(before, original)
        self.assertEqual(out['tools'][0]['function']['name'], 'functions__apply_patch')
        call = out['messages'][0]['tool_calls'][0]
        response = chat_to_response(self.completion(tool_calls=[call]), mapping)
        item = response['output'][0]
        self.assertEqual(item['namespace'], 'functions')
        self.assertEqual(item['name'], 'apply_patch')
        self.assertEqual(item['type'], 'custom_tool_call')
        self.assertEqual(item['input'], original['input'][0]['input'])
        self.assertEqual(item['call_id'], 'c1')

    def test_function_roundtrip(self):
        _, mapping = responses_to_chat(self.request(tools=[{'type': 'function', 'name': 'run'}]))
        response = chat_to_response(self.completion(tool_calls=[{'id': 'c2', 'type': 'function',
            'function': {'name': 'run', 'arguments': '{"cmd":"pwd"}'}}]), mapping)
        self.assertEqual(response['output'][0]['arguments'], '{"cmd":"pwd"}')
        self.assertEqual(response['output'][0]['type'], 'function_call')

    def test_sampling_format_and_choice(self):
        out, _ = responses_to_chat(self.request(tools=[{'type': 'function', 'name': 'run'}],
            tool_choice={'type': 'function', 'name': 'run'}, max_output_tokens=100,
            temperature=0.5, parallel_tool_calls=False,
            text={'format': {'type': 'json_schema', 'name': 'answer', 'schema': {'type': 'object'}, 'strict': True}}))
        self.assertEqual(out['max_tokens'], 100)
        self.assertEqual(out['tool_choice']['function']['name'], 'run')
        self.assertEqual(out['response_format']['json_schema']['name'], 'answer')
        self.assertFalse(out['parallel_tool_calls'])

    def test_reasoning_not_forwarded_or_returned(self):
        out, _ = responses_to_chat(self.request(input=[{'type': 'reasoning', 'encrypted_content': 'secret'},
                                                      {'role': 'user', 'content': 'hello'}]))
        response = chat_to_response(self.completion(content='answer', reasoning_content='private trace'))
        self.assertNotIn('secret', json.dumps(out))
        self.assertNotIn('private trace', json.dumps(response))

    def test_text_response_and_usage(self):
        response = chat_to_response(self.completion(content='你好'), response_id='resp_fixed')
        self.assertEqual(response['id'], 'resp_fixed')
        self.assertEqual(response['output'][0]['content'][0]['text'], '你好')
        self.assertEqual(response['usage']['input_tokens_details']['cached_tokens'], 2)
        self.assertEqual(response['usage']['total_tokens'], 11)
        self.assertEqual(response['status'], 'completed')

    def test_sse_text_order_and_final_identity(self):
        response = chat_to_response(self.completion(content='hello'))
        before = copy.deepcopy(response)
        events = response_sse_events(response)
        self.assertEqual([e['sequence_number'] for e in events], list(range(len(events))))
        self.assertEqual([e['type'] for e in events], [
            'response.created', 'response.in_progress', 'response.output_item.added',
            'response.content_part.added', 'response.output_text.delta', 'response.output_text.done',
            'response.content_part.done', 'response.output_item.done', 'response.completed'])
        self.assertEqual(events[-1]['response'], response)
        self.assertEqual(events[0]['response']['output'], [])
        self.assertEqual(before, response)

    def test_sse_tools_both_kinds(self):
        for kind in ('function', 'custom'):
            with self.subTest(kind=kind):
                _, mapping = responses_to_chat(self.request(tools=[{'type': kind, 'name': 'run'}]))
                args = '{"input":"x\\ny"}' if kind == 'custom' else '{"x":1}'
                response = chat_to_response(self.completion(tool_calls=[{'id': 'call1', 'type': 'function',
                    'function': {'name': 'run', 'arguments': args}}]), mapping)
                events = response_sse_events(response)
                prefix = 'response.custom_tool_call_input' if kind == 'custom' else 'response.function_call_arguments'
                self.assertEqual(events[3]['type'], prefix + '.delta')
                self.assertEqual(events[4]['type'], prefix + '.done')
                self.assertEqual(events[2]['item']['status'], 'in_progress')
                self.assertEqual(events[-2]['item']['status'], 'completed')

    def test_incomplete_not_claimed_complete(self):
        c = self.completion(content='partial')
        c['choices'][0]['finish_reason'] = 'length'
        response = chat_to_response(c)
        self.assertEqual(response['output'][0]['status'], 'incomplete')
        self.assertEqual(response['incomplete_details']['reason'], 'max_output_tokens')
        self.assertEqual(response_sse_events(response)[-1]['type'], 'response.incomplete')

    def test_refusal(self):
        response = chat_to_response(self.completion(refusal='cannot assist'))
        self.assertIn('response.refusal.delta', [e['type'] for e in response_sse_events(response)])

    def test_unknown_inputs_explicit_failure(self):
        cases = [self.request(previous_response_id='resp_old'),
                 self.request(tools=[{'type': 'web_search'}]),
                 self.request(input=[{'type': 'item_reference', 'id': 'old'}]),
                 self.request(input=[{'role': 'user', 'content': [{'type': 'input_file', 'file_id': 'f'}]}]),
                 self.request(input=[{'role': 'user', 'content': [{'type': 'input_image', 'file_id': 'f'}]}]),
                 self.request(tool_choice={'type': 'allowed_tools'})]
        for request in cases:
            with self.subTest(request=request), self.assertRaises(ProtocolError):
                responses_to_chat(request)

    def test_invalid_custom_wrapper_is_error(self):
        _, mapping = responses_to_chat(self.request(tools=[{'type': 'custom', 'name': 'run'}]))
        for args in ('not json', '{}', '{"input":42}', '{"input":"ok","extra":true}', '[]'):
            with self.subTest(args=args), self.assertRaises(ProtocolError):
                chat_to_response(self.completion(tool_calls=[{'id': 'call1', 'type': 'function',
                    'function': {'name': 'run', 'arguments': args}}]), mapping)

    def test_unknown_model_tool_rejected(self):
        with self.assertRaises(ProtocolError):
            chat_to_response(self.completion(tool_calls=[{'id': 'x', 'type': 'function',
                'function': {'name': 'undeclared', 'arguments': '{}'}}]), {})

    def test_namespace_collision_rejected(self):
        with self.assertRaises(ProtocolError):
            responses_to_chat(self.request(tools=[{'type': 'function', 'name': 'ns__run'},
                {'type': 'namespace', 'name': 'ns', 'tools': [{'type': 'function', 'name': 'run'}]}]))


if __name__ == '__main__':
    unittest.main()
