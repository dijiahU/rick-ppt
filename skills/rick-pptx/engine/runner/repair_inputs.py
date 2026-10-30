"""Reuse reviewed pictures and declared output in the existing bounded repair.

No aesthetic verdict, extra model, rendering, or change to delivery acceptance.
"""
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess

from PIL import Image

from design_feedback import load_baseline, optional_response
from progress import read_scoped


class StageDeadline(TimeoutError):
    """The host authoring timer expired; not a transport/tool timeout."""


def prepare(run, review):
    """Copy only checksum-bound reviewed target pictures into the author root."""
    if not optional_response(review) or getattr(run, 'records', None) is None:
        return '', []
    baseline = load_baseline(run)
    if baseline is None or baseline['rolled_back'] or baseline['receipt'] != review:
        return '', []
    from design_completion import response_findings
    findings = response_findings(review)
    if not findings:
        return '', []
    primary = findings[0]
    # Reviewer order is a proposed priority, not a new mandatory finding type.
    pages = sorted(set(primary['pages']))
    job = Path(run.job).resolve(strict=True)
    folder = job/'repair-inputs'/review['artifact_sha256']
    payload = {'artifact_sha256': review['artifact_sha256'],
               'input_revision': review['input_revision'], 'primary_finding': primary,
               'remaining_findings': findings[1:], 'pages': [],
               'meaning': 'Actual reviewed pixels and native object evidence; not an aesthetic verdict or completed repair.'}
    try:
        target = json.loads(read_scoped(job, 'repair-target.json', 100000))
        workspace = target['workspace']
        if not Path(workspace).resolve(strict=True).is_relative_to(job):
            raise ValueError('Repair workspace outside task')
    except (OSError, ValueError, KeyError):
        workspace = None
    images = []
    for page in pages:
        info = baseline['pages'][page - 1]
        row = {'page': page, 'image_status': 'unavailable'}
        payload['pages'].append(row)
        body = read_scoped(baseline['home'], info['file'], 30*1024*1024)
        if hashlib.sha256(body).hexdigest() != info['sha256']:
            raise ValueError('Reviewed repair image changed')
        try:
            with Image.open(io.BytesIO(body)) as opened:
                if opened.format != 'PNG':raise ValueError('Not a reviewed PNG')
                opened.verify()
        except (OSError, ValueError):
            row['image_status'] = 'unsupported; use existing scoped viewer'
            continue
        # Bound initial images; do not make an oversized first request. Full
        # sources remain in the host baseline and normal task viewing tools.
        with Image.open(io.BytesIO(body)) as opened:
            picture = opened.convert('RGB')
            if picture.width > 900:
                picture = picture.resize((900, round(picture.height*900/picture.width)), Image.Resampling.LANCZOS)
            encoded = io.BytesIO();picture.save(encoded, format='PNG')
        prepared = encoded.getvalue()
        if sum(x.stat().st_size for x in images) + len(prepared) > 3*1024*1024:
            row['image_status'] = 'initial image budget; view scoped page through normal tools'
            continue
        destination = folder/f'page-{page}.png'
        if destination.exists() and read_scoped(job, destination, 30*1024*1024) != prepared:
            raise ValueError('Repair input receipt collision')
        from font_assets import publish
        publish(job, str(destination.relative_to(job)), prepared)
        images.append(destination)
        row.update(image_status='initial_image', file=str(destination.relative_to(job)),
                   sha256=hashlib.sha256(prepared).hexdigest(),
                   reviewed_image_sha256=info['sha256'], representation='900px reading preview; not original pixels or playback')
        if workspace:
            try:
                outline = json.loads(read_scoped(job, 'outline.json', 2*1024*1024))
                page_id = outline['slides'][page-1]['id']
                from design_inputs import PageDesignInputs
                native = PageDesignInputs(run.cfg, job).context(page_id, workspace).get('native', {})
                objects = native.get('objects')
                row['native'] = {k: native[k] for k in ('part', 'page_sha256', 'workspace', 'object_count') if k in native}
                if objects is not None and len(json.dumps(objects, ensure_ascii=False).encode()) <= 24*1024:
                    row['native']['objects'] = objects
                else:
                    row['native']['objects_status'] = 'use existing page inspect command'
            except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError):
                row['native'] = {'objects_status': 'unavailable; use current repair-target workspace and existing inspect'}
    text = ('\nHOST REPAIR INPUT: the primary reviewed gap and target-page pictures are supplied directly. '
            'Read the attached pixels; path metadata alone is not image input. '
            'Check the proposed priority against actual task benefit. Preserve facts, scope, fonts and click groups. '
            'Complete the main useful action and export a full candidate to a fresh file with delivery.json before peripheral polish. '
            'A plan or adoption statement is not a candidate. Existing guides/material remain available for a concrete unresolved need.\n'
            + json.dumps(payload, ensure_ascii=False))
    return text, images


def deadline_handoff(server, thread, turn, root, baseline, *, check_current, timeout, recoveries=()):
    """Stop the writer, then accept only a changed explicit candidate for review.

    Caller suspends only its stage timer during bounded interruption; the task
    deadline, lease, stop and revision checks remain live. Errors propagate.
    """
    if (not isinstance(baseline, dict) or set(baseline) != {'sha256', 'input_revision'}
            or not isinstance(baseline.get('sha256'), str)
            or not re.fullmatch('[0-9a-f]{64}', baseline['sha256'])
            or type(baseline.get('input_revision')) is not int
            or baseline['input_revision'] < 0 or timeout <= 0 or not thread or not turn):
        return None
    check_current(baseline['input_revision'])
    active = server.active_turns.get(thread)
    if active:
        if active != turn:return None
        server.interrupt(thread, active)
        receipt = server.wait_turn(thread, active, timeout=timeout)
    else:
        receipt = server.completed_turns.get((thread, turn), {})
    if receipt.get('status') not in ('completed', 'interrupted') or thread in server.active_turns:
        return None
    check_current(baseline['input_revision'])
    from execution_continuity import declared_output
    candidate = declared_output(root, recoveries)
    if candidate is None or candidate['sha256'] == baseline['sha256']:
        return None
    check_current(baseline['input_revision'])
    if declared_output(root, recoveries) != candidate:
        raise ValueError('Declared candidate changed after writer interruption')
    return {**candidate, 'model_turn_status': receipt['status'],
            'acceptance': 'candidate only; normal authored checks, frozen render and independent reviews still required',
            'reason': 'stage_deadline_declared_candidate'}
