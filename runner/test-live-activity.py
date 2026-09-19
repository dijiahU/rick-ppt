"""Explicit local smoke: one search and public note; no production queue calls."""
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import runner
from progress import Reporter

cfg=runner.settings();job=runner.prepare(cfg)
prompt='''This is a bounded public activity smoke test, not a PPT task. Use the hosted web search tool ONCE to search for a university explanation of gradient descent. Do not use shell networking. Then write public-status.json in this task directory containing revision 1, phase research, and a short Chinese summary of whether the search actually worked. Do not include private reasoning, credentials or local paths. Do not read unrelated files or create a presentation. Finish immediately after that note.'''
with tempfile.TemporaryFile() as log:
    process=subprocess.Popen(runner.codex_command(cfg,job),stdin=subprocess.PIPE,stdout=log,stderr=log,env=runner.environment(job),cwd=job,start_new_session=True)
    try:
        process.communicate(prompt.encode(),timeout=150)
        if process.returncode:raise RuntimeError('Smoke CLI failed')
    finally:
        if process.poll() is None:os.killpg(process.pid,signal.SIGTERM);process.wait(timeout=10)
    calls=[];reporter=Reporter({}, {'id':'smoke','lease':'local'},job,lambda *args:calls.append(args))
    log.seek(0)
    kinds=set()
    for line in log:
        try:
            event=json.loads(line);kinds.add(event.get('item',{}).get('type',''))
            reporter.consume(event)
        except (ValueError,TypeError):pass
    reporter.poll_public_status()
    assert any(e.get('reported') for e in reporter.events),'Public note missing'
    searches=[e for e in reporter.events if e.get('state') and e.get('code')=='working' and e.get('detail')]
    print(json.dumps({'job':str(job),'types':sorted(kinds),'search_events':searches,'public_notes':[e for e in reporter.events if e.get('reported')]},ensure_ascii=False))
