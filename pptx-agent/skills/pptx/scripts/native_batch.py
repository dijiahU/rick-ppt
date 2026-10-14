"""Transactional, single-page JSON batches over the existing native_canvas helpers.

No content, coordinates, assets or style are selected here. Explicit text height
limits are never enlarged; max_height='auto' uses the selected font's measurement.
Rendering, publication, source checks and independent reviews remain required.
"""
import argparse
import copy
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

import native_canvas as canvas
from native_structure import shape
from pptx_core.package import select

OPERATIONS = {'text': canvas.add_text, 'shape': canvas.add_shape,
              'image': canvas.add_image, 'connector': canvas.add_connector,
              'group': canvas.semantic_group, 'reveal': canvas.reveal,
              'bars': canvas.add_bar_chart}
SYSTEM_FONTS = (Path('/System/Library/Fonts'), Path('/Library/Fonts'),
                Path('/usr/share/fonts'), Path('/usr/local/share/fonts'))


class BatchError(ValueError):
    def __init__(self, errors):
        self.errors = errors
        super().__init__('Native batch rejected: ' + '; '.join(e['message'] for e in errors))


def _error(index, operation, code, message, **details):
    return {'operation': index + 1, 'id': operation.get('id'), 'code': code,
            'message': str(message), **details}


def _scoped(root, value, *, directory=False):
    if not isinstance(value, (str, Path)) or not str(value):
        raise ValueError('Expected an explicit task-local path')
    path = Path(value)
    path = path if path.is_absolute() else root / path
    path = Path(os.path.abspath(path))
    if not path.is_relative_to(root):
        raise ValueError('Path must stay inside the task root')
    current = root
    for part in path.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise ValueError('Task paths must not traverse symlinks')
    if not (path.is_dir() if directory else path.is_file()):
        raise ValueError('Expected an existing ' + ('directory' if directory else 'file'))
    return path


def _font(root, value):
    if not isinstance(value, str) or not value:
        raise ValueError('Choose an actual font file')
    path = Path(value)
    path = Path(os.path.abspath(path if path.is_absolute() else root / path))
    allowed = [root / 'fonts', *SYSTEM_FONTS]
    if not any(path.is_relative_to(base) and path.resolve().is_relative_to(base.resolve())
               for base in allowed):
        raise ValueError('Fonts must be in task-root/fonts or an actual system font directory')
    if not path.is_file():
        raise ValueError('Selected font file does not exist')
    # Task font links cannot read other private files. System aliases are allowed
    # only when both the lexical and resolved file remain in a system font root.
    if path.is_relative_to(root / 'fonts'):
        return _scoped(root, path)
    return path.resolve()


def _hash_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _parts_hash(root):
    digest = hashlib.sha256()
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('Native parts must not contain symlinks')
        if path.is_file():
            digest.update(str(path.relative_to(root)).encode('utf-8'))
            digest.update(b'\0' + bytes.fromhex(_hash_file(path)))
        elif not path.is_dir():
            raise ValueError('Native parts contain a nonregular file')
    return digest.hexdigest()


def _targets(operation):
    if operation['op'] == 'connector':
        return [operation['start'], operation['end']]
    if operation['op'] == 'group':
        return operation['members']
    if operation['op'] == 'reveal':
        return [target for step in operation['steps'] for target in step]
    return []


def _prepare(root, parts, document):
    if not isinstance(document, dict) or set(document) != {'version', 'batch_id', 'operations'}:
        raise BatchError([{'message': 'Use exactly version, batch_id and operations', 'code': 'schema'}])
    if type(document['version']) is not int or document['version'] != 1:
        raise BatchError([{'message': 'Unsupported batch version', 'code': 'schema'}])
    batch_id = document['batch_id']
    if not isinstance(batch_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', batch_id):
        raise BatchError([{'message': 'batch_id needs 1–80 filename-safe characters', 'code': 'schema'}])
    operations = document['operations']
    if not isinstance(operations, list) or not operations or len(operations) > 500:
        raise BatchError([{'message': 'Use 1–500 operations for one page', 'code': 'schema'}])
    errors, prepared, names, dependencies, measurements = [], [], {}, {}, []
    pages = set()
    for index, raw in enumerate(operations):
        operation = copy.deepcopy(raw) if isinstance(raw, dict) else {}
        try:
            op = operation.get('op')
            if op not in OPERATIONS:
                raise ValueError('Unknown operation; use ' + ', '.join(OPERATIONS))
            slide = operation.get('slide')
            if type(slide) is not int or slide <= 0:
                raise ValueError('slide must be a positive page number')
            pages.add(slide)
            canvas.page(parts, slide)
            ident = operation.get('id')
            if op != 'reveal' and (not isinstance(ident, str) or not ident.strip() or ident in names):
                raise ValueError('Each object needs a distinct, nonempty id')
            if op == 'reveal' and ident is not None:
                raise ValueError('reveal has no object id; name its actual targets')
            params = {key: value for key, value in operation.items() if key not in ('op', 'id', 'slide')}
            # Bind against the exact current helper, not a second guessed API.
            inspect.signature(OPERATIONS[op]).bind(str(parts), slide, **params)
            if op == 'reveal' and 'replace' in params and type(params['replace']) is not bool:
                raise ValueError('reveal.replace must be an explicit JSON boolean; existing timing is preserved unless true is authorized')
            if op in ('shape', 'connector') and (type(params['line_width']) not in (int, float)
                                                  or not math.isfinite(params['line_width']) or params['line_width'] <= 0):
                raise ValueError('Positive line_width required even with stroke=null; explicitly choose a positive value such as 1')
            if op in ('connector', 'group', 'reveal'):
                targets = _targets(operation)
                if not isinstance(targets, list):
                    raise ValueError('Targets must be named handles or existing integer IDs')
                for target in targets:
                    if isinstance(target, str):
                        if target not in names or names[target] != slide:
                            raise ValueError('Named target must be an earlier object on this page: ' + target)
                    elif type(target) is int and target > 0:
                        shape(canvas.page(parts, slide)[2], target)
                    else:
                        raise ValueError('Use a named handle or existing positive integer ID')
            if op == 'image':
                source = _scoped(root, params['source'])
                params['source'] = str(source)
                # The caller cannot override scope through the helper argument.
                if params.get('task_root') not in (None, str(root)):
                    raise ValueError('image.task_root is supplied by the batch runner')
                params['task_root'] = str(root)
                if str(source) not in dependencies:
                    dependencies[str(source)] = _hash_file(source)
            if op == 'text':
                for key in ('font_file', 'latin_font'):
                    if params.get(key) is not None:
                        file = _font(root, params[key])
                        params[key] = str(file)
                        if str(file) not in dependencies:
                            dependencies[str(file)] = _hash_file(file)
                measured = canvas.text_measure(params['text'], params['font_file'], params['size'], params['width'],
                                               **{key: params[key] for key in ('index', 'padding', 'latin_font', 'latin_index') if key in params})
                limit = params['max_height']
                measurements.append({'id': ident, 'slide': slide, **measured, 'requested_height': limit})
                if limit == 'auto':
                    params['max_height'] = math.nextafter(measured['height'], math.inf)
                elif type(limit) not in (int, float) or not math.isfinite(limit) or limit <= 0:
                    raise ValueError('max_height must be a positive number or explicit "auto"')
                elif measured['height'] > limit:
                    errors.append(_error(index, operation, 'text_height', 'Text exceeds its explicit height',
                                         needs_height=measured['height'], available_height=limit,
                                         lines=len(measured['lines']), font_family=measured['font_family']))
            if op != 'reveal':
                names[ident] = slide
            prepared.append((op, slide, ident, params))
        except Exception as error:
            errors.append(_error(index, operation, 'invalid_operation', error))
    if len(pages) > 1:
        errors.append({'code': 'multiple_pages', 'message': 'Each batch must author exactly one page; submit pages sequentially'})
    if errors:
        raise BatchError(errors)
    return prepared, measurements, dependencies


def _execute(parts, prepared):
    handles, results = {}, []
    def resolve(value):
        return handles[value] if isinstance(value, str) else value
    for index, (op, slide, ident, source_params) in enumerate(prepared):
        params = copy.deepcopy(source_params)
        if op == 'connector':
            params['start'], params['end'] = resolve(params['start']), resolve(params['end'])
        elif op == 'group':
            params['members'] = [resolve(value) for value in params['members']]
        elif op == 'reveal':
            params['steps'] = [[resolve(value) for value in step] for step in params['steps']]
        try:
            result = OPERATIONS[op](str(parts), slide, **params)
        except Exception as error:
            raise BatchError([_error(index, {'id': ident}, 'operation_failed', error)]) from error
        if ident is not None:
            handles[ident] = result
        results.append({'op': op, 'id': ident, **result})
    return handles, results


def _json_write(path, value):
    pending = path.with_name(path.name + '.pending')
    if path.is_symlink() or pending.exists() or pending.is_symlink():
        raise ValueError('Unsafe or busy batch receipt path')
    try:
        with pending.open('x') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)


def run_batch(workspace, task_root, document, *, check_only=False):
    root = Path(task_root).resolve(strict=True)
    selected = _scoped(root, workspace, directory=True)
    ws = select(selected)
    _scoped(root, ws.root, directory=True)
    _scoped(root, ws.state_path)
    if (ws.home / '.lock').is_symlink():
        raise ValueError('Unsafe workspace lock')
    with ws.lock():
        before = _parts_hash(ws.root)
        prepared, measurements, dependencies = _prepare(root, ws.root, document)
        payload_sha = hashlib.sha256(json.dumps(document, sort_keys=True, ensure_ascii=False,
                                                allow_nan=False, separators=(',', ':')).encode()).hexdigest()
        receipts = ws.home / 'native-batches'
        if receipts.is_symlink():
            raise ValueError('Unsafe batch receipt directory')
        receipt_path = receipts / (document['batch_id'] + '.json')
        if receipt_path.is_symlink():
            raise ValueError('Unsafe batch receipt')
        if receipt_path.exists():
            receipt = json.loads(receipt_path.read_text())
            if receipt.get('input_sha256') != payload_sha or receipt.get('dependencies') != dependencies:
                raise ValueError('batch_id already committed with different input or assets; choose a new batch_id')
            if receipt.get('after_sha256') != before:
                raise ValueError('batch already committed, but native parts changed; do not append it again')
            return {**receipt, 'status': 'already_applied'}
        with tempfile.TemporaryDirectory(prefix='.native-batch-', dir=ws.home) as temporary:
            stage = Path(temporary) / 'parts'
            backup = Path(temporary) / 'before'
            shutil.copytree(ws.root, stage)
            handles, results = _execute(stage, prepared)
            # Temporary workspace identities must never escape into durable handles.
            for result in [*handles.values(), *results]:
                if 'workspace' in result:
                    result['workspace'] = str(ws.root)
            after = _parts_hash(stage)
            receipt = {'version': 1, 'batch_id': document['batch_id'],
                       'status': 'checked' if check_only else 'applied', 'slide': prepared[0][1],
                       'input_sha256': payload_sha, 'before_sha256': before, 'after_sha256': after,
                       'dependencies': dependencies, 'handles': handles, 'results': results,
                       'text_measurements': measurements, 'render_required': True, 'playback_verified': False}
            if check_only:
                return receipt
            if _parts_hash(ws.root) != before or any(_hash_file(Path(path)) != digest for path, digest in dependencies.items()):
                raise ValueError('Workspace or selected assets changed during batch execution')
            state_bytes = ws.state_path.read_bytes()
            swapped = False
            try:
                ws.root.rename(backup)
                try:
                    stage.rename(ws.root)
                    swapped = True
                except BaseException:
                    backup.rename(ws.root)
                    raise
                ws.refresh()
                receipts.mkdir(exist_ok=True)
                _json_write(receipt_path, receipt)
            except BaseException:
                if swapped:
                    ws.root.rename(stage)
                    backup.rename(ws.root)
                    pending_state = ws.state_path.with_name('state.native-batch-rollback')
                    pending_state.write_bytes(state_bytes)
                    os.replace(pending_state, ws.state_path)
                raise
            return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, help='Existing task-local session or native parts directory')
    parser.add_argument('--task-root', required=True)
    parser.add_argument('--input', required=True, help='Task-local JSON file with version,batch_id,operations')
    parser.add_argument('--check-only', action='store_true', help='Run the entire batch on a temporary copy without committing')
    args = parser.parse_args()
    try:
        root = Path(args.task_root).resolve(strict=True)
        source = _scoped(root, args.input)
        if source.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Batch JSON exceeds 2MB')
        document = json.loads(source.read_text(), parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON number')))
        print(json.dumps(run_batch(args.workspace, root, document, check_only=args.check_only), ensure_ascii=False, allow_nan=False))
    except Exception as error:
        print(json.dumps({'status': 'rejected', 'errors': getattr(error, 'errors', [{'code': 'batch_error', 'message': str(error)}]),
                          'render_required': True}, ensure_ascii=False))
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
