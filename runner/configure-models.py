"""Choose the model behind each slot in the worker; one command per change.

    python configure-models.py --show
    python configure-models.py --set visual_review '{"adapter":"claude_cli","model":"opus"}'
    python configure-models.py --preset content_review deepseek deepseek-chat
    python configure-models.py --cli critique 'gemini --model {model} -p {prompt} {images}'
    python configure-models.py --key content_review          # hidden prompt, private key file
    python configure-models.py --test content_review         # one real call, no deck
    python configure-models.py --clear visual_review

Slots: author, research_helper, content_review, visual_review, critique, advisor,
image_generation. Adapters: codex_cli (the author's Codex session; `provider` points it at
another OpenAI-compatible endpoint), claude_cli, openai_api, cli (any installed CLI).

The key is never accepted on the command line and never printed: --key reads it hidden and
saves it to runner/keys/<slot>.key with mode 0600, which the slot then names. Settings stay
in runner/settings.local.json (private, untracked). See docs/model-slots.md.
"""
import argparse
import getpass
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import model_slots  # noqa: E402

SETTINGS = HERE / 'settings.local.json'
KEYS = HERE / 'keys'


def load(path):
    return json.loads(Path(path).read_text()) if Path(path).exists() else {}


def write_private(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(value)
    os.replace(temporary, path)


def save_slots(path, slots):
    settings = load(path)
    settings['model_slots'] = {k: slots[k] for k in model_slots.SLOTS if k in slots}
    for slot, value in settings['model_slots'].items():   # fail before writing anything
        model_slots.validate(slot, dict(value))
    write_private(path, json.dumps(settings, indent=1, ensure_ascii=False) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--settings', type=Path, default=SETTINGS)
    parser.add_argument('--show', action='store_true', help='print every slot, its route and whether it can run here')
    parser.add_argument('--set', nargs=2, metavar=('SLOT', 'JSON'), action='append', default=[],
                        help='replace one slot with this object')
    parser.add_argument('--preset', nargs=3, metavar=('SLOT', 'PROVIDER', 'MODEL'), action='append', default=[],
                        help='an OpenAI-compatible provider from model_slots.API_PRESETS')
    parser.add_argument('--cli', nargs=2, metavar=('SLOT', 'COMMAND'), action='append', default=[],
                        help='any installed CLI; use {prompt}, {model}, {images} placeholders')
    parser.add_argument('--key', metavar='SLOT', action='append', default=[],
                        help='read an API key hidden and save it to keys/<slot>.key (private)')
    parser.add_argument('--test', metavar='SLOT', action='append', default=[],
                        help='make one real call through the slot and print the model that answered')
    parser.add_argument('--clear', metavar='SLOT', action='append', default=[])
    args = parser.parse_args()
    settings = load(args.settings)
    slots = dict(settings.get('model_slots') or {})

    for slot, raw in args.set:
        slots[slot] = json.loads(raw)
    for slot, provider, model in args.preset:
        if provider not in model_slots.API_PRESETS:
            raise SystemExit('Unknown provider; use one of: ' + ', '.join(model_slots.API_PRESETS))
        slots[slot] = {'adapter': 'openai_api', 'preset': provider, 'model': model}
    for slot, command in args.cli:
        slots[slot] = {'adapter': 'cli', 'command': command.split(), 'prompt_mode': 'arg'}
    for slot in args.key:
        KEYS.mkdir(mode=0o700, exist_ok=True)
        key = getpass.getpass(f'{slot} API key (hidden, saved to {KEYS.relative_to(HERE)}/{slot}.key): ')
        if not key or any(c in key for c in '\r\n'):
            raise SystemExit('A key must be non-empty and on one line')
        target = KEYS / (slot + '.key')
        write_private(target, key.strip() + '\n')
        slots[slot] = {**slots.get(slot, {}), 'key_file': str(target)}
        print('Saved', target, '(mode 600)')
    for slot in args.clear:
        slots.pop(slot, None)
        print('Cleared', slot)
    changed = any((args.set, args.preset, args.cli, args.key, args.clear))
    if changed:
        save_slots(args.settings, slots)
        print('Saved', args.settings)
    if args.show or not changed:
        for slot, row in model_slots.describe(load(args.settings)).items():
            print(f'{slot:16} {json.dumps(row, ensure_ascii=False)}')
    for slot in args.test:
        import claude_vision
        cfg = load(args.settings)
        try:
            answer = claude_vision.ask(cfg, 'Answer with the single word: ok', slot=slot, timeout=120)
        except claude_vision.ClaudeUnavailable as error:
            print(f'{slot}: unavailable — {error}')
            continue
        print(f'{slot}: {answer.get("adapter")} answered with {answer.get("model")} in {answer.get("seconds")}s')


if __name__ == '__main__':
    main()
