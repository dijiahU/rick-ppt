"""Opt-in Edge connection diagnostic for the local worker.

Uses the installed official browser client and Node MCP. It does not export
cookies, grant website permissions, enable browser tools for normal jobs, or
establish that an authenticated website is readable merely by connecting.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time
import tomllib

from durable import AppServer, task_configuration, TransportError, RPCError
from model_backend import DEFAULT_TASK_MODEL, DEFAULT_TASK_REASONING_EFFORT


def installed_runtime(config_file=None):
    codex = Path(os.environ.get('CODEX_HOME', Path.home() / '.codex'))
    # Read only in the host. Never return or log the MCP environment/credentials.
    config = tomllib.loads(Path(config_file or codex / 'config.toml').read_text())
    server = config.get('mcp_servers', {}).get('node_repl', {})
    version = server.get('env', {}).get('BROWSER_USE_CODEX_APP_VERSION', '')
    if not isinstance(version, str) or not version or Path(version).name != version or version in ('.', '..'):
        raise ValueError('Installed browser component version is unavailable')
    command = Path(server.get('command', ''))
    if (not command.is_absolute() or command.name != 'node_repl'
            or command.parent.name != 'bin' or not command.is_file()):
        raise ValueError('Installed browser Node runtime is unavailable')
    plugins = codex / 'plugins/cache/openai-bundled'
    paths = {'chrome_plugin': plugins / 'chrome' / version,
             'browser_plugin': plugins / 'browser' / version,
             'node_runtime': command.parent.parent}
    validate_runtime(paths)
    return paths


def validate_runtime(paths):
    for key, relative in (
        ('chrome_plugin', 'scripts/browser-client.mjs'),
        ('chrome_plugin', 'skills/control-chrome/SKILL.md'),
        ('browser_plugin', 'scripts/browser-service.mjs'),
        ('node_runtime', 'bin/node'),
        ('node_runtime', 'bin/node_repl'),
    ):
        if not (Path(paths[key]) / relative).is_file():
            raise ValueError('Missing installed browser component: ' + key)
    if not (Path(paths['node_runtime']) / 'lib/node_modules').is_dir():
        raise ValueError('Installed browser dependencies are unavailable')


def browser_configuration(workspace, paths):
    """Exact installed code read grants; browser policy remains authoritative."""
    validate_runtime(paths)
    config = task_configuration(workspace, web_search='disabled', read_roots=list(paths.values()))
    # Bundled macOS Node probes this path even when the config is absent.
    # EPERM aborts OpenSSL initialization; allowing this exact read preserves
    # normal missing-file behavior without exposing a private directory.
    if sys.platform == 'darwin':
        config['permissions']['pptx_job']['filesystem']['/System/Library/OpenSSL/openssl.cnf'] = 'read'
    config['features'].update(browser_use=True, browser_use_external=True, image_generation=False)
    config['mcp_servers.node_repl.enabled'] = True
    roots = [paths['browser_plugin'], paths['chrome_plugin'], Path(paths['node_runtime']) / 'lib/node_modules']
    config['mcp_servers.node_repl.env.NODE_REPL_TRUSTED_CODE_PATHS'] = ':'.join(str(Path(p).resolve()) for p in roots)
    return config


def connection_probe(output, paths, *, model=DEFAULT_TASK_MODEL, effort=DEFAULT_TASK_REASONING_EFFORT):
    """No site navigation. A connection receipt is never an access receipt."""
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / 'tmp').mkdir()
    config = browser_configuration(output, paths)
    config.update(model=model, model_reasoning_effort=effort)
    prompt = (
        'Run only an Edge connection diagnostic for Rick. Use only the exposed Node REPL js tool '
        'and the installed official browser client. Follow the complete Browser instructions below. '
        'Initialize once, select Edge, emit and read its complete documentation. Then list this '
        'session\'s tabs once; do not request user open tabs/history. Do not navigate to any website, '
        'inspect pages, open another browser, change permissions, read browser profiles/cookies or '
        'attempt another transport. An empty session tab list is a successful connection, not a failure. '
        'Stop on a denied action. Return a concise connection result. Website permissions and login '
        'inheritance remain unverified regardless of connection success.\n\n'
        + (Path(paths['chrome_plugin']) / 'skills/control-chrome/SKILL.md').read_text()
    )
    started = time.monotonic()
    calls = []
    def event(value):
        item = value.get('item') or {}
        if value.get('type') == 'item.completed' and item.get('type') == 'mcp_tool_call':
            # No page contents, tool arguments, account data or raw errors.
            calls.append({'tool': item.get('tool'), 'status': item.get('status')})
    result = {'connection': 'unverified', 'website_access': 'not_tested',
              'login_inheritance': 'not_tested', 'production_enabled': False}
    try:
        with AppServer(cwd=output, config=config, on_event=event,
                       enabled_mcp_servers=('node_repl',)) as server:
            thread = server.start_thread()['thread']['id']
            turn = server.start_turn(thread, prompt)['id']
            completed = server.wait_turn(thread, turn, timeout=120)
            result.update(turn_status=completed.get('status'),
                          model_report=server.result_text(thread, turn),
                          usage=server.usage.get((thread, turn), {}))
            # The natural-language answer remains a model report, not an
            # independent host assertion of connection or authenticated access.
    except (TransportError, RPCError, OSError, ValueError) as error:
        result.update(turn_status='failed', error_type=type(error).__name__)
    result.update(seconds=round(time.monotonic()-started, 2), tool_calls=calls)
    with (output / 'connection-result.json').open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe-connection', type=Path, help='New private output directory; starts one local Codex turn, without navigating to any site')
    parser.add_argument('--model', default=DEFAULT_TASK_MODEL)
    parser.add_argument('--effort', default=DEFAULT_TASK_REASONING_EFFORT)
    args = parser.parse_args()
    paths = installed_runtime()
    if args.probe_connection:
        result = connection_probe(args.probe_connection, paths, model=args.model, effort=args.effort)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({'installed_components': 'present', 'paths': {k:str(v) for k,v in paths.items()},
                          'connection': 'not_tested', 'website_access': 'not_tested', 'production_enabled': False}, indent=2))


if __name__ == '__main__':
    main()
