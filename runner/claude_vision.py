"""One-shot Claude calls with images, through the operator's local Claude Code CLI.

Used where a second model's eye helps more than another GPT pass: the in-author design
critique and the independent visual review. No tools, no files: everything the model may
use is in the single message, so a call costs one prompt plus the images (about 20k
tokens for a five-page deck) and returns in about a minute.

  ask(cfg, prompt, images, schema=None) -> {'text', 'structured', 'usage', 'cost_usd', 'seconds', 'model'}

Settings (runner/settings.local.json): "claude_cli" (path, default: claude on PATH or
~/.local/bin/claude), "claude_model" (default "opus"). Raises ClaudeUnavailable when the
CLI is missing or the call fails, so callers can fall back to their GPT route.
"""
import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

MEDIA = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp'}


class ClaudeUnavailable(RuntimeError):
    pass


def cli(cfg):
    path = cfg.get('claude_cli') or shutil.which('claude') or str(Path.home() / '.local/bin/claude')
    return path if Path(path).is_file() else None


def available(cfg):
    return cfg.get('claude_review', True) is not False and not cfg.get('_customer_funded') and cli(cfg) is not None


def ask(cfg, prompt, images=(), schema=None, *, timeout=360, model=None):
    binary = cli(cfg)
    if binary is None:
        raise ClaudeUnavailable('Claude CLI not found')
    model = model or cfg.get('claude_model', 'opus')
    content = []
    for image in images:
        image = Path(image)
        content += [{'type': 'text', 'text': image.name},
                    {'type': 'image', 'source': {'type': 'base64', 'media_type': MEDIA.get(image.suffix.lower(), 'image/png'),
                                                 'data': base64.b64encode(image.read_bytes()).decode()}}]
    # The operator's API relay rejects --json-schema requests (403 "client anomaly"), which
    # silently sent every structured review to the GPT fallback. Default: put the schema in
    # the prompt and parse the reply; "claude_json_schema": true restores the CLI flag.
    native_schema = schema is not None and cfg.get('claude_json_schema') is True
    if schema is not None and not native_schema:
        prompt += ('\n\nReply with exactly one JSON object and nothing else. It must validate against this JSON Schema:\n'
                   + json.dumps(schema, ensure_ascii=False))
    content.append({'type': 'text', 'text': prompt})
    line = json.dumps({'type': 'user', 'message': {'role': 'user', 'content': content}})
    command = [binary, '-p', '--input-format', 'stream-json', '--output-format', 'stream-json', '--verbose',
               '--model', model, '--tools', '', '--max-turns', '3']
    if native_schema:
        command += ['--json-schema', json.dumps(schema)]
    env = {k: v for k, v in os.environ.items() if not k.startswith(('CODEX_', 'PPTX_'))}
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='pptx-claude-') as work:
        try:
            done = subprocess.run(command, input=line.encode(), capture_output=True, cwd=work, env=env, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ClaudeUnavailable(f'Claude call failed: {type(error).__name__}') from error
    final = None
    for row in done.stdout.decode(errors='replace').splitlines():
        try:
            event = json.loads(row)
        except ValueError:
            continue
        if event.get('type') == 'result':
            final = event
    if done.returncode != 0 or final is None or final.get('is_error'):
        raise ClaudeUnavailable(f'Claude call failed (exit {done.returncode})')
    structured = final.get('structured_output')
    if structured is None and schema is not None:
        text = final.get('result') or ''
        try:
            structured = json.loads(text[text.index('{'):text.rindex('}') + 1])
        except ValueError:
            raise ClaudeUnavailable('Claude returned no structured report')
    return {'text': final.get('result') or '', 'structured': structured, 'usage': final.get('usage'),
            'cost_usd': final.get('total_cost_usd'), 'seconds': round(time.monotonic() - started, 1), 'model': model}
