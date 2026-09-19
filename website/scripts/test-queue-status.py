"""Local queue diagnostics and isolation. Restores only its own fixture state."""
import argparse,json,sqlite3,time,uuid,urllib.request,urllib.error
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--port',type=int,default=3000)
args=parser.parse_args()
base=f'http://localhost:{args.port}'
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def call(path,signed=True):
    request=urllib.request.Request(base+path,headers={'Cookie':'__sites_local_auth=1'} if signed else {})
    try:r=opener.open(request,timeout=30)
    except urllib.error.HTTPError as e:r=e
    return r.status,json.loads(r.read())

paths=[p for p in Path('.wrangler/state/v3/d1/miniflare-D1DatabaseObject').glob('*.sqlite') if p.name!='metadata.sqlite']
assert len(paths)==1
db=sqlite3.connect(paths[0],timeout=10)
old_worker=db.execute("SELECT heartbeat FROM worker WHERE id='primary'").fetchone()
marker='queue-fixture-'+str(uuid.uuid4())
ids=sorted(str(uuid.uuid4()) for _ in range(6))
now=int(time.time()*1000)
admin=call('/api/account')[1].get('admin',False)
try:
    for i,id in enumerate(ids):
        db.execute('INSERT INTO jobs(id,user_id,request_key,title,brief,pages,style,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
          (id,'local_seedy' if i==1 else marker,id,marker+str(i),'A local queue test',5,'test','queued' if i<3 else 'running',now,now))
    db.execute("INSERT INTO worker(id,heartbeat) VALUES('primary',?) ON CONFLICT(id) DO UPDATE SET heartbeat=excluded.heartbeat",(now-120000,))
    db.commit()
    route=f'/api/jobs/{ids[1]}/progress'
    assert call(route,False)[0]==401
    code,data=call(route)
    assert code==200 and data['scope']=='user'
    expected=db.execute("SELECT COUNT(*)+1 FROM jobs WHERE status='queued' AND (created_at<? OR (created_at=? AND id<?))",(now,now,ids[1])).fetchone()[0]
    assert data['queuePosition']==expected,data
    assert data['queue']['online'] is False and data['queue']['capacity']==3
    assert data['queue']['running']>=3 and data['queue']['queued']>=3
    assert all(k not in json.dumps(data['queue']) for k in ['user_id','lease','brief','result_key','token'])
    db.execute("UPDATE worker SET heartbeat=? WHERE id='primary'",(now,));db.commit()
    assert call(route)[1]['queue']['online'] is True
    assert call(f'/api/jobs/{ids[0]}/progress')[0]==(200 if admin else 404)
    if admin:
        listing=call('/api/admin/jobs?q='+marker+'1')[1]
        assert listing['total']==1 and listing['jobs'][0]['queuePosition']==expected
        assert listing['queue']['online'] and listing['queue']['lastHeartbeat']==now
        detail=call('/api/admin/jobs/'+ids[1])[1]
        assert detail['queuePosition']==expected and detail['queue']['online']
    else:
        assert call('/api/admin/jobs')[0]==403
    db.execute("UPDATE jobs SET status='running' WHERE id=?",(ids[1],));db.commit()
    data=call(route)[1]
    assert data['queue'] is None and data['queuePosition'] is None
    print('PASS: stale/fresh worker, FIFO tie-break, global positions, busy capacity, terminal queue removal, owner/admin isolation')
finally:
    db.executemany('DELETE FROM jobs WHERE id=?',[(i,) for i in ids])
    if old_worker:db.execute("INSERT INTO worker(id,heartbeat) VALUES('primary',?) ON CONFLICT(id) DO UPDATE SET heartbeat=excluded.heartbeat",old_worker)
    else:db.execute("DELETE FROM worker WHERE id='primary'")
    db.commit();db.close()
