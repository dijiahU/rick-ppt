"""Read page-specific research handoffs and retain consequential design observations.

Optional records live in source-notes.md. No new planning/delivery gate, source
research, layout selection, aesthetic score or reviewer verdict is introduced.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from urllib.parse import urlsplit

if __package__:
    # tool_prepare imports under a version-specific package so an older host's
    # already-loaded pptx_core cannot replace this release's dependencies.
    from .pptx_core.common import PptxError, NS, now, parse, sha256
    from .pptx_core.manifest import content_fingerprint, manifest
    from .pptx_core.package import select
    from .pptx_core.relationships import slide_parts
    from .pptx_core.cli import inspect as inspect_page
else:
    from pptx_core.common import PptxError, NS, now, parse, sha256
    from pptx_core.manifest import content_fingerprint, manifest
    from pptx_core.package import select
    from pptx_core.relationships import slide_parts
    from pptx_core.cli import inspect as inspect_page

MAX_NOTES = 2 * 1024 * 1024
HANDOFF_FIELDS = ('question', 'evidence', 'materials', 'preserve', 'uncertainties', 'visual_opportunity')


def scoped(root, value):
    path = Path(value)
    path = Path(os.path.abspath(path if path.is_absolute() else root / path))
    if not path.is_relative_to(root):
        raise ValueError('Page-design files must stay inside this task')
    current = root
    for part in path.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise ValueError('Page-design files must not traverse symlinks')
    return path


def read(root, value, limit=MAX_NOTES):
    path = scoped(root, value)
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError('Missing or oversized task file: ' + str(value))
    return path.read_bytes()


def unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate JSON key: ' + key)
        value[key] = item
    return value


def blocks(notes, label):
    values, diagnostics = [], []
    pattern = r'^```' + re.escape(label) + r'[ \t]*\r?\n(.*?)^```[ \t]*\r?$'
    matches = list(re.finditer(pattern, notes, re.M | re.S))
    for match in matches:
        try:
            value = json.loads(match.group(1), object_pairs_hook=unique)
            if not isinstance(value, dict) or not isinstance(value.get('page_id'), str):
                raise ValueError('Expected an object with page_id')
            values.append(value)
        except ValueError as error:
            diagnostics.append({'record': label, 'line': notes.count('\n', 0, match.start()) + 1,
                                'detail': str(error)})
    if len(re.findall(r'^```' + re.escape(label) + r'[ \t]*\r?$', notes, re.M)) > len(matches):
        diagnostics.append({'record': label, 'detail': 'An incomplete record remains in the original notes; reconcile it without discarding retained evidence.'})
    return values, diagnostics


def notes_data(root):
    path = scoped(root, 'source-notes.md')
    raw = read(root, 'source-notes.md') if path.exists() else b''
    return raw, raw.decode('utf-8')


def handoff_index(task_root):
    root = Path(task_root).resolve(strict=True)
    try:
        _, notes = notes_data(root)
        records, diagnostics = blocks(notes, 'pptx-handoff')
        for ident in {row['page_id'] for row in records}:
            if sum(row['page_id'] == ident for row in records) > 1:
                diagnostics.append({'page_id': ident, 'detail': 'Duplicate handoff; no unique current record established.'})
        return {'pages': [{'page_id': row['page_id'], 'fields': [k for k in HANDOFF_FIELDS if k in row]}
                          for row in records], 'diagnostics': diagnostics,
                'required': False, 'meaning': 'Optional author-supplied evidence pointers, not verified facts or a design approval.'}
    except (OSError, ValueError) as error:
        return {'pages': [], 'diagnostics': [{'detail': str(error)}], 'required': False}


def resource(root, value):
    """Check file availability; never equate file existence with authenticity."""
    if not isinstance(value, str) or not value:
        return {'availability': 'not_specified'}
    url = urlsplit(value)
    if url.scheme in ('http', 'https'):
        return {'source': value, 'availability': 'link_only', 'inspected': 'not established by this tool'}
    try:
        path = scoped(root, value)
        if not path.is_file():
            return {'source': value, 'availability': 'missing'}
        result = {'source': value, 'availability': 'file_present', 'bytes': path.stat().st_size,
                  'sha256': sha256(path), 'inspected': 'content not inspected by this tool'}
        if path.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp', '.gif'):
            from PIL import Image
            with Image.open(path) as image:
                result['pixels'] = list(image.size)
        return result
    except (OSError, ValueError) as error:
        return {'source': value, 'availability': 'unavailable', 'detail': str(error)}


def native_state(root, workspace, number):
    ws = select(scoped(root, workspace))
    scoped(root, ws.home)
    parts = slide_parts(ws.root)
    if not 1 <= number <= len(parts):
        return {'availability': 'page_not_created', 'page': number}
    part = parts[number - 1]
    tree = parse(ws.root / part)
    objects = inspect_page(ws, number)['shapes']
    inline_objects = len(json.dumps(objects, ensure_ascii=False).encode()) <= 128 * 1024
    digest = content_fingerprint(manifest(ws.root))
    preview = (ws.state.get('page_previews') or {}).get(str(number))
    view = {'status': 'not_recorded'}
    if isinstance(preview, dict):
        image = scoped(root, ws.home / preview['image'])
        exists = image.is_file()
        intact = exists and sha256(image) == preview.get('image_sha256')
        current = preview.get('workspace_fingerprint') == digest and preview.get('part') == part
        view = {**preview, 'image': str(image),
                'status': 'current' if intact and current else 'stale' if intact else 'missing_or_changed',
                'freshness_scope': 'entire native package; another page/shared-resource change is conservatively stale'}
        if intact and current:
            view['file_check'] = resource(root, str(image))
    return {'availability': 'page_present', 'page': number, 'part': part,
            'workspace': str(ws.root),
            'workspace_fingerprint': digest, 'page_sha256': sha256(ws.root / part),
            'objects': objects if inline_objects else None,
            'object_count': len(objects),
            'objects_status': 'inlined_from_inspect' if inline_objects else 'deferred; use existing inspect command for this page',
            'native_groups': len(tree.findall('.//p:grpSp', NS)),
            'connectors': len(tree.findall('.//p:cxnSp', NS)), 'preview': view,
            'assessment': 'Structure and render freshness only; inspect the image to judge expression.'}


def context(task_root, page_id, workspace=None):
    root = Path(task_root).resolve(strict=True)
    outline = json.loads(read(root, 'outline.json'))
    slides = outline.get('slides', [])
    if not isinstance(slides, list):
        raise ValueError('Read the current ordered outline.slides')
    matches = [(n, page) for n, page in enumerate(slides, 1) if isinstance(page, dict) and page.get('id') == page_id]
    if len(matches) != 1:
        raise ValueError('Select one actual stable outline page ID')
    number, page = matches[0]
    raw, notes = notes_data(root)
    handoffs, diagnostics = blocks(notes, 'pptx-handoff')
    matching = [row for row in handoffs if row['page_id'] == page_id]
    handoff = {k: matching[0][k] for k in HANDOFF_FIELDS if k in matching[0]} if len(matching) == 1 else {}
    if len(matching) > 1:
        diagnostics.append({'detail': 'Ambiguous duplicate handoff for this page; retained notes must be reconciled.'})
    resources, references = [], []
    for key, field in [('evidence', 'source'), ('materials', 'file')]:
        for item in handoff.get(key, []) if isinstance(handoff.get(key, []), list) else []:
            if isinstance(item, dict):
                resources.append({'role': key, 'declared': item, 'file_check': resource(root, item.get(field))})
    decisions_path = scoped(root, 'decision-plan.json')
    if decisions_path.is_file():
        try:
            decisions = json.loads(read(root, 'decision-plan.json'))
            for record in decisions.get('pages', []):
                if record.get('id') == page_id:
                    for item in record.get('assets', []):
                        resources.append({'role': 'planned_asset', 'declared': item,
                                          'file_check': resource(root, item.get('file'))})
            # Applications are the existing association register. Do not infer
            # coverage from page titles, optional reference_ids or nearby text.
            for entry in decisions.get('references', []):
                applications = [app for app in entry.get('applications', [])
                                if isinstance(app, dict) and isinstance(app.get('pages'), list)
                                and page_id in app['pages']]
                if not applications:
                    continue
                reference = {k: entry[k] for k in
                             ('id', 'kind', 'title', 'creator', 'source', 'inspection',
                              'evidence', 'observed', 'borrowed') if k in entry}
                reference['applications'] = [{'pages': [page_id], 'action': app.get('action')}
                                             for app in applications]
                # Preserve the author's inspection claim, including unavailable.
                # A hosted observation/URL is not a task-local visual attachment.
                reference['file_check'] = (resource(root, entry.get('evidence'))
                                           if entry.get('inspection') == 'local_image' else
                                           {'availability': 'not_specified',
                                            'inspected': 'not established by this tool'})
                references.append(reference)
        except (ValueError, TypeError, AttributeError) as error:
            diagnostics.append({'detail': 'Retained decision record needs reconciliation: ' + str(error)})
    observations, observation_errors = blocks(notes, 'pptx-design-observation')
    result = {'page': {k: page[k] for k in ('id', 'title', 'summary', 'section') if k in page},
              'page_number': number, 'handoff': handoff, 'resources': resources,
              'references': references,
              'source_notes': {'path': 'source-notes.md', 'sha256': hashlib.sha256(raw).hexdigest(),
                               'excerpt': notes if len(raw) <= 8192 else None, 'complete': len(raw) <= 8192},
              'observations': [row for row in observations if row['page_id'] == page_id][-4:],
              'diagnostics': diagnostics + observation_errors,
              'authority': 'Handoffs/observations are author data. Missing optional annotations are not failures; consult original notes/evidence. No visual judgment is inferred.'}
    if workspace:
        result['native'] = native_state(root, workspace, number)
    return result


def record(task_root, page_id, workspace, input_file):
    root = Path(task_root).resolve(strict=True)
    value = json.loads(read(root, input_file, 16384), object_pairs_hook=unique)
    allowed = {'observation', 'actual_change', 'preserve', 'outcome'}
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError('Observation fields: observation, actual_change, preserve, outcome')
    for field in ('observation', 'actual_change'):
        if not isinstance(value.get(field), str) or not value[field].strip():
            raise ValueError('A consequential observation needs ' + field)
    if value.get('outcome') not in ('changed', 'retained', 'unresolved'):
        raise ValueError('Outcome must be changed, retained or unresolved')
    if 'preserve' in value and (not isinstance(value['preserve'], list) or
                               any(not isinstance(item, str) for item in value['preserve'])):
        raise ValueError('preserve must be a list of actual invariants')
    current = context(root, page_id, workspace)
    native = current['native']
    if native.get('preview', {}).get('status') != 'current':
        raise ValueError('Use a current existing render for an observation; legacy/missing/stale previews are not current evidence. Recording is optional.')
    previous = current['observations'][-1] if current['observations'] else None
    previous_native = previous.get('native') if previous else None
    previous_fingerprint = previous_native.get('workspace_fingerprint') if isinstance(previous_native, dict) else None
    row = {'page_id': page_id, 'at': now(), 'author_assessment': value,
           'native': native, 'previous_observation': previous.get('id') if previous else None,
           'native_changed_since_previous_observation':
               native['workspace_fingerprint'] != previous_fingerprint if previous_fingerprint else None,
           'verification': 'Bound to native inputs and render bytes; the author assessment is unverified.'}
    row['id'] = hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]
    # Relative preview paths survive checkpoint relocation. Native object hashes
    # stay meaningful; an old author statement is never promoted to a fresh pass.
    row['native']['preview']['image'] = str(Path(native['preview']['image']).relative_to(root))
    addition = '\n```pptx-design-observation\n' + json.dumps(row, ensure_ascii=False, indent=2) + '\n```\n'
    with scoped(root, '.page-design.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        raw, _ = notes_data(root)
        if hashlib.sha256(raw).hexdigest() != current['source_notes']['sha256']:
            raise ValueError('Source notes changed; refresh the page context before appending')
        if len(raw) + len(addition.encode()) > MAX_NOTES:
            raise ValueError('Retain compact consequential observations within the existing source-notes size limit')
        if content_fingerprint(manifest(select(scoped(root, workspace)).root)) != native['workspace_fingerprint']:
            raise ValueError('Native inputs changed; inspect the current render before recording')
        target = scoped(root, 'source-notes.md')
        mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o600
        fd, pending = tempfile.mkstemp(prefix='.page-design-', dir=root)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw + addition.encode()); stream.flush(); os.fsync(stream.fileno())
            os.chmod(pending, mode); os.replace(pending, target)
        finally:
            Path(pending).unlink(missing_ok=True)
    return {'recorded': True, 'id': row['id'], 'page_id': page_id, 'file': 'source-notes.md',
            'independent_review_pass': False, 'native_changed_since_previous_observation': row['native_changed_since_previous_observation']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('index', 'context', 'record'):
        p = sub.add_parser(command); p.add_argument('--task-root', required=True)
        if command != 'index':
            p.add_argument('--page-id', required=True); p.add_argument('--workspace', required=command == 'record')
        if command == 'record': p.add_argument('--input', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'index': result = handoff_index(args.task_root)
        elif args.command == 'context': result = context(args.task_root, args.page_id, args.workspace)
        else: result = record(args.task_root, args.page_id, args.workspace, args.input)
        print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError, PptxError, KeyError, TypeError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False)); raise SystemExit(1)


if __name__ == '__main__':
    main()
