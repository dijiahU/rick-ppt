"""Local-only integration: request -> exact delivered PPTX, with read-only auth."""
import hashlib,json,sqlite3,subprocess,sys,tempfile,time,uuid,urllib.request,urllib.error
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'pptx-test-runner'))
from review import ReviewClient,NoRedirect

BASE='http://localhost:3000'
TOKEN='local-review-test-not-a-production-secret'
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
client=ReviewClient(BASE,TOKEN,opener)
def call(path,token=None,method='GET',body=None,headers=None):
    h=headers or {}
    if token:h['Authorization']='Bearer '+token
    try:r=opener.open(urllib.request.Request(BASE+path,data=body,headers=h,method=method),timeout=30)
    except urllib.error.HTTPError as e:r=e
    raw=r.read()
    return r.status,json.loads(raw) if 'application/json' in r.headers.get('Content-Type','') else raw

for path in ['/api/review/jobs','/api/review/jobs/missing','/api/review/jobs/missing/pptx']:
    assert call(path)[0]==401
    assert call(path,'wrong-token')[0]==401
    assert call(path,headers={'Cookie':'__sites_local_auth=1'})[0]==401
    for method in ['POST','PUT','PATCH','DELETE']:assert call(path,TOKEN,method)[0]==405
assert call('/api/worker',TOKEN,'POST',b'{}')[0]==401
assert call('/api/jobs',TOKEN,'POST',b'{}',{'Origin':BASE})[0]==401
assert call('/api/admin/jobs',TOKEN)[0]==401
assert call('/api/review/jobs?page=-1',TOKEN)[0]==400

dbs=[p for p in Path('.wrangler/state/v3/d1/miniflare-D1DatabaseObject').glob('*.sqlite') if p.name!='metadata.sqlite']
assert len(dbs)==1
db=sqlite3.connect(dbs[0],timeout=10)
ids=[str(uuid.uuid4()) for _ in range(3)];lease=str(uuid.uuid4());marker='review-fixture-'+str(uuid.uuid4());now=int(time.time()*1000)
key=f'results/{ids[0]}/{lease}.pptx';uploaded=False
try:
    for i,id in enumerate(ids):
        db.execute('INSERT INTO jobs(id,user_id,request_key,title,brief,pages,style,language,status,created_at,updated_at,lease,thread_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
          (id,marker+str(i),id,marker+' '+str(i),'Original requirement <script>untrusted</script>',5,'Designer choice','en','running' if i==0 else 'queued' if i==1 else 'complete',now+i,now,lease,'DO-NOT-EXPOSE'))
    db.execute('UPDATE jobs SET result_key=? WHERE id=?',('missing/'+ids[2],ids[2]));db.commit()
    worker_token=None
    for line in Path('.env').read_text().splitlines():
        if line.startswith('WORKER_TOKEN='):worker_token=line.split('=',1)[1].strip().strip('\"\'')
    assert worker_token and worker_token!=TOKEN,'Local worker test credential required'
    assert call('/api/review/jobs',worker_token)[0]==401
    pptx=Path('../pptx-test-runner/smoke-result.pptx').read_bytes()
    assert call(f'/api/worker/{ids[0]}?action=complete',worker_token,'POST',pptx,{'X-Job-Lease':lease})[0]==200
    uploaded=True
    snapshot=db.execute('SELECT * FROM jobs WHERE id IN (?,?,?)',ids).fetchall()
    listing=client.listing(marker);assert listing['total']==3 and listing['readOnly']
    assert client.listing(marker,'complete')['total']==2
    detail=client.metadata('/api/review/jobs/'+ids[0]);assert detail['artifact']['available']
    assert all(x not in json.dumps(detail) for x in ['result_key','lease','thread_id','DO-NOT-EXPOSE','request_key'])
    assert call('/api/review/jobs/'+ids[0]+'/pptx',TOKEN,headers={'If-Match':'"different"'})[0]==412
    with tempfile.TemporaryDirectory(prefix='pptx-review-test-') as folder:
        result=client.fetch(ids[0],Path(folder))
        assert Path(result['directory'],'output.pptx').read_bytes()==pptx
        assert result['sha256']==hashlib.sha256(pptx).hexdigest() and result['slideCount']>0
        assert Path(result['directory'],'output.pptx').stat().st_mode&0o077==0
        assert json.loads(Path(result['directory'],'request.json').read_text())['job']['brief']=='Original requirement <script>untrusted</script>'
        assert client.fetch(ids[1],Path(folder))['reason']=='not_completed'
        assert client.fetch(ids[2],Path(folder))['reason']=='stored_file_missing'
    assert db.execute('SELECT * FROM jobs WHERE id IN (?,?,?)',ids).fetchall()==snapshot,'Reads mutated task data'
    for action in ['fail','complete','heartbeat']:
        assert call(f'/api/worker/{ids[0]}?action={action}',TOKEN,'POST',b'{}',{'X-Job-Lease':lease})[0]==401
    print('PASS: private read-only authorization; cross-user request/PPTX pairing; exact bytes/hash; ETag mismatch; missing and unfinished results; no task mutations; no quota use; no secret fields')
finally:
    db.executemany('DELETE FROM jobs WHERE id=?',[(id,) for id in ids]);db.commit();db.close()
    if uploaded:
        result=subprocess.run(['npx','wrangler','r2','object','delete','site-creator-r2/'+key,'--local','--persist-to','.wrangler/state','--config','scripts/local-review.json'],capture_output=True,text=True)
        if result.returncode:raise RuntimeError('Local fixture object cleanup failed: '+key)
