"""One-shot calls to an OpenAI-compatible endpoint, with images and a JSON schema.

Covers the vendors behind an OpenAI-compatible API — OpenAI, DeepSeek, Qwen (DashScope
compatible mode), Gemini (its OpenAI-compatible endpoint), SiliconFlow, Moonshot — so a
slot in model_slots.py needs only a base URL, a model id and a key.

    ask(value, prompt, images=(), schema=None, timeout=300)
      -> {'text', 'structured', 'usage', 'cost_usd', 'seconds', 'model', 'adapter'}

The schema is embedded in the prompt and the reply is parsed with the same tolerant
extraction the Claude CLI path uses, because several compatible endpoints ignore a
response-format request. No tools, no files: everything is in the single message.
"""
import base64
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

MEDIA = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp',
         '.gif': 'image/gif'}
MAX_BODY = 32 * 1024 * 1024


class ApiUnavailable(RuntimeError):
    pass


def _data_url(path):
    path = Path(path)
    media = MEDIA.get(path.suffix.lower())
    if media is None:
        raise ApiUnavailable('Unsupported image type: ' + path.suffix)
    return 'data:' + media + ';base64,' + base64.b64encode(path.read_bytes()).decode()


def _extract_json(text):
    """The first balanced JSON object in a reply, ignoring code fences and prose."""
    if not isinstance(text, str):
        return None
    fenced = re.search(r'```(?:json)?\s*(.*?)```', text, re.S)
    body = fenced.group(1) if fenced else text
    start = body.find('{')
    while start >= 0:
        depth, in_string, escape = 0, False, False
        for index in range(start, len(body)):
            char = body[index]
            if in_string:
                if escape:
                    escape = False
                elif char == '\\':
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(body[start:index + 1])
                    except ValueError:
                        break
        start = body.find('{', start + 1)
    return None


def _payload(value, prompt, images, schema):
    wire = value.get('wire') or value.get('wire_api') or 'chat_completions'
    model = value['model']
    max_tokens = int(value.get('max_tokens') or 16000)
    instruction = prompt
    if schema is not None:
        instruction = (prompt + '\n\nReply with exactly one JSON object and nothing else. '
                       'It must validate against this JSON Schema:\n' + json.dumps(schema, ensure_ascii=False))
    parts = [{'type': 'text', 'text': instruction}]
    for image in images:
        parts.append({'type': 'image_url', 'image_url': {'url': _data_url(image)}})
    if wire == 'responses':
        content = []
        for part in parts:
            if part['type'] == 'text':
                content.append({'type': 'input_text', 'text': part['text']})
            else:
                content.append({'type': 'input_image', 'image_url': part['image_url']['url']})
        return {'model': model, 'input': [{'role': 'user', 'content': content}],
                'max_output_tokens': max_tokens, 'store': False}
    return {'model': model, 'messages': [{'role': 'user', 'content': parts}],
            'max_tokens': max_tokens, 'temperature': float(value.get('temperature', 0.2))}


def _text_and_usage(value, data):
    wire = value.get('wire') or value.get('wire_api') or 'chat_completions'
    if wire == 'responses':
        text = data.get('output_text')
        if not text:
            collected = []
            for item in data.get('output') or []:
                for part in (item.get('content') or []) if isinstance(item, dict) else []:
                    if isinstance(part, dict) and part.get('text'):
                        collected.append(part['text'])
            text = '\n'.join(collected)
        usage = data.get('usage') or {}
        return text or '', {'input_tokens': usage.get('input_tokens'), 'output_tokens': usage.get('output_tokens')}
    choices = data.get('choices') or []
    if not choices:
        raise ApiUnavailable('The endpoint returned no choices')
    message = choices[0].get('message') or {}
    text = message.get('content')
    if isinstance(text, list):
        text = ''.join(part.get('text', '') for part in text if isinstance(part, dict))
    usage = data.get('usage') or {}
    return text or '', {'input_tokens': usage.get('prompt_tokens'), 'output_tokens': usage.get('completion_tokens')}


def ask(value, prompt, images=(), schema=None, *, timeout=300):
    """One call to the configured endpoint. Raises ApiUnavailable with the actual error."""
    if value.get('adapter') != 'openai_api':
        raise ApiUnavailable('Not an API slot: ' + str(value.get('adapter')))
    wire = value.get('wire') or value.get('wire_api') or 'chat_completions'
    url = value['base_url'].rstrip('/') + ('/responses' if wire == 'responses' else '/chat/completions')
    body = json.dumps(_payload(value, prompt, images, schema), ensure_ascii=False).encode()
    request = urllib.request.Request(url, data=body, method='POST', headers={
        'Content-Type': 'application/json', 'Authorization': 'Bearer ' + value['api_key']})
    started = time.monotonic()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler(_proxy(value)))
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(MAX_BODY + 1)
    except urllib.error.HTTPError as error:
        detail = error.read(2048).decode('utf-8', 'replace')
        raise ApiUnavailable(f'{value.get("preset") or "api"} HTTP {error.code}: {detail[:300]}') from None
    except (urllib.error.URLError, TimeoutError) as error:
        raise ApiUnavailable(f'{value.get("preset") or "api"} unreachable: {error}') from None
    if len(raw) > MAX_BODY:
        raise ApiUnavailable('Reply exceeded the size limit')
    try:
        data = json.loads(raw)
    except ValueError:
        raise ApiUnavailable('The endpoint returned non-JSON') from None
    text, usage = _text_and_usage(value, data)
    structured = _extract_json(text) if schema is not None else None
    if schema is not None and structured is None:
        # Several compatible endpoints wrap or truncate JSON; one repair turn is cheaper than failing.
        raise ApiUnavailable('The reply contained no JSON object (' + text[:120].replace('\n', ' ') + ')')
    return {'text': text, 'structured': structured, 'usage': usage, 'cost_usd': None,
            'seconds': round(time.monotonic() - started, 1),
            'model': value['model'], 'adapter': 'openai_api'}


def _proxy(value):
    """Honour an explicit proxy for a vendor that needs one; loopback never goes through it."""
    proxy = value.get('proxy')
    if proxy:
        return {'http': proxy, 'https': proxy}
    env = {k: os.environ.get(k) for k in ('HTTPS_PROXY', 'https_proxy', 'HTTP_PROXY', 'http_proxy') if os.environ.get(k)}
    if not env:
        return {}
    chosen = env.get('HTTPS_PROXY') or env.get('https_proxy') or env.get('HTTP_PROXY') or env.get('http_proxy')
    return {'http': chosen, 'https': chosen}
