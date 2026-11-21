#!/usr/bin/env python3
"""Local task health report: phase times, tokens, context, tool use and deck pictures.

Reads only local state, records and Codex rollouts. Usage:
  python tools/task-report.py TASK_ID [--pptx FILE] [--json]
"""
import argparse
import collections
import glob
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT/'runner/state/local'
RECORDS = ROOT/'runner/records'
SESSIONS = Path.home()/'.codex/sessions'
# The final exception line after a real traceback, or a failing exit code; not exception
# names that merely appear in source code the model printed.
ERROR = re.compile(r'Traceback \(most recent call last\):.*?\n(\w+(?:Error|Exception)[^\n]{0,200})|(?:exit_code"?:\s*|exited with code )([1-9]\d*)', re.S)


def phases(task):
    rows, t0, open_at = [], None, {}
    for f in sorted((STATE/task/'events').glob('*.json')):
        e = json.loads(f.read_text())
        kind = e['kind']
        if kind not in ('phase.started', 'phase.completed', 'phase.interrupted'):
            continue
        t = e['at']/1e9; t0 = t0 or t
        name = (e.get('data') or {}).get('name') or (e.get('data') or {}).get('phase')
        if kind == 'phase.started':
            open_at[name] = t
        elif kind == 'phase.completed' and name in open_at:
            rows.append({'phase': name, 'start_min': round((open_at.pop(name)-t0)/60, 1), 'minutes': round((t-open_at.get(name, t))/60, 1) if False else None, 'end_min': round((t-t0)/60, 1)})
        elif kind == 'phase.interrupted':
            rows.append({'phase': 'interrupted', 'start_min': round((t-t0)/60, 1)})
    for r in rows:
        if 'end_min' in r:
            r['minutes'] = round(r['end_min']-r['start_min'], 1)
    return rows


def usage(task):
    stages = collections.defaultdict(lambda: collections.Counter())
    for f in (STATE/task/'usage').glob('*.json'):
        u = json.loads(f.read_text())
        s = stages[u['stage']]
        for k in ('inputTokens', 'cachedInputTokens', 'outputTokens', 'reasoningTokens'):
            s[k] += u.get(k) or 0
    return {k: dict(v) for k, v in sorted(stages.items())}


def threads(task):
    ids = set()
    for f in RECORDS.glob(task+'-*.jsonl'):
        for line in f.open():
            m = re.search(r'"thread_id": "([0-9a-f-]{36})"', line)
            if m:
                ids.add(m.group(1)); break
    return ids


def rollout(path):
    tools, errors, peak, images, image_bytes = collections.Counter(), [], 0, 0, 0
    first = last = None
    for line in open(path):
        e = json.loads(line); p = e.get('payload') or {}
        ts = e.get('timestamp'); first = first or ts; last = ts or last
        t = p.get('type')
        if t in ('function_call', 'custom_tool_call'):
            name = p.get('name') or ''
            text = p.get('arguments') or p.get('input') or ''
            tools[name] += 1
            for helper in ('pptx_icons', 'pptx_open_images', 'pptx_browser_sources', 'pptx_page_design_context',
                           'image_gen', 'pptx_design_critique', 'speaker_notes', 'pptx_browse', 'native_edit', 'edit_objects', 'image_query', 'web__run', 'native_page_batch', 'candidate_save', 'add_icon'):
                if helper in text and helper != name:
                    tools['  via code: '+helper] += text.count(helper)
        elif t in ('function_call_output', 'custom_tool_call_output'):
            out = p.get('output')
            if isinstance(out, list):
                for item in out:
                    if item.get('type') in ('input_image', 'inputImage'):
                        images += 1; image_bytes += len(item.get('image_url') or item.get('imageUrl') or '')
                text = ' '.join(str(item.get('text', '')) for item in out)
            else:
                text = str(out)
            for m in ERROR.finditer(text.replace('\\n', '\n')):
                errors.append((m.group(1) or 'exit code '+m.group(2))[:160])
        elif t == 'token_count' and p.get('info'):
            peak = max(peak, p['info']['last_token_usage']['input_tokens'])
        elif t == 'image_generation_call':
            tools['image_generation'] += 1
    minutes = None
    if first and last:
        f = lambda s: datetime.fromisoformat(s.replace('Z', '+00:00'))
        minutes = round((f(last)-f(first)).total_seconds()/60, 1)
    return {'file': Path(path).name, 'minutes': minutes, 'peak_context_tokens': peak, 'images_returned': images,
            'image_mb': round(image_bytes/1e6, 1), 'tools': dict(tools.most_common()),
            'errors': collections.Counter(errors).most_common(12)}


def deck(path):
    with zipfile.ZipFile(path) as z:
        slides = sorted([n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml', n)],
                        key=lambda n: int(re.findall(r'\d+', n)[0]))
        rows = []
        for n in slides:
            x = z.read(n).decode('utf8', 'replace')
            rows.append({'slide': n.split('/')[-1], 'pictures': x.count('<p:pic>'), 'shapes': x.count('<p:sp>'),
                         'custom_paths': x.count('<a:custGeom'), 'groups': x.count('<p:grpSp>'),
                         'connectors': x.count('<p:cxnSp>'), 'animated': x.count('<p:par>') > 0,
                         'background': (re.search(r'<p:bg>.*?srgbClr val="([0-9A-Fa-f]{6})"', x, re.S) or [None, None])[1]})
        media = [n for n in z.namelist() if n.startswith('ppt/media/')]
    return {'slides': rows, 'media_files': len(media)}


def main():
    a = argparse.ArgumentParser(); a.add_argument('task'); a.add_argument('--pptx'); a.add_argument('--json', action='store_true')
    args = a.parse_args()
    task = next((p.name for p in STATE.iterdir() if p.name.startswith(args.task)), args.task)
    report = {'task': task, 'phases': phases(task), 'usage_by_stage': usage(task), 'sessions': []}
    for tid in sorted(threads(task)):
        for f in glob.glob(str(SESSIONS/'**'/f'rollout-*{tid}.jsonl'), recursive=True):
            report['sessions'].append(rollout(f))
    if args.pptx:
        report['deck'] = deck(args.pptx)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1)); return
    print('TASK', task)
    for r in report['phases']:
        print(f"  {r['phase']:<16} start {r['start_min']:>6}m  {('took '+str(r['minutes'])+'m') if r.get('minutes') is not None else ''}")
    print('TOKENS (input / cached / output)')
    for k, v in report['usage_by_stage'].items():
        print(f"  {k:<28} {v.get('inputTokens',0):>11,} {v.get('cachedInputTokens',0):>11,} {v.get('outputTokens',0):>8,}")
    for s in report['sessions']:
        print('SESSION', s['file'][-45:], f"{s['minutes']}m peak_ctx={s['peak_context_tokens']:,} images={s['images_returned']} ({s['image_mb']}MB)")
        print('   tools:', ', '.join(f'{k}={v}' for k, v in s['tools'].items()))
        for msg, n in s['errors']:
            print(f'   error x{n}: {msg}')
    if 'deck' in report:
        d = report['deck']; print('DECK media files:', d['media_files'])
        for r in d['slides']:
            print('  ', r)


if __name__ == '__main__':
    main()
