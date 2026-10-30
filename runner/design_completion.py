"""Consume scoped design judgments; never infer quality from files or scores.

Opt in through the pinned skill. Historical reports/recovery keep their policy.
One bounded response remains; a valid artifact can remain explicitly unfinished.
"""
import copy
import json
from pathlib import Path
import re

from progress import read_scoped

CONTRACT = {'version': 1}
PRESENTATION = {'version': 1}
PRESENTATION_MARKER = '<!-- content-presentation/v1 -->'
GUIDE = 'references/design-completion.md'
STATES = ('ready', 'needs_revision', 'uncertain')
RESOLUTIONS = ('resolved', 'partial', 'remains', 'regressed', 'not_supported')


def enabled(cfg):
    root = Path(cfg['plugin'])/'skills/pptx'
    catalog = root/'assets/workflow-choices.json'
    return (root/GUIDE).is_file() and catalog.is_file() and json.loads(catalog.read_text())['version'] >= 3


def readiness(report):
    return report.get('design_assessment', {}).get('readiness')


def presentation_enabled(cfg):
    return enabled(cfg) and PRESENTATION_MARKER in read_scoped(Path(cfg['plugin'])/'skills/pptx', GUIDE, 30000).decode()


def presentation_schema(base):
    """Only the final source-checked content pass can nominate presentation work."""
    value = copy.deepcopy(base)
    value['properties']['presentation_findings'] = {'type': 'array', 'items': {'type': 'string'}}
    value['required'].append('presentation_findings')
    return value


def validate_presentation(report):
    findings = {f['id']: f for f in report['findings']}
    ids = report.get('presentation_findings')
    if not _ids(ids, findings):
        raise ValueError('Presentation priorities must reference unique actual content findings')
    if any(findings[i].get('route') == 'content_revision' for i in ids):
        raise ValueError('Presentation priorities cannot bypass source/content correction')


def presentation_ids(receipt):
    if receipt.get('content_presentation') != PRESENTATION:return []
    report = receipt.get('content', {})
    validate_presentation(report)
    return report['presentation_findings']


def response_findings(receipt):
    """Reuse existing findings, qualify IDs only for the new cross-review contract.

    Keep both independent reports unchanged. Ordinary content suggestions are not
    nominated; visual suggestions remain available as context, as before.
    """
    primary = receipt.get('visual', {}).get('design_assessment', {}).get('primary_findings', [])
    visual = receipt.get('visual', {}).get('findings', [])
    by_id = {f['id']: f for f in visual}
    ordered = [by_id[i] for i in primary] + [f for f in visual if f['id'] not in primary]
    if receipt.get('content_presentation') != PRESENTATION:return ordered
    content = {f['id']: f for f in receipt['content']['findings']}
    rows = [('content', content[i]) for i in presentation_ids(receipt)] + [('visual', f) for f in ordered]
    return [{**f, 'id': role+':'+f['id'], 'source_review': role, 'source_id': f['id']} for role, f in rows]


def response_needed(receipt):
    return bool(presentation_ids(receipt)) or readiness(receipt.get('visual', {})) == 'needs_revision'


def schema(base, comparison=None):
    value = copy.deepcopy(base)
    assessment = value['properties']['design_assessment']
    assessment['properties'].update(
        readiness={'type': 'string', 'enum': list(STATES)},
        primary_findings={'type': 'array', 'items': {'type': 'string'}})
    assessment['required'] += ['readiness', 'primary_findings']
    if comparison is not None:
        value['properties']['design_comparison'] = {
            'type': 'object', 'additionalProperties': False,
            'properties': {
                'baseline_sha256': {'type': 'string', 'enum': [comparison['baseline_sha256']]},
                'candidate_sha256': {'type': 'string', 'enum': [comparison['candidate_sha256']]},
                'verdict': {'type': 'string', 'enum': ['better', 'equivalent', 'worse', 'uncertain']},
                'reason': {'type': 'string'},
                'regression_findings': {'type': 'array', 'items': {'type': 'string'}},
                'resolutions': {'type': 'array', 'items': {
                    'type': 'object', 'additionalProperties': False,
                    'properties': {'id': {'type': 'string'},
                                   'status': {'type': 'string', 'enum': list(RESOLUTIONS)},
                                   'evidence': {'type': 'string'}},
                    'required': ['id', 'status', 'evidence']}}},
            'required': ['baseline_sha256', 'candidate_sha256', 'verdict', 'reason',
                         'regression_findings', 'resolutions']}
        value['required'].append('design_comparison')
    return value


def _ids(value, permitted):
    return (isinstance(value, list) and all(isinstance(s, str) for s in value)
            and len(value) == len(set(value)) and set(value) <= set(permitted))


def validate(report, comparison=None):
    assessment = report.get('design_assessment', {})
    state = readiness(report)
    ids = [f['id'] for f in report['findings']]
    primary = assessment.get('primary_findings')
    if state not in STATES or not _ids(primary, ids):
        raise ValueError('Design readiness needs a valid state and actual finding IDs')
    if bool(primary) != (state == 'needs_revision'):
        raise ValueError('needs_revision must identify actionable primary findings; other states use an empty list')
    value = report.get('design_comparison')
    if comparison is None:
        if value is not None:raise ValueError('Design comparison has no host-bound baseline')
        return
    fields = {'baseline_sha256', 'candidate_sha256', 'verdict', 'reason', 'regression_findings', 'resolutions'}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError('Missing structured design comparison')
    for key in ('baseline_sha256', 'candidate_sha256'):
        if value[key] != comparison[key]:raise ValueError('Design comparison identity mismatch')
    if value['verdict'] not in ('better', 'equivalent', 'worse', 'uncertain'):
        raise ValueError('Invalid design comparison verdict')
    if not comparison['visual_input_complete'] and value['verdict'] != 'uncertain':
        raise ValueError('Unavailable before/after visual input requires an uncertain comparison')
    if not isinstance(value['reason'], str) or not 5 <= len(value['reason'].strip()) <= 2400:
        raise ValueError('Design comparison needs observable evidence')
    if not _ids(value['regression_findings'], ids):
        raise ValueError('Design regressions must reference current findings')
    rows = value['resolutions']
    if not isinstance(rows, list):raise ValueError('Invalid design finding resolutions')
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {'id', 'status', 'evidence'}
                or row['status'] not in RESOLUTIONS or not isinstance(row['evidence'], str)
                or not 5 <= len(row['evidence'].strip()) <= 2400):
            raise ValueError('Invalid design finding resolution evidence')
    if not _ids([r['id'] for r in rows], comparison['finding_ids']) or set(r['id'] for r in rows) != set(comparison['finding_ids']):
        raise ValueError('Design comparison must account for each original finding')


def comparison_input(root, images, digest):
    """Use the same checksum-verified PNGs passed into the actual review turn."""
    try: index = json.loads(read_scoped(root, 'refinement-comparison/index.json', 2*1024*1024))
    except FileNotFoundError:return None
    if (index.get('schema') != 'native-edit-comparison/v1'
            or index.get('kind') != 'reviewed_refinement_baseline'
            or index.get('candidate_sha256') != digest
            or not re.fullmatch('[a-f0-9]{64}', index.get('source_sha256', ''))):
        raise ValueError('Invalid host design comparison identity')
    rows = index.get('pages', [])
    complete = bool(rows) and index.get('status') == 'prepared'
    complete = complete and all(r.get('before', {}).get('path') in images
                                and f"reading-page-{r['page']}.png" in images for r in rows)
    return {'baseline_sha256': index['source_sha256'], 'candidate_sha256': digest,
            'visual_input_complete': complete, 'finding_ids': [f['id'] for f in index['findings']]}


def selection(baseline, receipt):
    """Keep an explicitly unfinished improvement, but reject visual regressions."""
    if baseline.get('design_completion') != CONTRACT:return None
    comparison = receipt.get('visual', {}).get('design_comparison')
    decision = {'baseline_sha256': baseline['artifact_sha256'],
                'candidate_sha256': receipt['artifact_sha256'], 'selected': 'baseline',
                'reason': 'comparison_unavailable'}
    if not isinstance(comparison, dict):return decision
    if (comparison.get('baseline_sha256') != decision['baseline_sha256']
            or comparison.get('candidate_sha256') != decision['candidate_sha256']):
        raise ValueError('Design selection identity mismatch')
    if any(f['severity'] == 'required' for k in ('content', 'visual') for f in receipt[k]['findings']):
        decision['reason'] = 'required_regression'
    elif comparison.get('regression_findings') or any(r['status'] == 'regressed' for r in comparison.get('resolutions', [])):
        decision['reason'] = 'design_regression'
    elif readiness(baseline['visual']) == 'ready' and readiness(receipt['visual']) != 'ready':
        decision['reason'] = 'readiness_regression'
    elif (baseline.get('content_presentation') == PRESENTATION
          and receipt.get('content_presentation') != PRESENTATION):
        decision['reason'] = 'presentation_assessment_unavailable'
    elif not presentation_ids(baseline) and presentation_ids(receipt):
        decision['reason'] = 'presentation_regression'
    elif comparison.get('verdict') == 'better':
        decision.update(selected='candidate', reason='reviewed_improvement')
    else:
        decision['reason'] = 'comparison_' + str(comparison.get('verdict', 'unavailable'))
    return decision


def notice(receipt):
    """Truthful public completion statement, separate from technical validity."""
    if receipt.get('design_completion') != CONTRACT:return ''
    pending = presentation_ids(receipt)
    state = readiness(receipt['visual'])
    zh = str(receipt.get('output_language', '')).startswith('zh')
    if pending:
        return ('呈现判断：内容审核仍指出影响理解的呈现问题，需要修改；视觉审核的独立判断另行保留。' if zh else
                'Presentation assessment: substantive revision is still needed according to the source-checked content review; the independent visual judgment is retained separately.')
    en = {'ready': 'Design assessment: ready for the stated use; this is a model judgment, not human certification.',
          'needs_revision': 'Design assessment: substantive design revision is still needed. File validity does not establish finished design.',
          'uncertain': 'Design assessment: readiness is uncertain; it has not been confirmed.'}
    cn = {'ready': '设计判断：适合既定用途；这是模型判断，尚非人工验收。',
          'needs_revision': '设计判断：仍需实质设计修改。文件有效不代表设计已经完成。',
          'uncertain': '设计判断：完成度尚无法确定，未确认达到设计标准。'}
    return (cn if zh else en).get(state, '')
