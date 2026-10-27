"""Task-local public notes and native per-slide preview receipts. No network."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
from outline import validate_outline, page_version, MAX_SLIDES, MAX_OUTLINE_BYTES, MAX_JOURNAL_BYTES

ROOT=Path(__file__).resolve().parent
PHASES=('research','planning','design','building','rendering','review')

def append_record(record):
    data=(json.dumps(record,ensure_ascii=False)+'\n').encode()
    if len(data)>MAX_OUTLINE_BYTES:raise ValueError('Public update is too large')
    fd=os.open(ROOT/'public-progress.jsonl',os.O_WRONLY|os.O_APPEND|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'ab',buffering=0) as stream:
        fcntl.flock(stream,fcntl.LOCK_EX)
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode) or os.fstat(stream.fileno()).st_size+len(data)>MAX_JOURNAL_BYTES:
            raise ValueError('Public update journal is full')
        stream.write(data)

def run_json(command):
    result=subprocess.run(command,text=True,capture_output=True)
    if result.returncode:
        # Diagnostics stay in the private execution log, never the public journal.
        sys.stderr.write(result.stderr[-4000:])
        raise RuntimeError('Native page rendering failed')
    return json.loads(result.stdout)

def render_page(args):
    config=json.loads((ROOT/'capabilities.json').read_text())['progressive_authoring']
    workspace=args.workspace
    native_slide=args.slide
    outline=read_outline()
    rendered=run_json([sys.executable,config['pptx_cli'],'-w',workspace,'render',str(native_slide)])
    if rendered.get('ok') is not True or rendered.get('renderer')!='LibreOffice' or len(rendered.get('pages',[]))!=1:
        raise ValueError('Expected one successful native page render')
    # The host still validates the path, PNG bounds and upload before listing it.
    append_record({'kind':'preview','slide':args.slide,'render':rendered,'contentVersion':page_version(outline,args.slide)})
    return {'ok':True,'slide':args.slide,'pages':rendered['pages'],'workspace':workspace}

def read_outline():
    path=ROOT/'outline.json'
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise ValueError('Outline must be a regular file')
        data=stream.read(MAX_OUTLINE_BYTES+1)
        if len(data)>MAX_OUTLINE_BYTES:raise ValueError('Outline too large')
    request=json.loads((ROOT/'request.json').read_text()) if (ROOT/'request.json').exists() else {}
    return validate_outline(json.loads(data),request.get('pages'))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    note=sub.add_parser('note')
    note.add_argument('--phase',choices=PHASES,required=True)
    note.add_argument('--summary',required=True)
    note.add_argument('--next',dest='next_step')
    note.add_argument('--slide',type=int,choices=range(1,MAX_SLIDES+1))
    sub.add_parser('outline')
    render=sub.add_parser('render')
    render.add_argument('--workspace',required=True)
    render.add_argument('--slide',type=int,choices=range(1,MAX_SLIDES+1),required=True)
    args=parser.parse_args()
    if args.action=='note':
        if not args.summary.strip() or len(args.summary)>800 or len(args.next_step or '')>400:
            raise ValueError('Use a concise summary (800 characters) and next step (400 characters)')
        record={'kind':'note','phase':args.phase,'summary':args.summary,'at':int(time.time()*1000)}
        if args.slide:record['slide']=args.slide
        if args.next_step:record['next']=args.next_step
        append_record(record)
        print(json.dumps({'ok':True,'published':'note'}))
    elif args.action=='outline':
        outline=read_outline();append_record({'kind':'outline','outline':outline})
        print(json.dumps({'ok':True,'revision':outline['revision'],'pages':len(outline['slides'])}))
    else:print(json.dumps(render_page(args),ensure_ascii=False))

if __name__=='__main__':main()
