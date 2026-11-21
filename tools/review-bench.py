#!/usr/bin/env python3
"""Re-run an independent visual review offline on a frozen, already reviewed candidate.

Lets review prompts and guidance be tuned against existing decks without re-authoring:

  extract THREAD_ID BENCH_DIR   copy the reviewer's frozen root, prompt, images and the
                                original report out of ~/.codex/sessions (must still exist)
  run BENCH_DIR VARIANT [--prompt FILE] [--edit OLD=>NEW ...]
                                run codex exec on a private copy of the root with the same
                                model/effort and the host JSON schema; saves report + timing
  check BENCH_DIR VARIANT       validate the report with the production design checks
  compare BENCH_DIR             one line per variant: seconds, tokens, validity, readiness,
                                scores, finding counts

Reviewer roots live under the OS temp folder and disappear with cleanup; extract soon after
a job. The bench never touches jobs, queues or delivered files.
"""
import argparse
import glob
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[1] / 'runner'
SESSIONS = Path.home() / '.codex' / 'sessions'


def rollout(thread):
    hits = [p for p in glob.glob(str(SESSIONS / '*/*/*/*.jsonl')) if thread in Path(p).name]
    if not hits:
        sys.exit(f'no rollout for {thread}')
    return Path(hits[0])


def extract(args):
    rows = [json.loads(line) for line in rollout(args.thread).read_text().splitlines() if line.strip()]
    ctx = next(r['payload'] for r in rows if r.get('type') == 'turn_context')
    message = next(r['payload'] for r in rows if r.get('payload', {}).get('type') == 'message'
                   and r['payload'].get('role') == 'user' and len(json.dumps(r['payload'])) > 20000)
    texts = [c['text'] for c in message['content'] if c['type'] == 'input_text']
    prompt = texts[0]
    images = [t.split('path="', 1)[1].split('"', 1)[0] for t in texts[1:] if t.startswith('<image ') and 'path="' in t]
    final = next((r['payload'] for r in reversed(rows) if r.get('payload', {}).get('type') == 'task_complete'), {})
    root = Path(ctx['cwd'])
    if not root.is_dir():
        sys.exit(f'reviewer root is gone: {root}')
    bench = Path(args.bench); bench.mkdir(parents=True, exist_ok=True)
    shutil.copytree(root, bench / 'root', symlinks=True, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('font-cache', '__pycache__'))
    (bench / 'prompt.txt').write_text(prompt)
    (bench / 'original-report.json').write_text(final.get('last_agent_message') or '')
    meta = {'thread': args.thread, 'root': str(root), 'model': ctx['model'], 'effort': ctx.get('effort'),
            'images': [str(Path(i).relative_to(root)) for i in images]}
    (bench / 'meta.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print(f'extracted {len(prompt)} prompt chars, {len(images)} images -> {bench}')


CLAUDE_PREAMBLE = '''You are an independent visual reviewer of a finished PowerPoint deck. You did not make it
and never saw the author's reasoning; judge only the attached page images (900 px reading
renders, in page order, followed by contact sheets of native click-reveal states). You cannot
open files: everything you may use is in this message. Return only the JSON report.

Be a demanding art director: judge each page's first impression at stamp size first (is
there one focal point? is it mostly empty, flat, or generic?), then the details. required is
only for demonstrated errors, missing requested content, unreadability or broken requested
behaviour. For each finding give page/region, what the viewer sees, the consequence and a
concrete change. Use the route field: content_revision, native_repair or retain_suggestion.
Approved fonts are not a violation: Times New Roman/SimSun for reading text; DengXian/Arial for
display; Microsoft YaHei, SimHei, KaiTi, FangSong, Calibri, Cambria, Georgia, Century Gothic,
Verdana, Tahoma. The output language is Simplified Chinese for observations.
'''


def claude_prompt(bench, guides=None):
    root = bench / 'root'
    guides = Path(guides) if guides else RUNNER.parent / 'pptx-agent/skills/pptx/references'
    request = json.loads((root / 'request.json').read_text())
    index = json.loads((root / 'review-index.json').read_text())
    pages = []
    for slide in index['slides']:
        reveal = slide.get('native_reveal') or {}
        pages.append({'page': slide['page'], 'text': (slide.get('text') or '')[:600],
                      'fonts': (slide.get('formula_inventory') or {}).get('declaredFonts'),
                      'font_points': slide.get('explicit_font_points'),
                      'click_groups': len(reveal.get('click_groups') or [])})
    return (CLAUDE_PREAMBLE + '\n# Request\n' + json.dumps({k: request.get(k) for k in ('title', 'brief', 'style', 'pages')}, ensure_ascii=False)
            + '\n# Page facts (actual text, fonts, click groups)\n' + json.dumps(pages, ensure_ascii=False)
            + '\n\n' + (guides / 'visual-review.md').read_text() + '\n\n' + (guides / 'design-completion.md').read_text())


def run_claude(args):
    import base64
    bench = Path(args.bench); meta = json.loads((bench / 'meta.json').read_text())
    out = bench / 'runs' / args.variant; shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
    prompt = claude_prompt(bench, args.guides); (out / 'prompt.txt').write_text(prompt)
    schema = schema_for(bench / 'root'); (out / 'schema.json').write_text(json.dumps(schema))
    content = []
    images = [i.replace('reading-page-', 'page-') for i in meta['images']] if args.full else meta['images']
    for image in images:
        data = (bench / 'root' / image).read_bytes()
        media = 'image/png' if image.endswith('.png') else 'image/jpeg'
        content += [{'type': 'text', 'text': image}, {'type': 'image', 'source': {'type': 'base64', 'media_type': media,
                     'data': base64.b64encode(data).decode()}}]
    content.append({'type': 'text', 'text': prompt})
    line = json.dumps({'type': 'user', 'message': {'role': 'user', 'content': content}})
    command = ['claude', '-p', '--input-format', 'stream-json', '--output-format', 'stream-json', '--verbose',
               '--model', args.model, '--json-schema', json.dumps(schema), '--tools', '', '--max-turns', '3']
    started = time.time()
    result = subprocess.run(command, input=line.encode(), capture_output=True, cwd=str(out))
    seconds = round(time.time() - started)
    (out / 'events.jsonl').write_bytes(result.stdout + b'\n--stderr--\n' + result.stderr)
    final = None
    for row in result.stdout.decode(errors='replace').splitlines():
        try:
            event = json.loads(row)
        except ValueError:
            continue
        if event.get('type') == 'result':
            final = event
    report = (final or {}).get('structured_output')
    if report is None and final and final.get('result'):
        try:
            report = json.loads(final['result'])
        except ValueError:
            report = None
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False) if report else '')
    usage = (final or {}).get('usage')
    (out / 'timing.json').write_text(json.dumps({'seconds': seconds, 'exit': result.returncode, 'usage': usage,
                                                 'cost_usd': (final or {}).get('total_cost_usd')}))
    print(args.variant, 'seconds', seconds, 'exit', result.returncode, 'usage', usage, 'cost', (final or {}).get('total_cost_usd'))


def content_schema():
    sys.path.insert(0, str(RUNNER))
    import workflow
    return workflow.REPORT_SCHEMA


def schema_for(root):
    sys.path.insert(0, str(RUNNER))
    import workflow
    from design_completion import schema
    return schema(workflow.VISUAL_REPORT_SCHEMA, None, craft=True, coverage=True, generated_look=True)


def run(args):
    bench = Path(args.bench); meta = json.loads((bench / 'meta.json').read_text())
    prompt = Path(args.prompt).read_text() if args.prompt else (bench / 'prompt.txt').read_text()
    for edit in args.edit or []:
        old, new = edit.split('=>', 1)
        if old not in prompt:
            sys.exit(f'edit target not found: {old[:60]}')
        prompt = prompt.replace(old, new)
    out = bench / 'runs' / args.variant; shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
    work = out / 'root'
    shutil.copytree(bench / 'root', work, symlinks=True)
    # The original absolute root path appears in the prompt; point it at the private copy.
    prompt = prompt.replace(meta['root'], str(work))
    (out / 'prompt.txt').write_text(prompt)
    (out / 'schema.json').write_text(json.dumps(schema_for(work) if not args.content else content_schema()))
    command = ['codex', 'exec', '--skip-git-repo-check', '--json', '-C', str(work), '-s', 'workspace-write',
               '-c', f'model="{meta["model"]}"', '-c', f'model_reasoning_effort="{meta["effort"] or "medium"}"',
               '-c', 'approval_policy="never"', '--output-schema', str(out / 'schema.json'),
               '-o', str(out / 'report.json')]
    for image in meta['images']:
        command += ['-i', str(work / image)]
    command.append('-')  # -i is variadic, so the prompt goes through stdin
    started = time.time()
    with open(out / 'events.jsonl', 'w') as log:
        code = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, input=prompt.encode()).returncode
    seconds = round(time.time() - started)
    tokens = None
    for line in (out / 'events.jsonl').read_text().splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get('type') == 'turn.completed':
            tokens = event.get('usage')
    (out / 'timing.json').write_text(json.dumps({'seconds': seconds, 'exit': code, 'usage': tokens}))
    print(args.variant, 'seconds', seconds, 'exit', code, 'usage', tokens)


def check(bench, variant):
    if (bench / 'meta.json').is_file() and json.loads((bench / 'meta.json').read_text()).get('content'):
        path = bench / ('original-report.json' if variant == 'original' else f'runs/{variant}/report.json')
        try:
            report = json.loads(path.read_text())
        except (OSError, ValueError) as error:
            return {'valid': False, 'error': f'unreadable: {error}'}
        findings = report.get('findings') or []
        return {'valid': True, 'findings': len(findings), 'required': sum(f.get('severity') == 'required' for f in findings),
                'pages': report.get('pages_reviewed')}
    sys.path.insert(0, str(RUNNER))
    from design_completion import validate, normalize_derived
    path = bench / ('original-report.json' if variant == 'original' else f'runs/{variant}/report.json')
    try:
        report = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        return report_line(None, f'unreadable: {error}')
    pages = len(report.get('pages_reviewed') or [])
    root = bench / 'root'
    request = json.loads((root / 'request.json').read_text())
    request_text = '\n'.join(str(request.get(k) or '') for k in ('brief', 'style'))
    picture_counts = None
    report = normalize_derived(report)  # as production does before validating (derivable consistency fields)
    try:
        validate(report, None, craft=True, pages=pages, coverage=True, picture_counts=picture_counts,
                 request_text=request_text, generated_look=True)
        error = None
    except (ValueError, KeyError, TypeError) as exc:
        error = str(exc)[:160]
    return report_line(report, error)


def report_line(report, error):
    if report is None:
        return {'valid': False, 'error': error}
    a = report.get('design_assessment') or {}
    craft = a.get('visual_craft') or {}
    findings = report.get('findings') or []
    return {'valid': error is None, 'error': error, 'readiness': a.get('readiness'),
            'scores': {k: v.get('score') for k, v in craft.items() if isinstance(v, dict)},
            'generated_look': a.get('generated_look'),
            'findings': len(findings), 'required': sum(f.get('severity') == 'required' for f in findings),
            'repair_routes': sum(f.get('route') != 'retain_suggestion' for f in findings)}


def compare(args):
    bench = Path(args.bench)
    variants = ['original'] + sorted(p.name for p in (bench / 'runs').glob('*') if p.is_dir()) if (bench / 'runs').is_dir() else ['original']
    for variant in variants:
        timing = {}
        if variant != 'original' and (bench / 'runs' / variant / 'timing.json').is_file():
            timing = json.loads((bench / 'runs' / variant / 'timing.json').read_text())
        usage = timing.get('usage') or {}
        tokens = (usage.get('input_tokens') or 0) + (usage.get('cache_read_input_tokens') or 0) + (usage.get('cache_creation_input_tokens') or 0)
        print(variant, json.dumps({**check(bench, variant), 'seconds': timing.get('seconds'),
                                   'tokens': tokens or None, 'cost_usd': timing.get('cost_usd')}, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    e = sub.add_parser('extract'); e.add_argument('thread'); e.add_argument('bench')
    r = sub.add_parser('run'); r.add_argument('bench'); r.add_argument('variant')
    r.add_argument('--prompt'); r.add_argument('--edit', action='append')
    r.add_argument('--content', action='store_true', help='content reviewer schema instead of the visual one')
    cl = sub.add_parser('claude'); cl.add_argument('bench'); cl.add_argument('variant'); cl.add_argument('--model', default='opus')
    cl.add_argument('--guides', help='folder with alternative visual-review.md / design-completion.md')
    cl.add_argument('--full', action='store_true', help='send full-size page renders instead of 900 px reading pages')
    c = sub.add_parser('compare'); c.add_argument('bench')
    args = ap.parse_args()
    {'extract': extract, 'run': run, 'claude': run_claude, 'compare': compare}[args.cmd](args)


if __name__ == '__main__':
    main()
