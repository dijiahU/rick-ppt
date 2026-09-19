"""Prepare one owner-authorized acceptance job for an additive Sites data migration.

This is an operator tool, not a public submission endpoint. It reads no credential
and makes no network request. Apply its SQL only through the site's authenticated
owner deployment, after the release smoke gate. The account comes from one exact
existing task; the existing task, quota settings and delivered files are unchanged.
The new job counts in normal history and uses the ordinary worker/lease pipeline.
"""
import argparse
import json
from pathlib import Path
import time
import uuid


def canonical_uuid(value):
    if not isinstance(value,str) or str(uuid.UUID(value))!=value:
        raise ValueError('Expected a canonical task/request UUID')
    return value


def sql_text(value):
    if not isinstance(value,str) or '\x00' in value:raise ValueError('Invalid text')
    return "'"+value.replace("'","''")+"'"


def utf16_length(value):
    return len(value.encode('utf-16-le'))//2


def prepare(request, source_task, source_title, identifier, timestamp):
    canonical_uuid(source_task);canonical_uuid(identifier)
    if not isinstance(request,dict):raise ValueError('Expected a submission object')
    key=canonical_uuid(request.get('requestKey'))
    title,brief,style=(request.get(k) for k in ('title','brief','style'))
    if not isinstance(title,str) or not title.strip() or utf16_length(title)>120:raise ValueError('Invalid title')
    if not isinstance(brief,str) or len(brief.strip())<10 or utf16_length(brief)>12000:raise ValueError('Invalid brief')
    if not isinstance(style,str) or utf16_length(style)>80:raise ValueError('Invalid style')
    if request.get('language')!='en':raise ValueError('These researched acceptance cases require English')
    pages=request.get('pages')
    if isinstance(pages,bool) or not isinstance(pages,int) or not 1<=pages<=50:raise ValueError('Invalid page count')
    if request.get('mode','create')!='create' or request.get('files'):raise ValueError('Only new attachment-free cases are supported')
    if len(json.dumps(request,ensure_ascii=False,separators=(',',':')).encode())>16000:raise ValueError('Request exceeds the ordinary JSON body limit')
    if not isinstance(source_title,str) or not source_title:raise ValueError('Require the exact source task title')
    if isinstance(timestamp,bool) or not isinstance(timestamp,int) or timestamp<0:raise ValueError('Invalid timestamp')
    # A missing/mismatched source account or full queue fails NOT NULL constraints;
    # it cannot silently assign another account or exceed normal queue capacity.
    owner=f'(SELECT user_id FROM jobs WHERE id={sql_text(source_task)} AND title={sql_text(source_title)})'
    status="CASE WHEN (SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')) < 100 THEN 'queued' ELSE NULL END"
    return ('-- One explicitly requested site-owner acceptance case; preserves all existing rows.\n'
            '-- No credential, authentication route, account role or quota setting is modified.\n'
            'INSERT INTO jobs (id,user_id,request_key,title,brief,pages,style,language,attachments,status,created_at,updated_at)\n'
            'VALUES ('+', '.join((sql_text(identifier),owner,sql_text(key),sql_text(title.strip()),sql_text(brief.strip()),str(pages),sql_text(style),"'en'","'[]'",status,str(timestamp),str(timestamp)))+')\n'
            'ON CONFLICT(user_id,request_key) DO NOTHING;\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request',type=Path,required=True)
    p.add_argument('--owner-source-task',required=True)
    p.add_argument('--owner-source-title',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--job-id',default=None)
    args=p.parse_args();identifier=args.job_id or str(uuid.uuid4())
    request=json.loads(args.request.read_text())
    sql=prepare(request,args.owner_source_task,args.owner_source_title,identifier,int(time.time()*1000))
    with args.output.open('x') as stream:stream.write(sql)
    print(json.dumps({'prepared':str(args.output),'job_id':identifier,'pages':request['pages'],
                      'brief_utf16_units':utf16_length(request['brief']),'submitted':False}))


if __name__=='__main__':main()
