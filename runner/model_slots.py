"""Where each model is used, and which model answers there.

One place decides every model-backed call in the worker: the author, the research
helper, the two reviewers, the in-author critique, the borrowing advisor and image
generation. A deck can be made by one factory and reviewed by another, and each slot
can be a different vendor, reached over an OpenAI-compatible API or through a CLI.

Settings (private, `runner/settings.local.json`):

    "model_slots": {
      "author":        {"adapter": "codex_cli", "model": "gpt-6.2-sol", "effort": "xhigh"},
      "research_helper": {"adapter": "cli", "command": ["gemini", "-m", "{model}", "-p", "{prompt}"], "model": "gemini-4-pro"},
      "content_review": {"adapter": "openai_api", "preset": "deepseek", "model": "deepseek-chat"},
      "visual_review":  {"adapter": "claude_cli", "model": "opus"},
      "critique":       {"adapter": "openai_api", "preset": "qwen", "model": "qwen3.5-vl-plus"},
      "advisor":        {"adapter": "claude_cli", "model": "opus"}
    }

Legacy keys keep working: `visual_backend`/`critique_backend` ("claude" or "gpt"),
`claude_model`, `claude_cli`. An explicit slot always wins.

Adapters
    codex_cli   the existing Codex agent for a whole phase (author/research/review turn);
                `provider` points that session at another OpenAI-compatible endpoint
    claude_cli  one-shot Claude Code CLI call (`claude -p`), images and JSON schema
    openai_api  one-shot HTTP call to an OpenAI-compatible endpoint, images as data URLs
    cli         one-shot call to any installed CLI; `{prompt}`/`{model}`/`{images}` in
                the command, or the prompt on stdin

Keys never reach a task folder or a model's tool environment: an API key comes from a
named environment variable, a private key file, or the private settings file, and the
worker reads it in its own process.
"""
import json
import os
import shutil
from pathlib import Path

SLOTS = ('author', 'research_helper', 'content_review', 'visual_review', 'critique', 'advisor', 'image_generation')
TEXT_SLOTS = tuple(s for s in SLOTS if s != 'image_generation')
ADAPTERS = ('codex_cli', 'claude_cli', 'openai_api', 'cli')

# OpenAI-compatible endpoints. `wire` is the API shape; `key_env` is the conventional variable.
API_PRESETS = {
    'openai': {'base_url': 'https://api.openai.com/v1', 'wire': 'responses', 'key_env': 'OPENAI_API_KEY'},
    'deepseek': {'base_url': 'https://api.deepseek.com/v1', 'wire': 'chat_completions', 'key_env': 'DEEPSEEK_API_KEY'},
    'qwen': {'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1', 'wire': 'chat_completions',
             'key_env': 'DASHSCOPE_API_KEY'},
    'gemini': {'base_url': 'https://generativelanguage.googleapis.com/v1beta/openai', 'wire': 'chat_completions',
               'key_env': 'GEMINI_API_KEY'},
    'siliconflow': {'base_url': 'https://api.siliconflow.cn/v1', 'wire': 'chat_completions',
                    'key_env': 'SILICONFLOW_API_KEY'},
    'moonshot': {'base_url': 'https://api.moonshot.cn/v1', 'wire': 'chat_completions', 'key_env': 'MOONSHOT_API_KEY'},
}

# Example CLI invocations. Vendor flags change; edit `command` freely, it is not validated
# beyond the placeholders below.
CLI_PRESETS = {
    'claude': {'command': ['claude', '-p', '--model', '{model}', '--input-format', 'stream-json',
                           '--output-format', 'stream-json', '--verbose', '--tools', '', '--max-turns', '3'],
               'prompt': 'stream_json', 'images': 'content_blocks'},
    'gemini': {'command': ['gemini', '--model', '{model}', '--prompt', '{prompt}', '{images}'],
               'prompt': 'arg', 'images': 'paths'},
    'qwen': {'command': ['qwen', '--model', '{model}', '-p', '{prompt}', '{images}'],
             'prompt': 'arg', 'images': 'paths'},
    'codex': {'command': ['codex', 'exec', '--model', '{model}', '--skip-git-repo-check', '{prompt}'],
              'prompt': 'arg', 'images': 'paths'},
}

DEFAULTS = {slot: {'adapter': 'codex_cli'} for slot in TEXT_SLOTS}
DEFAULTS['image_generation'] = {'adapter': 'host'}


class SlotUnavailable(RuntimeError):
    """The slot is configured but cannot run here (missing CLI, key or command)."""


def _legacy(cfg, slot):
    """Translate the pre-2026-11 settings into a slot, so an old worker keeps its behaviour."""
    claude = {'adapter': 'claude_cli', 'model': cfg.get('claude_model', 'opus')}
    if cfg.get('claude_cli'):
        claude['executable'] = cfg['claude_cli']
    if slot == 'visual_review' and cfg.get('visual_backend') == 'claude':
        return claude
    if slot in ('critique', 'advisor') and cfg.get('critique_backend') == 'claude':
        return claude
    return None


def slot_config(cfg, slot):
    """The effective configuration for one slot: explicit, then legacy, then default."""
    if slot not in SLOTS:
        raise ValueError('Unknown model slot: ' + str(slot))
    chosen = dict(DEFAULTS[slot])
    legacy = _legacy(cfg, slot)
    if legacy:
        chosen = {**chosen, **legacy}
    configured = (cfg.get('model_slots') or {}).get(slot)
    if configured is not None:
        if not isinstance(configured, dict):
            raise ValueError('model_slots.' + slot + ' must be an object')
        chosen = {**chosen, **configured}
    return validate(slot, chosen)


def validate(slot, value):
    """Reject a slot that cannot be dispatched, with the field that is wrong."""
    value = {k: v for k, v in value.items() if v is not None}
    adapter = value.get('adapter', 'codex_cli')
    if adapter not in ADAPTERS and adapter != 'host':
        raise ValueError(f'model_slots.{slot}.adapter must be one of: ' + ', '.join(ADAPTERS))
    if adapter == 'host':
        if slot != 'image_generation':
            raise ValueError(f'model_slots.{slot}: only image_generation may use adapter "host"')
        return value
    if adapter == 'openai_api':
        preset = value.get('preset')
        if preset is not None:
            if preset not in API_PRESETS:
                raise ValueError(f'model_slots.{slot}.preset must be one of: ' + ', '.join(API_PRESETS))
            value = {**API_PRESETS[preset], **value}
            value.pop('preset', None)
            value['preset'] = preset
        base = value.get('base_url')
        if not isinstance(base, str) or not base.startswith(('https://', 'http://localhost', 'http://127.0.0.1')):
            raise ValueError(f'model_slots.{slot}.base_url must be an https URL (or a local http address)')
        if not isinstance(value.get('model'), str) or not value['model'].strip():
            raise ValueError(f'model_slots.{slot}.model is required for an API slot')
        if value.get('wire', value.get('wire_api')) not in (None, 'chat_completions', 'responses'):
            raise ValueError(f'model_slots.{slot}.wire must be chat_completions or responses')
        return value
    if adapter == 'cli':
        command = value.get('command')
        if not isinstance(command, list) or not command or not all(isinstance(c, str) and c for c in command):
            raise ValueError(f'model_slots.{slot}.command must be a non-empty list of strings')
        if value.get('prompt_mode', 'arg') not in ('arg', 'stdin'):
            raise ValueError(f'model_slots.{slot}.prompt_mode must be arg or stdin')
        return value
    # claude_cli / codex_cli
    if value.get('model') is not None and not isinstance(value['model'], str):
        raise ValueError(f'model_slots.{slot}.model must be a string')
    return value


def _key_for(slot, value):
    """The API key for a slot: environment variable, private file, or the private settings."""
    if value.get('api_key'):
        return value['api_key']
    name = value.get('key_env') or 'PPTX_MODEL_API_KEY'
    key = os.environ.get(name)
    if key:
        return key
    path = value.get('key_file')
    if path:
        candidate = Path(path).expanduser()
        info = candidate.stat()
        if info.st_mode & 0o077:
            raise SlotUnavailable(f'model_slots.{slot}.key_file must be private: chmod 600 {path}')
        key = candidate.read_text().strip()
        if key:
            return key
    raise SlotUnavailable(f'model_slots.{slot}: no API key (set {name}, key_file, or api_key)')


def resolve(cfg, slot):
    """The slot's configuration plus its key and executable, or SlotUnavailable."""
    value = slot_config(cfg, slot)
    adapter = value.get('adapter', 'codex_cli')
    if adapter == 'openai_api':
        return {**value, 'api_key': _key_for(slot, value)}
    if adapter == 'claude_cli':
        from claude_vision import cli as claude_executable
        executable = value.get('executable') or claude_executable(cfg)
        if not executable:
            raise SlotUnavailable(f'model_slots.{slot}: the claude CLI is not installed')
        return {**value, 'executable': executable}
    if adapter == 'cli':
        binary = value['command'][0]
        if not (shutil.which(binary) or Path(binary).expanduser().is_file()):
            raise SlotUnavailable(f'model_slots.{slot}: command "{binary}" is not installed')
        return value
    return value


def available(cfg, slot):
    """Whether this slot can run here, without raising."""
    try:
        resolve(cfg, slot)
        return True
    except (SlotUnavailable, ValueError, OSError):
        return False


def describe(cfg):
    """A safe summary for logs and the worker identity: no keys, no file contents."""
    report = {}
    for slot in SLOTS:
        try:
            value = slot_config(cfg, slot)
        except (ValueError, OSError) as error:
            report[slot] = {'error': str(error)[:160]}
            continue
        row = {'adapter': value.get('adapter', 'codex_cli')}
        for key in ('model', 'preset', 'base_url', 'command'):
            if value.get(key) is not None:
                row[key] = value[key] if key != 'command' else value[key][:1] + ['…']
        row['available'] = available(cfg, slot)
        report[slot] = row
    return report


def codex_overrides(cfg, slot):
    """Extra `-c` arguments for the author slot's provider, when it names one.

    The author phase is always the Codex session (it owns the files and tools); a slot
    can change which endpoint answers behind it: `base_url` + `wire` + `key_env` become
    a model_providers entry, so DeepSeek, Qwen or Gemini can author a deck through the
    same harness. The key is read here and passed as the environment variable `key_env`
    names, never written into a task folder.
    """
    value = slot_config(cfg, slot)
    if value.get('adapter') != 'codex_cli':
        return []
    provider = value.get('provider')
    if not provider:
        return []
    if not isinstance(provider, dict):
        raise ValueError(f'model_slots.{slot}.provider must be an object')
    name = provider.get('id') or slot
    base = provider.get('base_url')
    if not isinstance(base, str) or not base.startswith(('https://', 'http://localhost', 'http://127.0.0.1')):
        raise ValueError(f'model_slots.{slot}.provider.base_url must be an https URL')
    imports = []
    parts = [f'model_providers.{name}.name="{provider.get("name") or name}"',
             f'model_providers.{name}.base_url="{base.rstrip("/")}"']
    if provider.get('key_env'):
        parts.append(f'model_providers.{name}.env_key="{provider["key_env"]}"')
        imports.append(provider['key_env'])
    if provider.get('wire'):
        parts.append(f'model_providers.{name}.wire_api="{provider["wire"]}"')
    if value.get('model'):
        parts.append(f'model="{value["model"]}"')
        parts.append(f'model_provider="{name}"')
    arguments = []
    for part in parts:
        arguments += ['-c', part]
    return [{'args': arguments, 'env_keys': imports}]


def second_model(cfg, slot):
    """Whether this slot is answered by an outside model rather than the author backend."""
    try:
        return slot_config(cfg, slot).get('adapter', 'codex_cli') != 'codex_cli'
    except (ValueError, OSError):
        return False


def author_profile(cfg):
    """A model profile for the author session when the author slot names an API model.

    Returns None when the author keeps the operator's Codex default. The profile uses the
    same shape as `model_backend.load_profile` and is merged into the existing profile by
    the caller, so a website-selected customer profile still wins.
    """
    value = slot_config(cfg, 'author')
    if value.get('adapter') != 'openai_api':
        return None
    return {'model': value['model'], 'base_url': value['base_url'], 'wire_api': value.get('wire', 'chat_completions'),
            'api_key': _key_for('author', value),
            **({'reasoning_effort': value['effort']} if value.get('effort') else {})}


def templates():
    """Presets for configure-models.py and the docs; no secrets."""
    return {'api': API_PRESETS, 'cli': CLI_PRESETS}

