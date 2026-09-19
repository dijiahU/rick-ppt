#!/usr/bin/env python3
"""Mirror website task identities and recover legacy public CLI events read-only."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import uuid
import re

from trajectory import Trajectory,record,encoded,private_write,SCHEMA
from assets import AssetImporter

ROOT=Path(__file__).resolve().parent

def trusted_workspaces():
    """Only supervisor-created job/root mappings; never paths supplied by tools."""
    mappings={}
    pattern=re.compile(r'^Starting (?:content-first )?job ([0-9a-f-]{36}) in (/[^\r\n]+/pptx-lab-job-[^/\r\n]+)$')
    for file in (ROOT.parent/'.work').glob('*/worker.log'):
        with file.open(errors='replace') as stream:
            for line in stream:
                match=pattern.fullmatch(line.strip())
                if not match:continue
                ident,path=match.groups();root=Path(path)
                if root.is_dir() and not root.is_symlink():mappings.setdefault(ident,set()).add(root)
    return mappings

def atomic_json(path,value):
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.pending')
    private_write(temp,encoded(value));os.replace(temp,path)

def review_command(*args):
    result=subprocess.run([sys.executable,str(ROOT/'review.py'),*args],capture_output=True,text=True,timeout=160)
    if result.returncode:raise RuntimeError('Read-only website review unavailable')
    return json.loads(result.stdout)

def sync(directory,read=review_command,records=None):
    directory=Path(directory);records=Path(records or ROOT/'records')
    workspaces=trusted_workspaces() if read is review_command else {}
    page=1;jobs=[]
    while True:
        value=read('list','--page',str(page));jobs.extend(value['jobs'])
        if page*value['limit']>=value['total']:break
        page+=1
    counts={'tasks':len(jobs),'recovered':0,'live':0,'pending':0,'errors':0}
    for job in jobs:
        try:
            ident=str(uuid.UUID(job['id']))
            if ident!=job['id']:raise ValueError('Invalid task identity')
            folder=directory/ident;folder.mkdir(mode=0o700,parents=True,exist_ok=True)
            atomic_json(folder/'task.json',job)
            manifests=list(folder.glob('*/manifest.json'))
            live=[p for p in manifests if json.loads(p.read_text()).get('source_mode')=='live']
            if live:counts['live']+=1;continue
            if job['status'] in ('queued','running'):
                counts['pending']+=1;continue
            marker=folder/'history-recovered.json'
            logs=sorted((p for p in records.glob(ident+'*.jsonl') if '-admin-trace-' not in p.name and not p.is_symlink()),key=lambda p:(p.stat().st_mtime_ns,p.name))
            signature={'schema':SCHEMA,'updated_at':job['updated_at'],'logs':[{ 'name':p.name,'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for p in logs]}
            if marker.exists() and json.loads(marker.read_text()).get('signature')==signature:continue
            fetched=read('fetch',ident,'--out',str(folder/'source'))
            source=Path(fetched['directory']).resolve()
            if not source.is_relative_to(folder.resolve()):raise ValueError('Unexpected review directory')
            metadata=json.loads((source/'request.json').read_text())
            task=metadata.get('job',job)
            trajectory=Trajectory({},task,directory,historical=True)
            trajectory.gap('historical_recovery','Original phase prompts, exact runtime/model context and intermediate file versions were not recorded.')
            trajectory.gap('historical_attempt_identity','Original leases/retry boundaries are unavailable; logs are separate recovered sessions, not an inferred single attempt.')
            trajectory.gap('historical_timing','CLI logs lack reliable per-event execution timestamps. Receipt times below are recovery times.')
            trajectory.emit('task.recovered',metadata)
            trajectory.snapshot(source,'historical.request-and-delivered-artifact')
            if (source/'output.pptx').is_file():trajectory.artifact((source/'output.pptx').read_bytes(),'presentation.pptx','delivered',{'retrieval':'read-only review service'},final=True)
            if not logs:trajectory.gap('no_local_cli_logs','No matching original CLI event file exists on this host.')
            for log in logs:
                trajectory.stage='recovered-session';trajectory.phase_id=str(uuid.uuid4());trajectory.thread=None;trajectory.turn=0;trajectory.offset=0
                trajectory.phases.append({'id':trajectory.phase_id,'name':'recovered-session','log_name':log.name,
                  'log_mtime':int(log.stat().st_mtime*1000),'supplied_prompt':None,'attempt_boundary':'unknown'})
                trajectory.emit('session.recovered',{'filename':log.name,'ordering':'File modification order only; cross-session execution order is unknown.'})
                with log.open('rb') as stream:
                    while trajectory.offset<log.stat().st_size:
                        before=trajectory.offset;trajectory.poll(stream)
                        if trajectory.offset==before:
                            trajectory.gap('incomplete_log_tail',log.name);break
                if trajectory.active:
                    trajectory.gap('unmatched_started_items',{'log':log.name,'count':len(trajectory.active)})
                    trajectory.active.clear()
                importer=AssetImporter(None,trajectory=trajectory)
                importer.consume({'type':'thread.started','thread_id':trajectory.thread})
                if importer.thread:importer.import_images()
            for workspace in sorted(workspaces.get(ident,())):
                trajectory.snapshot(workspace,'historical.surviving-workspace')
            trajectory.gap('historical_artifacts_partial','Only surviving files and trusted-thread generated images are recoverable. Download originals and deleted transient states may be absent.')
            result=trajectory.finish(job['status'])
            atomic_json(marker,{'signature':signature,'run_id':trajectory.run_id,'directory':result.name})
            counts['recovered']+=1
        except Exception as error:
            counts['errors']+=1
            print('Trajectory history pending:',job.get('id','unknown'),type(error).__name__,flush=True)
    return counts

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--watch',action='store_true');parser.add_argument('--wait-for-mirror',action='store_true')
    parser.add_argument('--directory',type=Path,default=ROOT.parent/'trajectory');args=parser.parse_args()
    args.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    lock=(args.directory/'.history.lock').open('a+');os.chmod(lock.name,0o600)
    try:fcntl.flock(lock,fcntl.LOCK_EX|(0 if args.wait_for_mirror else fcntl.LOCK_NB))
    except BlockingIOError:raise SystemExit('Trajectory history mirror already running')
    lock.seek(0);lock.truncate();lock.write(str(os.getpid()));lock.flush()
    stop=threading.Event()
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *_:stop.set())
    while not stop.is_set():
        try:print(json.dumps(sync(args.directory)),flush=True)
        except Exception as error:print('Trajectory history sync pending:',type(error).__name__,flush=True)
        if not args.watch:break
        stop.wait(60)

if __name__=='__main__':main()
