"""Reuse native fingerprints/rendering for an edit's original-page evidence.

No model, source selection, new review pass or visual verdict. Positional page
comparisons are explicitly tentative; blind audience reviewers never receive them.
"""
import hashlib
import io
import json
from pathlib import Path
import subprocess

from PIL import Image

from progress import read_scoped


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def globals_identity(data):
    # Page fingerprints omit dimensions and embedded fonts. Conservatively
    # compare all pages when these shared presentation parts change.
    from office_policy import archive
    with archive(data) as z:
        return {name: hashlib.sha256(z.read(name)).hexdigest() for name in z.namelist()
                if name == 'ppt/presentation.xml' or name.lower().endswith(('.fntdata', '.odttf', '.ttf', '.otf'))}


def prepare_refinement(run, artifact, packet):
    """Reuse a verified optional-response baseline in the existing visual pass.

    Only host-private current-task receipts supply authority. No author rationale,
    new rendering/model call, automatic quality verdict or extra repair is added.
    """
    from design_feedback import load_baseline
    from design_completion import response_findings
    from design_roles import enabled
    if not enabled(run.cfg) or getattr(run, 'records', None) is None:
        return
    baseline = load_baseline(run)
    if baseline is None or baseline['rolled_back']:
        return
    digest = hashlib.sha256(artifact).hexdigest()
    if digest == baseline['receipt']['artifact_sha256']:
        return
    from canvas_snapshot import native_pages
    from user_pages import fingerprint
    folder = Path(packet) / 'refinement-comparison'
    folder.mkdir(exist_ok=True)
    index = {'schema': 'native-edit-comparison/v1', 'status': 'prepared',
             'kind': 'reviewed_refinement_baseline', 'candidate_sha256': digest,
             'source_sha256': baseline['receipt']['artifact_sha256'], 'pages': [],
             'findings': response_findings(baseline['receipt']),
             'meaning': 'Prior reviewed bytes and actual previews, not an ideal or proof of design quality. Reassess the old observations against current visual evidence.'}
    original = baseline['artifact_bytes']
    count = len(native_pages(artifact))
    if count != len(native_pages(original)) or count != len(baseline['pages']):
        index['status'] = 'page_count_differs; correspondence_unverified'
    else:
        # Old receipts retain their comparison policy. New selection must also
        # inspect edits outside the original feedback; unchanged targets show
        # whether the old issue remains. No new rendering is needed.
        targets = {page for finding in index['findings'] for page in finding['pages']}
        from design_completion import CONTRACT
        globals_unchanged = globals_identity(original) == globals_identity(artifact)
        if baseline['receipt'].get('design_completion') == CONTRACT:
            targets.update(page for page in range(1, count + 1)
                           if not globals_unchanged or fingerprint(original, page) != fingerprint(artifact, page))
            index['presentation_and_font_parts_unchanged'] = globals_unchanged
        home = Path(baseline['home'])
        for page in sorted(targets):
            if type(page) is not int or not 1 <= page <= count:
                raise ValueError('Refinement feedback page outside its reviewed baseline')
            info = baseline['pages'][page - 1]
            body = read_scoped(home, info['file'], 30 * 1024 * 1024)
            if hashlib.sha256(body).hexdigest() != info['sha256']:
                raise ValueError('Refinement baseline preview changed')
            name = f'refinement-comparison/before-page-{page}.png'
            with Image.open(io.BytesIO(body)) as image:
                image.convert('RGB').resize((900, round(image.height * 900 / image.width)),
                    Image.Resampling.LANCZOS).save(Path(packet) / name)
            prepared = read_scoped(packet, name, 30 * 1024 * 1024)
            before, after = fingerprint(original, page), fingerprint(artifact, page)
            index['pages'].append({'page': page, 'source_fingerprint': before,
                'candidate_fingerprint': after, 'native_dependencies_unchanged': before == after and globals_unchanged,
                'before': {'path': name, 'sha256': hashlib.sha256(prepared).hexdigest(),
                    'bytes': len(prepared), 'representation': '900px reading preview of prior reviewed candidate; not playback'}})
    write_json(folder / 'index.json', index)


def prepare(run, artifact, packet, payload):
    if payload.get('mode') != 'edit':
        return
    folder = Path(packet) / 'edit-comparison'
    folder.mkdir(exist_ok=True)
    index = {'schema': 'native-edit-comparison/v1', 'status': 'source_unavailable',
             'candidate_sha256': hashlib.sha256(artifact).hexdigest(), 'pages': [],
             'meaning': 'Original source pages at the same positions; verify correspondence before judging changes. No playback or quality verdict.'}
    sources = [a for a in payload.get('attachments', []) if isinstance(a, dict)
               and str(a.get('path', '')).lower().endswith('.pptx')]
    if len(sources) != 1:
        index['status'] = 'no_unique_original_pptx'
        write_json(folder / 'index.json', index)
        return
    source = sources[0]
    if not source.get('sha256'):
        index['status'] = 'original_checksum_not_recorded'
        write_json(folder / 'index.json', index)
        return
    from recovery_workspace import resolve_delivery
    recoveries = list(run.journal.state.get('recoveries', {}).values()) if run.journal else []
    location = resolve_delivery({'path': source['path']}, run.job, recoveries)['path']
    original = read_scoped(run.job, location, 20 * 1024 * 1024)
    digest = hashlib.sha256(original).hexdigest()
    if digest != source['sha256'] or source.get('size', len(original)) != len(original):
        raise ValueError('Original review attachment checksum changed')
    index['source'] = {'path': source['path'], 'sha256': digest, 'bytes': len(original)}
    try:
        from canvas_snapshot import native_pages
        from user_pages import fingerprint
        globals_unchanged = globals_identity(original) == globals_identity(artifact)
        index['presentation_and_font_parts_unchanged'] = globals_unchanged
        count = len(native_pages(artifact))
        if len(native_pages(original)) != count:
            index['status'] = 'page_count_differs; original_attachment_remains_available'
        else:
            changed = []
            for page in range(1, count + 1):
                before, after = fingerprint(original, page), fingerprint(artifact, page)
                index['pages'].append({'page': page, 'source_fingerprint': before,
                    'candidate_fingerprint': after, 'dependencies_unchanged': before == after and globals_unchanged})
                if before != after or not globals_unchanged:
                    changed.append(page)
            if changed:
                cache = getattr(run, '_comparison_sources', {})
                if digest not in cache:
                    root = run.bridge.prepare(run.cfg)
                    (root / 'original.pptx').write_bytes(original)
                    from font_assets import copy_fonts
                    copy_fonts(run.job, root)
                    cli = str(Path(run.cfg['plugin']) / 'skills/pptx/scripts/pptx.py')
                    result = json.loads(run.run_check(root, run.bridge.sandbox(run.cfg, root,
                        [run.cfg['python'], cli, 'unpack', str(root / 'original.pptx')]), tick=run.lease.check))
                    cache[digest] = (root, result['workspace'], cli)
                    run._comparison_sources = cache
                root, workspace, cli = cache[digest]
                for page in changed:
                    rendered = json.loads(run.run_check(root, run.bridge.sandbox(run.cfg, root,
                        [run.cfg['python'], cli, '--workspace', workspace, 'render', str(page)]),
                        tick=run.lease.check, timeout=330))
                    image_path = rendered['pages'][0]
                    name = f'edit-comparison/original-{digest[:16]}-page-{page}.png'
                    with Image.open(io.BytesIO(read_scoped(root, image_path, 20 * 1024 * 1024))) as image:
                        image.convert('RGB').resize((900, round(image.height * 900 / image.width)),
                            Image.Resampling.LANCZOS).save(Path(packet) / name)
                    body = read_scoped(packet, name, 20 * 1024 * 1024)
                    index['pages'][page - 1]['before'] = {'path': name,
                        'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body),
                        'representation': '900px reading preview of original source; not original pixels or playback'}
            index['status'] = 'prepared'
    except (OSError, ValueError, subprocess.SubprocessError, TimeoutError) as error:
        index.update(status='preview_unavailable; original_attachment_remains_available',
                     error_type=type(error).__name__)
    write_json(folder / 'index.json', index)
