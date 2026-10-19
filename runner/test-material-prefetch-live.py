"""Opt-in: a real single author edits native XML while two hosted searches run.

No runner settings, website requests, leases or production tasks are used.
This is a small engineering fixture, not a full presentation or design benchmark.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import time

from durable import AppServer, task_configuration
from material_prefetch import MaterialPrefetchBroker
from model_backend import DEFAULT_TASK_MODEL, DEFAULT_TASK_REASONING_EFFORT


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--outdir', required=True, type=Path)
    p.add_argument('--model', default=DEFAULT_TASK_MODEL)
    p.add_argument('--effort', default=DEFAULT_TASK_REASONING_EFFORT)
    args = p.parse_args()
    proof_root = args.outdir.absolute()
    proof_root.mkdir(parents=True, exist_ok=False)
    job = proof_root / 'author'
    job.mkdir()
    (job / 'tmp').mkdir()
    (job / 'assets').mkdir()
    write(job / 'assets/index.json', {'images': []})
    write(job / 'request.json', {'title': 'Single-author preparation engineering fixture', 'pages': 3})
    write(job / 'outline.json', {'title': 'Preparation overlap', 'purpose': 'Engineering validation',
        'slides': [{'id': 'p1', 'title': 'Current native page', 'summary': 'One author remains active'},
                   {'id': 'p2', 'title': 'Attention source', 'summary': 'Original paper evidence'},
                   {'id': 'p3', 'title': 'PPTX source', 'summary': 'Original OOXML documentation'}]})
    write(job / 'decision-plan.json', {'task': {'research': 'targeted_verification'},
        'pages': [{'id': 'p1', 'assets': [{'route': 'none'}]},
                  {'id': 'p2', 'assets': [{'route': 'none'}]},
                  {'id': 'p3', 'assets': [{'route': 'none'}]}]})
    write(job / 'capabilities.json', {'web_search': {'mode': 'live'}, 'image_generation': {'mode': 'disabled'}})
    here = Path(__file__).resolve().parent
    shutil.copyfile(here / 'prefetch-proxy.py', job / 'prefetch-proxy.py')
    shutil.copyfile(here.parent / 'pptx-agent/skills/pptx/assets/blank.pptx', job / 'blank.pptx')
    write(job / 'material-jobs.json', [
        {'kind': 'search', 'page_ids': ['p2'], 'purpose': 'Original attention evidence for the later page',
         'request': 'Open https://arxiv.org/abs/1706.03762 using hosted search/open. Report the paper title and one explicitly supported attention architecture fact with that exact source URL. One source is enough; be concise and state actual inspection limits.'},
        {'kind': 'search', 'page_ids': ['p3'], 'purpose': 'Original OOXML evidence for the later page',
         'request': 'Open https://learn.microsoft.com/en-us/office/open-xml/presentation/structure-of-a-presentationml-document using hosted search/open. Report one supported fact about the presentation/slide relationship with that exact source URL. One source is enough; be concise and state actual inspection limits.'}])
    # Self-contained deterministic native edit; no template/layout generator.
    (job / 'write_current_page.py').write_text('''from pathlib import Path
import json,time,zipfile,xml.etree.ElementTree as E
root=Path(__file__).resolve().parent
started=time.time()
with zipfile.ZipFile(root/'blank.pptx') as z:parts={n:z.read(n) for n in z.namelist()}
P='http://schemas.openxmlformats.org/presentationml/2006/main'
A='http://schemas.openxmlformats.org/drawingml/2006/main'
s=E.fromstring(parts['ppt/slides/slide1.xml']);tree=s.find('{'+P+'}cSld/{'+P+'}spTree')
shape=E.SubElement(tree,'{'+P+'}sp')
nv=E.SubElement(shape,'{'+P+'}nvSpPr');E.SubElement(nv,'{'+P+'}cNvPr',id='99',name='Current page authored during material preparation');E.SubElement(nv,'{'+P+'}cNvSpPr');E.SubElement(nv,'{'+P+'}nvPr')
props=E.SubElement(shape,'{'+P+'}spPr');x=E.SubElement(props,'{'+A+'}xfrm');E.SubElement(x,'{'+A+'}off',x='457200',y='457200');E.SubElement(x,'{'+A+'}ext',cx='8229600',cy='914400');E.SubElement(E.SubElement(props,'{'+A+'}prstGeom',prst='rect'),'{'+A+'}avLst')
body=E.SubElement(shape,'{'+P+'}txBody');E.SubElement(body,'{'+A+'}bodyPr');E.SubElement(body,'{'+A+'}lstStyle');para=E.SubElement(body,'{'+A+'}p');run=E.SubElement(para,'{'+A+'}r');pr=E.SubElement(run,'{'+A+'}rPr',sz='2800');E.SubElement(pr,'{'+A+'}latin',typeface='Times New Roman');E.SubElement(pr,'{'+A+'}ea',typeface='SimSun');E.SubElement(run,'{'+A+'}t').text='One author edits this native page while later sources are prepared.'
parts['ppt/slides/slide1.xml']=E.tostring(s,encoding='utf-8',xml_declaration=True)
with zipfile.ZipFile(root/'current-page.pptx','w',zipfile.ZIP_DEFLATED) as z:
 for n,data in parts.items():z.writestr(n,data)
(root/'current-page-receipt.json').write_text(json.dumps({'started_at':started,'completed_at':time.time(),'native_text':True}))
print('Native current-page edit completed')
''')
    deadline = time.monotonic() + 360
    broker = MaterialPrefetchBroker({'default_model': args.model, 'default_reasoning_effort': args.effort},
        job, deadline=deadline)
    counts = {}
    operations = []
    def event(value):
        name = value.get('type', '?')
        counts[name] = counts.get(name, 0) + 1
        if name == 'item.completed':
            item = value.get('item', {})
            operations.append({k: item[k] for k in ('type', 'status', 'exit_code', 'aggregated_output') if k in item})
    config = task_configuration(job, read_roots=[Path(sys.executable).parent.parent, Path('/opt/homebrew')], web_search='disabled')
    config['model'] = args.model
    config['model_reasoning_effort'] = args.effort
    config['features']['image_generation'] = False
    def tick():
        if time.monotonic() >= deadline:
            raise TimeoutError('Bounded live material test exceeded its deadline')
        broker.poll()
    result = {'kind': 'single-author-prefetch-live', 'production_changed': False,
              'model': args.model, 'effort': args.effort, 'passed': False}
    result['source_sha256']={name:hashlib.sha256((here/name).read_bytes()).hexdigest()
        for name in ('material_prefetch.py','prefetch-proxy.py','auxiliary_tools.py','test-material-prefetch-live.py')}
    started = time.monotonic()
    try:
        with AppServer(cwd=job, config=config, on_event=event, tick=tick) as server:
            thread = server.start_thread()['thread']['id']
            prompt = f'''This is a bounded engineering validation, not a finished presentation.
Use only your current workspace. Use two sequential shell tool calls: first run
{sys.executable} prefetch-proxy.py submit --batch material-jobs.json;
then run {sys.executable} write_current_page.py. Both scripts are
provided unchanged. Do not perform the searches yourself, wait, poll status,
delegate, inspect private files, edit the scripts or build further slides.
Report briefly that the current native page is written and later-source
requests were submitted. Do not claim the source work is already done.'''
            turn = server.start_turn(thread, prompt)['id']
            completed = server.wait_turn(thread, turn, timeout=180)
            result['author_completed'] = completed.get('status') == 'completed'
            result['author_usage'] = server.usage.get((thread, turn), {})
            result['author_response'] = server.result_text(thread, turn)
            result['events'] = counts
            result['operations'] = operations
        while any(r['state'] in ('queued', 'running') for r in broker.status()) and time.monotonic() < deadline:
            tick()
            time.sleep(.1)
        rows = broker.status()
        page = json.loads((job / 'current-page-receipt.json').read_text())
        records = [broker.get(row['id']) for row in rows]
        result['requests'] = records
        result['events'] = counts
        result['native_page_edit'] = page
        result['native_page_sha256'] = hashlib.sha256((job / 'current-page.pptx').read_bytes()).hexdigest()
        result['two_ready_results'] = len(records) == 2 and all(r['state'] == 'ready' for r in records)
        result['actual_source_urls'] = result['two_ready_results'] and all(
            re.search(r'https://', r['result']['text']) for r in records)
        result['actual_hosted_search_events'] = result['two_ready_results'] and all(
            any(c.get('tool_events',{}).get('web_search',0)>0 for c in r.get('calls',[])) for r in records)
        result['native_edit_overlapped_preparation'] = any(
            r.get('started_at', float('inf')) <= page['started_at'] <= r.get('completed_at', 0)
            for r in records)
        result['source_tasks_overlapped'] = len(records) == 2 and max(r.get('started_at', float('inf')) for r in records) < min(r.get('completed_at', 0) for r in records)
        result['passed'] = all(result.get(k) for k in ('author_completed', 'two_ready_results',
            'actual_source_urls','actual_hosted_search_events', 'native_edit_overlapped_preparation', 'source_tasks_overlapped'))
    except Exception as error:
        result['error_type'] = type(error).__name__
    finally:
        broker.close()
        result['seconds'] = round(time.monotonic() - started, 3)
        write(proof_root / 'proof.json', result)
    print(json.dumps({k: result[k] for k in ('passed', 'seconds', 'error_type') if k in result}))
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
