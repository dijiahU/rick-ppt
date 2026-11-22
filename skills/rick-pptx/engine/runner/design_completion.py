"""Consume evidenced design judgments; scores are model opinions, not certification.

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
CRAFT = {'version': 2}
CRAFT_MARKER = '<!-- visual-craft/v2 -->'
CRAFT_DIMENSIONS = ('composition', 'visual_expression', 'typography', 'sequence')
VISUAL_COVERAGE = {'version': 1}
VISUAL_COVERAGE_MARKER = '<!-- visual-coverage/v1 -->'
VISUAL_KINDS = ('embedded_image', 'native_illustration', 'native_schematic', 'native_chart', 'document_example', 'text_only')
PICTORIAL_KINDS = {'embedded_image', 'native_illustration', 'native_schematic'}
VISUAL_STATES = ('sufficient', 'text_appropriate', 'missing', 'uncertain')
GENERATED_LOOK = {'version': 1}
GENERATED_LOOK_MARKER = '<!-- generated-look/v1 -->'
GENERATED_LOOK_LEVELS = ('clear', 'some_tells', 'pronounced')
TELL_FIELDS = ('pages', 'region', 'resembles', 'why_unjustified', 'direction', 'scope', 'finding_ids')
READING_ORDER = {'version': 1}
READING_ORDER_MARKER = '<!-- reading-order/v1 -->'
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


def craft_enabled(cfg):
    return enabled(cfg) and CRAFT_MARKER in read_scoped(Path(cfg['plugin'])/'skills/pptx', GUIDE, 30000).decode()


def coverage_enabled(cfg):
    return craft_enabled(cfg) and VISUAL_COVERAGE_MARKER in read_scoped(Path(cfg['plugin'])/'skills/pptx', GUIDE, 30000).decode()


def generated_look_enabled(cfg):
    """The pinned visual-review guide opts in; the uncalibrated level never gates readiness."""
    return enabled(cfg) and GENERATED_LOOK_MARKER in read_scoped(
        Path(cfg['plugin'])/'skills/pptx', 'references/visual-review.md', 100000).decode()


def reading_order_enabled(cfg):
    return enabled(cfg) and READING_ORDER_MARKER in read_scoped(
        Path(cfg['plugin'])/'skills/pptx', 'references/visual-review.md', 100000).decode()


def coverage_inventory(root, pages):
    """Frozen object counts disprove invented embedding, never judge visual meaning."""
    try:
        index = json.loads(read_scoped(Path(root), 'review-index.json', 8 * 1024 * 1024))
    except FileNotFoundError:
        return None
    slides = index.get('slides', [])
    if (index.get('schema') != 'native-review-index/v1'
            or [s.get('page') for s in slides] != list(range(1, pages + 1))):
        raise ValueError('Visual coverage needs the complete frozen page inventory')
    return {s['page']: s.get('object_counts', {}).get('pic', 0) for s in slides}


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


def schema(base, comparison=None, *, craft=False, coverage=False, generated_look=False, reading_order=False):
    value = copy.deepcopy(base)
    assessment = value['properties']['design_assessment']
    # Strict structured output needs every offered property in required (2026-11-21: an
    # optional reading_order made the visual reviewer's schema invalid and both test jobs failed).
    if not reading_order:assessment['properties'].pop('reading_order', None)
    elif 'reading_order' not in assessment['required']:assessment['required'] = assessment['required'] + ['reading_order']
    assessment['properties'].update(
        readiness={'type': 'string', 'enum': list(STATES)},
        primary_findings={'type': 'array', 'items': {'type': 'string'}})
    assessment['required'] += ['readiness', 'primary_findings']
    if craft:
        row = {'type': 'object', 'additionalProperties': False, 'properties': {
            'score': {'type': ['integer', 'null'], 'enum': list(range(1, 11)) + [None]},
            'pages': {'type': 'array', 'items': {'type': 'integer'}},
            'evidence': {'type': 'string'},
            'finding_ids': {'type': 'array', 'items': {'type': 'string'}}},
            'required': ['score', 'pages', 'evidence', 'finding_ids']}
        assessment['properties']['visual_craft'] = {
            'type': 'object', 'additionalProperties': False,
            'properties': {k: copy.deepcopy(row) for k in CRAFT_DIMENSIONS},
            'required': list(CRAFT_DIMENSIONS)}
        assessment['required'].append('visual_craft')
    if coverage:
        if not craft:
            raise ValueError('Visual coverage requires the existing craft assessment')
        assessment['properties']['visual_coverage'] = {
            'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
                'properties': {
                    'page': {'type': 'integer'},
                    'kind': {'type': 'string', 'enum': list(VISUAL_KINDS)},
                    'subject': {'type': 'string'},
                    'status': {'type': 'string', 'enum': list(VISUAL_STATES)},
                    'evidence': {'type': 'string'},
                    'finding_ids': {'type': 'array', 'items': {'type': 'string'}}},
                'required': ['page', 'kind', 'subject', 'status', 'evidence', 'finding_ids']}}
        assessment['required'].append('visual_coverage')
        assessment['properties']['image_requirement_exemption'] = {'type': ['string', 'null']}
        assessment['required'].append('image_requirement_exemption')
    if generated_look:
        assessment['properties']['generated_look'] = {'type': 'string', 'enum': list(GENERATED_LOOK_LEVELS)}
        assessment['properties']['generated_tells'] = {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False, 'properties': {
                'pages': {'type': 'array', 'items': {'type': 'integer'}},
                'region': {'type': 'string'}, 'resembles': {'type': 'string'},
                'why_unjustified': {'type': 'string'}, 'direction': {'type': 'string'},
                'scope': {'type': 'string', 'enum': ['page', 'deck']},
                'finding_ids': {'type': 'array', 'items': {'type': 'string'}}},
            'required': list(TELL_FIELDS)}}
        assessment['required'] += ['generated_look', 'generated_tells']
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


def validate_craft(report, pages):
    assessment = report['design_assessment']
    rows = assessment.get('visual_craft')
    if not isinstance(rows, dict) or set(rows) != set(CRAFT_DIMENSIONS):
        raise ValueError('Visual craft requires all four independently evidenced dimensions')
    findings = {f['id']: f for f in report['findings']}
    for name, row in rows.items():
        if not isinstance(row, dict) or set(row) != {'score', 'pages', 'evidence', 'finding_ids'}:
            raise ValueError('Invalid visual craft assessment: '+name)
        score = row['score']
        if score is not None and (type(score) is not int or not 1 <= score <= 10):
            raise ValueError('Visual craft score must be 1–10 or null for unavailable evidence')
        if (not isinstance(row['pages'], list) or not row['pages']
                or any(type(p) is not int or not 1 <= p <= pages for p in row['pages'])
                or len(set(row['pages'])) != len(row['pages'])
                or not isinstance(row['evidence'], str) or not 5 <= len(row['evidence'].strip()) <= 2400):
            raise ValueError('Visual craft needs actual page/region evidence')
        if not _ids(row['finding_ids'], findings):
            raise ValueError('Visual craft must reference actual findings')
        if any(not set(findings[i]['pages']) & set(row['pages']) for i in row['finding_ids']):
            raise ValueError('Visual craft evidence and findings must refer to matching pages')
        if score is None and assessment['readiness'] == 'ready':
            raise ValueError('Uncertain visual craft cannot establish ready')
        if score is not None and score < 7:
            if (assessment['readiness'] != 'needs_revision' or not row['finding_ids']
                    or not set(row['finding_ids']) <= set(assessment['primary_findings'])
                    or any(findings[i].get('route') == 'retain_suggestion' for i in row['finding_ids'])):
                raise ValueError('Unfinished visual craft needs actionable primary findings and needs_revision')


def validate_coverage(report, pages, picture_counts=None, request_text=None):
    assessment = report['design_assessment']
    rows = assessment.get('visual_coverage')
    if (not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows)
            or [r.get('page') for r in rows] != list(range(1, pages + 1))):
        raise ValueError('Visual coverage must account for every page exactly once in order')
    findings = {f['id']: f for f in report['findings']}
    for row in rows:
        if (set(row) != {'page', 'kind', 'subject', 'status', 'evidence', 'finding_ids'}
                or type(row['page']) is not int or row['kind'] not in VISUAL_KINDS
                or row['status'] not in VISUAL_STATES
                or any(not isinstance(row[k], str) or not 2 <= len(row[k].strip()) <= 2400
                       for k in ('subject', 'evidence'))):
            raise ValueError('Invalid visual coverage evidence')
        ids = row['finding_ids']
        if (not _ids(ids, findings)
                or any(row['page'] not in findings[i]['pages'] for i in ids)):
            raise ValueError('Visual coverage findings must locate this same page')
        if row['kind'] == 'embedded_image' and picture_counts is not None and picture_counts[row['page']] == 0:
            raise ValueError('No image object exists on the claimed page; reference images are not slide imagery')
        if row['status'] == 'text_appropriate' and row['kind'] != 'text_only':
            raise ValueError('Text-led exemption must be recorded as text_only')
        if row['status'] == 'sufficient' and row['kind'] == 'text_only':
            raise ValueError('Text alone is not evidence of a visible demonstration; justify text_appropriate or identify the gap')
        if row['status'] == 'missing':
            score = assessment['visual_craft']['visual_expression']['score']
            # 2026-11-22: a row may also cite a retained suggestion on the same page (task 4ac88476 failed
            # twice for page 5 citing F01 native_repair + F04 retain_suggestion). At least one linked
            # finding must be actionable, and every actionable one must drive the revision.
            actionable = [i for i in ids if findings[i].get('route') != 'retain_suggestion']
            if (assessment['readiness'] != 'needs_revision' or not actionable
                    or not set(actionable) <= set(assessment['primary_findings'])
                    or not set(actionable) <= set(assessment['visual_craft']['visual_expression']['finding_ids'])
                    or score is None or score >= 7):
                raise ValueError('Missing demonstration needs a same-page actionable finding, unfinished expression score and revision')
        if row['status'] == 'uncertain' and assessment['readiness'] == 'ready':
            raise ValueError('Uncertain visual coverage cannot establish ready')
    exemption = assessment.get('image_requirement_exemption')
    if exemption is not None:
        if (not isinstance(exemption, str) or not 4 <= len(exemption.strip()) <= 600
                or not request_text or exemption not in request_text):
            raise ValueError('An image exemption must quote the actual user request verbatim')
    pictorial = any(r['kind'] in PICTORIAL_KINDS and r['status'] == 'sufficient' for r in rows)
    required_gap = any(r['status'] == 'missing' and any(findings[i]['severity'] == 'required'
                       for i in r['finding_ids']) for r in rows)
    if not pictorial and exemption is None:
        if not required_gap and not (assessment['readiness'] == 'uncertain'
                                     and any(r['status'] == 'uncertain' for r in rows)):
            raise ValueError('Charts/document text do not meet the image requirement; identify a required pictorial correction')


def validate_generated_look(report, pages):
    """Structure only: every listed tell is located and carried by real findings.

    No count or palette rule is enforced. Deck-wide or pronounced tells must reach the
    bounded design response; page-local tells may remain suggestions.
    """
    assessment = report['design_assessment']
    level, tells = assessment.get('generated_look'), assessment.get('generated_tells')
    if level not in GENERATED_LOOK_LEVELS or not isinstance(tells, list):
        raise ValueError('Generated-look check needs a level and a tell list')
    if (level == 'clear') != (not tells):
        raise ValueError('Generated-look level must match the listed tells (clear means none listed)')
    findings = {f['id']: f for f in report['findings']}
    for tell in tells:
        if (not isinstance(tell, dict) or set(tell) != set(TELL_FIELDS)
                or tell['scope'] not in ('page', 'deck')
                or not isinstance(tell['pages'], list) or not tell['pages']
                or any(type(p) is not int or not 1 <= p <= pages for p in tell['pages'])
                or len(set(tell['pages'])) != len(tell['pages'])
                or any(not isinstance(tell[k], str) or not 2 <= len(tell[k].strip()) <= 1200
                       for k in ('region', 'resembles', 'why_unjustified', 'direction'))):
            raise ValueError('Each generated-look tell needs located pages/region, the matched default, the missing reason and a direction')
        if (not tell['finding_ids'] or not _ids(tell['finding_ids'], findings)
                or any(not set(findings[i]['pages']) & set(tell['pages']) for i in tell['finding_ids'])):
            raise ValueError('Each generated-look tell must be carried by actual findings on its pages')
    # A deck-wide or pronounced generated look undermines direct use: it enters the
    # existing bounded design response instead of staying an ignorable suggestion.
    serious = [t for t in tells if t['scope'] == 'deck' or level == 'pronounced']
    if serious:
        ids = {i for t in serious for i in t['finding_ids']}
        if (assessment.get('readiness') != 'needs_revision'
                or not ids & set(assessment.get('primary_findings') or [])
                or all(findings[i].get('route') == 'retain_suggestion' for i in ids)):
            raise ValueError('Deck-wide generated look needs an actionable primary finding and needs_revision')


def normalize_derived(report):
    """Fill fields that follow from the reviewer's own judgments (2026-11-21).

    A low craft score, a missing demonstration or a serious generated-look tell that the
    reviewer already linked to actionable findings implies those findings are primary and
    the deck needs revision. Reviewers (GPT and Claude alike) often forget to copy the links;
    the host derives them instead of failing the report. Judgments are never changed: a
    low score linked only to retained suggestions still goes back for a format correction.
    """
    if not isinstance(report, dict) or not isinstance(report.get('design_assessment'), dict):
        return report
    report = json.loads(json.dumps(report))
    a = report['design_assessment']
    findings = {f.get('id'): f for f in report.get('findings') or [] if isinstance(f, dict)}
    actionable = lambda ids: [i for i in ids or [] if i in findings and findings[i].get('route') != 'retain_suggestion']
    implied = []
    for row in (a.get('visual_craft') or {}).values():
        # A linked finding on other pages extends the entry's pages (2026-11-21: 3 of 12 Claude reviews
        # failed "must refer to matching pages" for exactly this and cost a format-correction call).
        if isinstance(row, dict) and isinstance(row.get('pages'), list):
            for i in row.get('finding_ids') or []:
                extra = [p for p in (findings.get(i) or {}).get('pages') or [] if type(p) is int and p not in row['pages']]
                if extra and not set(row['pages']) & set((findings.get(i) or {}).get('pages') or []):
                    row['pages'] = sorted(row['pages'] + extra)
    for row in (a.get('visual_craft') or {}).values():
        if isinstance(row, dict) and type(row.get('score')) is int and row['score'] < 7:
            implied += actionable(row.get('finding_ids'))
    expression = (a.get('visual_craft') or {}).get('visual_expression')
    for row in a.get('visual_coverage') or []:
        if isinstance(row, dict) and row.get('status') == 'missing':
            ids = actionable(row.get('finding_ids'))
            implied += ids
            # A missing demonstration is a visual-expression gap; link it when that score is already low.
            if isinstance(expression, dict) and type(expression.get('score')) is int and expression['score'] < 7:
                linked = list(expression.get('finding_ids') or [])
                expression['finding_ids'] = linked + [i for i in ids if i not in linked]
    for tell in a.get('generated_tells') or []:
        if isinstance(tell, dict) and (tell.get('scope') == 'deck' or a.get('generated_look') == 'pronounced'):
            implied += actionable(tell.get('finding_ids'))
    implied += [i for i, f in findings.items() if f.get('severity') == 'required' and f.get('route') != 'retain_suggestion']
    if implied:
        primary = list(a.get('primary_findings') or [])
        a['primary_findings'] = primary + [i for i in dict.fromkeys(implied) if i not in primary]
        a['readiness'] = 'needs_revision'
    return report


def validate(report, comparison=None, *, craft=False, pages=None, coverage=False, picture_counts=None, request_text=None, generated_look=False):
    assessment = report.get('design_assessment', {})
    state = readiness(report)
    ids = [f['id'] for f in report['findings']]
    primary = assessment.get('primary_findings')
    if state not in STATES or not _ids(primary, ids):
        raise ValueError('Design readiness needs a valid state and actual finding IDs')
    if bool(primary) != (state == 'needs_revision'):
        raise ValueError('needs_revision must identify actionable primary findings; other states use an empty list')
    if craft:validate_craft(report, pages)
    if coverage:
        if not craft:raise ValueError('Visual coverage requires craft')
        validate_coverage(report, pages, picture_counts, request_text)
    if generated_look:validate_generated_look(report, pages)
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


def selection(baseline, receipt, introduced=None, polish=False):
    """Keep an explicitly unfinished improvement, but reject visual regressions.

    introduced: required findings the response actually introduced (host rule in
    design_feedback.introduced_required). None keeps the historical any-required test.
    polish: a finishing-polish candidate fixes small suggestions, so an "equivalent" page
    with at least one suggestion verified as resolved (and no regression) is selected.
    """
    if baseline.get('design_completion') != CONTRACT:return None
    comparison = receipt.get('visual', {}).get('design_comparison')
    decision = {'baseline_sha256': baseline['artifact_sha256'],
                'candidate_sha256': receipt['artifact_sha256'], 'selected': 'baseline',
                'reason': 'comparison_unavailable'}
    if not isinstance(comparison, dict):return decision
    if (comparison.get('baseline_sha256') != decision['baseline_sha256']
            or comparison.get('candidate_sha256') != decision['candidate_sha256']):
        raise ValueError('Design selection identity mismatch')
    required = (bool(introduced) if introduced is not None else
                any(f['severity'] == 'required' for k in ('content', 'visual') for f in receipt[k]['findings']))
    if required:
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
    elif (polish and comparison.get('verdict') == 'equivalent'
          and any(r.get('status') == 'resolved' for r in comparison.get('resolutions', []))):
        decision.update(selected='candidate', reason='polish_resolved')
    else:
        decision['reason'] = 'comparison_' + str(comparison.get('verdict', 'unavailable'))
    return decision


def notice(receipt):
    """Truthful public completion statement, separate from technical validity."""
    if receipt.get('design_completion') != CONTRACT:return ''
    pending = presentation_ids(receipt)
    state = readiness(receipt['visual'])
    zh = str(receipt.get('output_language', '')).startswith('zh')
    scores = receipt['visual'].get('design_assessment', {}).get('visual_craft', {})
    rating = ''
    if receipt.get('visual_craft') == CRAFT and set(scores) == set(CRAFT_DIMENSIONS):
        labels = ('构图焦点', '视觉表达', '字体与细节', '整套节奏') if zh else CRAFT_DIMENSIONS
        rating = '\n' + ('画面设计（模型评分，满分 10）：' if zh else 'Visual craft (model rating, out of 10): ')
        rating += ' / '.join(label+' '+(str(scores[key]['score']) if scores[key]['score'] is not None else '?')
                             for label, key in zip(labels, CRAFT_DIMENSIONS))
    if pending:
        return ('呈现判断：内容审核仍指出影响理解的呈现问题，需要修改；视觉审核的独立判断另行保留。' if zh else
                'Presentation assessment: substantive revision is still needed according to the source-checked content review; the independent visual judgment is retained separately.') + rating
    en = {'ready': 'Design assessment: ready for the stated use; this is a model judgment, not human certification.',
          'needs_revision': 'Design assessment: substantive design revision is still needed. File validity does not establish finished design.',
          'uncertain': 'Design assessment: readiness is uncertain; it has not been confirmed.'}
    cn = {'ready': '设计判断：适合既定用途；这是模型判断，尚非人工验收。',
          'needs_revision': '设计判断：仍需实质设计修改。文件有效不代表设计已经完成。',
          'uncertain': '设计判断：完成度尚无法确定，未确认达到设计标准。'}
    return (cn if zh else en).get(state, '') + rating
