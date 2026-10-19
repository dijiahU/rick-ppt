"""Host-owned native Responses transport with atomic tool-call delivery.

Buffer the upstream response and validate its terminal status before exposing
any executable tool call to app-server. The provider key stays in host memory;
only an ephemeral loopback credential reaches the provider child process.
"""
import copy
import hashlib
import json
import re
import time
from collections import OrderedDict,Counter

from chat_proxy import ChatProxy, MAX_BODY, UpstreamError, curl_reply, SAFE_SSE_EVENT_TYPES

MAX_ATTEMPTS = 2
MAX_FAILED_REQUESTS = 128
RETRY_HTTP = frozenset((429, 500, 502, 503, 504, 524))

class SSEParseError(ValueError):
    def __init__(self,telemetry,output_seen):
        super().__init__('Malformed upstream event');self.telemetry=telemetry;self.output_seen=output_seen


class ResponsesProxy(ChatProxy):
    def __init__(self, profile, on_usage=None):
        super().__init__(profile, on_usage=on_usage)
        self.failed_requests = OrderedDict()
        self.request_lock = __import__('threading').Lock()

    def _marker(self, value, limit=200):
        if (isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.:/-]{1,' + str(limit) + r'}', value)
                and self.profile['api_key'] not in value and self.token not in value):
            return value
        return None

    def _remember_failure(self, digest, status, message):
        self.failed_requests[digest] = (status, message)
        self.failed_requests.move_to_end(digest)
        while len(self.failed_requests) > MAX_FAILED_REQUESTS:
            self.failed_requests.popitem(last=False)

    def _request(self, body):
        if not isinstance(body, dict) or body.get('model') != self.profile['model']:
            raise ValueError('Model does not match selected profile')
        # Stateful IDs, reasoning items, encrypted content, namespaces, image
        # inputs and JSON schemas pass through untouched on the native route.
        request = copy.deepcopy(body)
        # Stream from the provider to avoid waiting for the entire generation
        # before the upstream HTTP connection has observable response data.
        # Delivery to app-server remains atomic after full validation.
        request['stream'] = self.profile.get('responses_transport', 'streaming') == 'streaming'
        if self.profile.get('reasoning_effort'):
            reasoning = request.get('reasoning') or {}
            if not isinstance(reasoning, dict):
                raise ValueError('Malformed reasoning configuration')
            request['reasoning'] = {**reasoning, 'effort': self.profile['reasoning_effort']}
        tier = self.profile.get('service_tier')
        if tier is not None:
            request['service_tier'] = 'priority' if tier == 'fast' else tier
        return request

    def _parse(self, raw, streaming):
        output_seen = False
        telemetry={'sse_event_count':0,'sse_unknown_event_count':0,'sse_malformed_event_count':0,
                   'sse_event_counts':{},'sse_event_label_counts':{},'sse_terminal_seen':False,
                   'sse_terminal_label_seen':False,'sse_data_type_missing':False}
        unsafe_output=False
        if not streaming:
            result = json.loads(raw)
            terminal = True
        else:
            result, terminal, top_error = None, False, None
            counts,labels=Counter(),Counter()
            for frame in re.split(r'\r?\n\r?\n', raw):
                event_labels=[line[6:].strip() for line in frame.splitlines() if line.startswith('event:')]
                label=event_labels[-1] if event_labels else None
                if label in SAFE_SSE_EVENT_TYPES:labels[label]+=1
                if label in ('response.completed','response.failed','response.incomplete'):telemetry['sse_terminal_label_seen']=True
                data = '\n'.join(line[5:].lstrip() for line in frame.splitlines() if line.startswith('data:'))
                if not data or data == '[DONE]':
                    continue
                telemetry['sse_event_count']+=1
                try:
                    event = json.loads(data)
                    if not isinstance(event,dict):raise ValueError('Malformed upstream event')
                except ValueError:
                    telemetry['sse_malformed_event_count']+=1
                    telemetry.update(sse_event_counts=dict(counts),sse_event_label_counts=dict(labels))
                    raise SSEParseError(telemetry,output_seen) from None
                kind=event.get('type','')
                if not kind:telemetry['sse_data_type_missing']=True
                if kind in SAFE_SSE_EVENT_TYPES:counts[kind]+=1
                else:telemetry['sse_unknown_event_count']+=1
                if (kind in ('response.output_item.added','response.output_item.done','response.content_part.added','response.content_part.done')
                        or isinstance(kind,str) and kind.startswith('response.') and kind.endswith('.delta')):
                    output_seen = True
                if kind in ('response.output_item.added','response.output_item.done'):
                    item=event.get('item')
                    if not isinstance(item,dict) or item.get('type') not in ('function_call','custom_tool_call','message','reasoning'):
                        unsafe_output=True
                if event.get('type') in ('response.completed', 'response.failed', 'response.incomplete'):
                    result, terminal = event.get('response'), True
                elif event.get('type') == 'error':
                    top_error = event.get('error') or event
            telemetry.update(sse_event_counts=dict(counts),sse_event_label_counts=dict(labels),sse_terminal_seen=terminal)
            telemetry['_unsafe_output']=unsafe_output
            if not terminal:
                return {'status': 'failed', 'error': top_error or {'type': 'stream_incomplete'}}, False, output_seen, telemetry
        if not isinstance(result, dict):
            raise ValueError('Malformed upstream response')
        return result, terminal, output_seen, telemetry

    def _client_generation(self,request):
        # New generations are safe before downlink only when API-side execution
        # and appendable conversation state are absent. Immutable parent IDs
        # remain unchanged; this proxy never executes client tool declarations.
        if request.get('conversation') is not None:return False
        def local(specs,depth=0):
            if not isinstance(specs,list) or depth>16:return False
            for spec in specs:
                if not isinstance(spec,dict):return False
                kind=spec.get('type')
                if not isinstance(spec.get('name'),str) or not spec['name']:return False
                if kind in ('function','custom'):
                    if kind=='function' and 'parameters' in spec and not isinstance(spec['parameters'],dict):return False
                    if kind=='custom' and 'format' in spec and not isinstance(spec['format'],dict):return False
                    continue
                if kind=='namespace' and local(spec.get('tools'),depth+1):continue
                return False
            return True
        return local(request.get('tools',[]))

    def _receipt(self, request, result, *, status, attempt, seconds, size, request_id):
        error = result.get('error') if isinstance(result, dict) else None
        error = error if isinstance(error, dict) else {}
        receipt = {'protocol': 'responses', 'endpoint': '/responses', 'attempt': attempt,
                   'upstream_status': status, 'http_ok': status == 200,
                   'ok': status == 200 and result.get('status') == 'completed',
                   'stream': request['stream'], 'requested_model': self.profile['model'],
                   'seconds': round(seconds, 3), 'response_bytes': size,
                   'tools': len(request['tools']) if isinstance(request.get('tools'),list) else 0}
        incomplete=result.get('incomplete_details')
        incomplete=incomplete if isinstance(incomplete,dict) else {}
        for key, value in (('response_model', result.get('model')),
                           ('response_id', result.get('id')),
                           ('response_status', result.get('status')),
                           ('response_error_code', error.get('code')),
                           ('response_error_type', error.get('type')),
                           ('incomplete_reason', incomplete.get('reason')),
                           ('request_id', request_id)):
            marker = self._marker(value)
            if marker is not None:
                receipt[key] = marker
        for key, value in (('requested_service_tier', request.get('service_tier')),
                           ('actual_service_tier', result.get('service_tier'))):
            if value in ('auto', 'default', 'fast', 'priority'):
                receipt[key] = value
        if isinstance(result.get('usage'), dict):
            from chat_proxy import safe_api_calls
            receipt['usage'] = safe_api_calls([{'usage': result['usage']}])[0]['usage']
        return receipt

    def _valid_output(self,result):
        if (not isinstance(result.get('id'),str) or not result['id'] or result.get('object')!='response'
                or not isinstance(result.get('output'),list)):
            return False
        for item in result['output']:
            if not isinstance(item,dict) or item.get('status') not in (None,'completed'):
                return False
            if not isinstance(item.get('id'),str) or not item['id'] or not isinstance(item.get('type'),str):
                return False
            if item['type'] in ('function_call','custom_tool_call'):
                field='arguments' if item['type']=='function_call' else 'input'
                if any(not isinstance(item.get(key),str) for key in ('call_id','name',field)):
                    return False
                if not item['call_id'] or not item['name']:
                    return False
                if item['type']=='function_call':
                    try:json.loads(item['arguments'])
                    except ValueError:return False
            elif item['type']=='message':
                if item.get('role')!='assistant' or not isinstance(item.get('content'),list):
                    return False
                for part in item['content']:
                    if not isinstance(part,dict) or part.get('type') not in ('output_text','refusal'):
                        return False
                    if not isinstance(part.get('text' if part['type']=='output_text' else 'refusal'),str):
                        return False
        return True

    def complete(self, body):
        request = self._request(body)
        encoded = json.dumps(request, ensure_ascii=False, separators=(',', ':'))
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        with self.request_lock:
            return self._complete(request, encoded, digest)

    def _digest(self, body):
        encoded = json.dumps(self._request(body), ensure_ascii=False, separators=(',', ':'))
        return hashlib.sha256(encoded.encode()).hexdigest()

    def _complete(self, request, encoded, digest):
        if digest in self.failed_requests:
            status, message = self.failed_requests[digest]
            self.record_call({'ok': False, 'cache_hit': True, 'terminal': True, 'protocol': 'responses'})
            raise UpstreamError(status, message)
        config = ('header = ' + json.dumps('Authorization: Bearer ' + self.profile['api_key']) + '\n'
                  'header = "Content-Type: application/json"\n'
                  # curl's config language does not implement JSON \u escapes.
                  # Keep literal UTF-8 in this outer quoting layer; the inner
                  # JSON document still escapes newlines, quotes and slashes.
                  'data = ' + json.dumps(encoded, ensure_ascii=False) + '\n')
        timeout = 600 if self.profile.get('reasoning_effort') else 180
        for attempt in range(1, MAX_ATTEMPTS + 1):
            if self.stopping.is_set():
                raise UpstreamError(499, 'Configured API request interrupted')
            started = time.monotonic()
            process = self._upstream(['curl', '--disable', '--config', '-', '--silent', '--show-error',
                '--max-time', str(timeout), '--max-filesize', str(MAX_BODY),
                '--write-out', '\n%{http_code}\n%header{x-request-id}\n%header{request-id}',
                self.profile['base_url'] + '/responses'], input=config, text=True,
                capture_output=True, timeout=timeout + 10)
            if process.returncode:
                self.record_call({'ok': False, 'attempt': attempt, 'protocol': 'responses',
                                   'transport_code': process.returncode, 'seconds': round(time.monotonic()-started, 3)})
                # A partial body is never replayed: it may include server-side
                # state. Empty connect/TLS/socket failures get one host retry.
                retry = (attempt < MAX_ATTEMPTS and process.returncode in (7, 28, 35, 52, 55, 56)
                         and process.stdout.strip() in ('', '000') and self._client_generation(request))
                if retry:
                    continue
                message = 'Configured API transport failed'
                self._remember_failure(digest, 502, message)
                raise UpstreamError(502, message)
            try:
                telemetry={};status=None
                raw, status, request_id = curl_reply(process.stdout)
                try:
                    result, stream_terminal, output_seen, telemetry = self._parse(raw, request['stream'])
                    parse_error=False
                except (ValueError, TypeError) as error:
                    telemetry=getattr(error,'telemetry',{})
                    parse_error=True
                    if status == 200:
                        raise
                    result = {'error': {'type': 'http_error'}}
                    # A malformed later frame must not erase an earlier tool
                    # item. Any SSE framing makes non-200 replay uncertain.
                    stream_terminal = False
                    output_seen = bool(re.search(r'(?m)^(?:data|event):', raw))
            except (ValueError, TypeError, KeyError):
                self.record_call({'ok': False, 'attempt': attempt, 'protocol': 'responses',
                                   'response_error_type': 'malformed_response','upstream_status':status,**telemetry})
                message = 'Configured API returned a malformed response'
                self._remember_failure(digest, 502, message)
                raise UpstreamError(502, message) from None
            receipt = self._receipt(request, result, status=status, attempt=attempt,
                seconds=time.monotonic()-started, size=len(raw.encode()), request_id=request_id)
            unsafe_output=telemetry.pop('_unsafe_output',False)
            receipt.update(telemetry)
            self.record_call(receipt)
            valid = (status == 200 and result.get('status') == 'completed'
                     and result.get('model') == self.profile['model']
                     and self._valid_output(result))
            if valid:
                if self.profile['api_key'] in json.dumps(result,ensure_ascii=False) or self.token in json.dumps(result,ensure_ascii=False):
                    receipt['ok']=False
                    self._remember_failure(digest,502,'Configured API returned protected credential material')
                    raise UpstreamError(502,'Configured API returned protected credential material')
                receipt['output_types'] = [x.get('type') for x in result['output'] if isinstance(x, dict)]
                return result
            receipt['ok'] = False
            local_result=(not result.get('output') or isinstance(result['output'],list) and
                          all(isinstance(item,dict) and item.get('type') in ('function_call','custom_tool_call','message','reasoning') for item in result['output']))
            regenerate=(self._client_generation(request) and local_result and not unsafe_output and not parse_error and
                        (status==524 or status==200 and result.get('status')=='failed'
                         and receipt.get('response_error_type') in ('stream_incomplete','server_error')))
            ordinary_retry=(self._client_generation(request) and status in RETRY_HTTP-{524} and not result.get('output') and not output_seen
                            and (not request['stream'] or status!=200 or stream_terminal))
            retry=attempt<MAX_ATTEMPTS and (regenerate or ordinary_retry)
            if retry:
                delay = 120 if status == 524 else 1
                receipt['retry_delay_seconds'] = delay
                receipt['generation_retry']=regenerate
                if self.stopping.wait(delay):
                    raise UpstreamError(499, 'Configured API request interrupted')
                continue
            marker = receipt.get('response_error_type') or receipt.get('response_error_code') or receipt.get('response_status') or 'invalid_response'
            message = 'Configured API request failed (' + marker + ')'
            self._remember_failure(digest, status if 400 <= status < 600 else 502, message)
            raise UpstreamError(status if 400 <= status < 600 else 502, message)
