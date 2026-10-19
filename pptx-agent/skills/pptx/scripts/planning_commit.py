"""Validate one complete planning bundle and transactionally split its three files.

The author chooses all content/design branches. This helper never selects, repairs,
normalizes or judges them, and does not replace authored checks or audience reviews.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile

from workflow_decisions import MAX_PLAN_BYTES, validate_plan

MAX_OUTLINE_BYTES = 2 * 1024 * 1024
MAX_NOTES_BYTES = 2 * 1024 * 1024
MAX_INPUT_BYTES = MAX_OUTLINE_BYTES + MAX_NOTES_BYTES + MAX_PLAN_BYTES + 65536
OUTPUTS = ('outline.json', 'decision-plan.json', 'source-notes.md')


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key: ' + key)
        result[key] = value
    return result


def _constant(value):
    raise ValueError('Non-finite JSON number: ' + value)


def _float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Non-finite JSON number: ' + value)
    return result


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def _path(root, value):
    path = Path(value)
    path = path if path.is_absolute() else root / path
    path = Path(os.path.abspath(path))
    if not path.is_relative_to(root):
        raise ValueError('Planning paths must stay inside --task-root')
    current = root
    for part in path.relative_to(root).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('Planning paths must not contain symlinks')
    return path


def _root(value):
    root = Path(os.path.abspath(value))
    current = Path(root.anchor)
    for part in root.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise ValueError('--task-root must not contain symlinks; use its real path')
    if not root.is_dir():
        raise ValueError('--task-root must be an existing directory')
    return root


def _read(path, limit):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= limit:
        raise ValueError(f'{path.name} must be a nonempty regular file within {limit} bytes')
    with path.open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError(path.name + ' exceeds its size limit')
    return data


def _text(value, limit, label, optional=False):
    if optional and value is None:
        return
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError('Invalid outline text: ' + label)
    # Same public-content boundary as the host outline contract. Check only;
    # submitted whitespace and original values are never rewritten.
    public = ' '.join(value.split())
    if re.search(r'(?:/Users/|/private/|/tmp/|[A-Z]:\\)|(?i:bearer\s+\S+|sk-[\w-]{10,}|(?:password|api[_-]?key|secret)\s*[:=]\s*\S+)', public):
        raise ValueError('Outline must contain only public presentation content')


def validate_outline(outline, expected_pages=None):
    """Check the current public outline fields without rewriting the source object."""
    if not isinstance(outline, dict):
        raise ValueError('Outline object required')
    if 'slides' not in outline:
        raise ValueError('outline.json missing "slides"; "pages" is not an alias')
    slides = outline['slides']
    if not isinstance(slides, list) or not 1 <= len(slides) <= 50:
        raise ValueError('outline.json "slides" must contain 1–50 page objects')
    if expected_pages is not None and (type(expected_pages) is not int or not 1 <= expected_pages <= 50):
        raise ValueError('--expected-pages must be an integer from 1 to 50')
    if expected_pages is not None and len(slides) != expected_pages:
        raise ValueError('Outline page count differs from the requested count')
    _text(outline.get('title'), 200, 'title')
    _text(outline.get('purpose'), 1600, 'purpose')
    if outline.get('style'):
        _text(outline['style'], 1200, 'style')
    ids = set()
    for page in slides:
        if not isinstance(page, dict):
            raise ValueError('Invalid outline page')
        ident = page.get('id')
        if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', ident) or ident in ids:
            raise ValueError('Outline page IDs must be unique and stable')
        ids.add(ident)
        _text(page.get('title'), 200, 'slide.title')
        _text(page.get('summary'), 2400, 'slide.summary')
        if page.get('section'):
            _text(page['section'], 200, 'slide.section')
        if 'presentationMode' in page and page['presentationMode'] not in ('native', 'interactive', 'hybrid'):
            raise ValueError('Invalid outline presentationMode')
        if 'interaction' in page:
            interaction = page['interaction']
            if not isinstance(interaction, dict) or not isinstance(interaction.get('scene'), str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,95}', interaction['scene']):
                raise ValueError('Outline interaction scene must be a scene ID')
            _text(interaction.get('purpose'), 1600, 'interaction.purpose')
            if 'bounds' in interaction:
                bounds = interaction['bounds']
                if not isinstance(bounds, dict):
                    raise ValueError('Outline interaction bounds must be an EMU rectangle')
                for key in ('x', 'y', 'width', 'height'):
                    number = bounds.get(key)
                    if type(number) not in (int, float) or not (0 if key in ('x', 'y') else 1) <= number <= 2147483647 or int(number) != number:
                        raise ValueError('Invalid outline interaction EMU bounds')
                if bounds['x'] + bounds['width'] > 2147483647 or bounds['y'] + bounds['height'] > 2147483647:
                    raise ValueError('Outline interaction bounds overflow')
    return outline


def _write(path, data, mode=0o600):
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(mode)


def commit_bundle(task_root, input_file, *, mode='create', expected_pages=None, allow_legacy=False):
    root = _root(task_root)
    source = _path(root, input_file)
    if source.name in OUTPUTS and source.parent == root:
        raise ValueError('--input must be a separate planning bundle, not an output file')
    raw = _read(source, MAX_INPUT_BYTES)
    bundle = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_float)
    if not isinstance(bundle, dict) or set(bundle) != {'version', 'outline', 'decisions', 'source_notes'} or type(bundle['version']) is not int or bundle['version'] != 1:
        raise ValueError('Planning bundle requires version=1, outline, decisions, source_notes; no other top-level fields')
    if mode not in ('create', 'edit'):
        raise ValueError('Planning mode must be create or edit')
    outline = validate_outline(bundle['outline'], expected_pages)
    notes = bundle['source_notes']
    if not isinstance(notes, str) or not notes.strip():
        raise ValueError('source_notes must contain the original nonempty Markdown text')
    output_bytes = {
        'outline.json': _json_bytes(outline),
        'decision-plan.json': _json_bytes(bundle['decisions']),
        'source-notes.md': notes.encode('utf-8'),
    }
    for name, limit in zip(OUTPUTS, (MAX_OUTLINE_BYTES, MAX_PLAN_BYTES, MAX_NOTES_BYTES)):
        if len(output_bytes[name]) > limit:
            raise ValueError(name + ' exceeds its size limit')
    result = validate_plan(bundle['decisions'], outline, stage='planning', root=root, mode=mode,
                           allow_legacy=allow_legacy,
                           require_click_reveal=False if allow_legacy else None)
    # Capture existing bytes before mutation. Replacements retain original permissions.
    before = {}
    for name in OUTPUTS:
        target = _path(root, name)
        if target.exists():
            info = target.lstat()
            if not stat.S_ISREG(info.st_mode):
                raise ValueError(name + ' must be a regular file')
            before[name] = (target.read_bytes(), stat.S_IMODE(info.st_mode))
        else:
            before[name] = None
    staging = Path(tempfile.mkdtemp(prefix='.planning-commit-', dir=root))
    committed = []
    try:
        for index, name in enumerate(OUTPUTS):
            original = before[name]
            _write(staging / ('new-' + str(index)), output_bytes[name], original[1] if original else 0o600)
            if original is not None:
                _write(staging / ('old-' + str(index)), *original)
        for index, name in enumerate(OUTPUTS):
            target = _path(root, name)
            # Refuse changes by another writer after the validation snapshot.
            if before[name] is None:
                if target.exists():
                    raise ValueError(name + ' changed during planning commit')
            elif not target.is_file() or target.read_bytes() != before[name][0]:
                raise ValueError(name + ' changed during planning commit')
            os.replace(staging / ('new-' + str(index)), target)
            committed.append((index, name))
    except BaseException:
        rollback_errors = []
        for index, name in reversed(committed):
            try:
                if before[name] is None:
                    (root / name).unlink()
                else:
                    # rename is an atomic same-filesystem replacement on supported
                    # POSIX hosts and remains usable if replace itself was rejected.
                    os.rename(staging / ('old-' + str(index)), root / name)
            except OSError as error:
                rollback_errors.append(f'{name}: {error}')
        if rollback_errors:
            raise RuntimeError('Planning rollback failed; preserved backups at ' + str(staging) + ': ' + '; '.join(rollback_errors))
        shutil.rmtree(staging)
        raise
    else:
        shutil.rmtree(staging)
    return {'ok': True, **result, 'files': [
        {'path': name, 'sha256': hashlib.sha256(output_bytes[name]).hexdigest(),
         'bytes': len(output_bytes[name]), 'replaced': before[name] is not None}
        for name in OUTPUTS], 'input_unchanged': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task-root', type=Path, required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--mode', choices=('create', 'edit'), default='create')
    parser.add_argument('--expected-pages', type=int)
    parser.add_argument('--allow-legacy', action='store_true', help='Preserve explicitly admitted historical plans; never use for new admissions')
    args = parser.parse_args()
    try:
        result = commit_bundle(args.task_root, args.input, mode=args.mode,
                               expected_pages=args.expected_pages, allow_legacy=args.allow_legacy)
    except (OSError, ValueError, KeyError, TypeError, RecursionError, RuntimeError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False))
        raise SystemExit(1)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
