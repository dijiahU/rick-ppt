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
    # Refreshing material pointers must not discard the author's explicit
    # native selection. Reuse only that exact, still-valid task-local workspace;
    # never discover another candidate or follow a historical external path.
    previous = root / 'tool-manifest.json'
    if workspace is None and previous.is_file():
        try:
            candidate = _read(previous, root).get('parts_dir')
            given = Path(candidate) if isinstance(candidate, str) and candidate else None
            if given and given.is_absolute() and given.is_relative_to(root) and given.resolve().is_relative_to(root):
                selected = _module('pptx_core.package').select(given)
                if selected.root.is_dir() and selected.home.is_relative_to(root):
                    workspace = given
        except (OSError, ValueError, AttributeError, KeyError, TypeError, _module('pptx_core.common').PptxError):
            pass  # No valid retained selection; require the usual explicit refresh.
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
    plan_check = {'status': 'not_present'}
    if outline is not None:
        if not isinstance(outline, dict) or not isinstance(outline.get('slides'), list):
            scaffold_error = 'outline.json needs ordered slides before scaffold preparation'
        else:
            ids = [page.get('id') for page in outline['slides'] if isinstance(page, dict)]
            if not ids or len(ids) != len(outline['slides']) or any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
                scaffold_error = 'Outline IDs must be present and unique'
            else:
                scaffold = decisions.plan_template(outline)
    if (root / 'decision-plan.json').exists() and scaffold is not None:
        try:
            plan = _read(root / 'decision-plan.json', root)
            request = _read(root / 'request.json', root) if (root / 'request.json').exists() else {}
            decisions.validate_plan(plan, outline, root=root,
                                    mode=request.get('mode', plan.get('task', {}).get('operation', 'create')))
            plan_check = {'status': 'valid', 'scope': 'Existing planning contract and local file checks; not design quality or visual inspection.'}
        except (OSError, ValueError) as error:
            plan_check = {'status': 'needs_repair', 'detail': str(error),
                          'scope': 'Retain current files and repair the existing record; no new admission gate.'}
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
        'compatibility': [interpreter, str(SCRIPTS / 'compatibility.py'), '--workspace', parts_arg],
        'decision_scaffold': [interpreter, str(SCRIPTS / 'workflow_decisions.py'), '--template', '--outline', 'outline.json'],
        'planning_check': [interpreter, str(SCRIPTS / 'workflow_decisions.py'), '--plan', 'decision-plan.json', '--outline', 'outline.json', '--stage', 'planning'],
    }
    batch_script = SCRIPTS / 'native_batch.py'
    planning_script = SCRIPTS / 'planning_commit.py'
    pages_script = SCRIPTS / 'native_pages.py'
    if planning_script.is_file():
        commands['planning_commit'] = [interpreter, str(planning_script), '--task-root', str(root),
                                        '--input', 'planning-input.json']
    if pages_script.is_file():
        commands['ensure_next_page'] = [interpreter, str(pages_script), '--task-root', str(root),
                                         '--workspace', parts_arg, '--page', 'CHOSEN_PAGE',
                                         '--key', 'STABLE_PAGE_OPERATION_ID', '--mode', 'blank_from_layout',
                                         '--source-slide', 'CHOSEN_LAYOUT_SOURCE_PAGE']
    if batch_script.is_file():
        commands['native_page_batch'] = [interpreter, str(batch_script), '--task-root', str(root),
                                         '--workspace', parts_arg, '--input', 'CHOSEN_PAGE_BATCH.json']
    candidate_script = SCRIPTS / 'candidate_save.py'
    if candidate_script.is_file():
        commands['save_candidate'] = [interpreter, str(candidate_script), '--task-root', str(root),
                                      '--workspace', parts_arg, '--output', 'exports/CHOSEN_VERSION.pptx']
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
        'plan_check': plan_check,
        'native_authoring': {
            'python_module': 'native_canvas', 'module_directory': str(SCRIPTS),
            'guide': str(SCRIPTS.parent / 'references/native-canvas.md'),
            'workspace': 'parts_dir',
            'object_handles': 'Use returned workspace/slide/shape_id handles directly for connectors, groups and reveals.',
            'implementation': 'Helper geometry choices describe this callable, not the full PowerPoint geometry range. Use supported operations where suitable; direct OOXML remains available for unsupported native features and deliberate richer geometry. No fixed page layout.',
            'verification': 'Font coverage, text fit and endpoint checks do not establish design quality or target-player playback.'},
        'native_canvas': {name: _parameters(getattr(canvas, name)) for name in
                          ('check_glyphs', 'text_measure', 'add_text', 'add_image', 'add_shape', 'add_path', 'add_connector', 'semantic_group', 'reveal', 'add_bar_chart')},
        'decision_contract': {'version': catalog['version'], 'top_level_fields': ['version', 'task', 'template_preservation', 'pages', 'design_direction', 'references'],
                              'task_options': catalog['task'], 'page_options': catalog['page'],
                              'asset_options': catalog['asset'],
                              'reference_options': catalog['reference'],
                              'page_fields': ['id', 'behavior', 'assets'],
                              'optional_page_fields': ['role', 'visual_action', 'intent', 'strategy', 'form', 'support', 'composition', 'reference_ids'],
                              'design_choices': 'Optional free descriptions; no design taxonomy or form eligibility gate.',
                              'reference_associations': 'Derived from references[].applications[].pages; record each application once.',
                              'reference_fields': ['id', 'kind', 'title', 'creator', 'source', 'inspection', 'evidence', 'observed', 'borrowed', 'applications'],
                              'reference_source': 'Credential-free HTTPS URL or exact task-relative path; no human-label prefix.',
                              'native_asset_records': 'none/source_grounded_native records contain only route.',
                              'file_asset_fields': ['route', 'kind', 'status', 'file', 'origin']},
        'outline_fields': {'required': ['title', 'purpose', 'slides'], 'page_required': ['id', 'title', 'summary']},
        'command_outputs': {'decision_scaffold': 'Prints unselected JSON to stdout; does not create decision-plan.json. Save/fill it explicitly.'},
        'decision_scaffold': scaffold, 'scaffold_error': scaffold_error, 'attachments': attachments,
        'authority': 'Interface preparation only. The author selects content and visual expression; validators check delivery records, assets and behavior; reviews judge the actual result.'}
    manifest['native_canvas']['add_shape']['choices'] = {'geometry': list(canvas.SHAPE_GEOMETRIES)}
    if planning_script.is_file():
        manifest['planning_commit'] = {
            'guide': str(SCRIPTS.parent / 'references/planning-commit.md'),
            'command': commands['planning_commit'],
            'document': {'version': 1, 'outline': 'Complete current outline object',
                         'decisions': 'Complete current v4 delivery record; open design direction and explicit protected template elements',
                         'source_notes': 'Original nonempty Markdown evidence and page/build plan; alternatively replace this key with source_notes_file'},
            'source_notes_file': 'Alternative to source_notes: existing task-local UTF-8 Markdown path, e.g. source-notes.md. Reads exact bytes; never include both keys.',
            'options': {'mode': 'Add --mode create or edit exactly as selected by the host.',
                        'expected_pages': 'Add --expected-pages with the resolved task total when fixed.',
                        'allow_legacy': 'Only for explicitly historically admitted contracts.'},
            'outputs': ['outline.json', 'decision-plan.json', 'source-notes.md'],
            'validation': 'Checks current outline and planning decisions before transactional commit; does not select branches or certify facts/design.'}
    if candidate_script.is_file():
        manifest['candidate_save'] = {'command': commands['save_candidate'],
            'operation': 'Native export with real render, existing authored check when records exist, then atomic delivery.json update.',
            'scope': 'Complete candidate only. No independent review or aesthetic/playback verdict. Failure leaves the prior declaration unchanged; older exports remain immutable.'}
    if pages_script.is_file():
        manifest['native_pages'] = {
            'guide': str(SCRIPTS.parent / 'references/native-pages.md'),
            'command': commands['ensure_next_page'],
            'mode': 'blank_from_layout',
            'selection': 'Explicit --source-slide N or --layout EXISTING_LAYOUT_PART; no style/layout selection by the tool.',
            'retry': 'Same persistent --key and request reuse the same page even after it has been edited.',
            'scope': 'Reuse existing pages or append only the next page with the existing layout/master/theme chain. Not a clone of source objects, notes or animation.'}
    if batch_script.is_file():
        # Derive the JSON call contract from the same functions used by the
        # batch implementation. Do not make the model translate Python-only
        # workspace arguments or rediscover optional/required parameter names.
        operations = {'text': 'add_text', 'shape': 'add_shape', 'path': 'add_path', 'image': 'add_image',
                      'connector': 'add_connector', 'group': 'semantic_group',
                      'reveal': 'reveal', 'bars': 'add_bar_chart'}
        manifest['native_batch'] = {
            'guide': str(SCRIPTS.parent / 'references/native-batch.md'),
            'document_fields': ['version', 'batch_id', 'operations'], 'version': 1,
            'optional_document_fields': ['defaults', 'source_frame'],
            'source_frame': {'fields': ['image', 'box'], 'box': 'Destination x,y,w,h in slide inches.',
                             'coordinates': 'With source_frame, operation geometry uses oriented source pixels; font sizes and line widths remain points. Uniform contain, no distortion.',
                             'identity': 'Source bytes/dimensions/transform recorded, not embedded or claimed viewed.'},
            'defaults': {op: sorted(fields) for op, fields in canvas.BATCH_STYLE_FIELDS.items()},
            'operation_fields': 'op,id,slide plus exact native_canvas helper parameters; reveal has no id',
            'operations': operations,
            'operation_choices': {'shape': {'geometry': list(canvas.SHAPE_GEOMETRIES)}},
            'operation_parameters': {op: manifest['native_canvas'][name]['parameters'][2:]
                                     for op, name in operations.items()},
            'references': 'Earlier id string or existing positive integer object ID, same page only.',
            'text_height': 'Numeric max_height is strict; explicit auto measures without shrinking.',
            'transaction': 'Checks every text first, stages all objects, commits on success, rolls back on failure; exact successful retries do not append.',
            'scope': 'One existing page per batch; content, coordinates, actual assets/style and page order are author choices.'}
    recreation = SCRIPTS / 'recreation_tools.py'
    if recreation.is_file():
        manifest['image_recreation'] = {
            'guide': str(SCRIPTS.parent / 'references/image-recreation.md'),
            'inspect': [interpreter, str(recreation), 'inspect', '--task-root', str(root),
                        '--source', 'SOURCE_IMAGE', '--regions', 'REGIONS_JSON', '--out', 'FRESH_OUTPUT_DIR'],
            'compare': [interpreter, str(recreation), 'compare', '--task-root', str(root),
                        '--source', 'SOURCE_IMAGE', '--render', 'ACTUAL_RENDER',
                        '--regions', 'INSPECT_RECEIPT_JSON', '--out', 'FRESH_OUTPUT_DIR'],
            'scope': 'Task-local images; explicit source-pixel regions; hashes and dimensions in receipt. Open output images; no inspection or quality claim.'}
    page_design = SCRIPTS / 'page_design.py'
    if page_design.is_file():
        commands['page_design_context'] = [interpreter, str(page_design), 'context', '--task-root', str(root),
                                            '--page-id', 'ACTUAL_OUTLINE_PAGE_ID']
        if parts_dir:
            commands['page_design_context'] += ['--workspace', parts_dir]
        commands['record_design_observation'] = [interpreter, str(page_design), 'record', '--task-root', str(root),
                                                  '--page-id', 'ACTUAL_OUTLINE_PAGE_ID', '--workspace', parts_arg,
                                                  '--input', 'CHOSEN_CONSEQUENTIAL_OBSERVATION.json']
        manifest['page_design'] = {
            'guide': str(SCRIPTS.parent / 'references/page-design.md'),
            'context_command': commands['page_design_context'],
            'record_command': commands['record_design_observation'],
            'handoff_index': _module('page_design').handoff_index(root),
            'notes_marker': 'Optional pptx-handoff JSON fence in source-notes.md; page_id plus only useful fields.',
            'handoff_fields': ['question', 'evidence', 'materials', 'preserve', 'uncertainties', 'visual_opportunity'],
            'visual_input': 'The CLI returns text/file checks only. Host tool pptx_page_design_context returns actual supported local images; after render N pass workspace as well as page_id to receive the current page preview first. Otherwise open the exact current preview/main material/applicable references through the existing image viewer. Stale/missing previews are not fresh visual input.',
            'use': 'Use supplied notes directly; retrieve this page when notes are large or material/expression is unclear. Record consequential changes only, not a per-page form or approval.',
            'authority': 'File checks and version-bound author observations, not source authenticity, aesthetic scores or independent review passes.'}
    groups = _module('tool_groups')
    manifest['discovery'] = groups.catalog(manifest, SCRIPTS/'tool_prepare.py')
    manifest['entry_commands'] = {name: commands[name] for name in
                                  ('refresh', 'unpack_selected_source', 'render_page', 'save_candidate') if name in commands}
    manifest_path = _write(root, 'tool-manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    guide_path = _write(root, 'tool-quickstart.md', groups.quickstart(manifest))
    return {'manifest': manifest_path, 'quickstart': guide_path, 'python': interpreter,
            'session_dir': session_dir, 'parts_dir': parts_dir}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task-root', default='.')
    parser.add_argument('--python', help='Exact host interpreter invocation; defaults to sys.executable')
    parser.add_argument('--workspace', help='Existing task-local session or parts directory; never automatically unpack')
    lookup = parser.add_mutually_exclusive_group()
    lookup.add_argument('--group', choices=list(_module('tool_groups').GROUPS), help='Read only the selected group; no preparation or native mutation')
    lookup.add_argument('--list-groups', action='store_true', help='Read the folder index without full tool signatures')
    args = parser.parse_args()
    if args.group or args.list_groups:
        if args.workspace or args.python:
            parser.error('Group lookup is read-only; refresh with --workspace/--python separately.')
        root = Path(args.task_root).resolve(strict=True)
        manifest = _read(root/'tool-manifest.json', root)
        if manifest.get('task_root') != str(root):
            raise ValueError('Tool manifest belongs to another task; prepare this task first')
        groups = _module('tool_groups')
        value = groups.select_group(manifest, args.group, SCRIPTS) if args.group else groups.catalog(manifest, SCRIPTS/'tool_prepare.py')
        print(json.dumps(value, ensure_ascii=False))
        return
    print(json.dumps(prepare_tool_manifest(args.task_root, python=args.python, workspace=args.workspace), ensure_ascii=False))


if __name__ == '__main__':
    main()
