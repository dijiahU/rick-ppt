"""One-shot Claude calls with images, through the operator's local Claude Code CLI.

Used where a second model's eye helps more than another GPT pass: the in-author design
critique and the independent visual review. No tools, no files: everything the model may
use is in the single message, so a call costs one prompt plus the images (about 20k
tokens for a five-page deck) and returns in about a minute.

  ask(cfg, prompt, images, schema=None) -> {'text', 'structured', 'usage', 'cost_usd', 'seconds', 'model'}

Settings (runner/settings.local.json): "claude_cli" (path, default: claude on PATH or
~/.local/bin/claude), "claude_model" (default "opus"). Raises ClaudeUnavailable when the
CLI is missing or the call fails, so callers can fall back to their GPT route.

With `slot=`, model_slots decides who answers instead: the same call may go to an
OpenAI-compatible API or to another installed CLI (see model_slots.py). The return shape
is the same either way.
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


def available(cfg, slot=None):
    """Whether this slot can answer here. No slot: the local Claude CLI, as before."""
    if cfg.get('claude_review', True) is False or cfg.get('_customer_funded'):
        return False
    if slot is None:
        return cli(cfg) is not None
    import model_slots
    try:
        if not model_slots.second_model(cfg, slot):
            return False
        return model_slots.available(cfg, slot)
    except (ValueError, OSError):
        return False


def _schema_prompt(prompt, schema):
    return (prompt + '\n\nReply with exactly one JSON object and nothing else. It must validate against this JSON Schema:\n'
            + json.dumps(schema, ensure_ascii=False))


def _ask_cli(value, prompt, images, schema, timeout):
    """One call to an arbitrary installed CLI: `{prompt}`, `{model}` and `{images}` placeholders."""
    text = _schema_prompt(prompt, schema) if schema is not None else prompt
    paths = [str(Path(image).resolve()) for image in images]
    command = []
    for token in value['command']:
        if token == '{images}':
            command += paths
        elif '{images}' in token:
            command.append(token.replace('{images}', ' '.join(paths)))
        else:
            command.append(token.replace('{prompt}', text).replace('{model}', value.get('model') or ''))
    stdin = text if value.get('prompt_mode', 'arg') == 'stdin' and '{prompt}' not in value['command'] else None
    env = {k: v for k, v in os.environ.items() if not k.startswith(('CODEX_', 'PPTX_'))}
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='pptx-model-') as work:
        try:
            done = subprocess.run(command, input=None if stdin is None else stdin.encode(),
                                  capture_output=True, cwd=work, env=env, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ClaudeUnavailable(f'{value["command"][0]} call failed: {type(error).__name__}') from error
    if done.returncode != 0:
        detail = done.stderr.decode('utf-8', 'replace')[:300]
        raise ClaudeUnavailable(f'{value["command"][0]} exited {done.returncode}: {detail}')
    reply = done.stdout.decode('utf-8', 'replace')
    import model_api
    structured = model_api._extract_json(reply)
    if structured is None and schema is not None:
        raise ClaudeUnavailable(f'{value["command"][0]} returned no JSON report')
    return {'text': reply, 'structured': structured, 'usage': None, 'cost_usd': None,
            'seconds': round(time.monotonic() - started, 1), 'model': value.get('model') or value['command'][0],
            'adapter': 'cli'}


def ask(cfg, prompt, images=(), schema=None, *, timeout=360, model=None, slot=None):
    """One call, answered by the slot's model when a slot is named."""
    binary = cli(cfg)
    adapter = 'claude_cli'
    if slot is not None:
        import model_slots
        try:
            value = model_slots.resolve(cfg, slot)
        except (model_slots.SlotUnavailable, ValueError) as error:
            raise ClaudeUnavailable(str(error)) from None
        adapter = value.get('adapter', 'claude_cli')
        if adapter == 'openai_api':
            import model_api
            try:
                return model_api.ask(value, prompt, images, schema, timeout=timeout)
            except model_api.ApiUnavailable as error:
                raise ClaudeUnavailable(str(error)) from None
        if adapter == 'cli':
            return _ask_cli(value, prompt, images, schema, timeout)
        binary = value.get('executable') or binary
        model = value.get('model') or model
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
        prompt = _schema_prompt(prompt, schema)
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
