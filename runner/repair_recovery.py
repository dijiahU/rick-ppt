"""Read-only recovery decisions for unfinished audience-review corrections.

The host journal supplies stage identity; task-written findings alone are never
authority to resume a correction. Legacy review records additionally need a
matching restored findings file and a causal host-record timestamp.
"""
from dataclasses import dataclass
import json
from pathlib import Path
import re

from durable import JournalError
from progress import read_scoped


CORRECTION = re.compile(r'(content-revision|repair)-([12])\Z')
PRODUCER = re.compile(r'(?:author|repair-[12]|live-revision-[A-Za-z0-9-]+)\Z')
LIMIT = 500_000


@dataclass(frozen=True)
class RecoveryRoute:
    block_author: bool = False
    review_round: int = 1
    repair_round: int | None = None
    content_required: bool = True
    findings_path: str | None = None
    findings: dict | None = None
    author_thread: str | None = None
    repair_thread: str | None = None
    reason: str = 'ordinary'


def _matching_identity(receipt, state):
    return (receipt.get('input_revision') == state['input_revision'] and
            receipt.get('plugin_version') == state['plugin_version'])


def _load(root, name):
    return json.loads(read_scoped(root, name, LIMIT))


def _findings_valid(value, number, digest):
    if (not isinstance(value, dict) or type(value.get('round')) is not int or
            value['round'] != number or value.get('artifact_sha256') != digest):
        return False
    required = False
    for kind in ('content', 'visual'):
        report = value.get(kind)
        if not isinstance(report, dict) or not isinstance(report.get('findings'), list):
            return False
        for finding in report['findings']:
            if not isinstance(finding, dict) or finding.get('severity') not in ('required', 'suggestion'):
                return False
            required |= finding['severity'] == 'required'
    return required


def _trusted_findings(journal, job, records, task_id, phase, baseline, number, digest):
    if records is None or not re.fullmatch(r'[A-Za-z0-9_-]{1,150}', task_id or ''):
        return None
    records = Path(records)
    # Review records must remain host-private, never in the model's workspace.
    if records.is_symlink() or records.resolve().is_relative_to(Path(job).resolve()):
        return None
    task_files = sorted(Path(job).glob(f'review-findings-{number}-*.json'))
    host_files = sorted(records.glob(task_id + '-review-*.json'))
    if len(task_files) > 1000 or len(host_files) > 1000:
        return None
    restored = []
    for path in task_files:
        try:
            restored.append((path.name, _load(job, path.name)))
        except (OSError, ValueError):
            continue
    matches = []
    for path in host_files:
        try:
            value = _load(records, path.name)
            timestamp = path.stat(follow_symlinks=False).st_mtime_ns
        except (OSError, ValueError):
            continue
        if not _findings_valid(value, number, digest):
            continue
        # A receipt for this baseline must predate the interrupted correction.
        if not baseline['completed_at'] <= timestamp <= phase['started_at']:
            continue
        paths = [name for name, item in restored if item == value]
        explicit = 'input_revision' in value or 'plugin_version' in value
        if explicit:
            if not _matching_identity(value, journal.state):
                continue
        elif not paths:
            continue
        if not any(item[1] == value for item in matches):
            matches.append((paths[0] if paths else None, value))
    # Ambiguous records cannot choose the author's repair instructions for them.
    return matches[0] if len(matches) == 1 else None


def recovery_route(journal, job, *, records=None, task_id=None):
    """Return a plan without changing files, journal state, or input revision."""
    if journal is None:
        return RecoveryRoute()
    state = journal.state
    phase = state.get('phase') or {}
    name = phase.get('name', '')
    correction = CORRECTION.fullmatch(name)
    if correction is None:
        if (name == 'author' or name.startswith('live-revision-')) and phase.get('status') in ('running', 'interrupted'):
            return RecoveryRoute(block_author=True, reason='unfinished_author')
        return RecoveryRoute()
    blocked = RecoveryRoute(block_author=True, reason='unverified_correction')
    if phase.get('input_revision') != state['input_revision']:
        return blocked
    kind, number = correction[1], int(correction[2])
    if kind == 'repair' and phase.get('status') == 'completed':
        if not journal.can_reuse(name, job):
            return blocked
        receipt = state['completed_stages'][name]
        return RecoveryRoute(review_round=number + 1, author_thread=receipt.get('thread_id'),
                             reason='completed_repair')
    if phase.get('status') not in ('running', 'interrupted', 'completed'):
        return blocked
    if kind == 'content-revision' and phase.get('status') == 'completed' and state.get('next_phase') != f'repair-{number}':
        return blocked
    candidates = [receipt for stage, receipt in state['completed_stages'].items()
                  if PRODUCER.fullmatch(stage) and _matching_identity(receipt, state) and
                  receipt['completed_at'] < phase['started_at']]
    if not candidates:
        return blocked
    baseline = max(candidates, key=lambda receipt: receipt['completed_at'])
    pptx = [path for path in baseline['artifacts'] if Path(path).suffix.lower() == '.pptx']
    if len(pptx) != 1:
        return blocked
    try:
        actual = journal.artifacts(job, pptx)
    except (JournalError, ValueError, OSError):
        return blocked
    # delivery.json may already refer to a new partial export. The preserved
    # reviewed PPTX itself must still match; never overwrite it during recovery.
    if actual[pptx[0]] != baseline['artifacts'][pptx[0]]:
        return blocked
    found = _trusted_findings(journal, job, records, task_id, phase, baseline,
                             number, actual[pptx[0]]['sha256'])
    if found is None:
        return blocked
    content_required = kind == 'content-revision' and not (
        phase['status'] == 'completed' and journal.can_reuse(name, job))
    return RecoveryRoute(block_author=True, review_round=number + 1, repair_round=number,
                         content_required=content_required, findings_path=found[0], findings=found[1],
                         author_thread=baseline.get('thread_id'),
                         repair_thread=phase.get('thread_id') if kind == 'repair' else None,
                         reason='unfinished_correction')
