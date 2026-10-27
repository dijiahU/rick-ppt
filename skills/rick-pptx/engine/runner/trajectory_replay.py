#!/usr/bin/env python3
"""Restore archived bytes without executing commands, contacting sites or models."""
import argparse
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import re
import stat


def read_json(path):
    with path.open() as f:return json.load(f)

def checked_path(value):
    path=PurePosixPath(value)
    if not value or path.is_absolute() or any(p in ('.','..') for p in value.split('/')) or '\\' in value or '\x00' in value:
        raise ValueError('Unsafe archive path')
    return path

def copy_original(run,ref,destination):
    sha=ref.get('raw_sha256')
    if not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha):
        raise ValueError('Original bytes unavailable; exact restoration refused')
    base=os.open(run/'raw-blobs',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:fd=os.open(sha,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=base)
    finally:os.close(base)
    with os.fdopen(fd,'rb') as source:
        if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):raise ValueError('Invalid original blob')
        hasher=hashlib.sha256();count=0
        with os.fdopen(os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as target:
            while block:=source.read(1024*1024):target.write(block);hasher.update(block);count+=len(block)
        if hasher.hexdigest()!=sha or count!=ref['raw_bytes']:
            raise ValueError('Original checksum mismatch; restored output must not be used')
    return count

def restore_snapshot(run,snapshot_id,out):
    run=Path(run);out=Path(out)
    if not re.fullmatch('[0-9a-f-]{36}',snapshot_id):raise ValueError('Expected snapshot UUID')
    snapshot=read_json(run/'snapshots'/(snapshot_id+'.json'))
    if snapshot.get('unavailable'):raise ValueError('Snapshot has missing files; exact restoration refused')
    entries=[(checked_path(name),ref) for name,ref in snapshot['files'].items()]
    # Destination must be new. No cleanup or overwrite of caller-owned files.
    out.mkdir(mode=0o700,parents=False,exist_ok=False)
    count=0
    for relative,ref in entries:
        target=out.joinpath(*relative.parts);target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        # No symlinks are produced and the fresh directory is owner-private.
        count+=copy_original(run,ref,target)
        os.chmod(target,int(ref.get('mode',0o600))&0o777)
        if isinstance(ref.get('mtime_ns'),int):os.utime(target,ns=(ref['mtime_ns'],ref['mtime_ns']))
    return {'restored_files':len(entries),'bytes':count,'source_scope':snapshot['scope'],
            'file_bytes_verified':True,'snapshot_atomic':False,'model_rerun':False,'destination':str(out)}

def list_run(run):
    run=Path(run);manifest=read_json(run/'manifest.json')
    snapshots=[]
    for p in (run/'snapshots').glob('*.json'):
        value=read_json(p);snapshots.append({k:value[k] for k in ('id','scope','phase_id','after_event_seq','reason')})
    return {'manifest':manifest,'snapshots':snapshots,'artifacts':list_artifacts(run)}

def list_artifacts(run):
    file=Path(run)/'artifacts.jsonl'
    return [json.loads(line) for line in file.read_text().splitlines()] if file.exists() else []

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    listing=sub.add_parser('list');listing.add_argument('run',type=Path)
    restore=sub.add_parser('restore');restore.add_argument('run',type=Path);restore.add_argument('--snapshot',required=True);restore.add_argument('--out',type=Path,required=True)
    item=sub.add_parser('artifact');item.add_argument('run',type=Path);item.add_argument('--id',required=True);item.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='list':result=list_run(args.run)
    elif args.command=='restore':result=restore_snapshot(args.run,args.snapshot,args.out)
    else:
        records=[a for a in list_artifacts(args.run) if a['id']==args.id]
        if len(records)!=1:raise ValueError('Artifact ID not found')
        size=copy_original(args.run,records[0]['original'],args.out)
        result={'artifact_id':args.id,'bytes':size,'file_bytes_verified':True,'destination':str(args.out)}
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
