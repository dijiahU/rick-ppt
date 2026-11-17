"""Prepare/check distinct worker checkouts without touching production services."""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runner'))
from environment_profile import validate


def private_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as f:
        f.write(text)


def initialize_local(root, python, port=3000):
    root = Path(root).resolve()
    worker = root / 'runner'
    settings = worker / 'settings.local.json'
    marker = worker / 'deployment.local.json'
    binding = root / 'website/.dev.vars'
    if any(p.exists() for p in (settings, marker, binding, root / 'website/.env.local')):
        raise ValueError('Existing private configuration preserved; use check instead')
    python = Path(python).absolute()  # Keep venv symlink identity.
    if not python.is_file():
        raise ValueError('Create the development Python environment first')
    if not 1 <= port <= 65535:
        raise ValueError('Invalid local port')
    source = root / 'pptx-agent'
    version = json.loads((source / '.codex-plugin/plugin.json').read_text())['version']
    if not version or Path(version).name != version or version in ('.', '..'):
        raise ValueError('Invalid plugin version')
    runtime = worker / 'runtime' / version / 'pptx-agent'
    if runtime.exists():
        raise ValueError('Existing runtime preserved; initialize a fresh checkout')
    token = secrets.token_hex(32)
    cfg = {'deployment_environment': 'local', 'site': f'http://127.0.0.1:{port}',
           'token': token, 'python': str(python), 'plugin': str(runtime),
           'blank': str(runtime / 'skills/pptx/assets/blank.pptx'),
           'state_directory': str(worker / 'state/local'), 'capacity': 1,
           'parallel_reviews': True, 'job_timeout_seconds': 5400,
           'author_context_mode': 'continuous'}
    validate(cfg, worker, expected='local')
    # A separate immutable initial plugin copy; normal stage-runtime.py updates
    # remain explicit and retain their own self-tests. No model calls here.
    shutil.copytree(source, runtime, ignore=shutil.ignore_patterns(
        '.venv', 'node_modules', '__pycache__', '.pytest_cache', 'test-results'))
    private_write(settings, json.dumps(cfg, indent=2) + '\n')
    private_write(marker, '{"environment":"local"}\n')
    private_write(binding, 'WORKER_TOKEN=' + token + '\nREVIEW_TOKEN=' + secrets.token_hex(32)
                  + '\nBYOK_ENCRYPTION_KEY=' + secrets.token_hex(32) + '\n')
    return cfg


BROWSER_SITES = ['https://www.xiaohongshu.com', 'https://x.com', 'https://www.pinterest.com', 'https://www.google.com']


def initialize_mac(root, python, site):
    """Production worker on the operator's Mac, in its own checkout.

    The generated token is the site's LOCAL_WORKER_TOKEN (see copy-token); it is
    written only to this checkout's private settings and never printed.
    """
    root = Path(root).resolve()
    worker = root / 'runner'
    settings = worker / 'settings.local.json'
    marker = worker / 'deployment.local.json'
    if any(p.exists() for p in (settings, marker)):
        raise ValueError('Existing private configuration preserved; use check instead')
    python = Path(python).absolute()
    if not python.is_file():
        raise ValueError('Python interpreter not found')
    source = root / 'pptx-agent'
    version = json.loads((source / '.codex-plugin/plugin.json').read_text())['version']
    if not version or Path(version).name != version or version in ('.', '..'):
        raise ValueError('Invalid plugin version')
    runtime = worker / 'runtime' / version / 'pptx-agent'
    if runtime.exists():
        raise ValueError('Existing runtime preserved; initialize a fresh checkout')
    cfg = {'deployment_environment': 'mac', 'site': site.rstrip('/'),
           'token': secrets.token_hex(32), 'python': str(python), 'plugin': str(runtime),
           'blank': str(runtime / 'skills/pptx/assets/blank.pptx'),
           'state_directory': str(worker / 'state/mac'), 'capacity': 5,
           'parallel_reviews': True, 'job_timeout_seconds': 7200,
           'author_context_mode': 'continuous', 'default_service_tier': 'fast',
           'browser_research': {'enabled': True, 'browser': 'edge', 'sites': BROWSER_SITES}}
    validate(cfg, worker, expected='mac')
    shutil.copytree(source, runtime, ignore=shutil.ignore_patterns(
        '.venv', 'node_modules', '__pycache__', '.pytest_cache', 'test-results'))
    private_write(settings, json.dumps(cfg, indent=2) + '\n')
    private_write(marker, '{"environment":"mac"}\n')
    return cfg


def inspect(root, expected):
    worker = Path(root).resolve() / 'runner'
    cfg = json.loads((worker / 'settings.local.json').read_text())
    validate(cfg, worker, expected=expected)
    missing = [key for key in ('python', 'plugin', 'blank') if not Path(cfg[key]).exists()]
    if missing:
        raise ValueError('Missing configured paths: ' + ', '.join(missing))
    if len(cfg.get('token', '')) < 32:
        raise ValueError('Worker token too short')
    # Whitelist the public report. Never return the settings mapping or token.
    return cfg, {'environment': expected, 'site': cfg['site'],
                 'code_directory': str(worker.parent), 'state_directory': cfg['state_directory'],
                 'runtime': cfg['plugin'], 'configuration_valid': True,
                 'service_running_checked': False}


def local_launch(root, cfg, reload=False):
    env = dict(os.environ)
    # Old shell exports must not choose another checkout's state or API profile.
    for key in list(env):
        if key.startswith('PPTX_RUNNER_') or key in ('PPTX_AUTHOR_CONTEXT_MODE', 'PPTX_USAGE_PRICING_FILE'):
            env.pop(key)
    env['PPTX_WORKER_AC_ONLY'] = '1'
    for key in ('NO_PROXY', 'no_proxy'):
        env[key] = ','.join(filter(None, [env.get(key), 'localhost,127.0.0.1,::1']))
    command = [cfg['python'], str(Path(root) / 'runner/start-worker.py')]
    if reload:
        command.append('--reload')
    return command, env


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    init = sub.add_parser('init-local')
    init.add_argument('--python', type=Path, default=ROOT / '.venv/bin/python')
    init.add_argument('--port', type=int, default=3000)
    check = sub.add_parser('check')
    check.add_argument('environment', choices=['local', 'server', 'mac'])
    start = sub.add_parser('start-local')
    start.add_argument('--reload', action='store_true')
    init_mac = sub.add_parser('init-mac', help='Production worker on this Mac (own checkout)')
    init_mac.add_argument('--site', required=True, help='Hosted website origin, https://...')
    init_mac.add_argument('--python', type=Path, default=ROOT / '.venv/bin/python')
    start_mac = sub.add_parser('start-mac')
    start_mac.add_argument('--reload', action='store_true')
    sub.add_parser('copy-token', help='Copy this Mac worker token to the clipboard for LOCAL_WORKER_TOKEN')
    args = p.parse_args()
    try:
        if args.action == 'init-local':
            initialize_local(ROOT, args.python, args.port)
            _, report = inspect(ROOT, 'local')
        elif args.action == 'init-mac':
            initialize_mac(ROOT, args.python, args.site)
            _, report = inspect(ROOT, 'mac')
        elif args.action in ('start-mac', 'copy-token'):
            cfg, report = inspect(ROOT, 'mac')
        else:
            cfg, report = inspect(ROOT, args.environment if args.action == 'check' else 'local')
        if args.action == 'copy-token':
            # Clipboard only: the secret never reaches stdout, logs or prompts.
            subprocess.run(['/usr/bin/pbcopy'], input=cfg['token'].encode(), check=True)
            print('Copied this Mac worker token; set it as the site secret LOCAL_WORKER_TOKEN.')
            return 0
        print(json.dumps(report, ensure_ascii=False), flush=True)
        if args.action in ('start-local', 'start-mac'):
            command, env = local_launch(ROOT, cfg, args.reload)
            return subprocess.call(command, cwd=ROOT, env=env)
        return 0
    except (ValueError, OSError, KeyError) as error:
        # Configuration parsing may contain secrets; do not dump raw contents.
        print('Environment check failed: ' + (str(error) if isinstance(error, ValueError)
              and not isinstance(error, json.JSONDecodeError) else type(error).__name__), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
