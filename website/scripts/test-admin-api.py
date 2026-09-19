"""Local simulator only. --admin expects local_seedy to be explicitly allowed.
Seeds/deletes only its own UUID fixtures in the local SQLite database.
Never touches a production queue or real user quota.
"""
import argparse, json, sqlite3, time, uuid, urllib.request, urllib.error
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--admin',action='store_true')
parser.add_argument('--port',type=int,default=3000)
args=parser.parse_args()
BASE=f'http://localhost:{args.port}'
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def call(path,signed=False,spoof=False):
    headers={}
    if signed: headers['Cookie']='__sites_local_auth=1'
    if spoof: headers.update({'oai-authenticated-user-id':'local_seedy','oai-authenticated-user-email':'seedy@sites.test'})
    request=urllib.request.Request(BASE+path,headers=headers)
    try:
        response=opener.open(request,timeout=30)
    except urllib.error.HTTPError as error: response=error
    raw=response.read()
    return response.status,json.loads(raw) if 'application/json' in response.headers.get('Content-Type','') else raw,response.headers

paths=['/api/admin/jobs','/api/admin/jobs/missing','/api/admin/jobs/missing/download','/api/admin/jobs/missing/preview/1']
for path in paths:
    assert call(path)[0]==401,path
    assert call(path,spoof=True)[0]==401,path
if not args.admin:
    for path in paths: assert call(path,signed=True)[0]==403,path
    assert call('/api/account',True)[1]['admin'] is False
    print('PASS: anonymous=401, forged headers=401, non-admin=403 on every admin API; fail closed')
    raise SystemExit

dbs=list(Path('.wrangler/state/v3/d1/miniflare-D1DatabaseObject').glob('*.sqlite'))
dbs=[p for p in dbs if p.name!='metadata.sqlite']
assert len(dbs)==1,'Expected one local database'
db=sqlite3.connect(dbs[0],timeout=10)
ids=[str(uuid.uuid4()) for _ in range(28)]
marker='admin-fixture-'+str(uuid.uuid4())
now=int(time.time()*1000)
try:
    progress=json.dumps({'updatedAt':now,'events':[{'seq':1,'at':now,'code':'working','secret':'MUST-NOT-LEAK'}],'previews':[1]})
    for i,id in enumerate(ids):
        db.execute('INSERT INTO jobs (id,user_id,request_key,title,brief,pages,style,language,status,created_at,updated_at,lease,thread_id,progress) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
         (id,marker+'-user-'+str(i%2),str(uuid.uuid4()),marker+(' 50%_' if i==0 else ''),'An original request with <script>never execute</script>',5,'Designer choice','en','running' if i==0 else 'queued',now+i,now,'PRIVATE-LEASE','PRIVATE-THREAD',progress))
    db.commit()
    code,data,headers=call('/api/admin/jobs?q='+marker,True)
    assert code==200 and data['total']==28 and len(data['jobs'])==25,data
    assert 'no-store' in headers['Cache-Control']
    assert len(call('/api/admin/jobs?q='+marker+'&page=2',True)[1]['jobs'])==3
    assert call('/api/admin/jobs?q='+marker+'&status=running',True)[1]['total']==1
    assert call('/api/admin/jobs?q='+marker+'%2050%25_',True)[1]['total']==1
    assert call('/api/admin/jobs?page=-1',True)[0]==400
    assert call('/api/admin/jobs?status=oops',True)[0]==400
    detail=call('/api/admin/jobs/'+ids[0],True)[1]
    assert detail['brief'].startswith('An original request') and detail['progress']['events'][0]['code']=='working'
    serialized=json.dumps([data,detail])
    assert all(secret not in serialized for secret in ['PRIVATE-LEASE','PRIVATE-THREAD','MUST-NOT-LEAK','result_key','request_key'])
    assert call('/api/admin/jobs/missing',True)[0]==404
    assert call('/api/admin/jobs/'+ids[0]+'/download',True)[0]==404
    assert call('/api/admin/jobs/'+ids[0]+'/preview/16',True)[0]==404
    task_progress=call('/api/jobs/'+ids[0]+'/progress',True)
    assert task_progress[0]==200 and task_progress[1]['scope']=='admin'
    for suffix in ['download','preview/1']:
        assert call('/api/jobs/'+ids[0]+'/'+suffix,True)[0]==404,'User routes must remain owner-scoped'
    assert not any(j['id'] in ids for j in call('/api/account',True)[1]['jobs'])
    assert call('/api/account',True)[1]['admin'] is True
    assert call('/admin',True)[0]==200
    print('PASS: cross-user list/detail, pagination, literal search, statuses, original brief, safe progress, secret exclusion, unchanged user isolation, admin page')
finally:
    db.executemany('DELETE FROM jobs WHERE id=?',[(id,) for id in ids]);db.commit();db.close()
