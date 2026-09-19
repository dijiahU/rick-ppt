"""Local-only worker progress/preview integration. Never targets production."""
import http.cookiejar
import json
import urllib.request
import urllib.error
import time
import uuid
import base64
import subprocess
import sys
from pathlib import Path

BASE='http://localhost:3000'
TOKEN='local-progress-test-not-a-production-secret'
jar=http.cookiejar.CookieJar()
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(jar))
opener.open(BASE+'/signin-with-chatgpt?return_to=/api/account').read()
cookie='; '.join(f'{c.name}={c.value}' for c in jar)

def call(path,body=None,*,signed=False,worker=False,lease=None):
    headers={}
    if signed:headers['Cookie']=cookie
    if worker:headers['Authorization']='Bearer '+TOKEN
    if lease:headers['X-Job-Lease']=lease
    if isinstance(body,dict):body=json.dumps(body).encode();headers['Content-Type']='application/json'
    req=urllib.request.Request(BASE+path,data=body,headers=headers)
    try:
        response=urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req)
    except urllib.error.HTTPError as error:response=error
    raw=response.read()
    try:value=json.loads(raw)
    except ValueError:value=raw
    return response.status,value,response.headers

fixtures=call('/api/account',signed=True)[1].get('jobs',[])
assert fixtures and all(j['title']=='本地额度测试' for j in fixtures), 'Refuse to touch non-fixture jobs'
id,lease=str(uuid.uuid4()),str(uuid.uuid4())
other=str(uuid.uuid4())
# Create new explicit test fixtures; never claim or alter any pre-existing queue item.
for fixture_id,owner in [(id,'local_seedy'),(other,'local_progress_other')]:
    sql=f"INSERT INTO jobs(id,user_id,request_key,title,brief,pages,style,status,created_at,updated_at,lease) VALUES ('{fixture_id}','{owner}','{fixture_id}','本地额度测试','Progress-only fixture',5,'test','running',{int(time.time()*1000)},{int(time.time()*1000)},'{lease}')"
    subprocess.run(['npx','wrangler','d1','execute','DB','--config','scripts/local-db.json','--local','--persist-to','.wrangler/state','--command',sql],check=True,capture_output=True)
base=f'/api/worker/{id}'
progress={'updatedAt':int(time.time()*1000),'events':[{'seq':1,'at':int(time.time()*1000),'code':'started'}],'previews':[]}
assert call(base+'?action=progress',progress,lease=lease)[0]==401
assert call(base+'?action=progress',progress,worker=True,lease='wrong')[0]==409
bad={**progress,'events':[{'seq':1,'at':1,'code':'SECRET_RAW_REASONING'}]}
assert call(base+'?action=progress',bad,worker=True,lease=lease)[0]==400
progress['events'][0]['text']='SECRET_EXTRA_FIELD'
assert call(base+'?action=progress',progress,worker=True,lease=lease)[0]==200
assert call(f'/api/jobs/{id}/progress')[0]==401
status,data,headers=call(f'/api/jobs/{id}/progress',signed=True)
assert status==200 and data['progress']['events'][0]['code']=='started'
assert 'SECRET' not in json.dumps(data) and 'no-store' in headers['Cache-Control']
assert call(f'/api/jobs/{uuid.uuid4()}/progress',signed=True)[0]==404
assert call(f'/api/jobs/{other}/progress',signed=True)[0]==404
assert call(base+'?action=preview&slide=1',b'not a png',worker=True,lease=lease)[0]==400
assert call(base+'?action=preview&slide=99',b'none',worker=True,lease=lease)[0]==400
png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
assert call(base+'?action=preview&slide=1',png,worker=True,lease=lease)[0]==200
assert call(f'/api/jobs/{id}/preview/1')[0]==401
status,data,headers=call(f'/api/jobs/{id}/preview/1',signed=True)
assert status==200 and data==png and 'no-store' in headers['Cache-Control']
assert call(f'/api/jobs/{uuid.uuid4()}/preview/1',signed=True)[0]==404
assert call(f'/api/jobs/{other}/preview/1',signed=True)[0]==404
if len(sys.argv)>1:
    # Replay a completed local smoke log through the actual bridge sanitizer.
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'pptx-test-runner'))
    from progress import Reporter
    source=Path(sys.argv[1]).resolve()
    def send(cfg,path,body,lease):
        status,result,_=call(path,body,worker=True,lease=lease)
        assert status==200,(status,result)
        return result
    reporter=Reporter({}, {'id':id,'lease':lease},source.parent,send)
    with source.open('rb') as stream:
        reporter.poll(stream)
    reporter.flush(force=True)
    synced=call(f'/api/jobs/{id}/progress',signed=True)[1]['progress']
    assert synced['previews']==[1,2,3,4,5],synced
    assert any(e['code']=='rendered' for e in synced['events'])
    print('PASS: replayed real five-slide Codex log and uploaded five actual rendered previews')
assert call(base+'?action=fail',{},worker=True,lease=lease)[0]==200
assert call(base+'?action=progress',progress,worker=True,lease=lease)[0]==409
assert call(f'/api/jobs/{id}/progress',signed=True)[1]['status']=='failed'
assert call(f'/api/worker/{other}?action=fail',{},worker=True,lease=lease)[0]==200
print('PASS: lease checks, allowlisted events, extra-field stripping, private progress/PNG retrieval, cache control and terminal-state rejection')
