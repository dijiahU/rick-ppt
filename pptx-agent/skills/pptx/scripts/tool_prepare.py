"""Prepare task-local, current-version tool interfaces without choosing a design.

No PPTX, source, decision plan or review is modified. The host supplies its actual
Python invocation path; retaining a venv symlink path is intentional.
"""
import argparse
import hashlib
import importlib
import inspect
import json
import os
from pathlib import Path
import shlex
import sys
import types
import uuid

SCRIPTS = Path(__file__).resolve().parent


def _module(name):
    # Isolate versions if a host already imported another plugin's pptx_core.
    prefix = '_pptx_tool_prepare_' + hashlib.sha256(str(SCRIPTS).encode()).hexdigest()[:16]
    if prefix not in sys.modules:
        package = types.ModuleType(prefix)
        package.__path__ = [str(SCRIPTS)]
        sys.modules[prefix] = package
    return importlib.import_module(prefix + '.' + name)


def _read(path, root):
    if not path.resolve().is_relative_to(root):
        raise ValueError('Preparation input escaped the task: ' + path.name)
    current = root
    for component in path.relative_to(root).parts:
        current = current / component
        if current.is_symlink():
            raise ValueError('Preparation input must not use symlinks: ' + path.name)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Expected a bounded task-local JSON file: ' + path.name)
    return json.loads(path.read_text())


def _write(root, name, value):
    path = root / name
    if path.is_symlink():
        raise ValueError('Tool preparation output must not be a symlink: ' + name)
    pending = root / ('.' + name + '.' + uuid.uuid4().hex + '.pending')
    try:
        with pending.open('x') as stream:
            stream.write(value)
        os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)
    return str(path)


def _parameters(function):
    return {'signature': str(inspect.signature(function)), 'parameters': [
        {'name': name, 'kind': param.kind.name, 'required': param.default is inspect.Parameter.empty,
         **({} if param.default is inspect.Parameter.empty else {'default': param.default})}
        for name, param in inspect.signature(function).parameters.items()]}


def _cli_contract():
    parser = _module('pptx_core.cli').parser()
    choices = next(a.choices for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    result = {}
    for name in ('unpack', 'list', 'inspect', 'find', 'refs', 'validate', 'render', 'diff', 'snapshot', 'rollback', 'export'):
        command = choices[name]
        result[name] = {'usage': command.format_usage().strip(), 'arguments': [
            {'name': action.dest, 'flags': action.option_strings, 'required': action.required,
             'choices': list(action.choices) if action.choices is not None else None,
             'nargs': action.nargs}
            for action in command._actions if action.dest != 'help']}
    return {'global_workspace_before_subcommand': True, 'commands': result}


def prepare_tool_manifest(task_root, *, python=None, workspace=None):
    root = Path(task_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Task root must be a directory')
    # resolve() would turn venv/bin/python into a system binary invocation.
    interpreter = os.path.abspath(os.fspath(python or sys.executable))
    if not Path(interpreter).is_file() or not os.access(interpreter, os.X_OK):
        raise ValueError('Host-provided Python must be an executable file')
    session_dir = parts_dir = None
    if workspace is not None:
        given = Path(workspace).resolve(strict=True)
        if not given.is_relative_to(root):
            raise ValueError('Workspace must belong to this task')
        selected = _module('pptx_core.package').select(given)
        parts = selected.root.resolve(strict=True)
        home = selected.home.resolve(strict=True)
        if not parts.is_relative_to(root) or not home.is_relative_to(root):
            raise ValueError('Selected workspace escaped this task')
        session_dir, parts_dir = str(home), str(parts)
    canvas = _module('native_canvas')
    decisions = _module('workflow_decisions')
    catalog = decisions.load_catalog()
    outline_path = root / 'outline.json'
    outline = None
    scaffold_error = None
    if outline_path.exists():
        try:
            outline = _read(outline_path, root)
        except (json.JSONDecodeError, UnicodeError) as error:
            scaffold_error = type(error).__name__ + ': outline needs repair before scaffold generation'
    scaffold = None
    if outline is not None:
        if not isinstance(outline, dict) or not isinstance(outline.get('slides'), list):
            scaffold_error = 'outline.json needs ordered slides before scaffold preparation'
        else:
            ids = [page.get('id') for page in outline['slides'] if isinstance(page, dict)]
            if not ids or len(ids) != len(outline['slides']) or any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
                scaffold_error = 'Outline IDs must be present and unique'
            else:
                scaffold = decisions.plan_template(outline)
    attachments = []
    index = root / 'references/index.json'
    if index.exists():
        entries = _read(index, root)
        if not isinstance(entries, list):
            raise ValueError('Reference index must be a list')
        for entry in entries:
            relative = entry.get('path') if isinstance(entry, dict) else None
            if not isinstance(relative, str) or '\\' in relative or Path(relative).is_absolute() or '..' in Path(relative).parts:
                raise ValueError('Reference index needs actual task-relative paths')
            source = root / relative
            if source.is_symlink() or not source.resolve(strict=True).is_relative_to(root):
                raise ValueError('Reference path escaped the task')
            attachments.append({k: entry[k] for k in ('name', 'path', 'size', 'sha256') if k in entry})
    parts_arg = parts_dir or 'PARTS_DIR_FROM_UNPACK'
    cli = str(SCRIPTS / 'pptx.py')
    commands = {
        'refresh': [interpreter, str(SCRIPTS / 'tool_prepare.py'), '--task-root', str(root), '--python', interpreter],
        'unpack_selected_source': [interpreter, cli, 'unpack', 'SELECTED_SOURCE.pptx', '--base', str(root / 'projects')],
        'list_slides': [interpreter, cli, '--workspace', parts_arg, 'list', 'slides'],
        'inspect_page': [interpreter, cli, '--workspace', parts_arg, 'inspect', '1'],
        'validate': [interpreter, cli, '--workspace', parts_arg, 'validate'],
        'render_page': [interpreter, cli, '--workspace', parts_arg, 'render', '1'],
        'export': [interpreter, cli, '--workspace', parts_arg, 'export', 'exports/CHOSEN_VERSION.pptx'],
        'decision_scaffold': [interpreter, str(SCRIPTS / 'workflow_decisions.py'), '--template', '--outline', 'outline.json'],
        'planning_check': [interpreter, str(SCRIPTS / 'workflow_decisions.py'), '--plan', 'decision-plan.json', '--outline', 'outline.json', '--stage', 'planning'],
    }
    if parts_dir:
        commands['refresh'] += ['--workspace', parts_dir]
    progress = root / 'public-progress.py'
    if progress.is_file() and not progress.is_symlink():
        commands['publish_outline'] = [interpreter, str(progress), 'outline']
        commands['publish_building_note'] = [interpreter, str(progress), 'note', '--phase', 'building', '--summary', 'CURRENT_FACTUAL_PROGRESS']
    manifest = {
        'version': 1, 'python': interpreter, 'task_root': str(root),
        'session_dir': session_dir, 'parts_dir': parts_dir,
        'workspace_status': 'selected' if parts_dir else 'not_selected',
        'workspace_contract': {'pptx_cli': 'session_dir or parts_dir', 'native_builds': 'session_dir or parts_dir',
                               'native_canvas': 'parts_dir', 'design_references': 'parts_dir'},
        'commands': commands, 'pptx_cli': _cli_contract(),
        'native_canvas': {name: _parameters(getattr(canvas, name)) for name in
                          ('text_measure', 'add_text', 'add_image', 'add_shape', 'add_connector', 'semantic_group', 'reveal', 'add_bar_chart')},
        'decision_contract': {'version': catalog['version'], 'top_level_fields': ['version', 'task', 'pages', 'design_direction', 'references'],
                              'task_options': catalog['task'], 'page_options': catalog['page'],
                              'eligible_forms': catalog['eligible_forms'], 'asset_options': catalog['asset'],
                              'reference_options': catalog['reference'],
                              'page_fields': ['id', 'intent', 'strategy', 'form', 'support', 'composition', 'behavior', 'assets', 'role', 'visual_action', 'reference_ids'],
                              'reference_fields': ['id', 'kind', 'title', 'creator', 'source', 'inspection', 'evidence', 'observed', 'borrowed', 'applications'],
                              'reference_source': 'Credential-free HTTPS URL or exact task-relative path; no human-label prefix.',
                              'native_asset_records': 'none/source_grounded_native records contain only route.',
                              'file_asset_fields': ['route', 'kind', 'status', 'file', 'origin']},
        'outline_fields': {'required': ['title', 'purpose', 'slides'], 'page_required': ['id', 'title', 'summary']},
        'decision_scaffold': scaffold, 'scaffold_error': scaffold_error, 'attachments': attachments,
        'authority': 'Interface preparation only. The author selects content, visual expression and explicit branches; unchanged validators and reviews remain authoritative.'}
    lines = ['# Task tool quickstart', '', 'Read SKILL.md and task requirements. This guide prepares interfaces, not content or design.',
             '', f'Use this interpreter for every script and inline patch: `{interpreter}`. Do not use bare python/python3.',
             f'Parts directory: `{parts_dir}`' if parts_dir else 'No native workspace selected yet. Choose the task-appropriate source, unpack it, then refresh with the returned workspace path.',
             'pptx/native_builds accept session or parts directories; native_canvas/design_references need the parts directory.',
             'Put pptx --workspace before its subcommand. Use list slides, inspect N, render N; unpack uses --base, not --output.', '', '```sh']
    lines += [shlex.join(argv) for argv in commands.values()]
    lines += ['```', '', 'SELECTED_SOURCE / CHOSEN_VERSION and page 1 are replaceable examples, not template/style selections.',
              'The manifest contains exact CLI arguments, native_canvas Python signatures and current decision options.',
              'add_text uses font_file,size,ink and x/y/width/max_height; box belongs to other helpers. Use returned object handles for links/groups/reveals.',
              'Before edits take a snapshot. A failed multi-object script can leave earlier changes saved: inspect or restore before retry; never append hardcoded IDs.',
              'Write outline.slides, not outline.pages. Generate the unselected scaffold only after outline IDs/order exist. Do not infer aesthetics from choice counts.',
              'reference.source is the exact HTTPS URL or actual attachment path below; provenance labels go in title/observed. Ready file assets need file/kind/status/origin; native/no-asset records only route.',
              'Choose and execute every required finite branch yourself. Preserve source invariants, meaningful native reveals, sequential authoring, actual rendering and independent reviews.', '']
    lines += [f'- `{a["path"]}` ({a.get("name", "attachment")})' for a in attachments]
    manifest_path = _write(root, 'tool-manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    guide_path = _write(root, 'tool-quickstart.md', '\n'.join(lines) + '\n')
    return {'manifest': manifest_path, 'quickstart': guide_path, 'python': interpreter,
            'session_dir': session_dir, 'parts_dir': parts_dir}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task-root', default='.')
    parser.add_argument('--python', help='Exact host interpreter invocation; defaults to sys.executable')
    parser.add_argument('--workspace', help='Existing task-local session or parts directory; never automatically unpack')
    args = parser.parse_args()
    print(json.dumps(prepare_tool_manifest(args.task_root, python=args.python, workspace=args.workspace), ensure_ascii=False))


if __name__ == '__main__':
    main()
