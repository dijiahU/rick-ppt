"""Local-only detail-page integration; creates/removes only its own fixtures."""
import argparse,json,sqlite3,time,uuid,urllib.request,urllib.error
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=3000);args=parser.parse_args()
BASE=f'http://localhost:{args.port}'
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
token=next(line.split('=',1)[1].strip().strip('\"\'') for line in Path('.env').read_text().splitlines() if line.startswith('WORKER_TOKEN='))
def call(path,signed=False,body=None,lease=None):
    headers={'Cookie':'__sites_local_auth=1'} if signed else {}
    if body is not None:headers.update({'Authorization':'Bearer '+token,'X-Job-Lease':lease or '', 'Content-Type':'application/json'});body=json.dumps(body).encode()
    try:r=opener.open(urllib.request.Request(BASE+path,data=body,headers=headers),timeout=30)
    except urllib.error.HTTPError as e:r=e
    raw=r.read()
    return r.status,json.loads(raw) if 'application/json' in r.headers.get('Content-Type','') else raw
account=call('/api/account',True)[1]
paths=[p for p in Path('.wrangler/state/v3/d1/miniflare-D1DatabaseObject').glob('*.sqlite') if p.name!='metadata.sqlite']
assert len(paths)==1
db=sqlite3.connect(paths[0],timeout=10)
ids=[str(uuid.uuid4()),str(uuid.uuid4())];lease=str(uuid.uuid4());now=int(time.time()*1000)
try:
    for id,owner in zip(ids,['local_seedy','progress-room-other']):
        db.execute('INSERT INTO jobs(id,user_id,request_key,title,brief,pages,style,status,created_at,updated_at,lease) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(id,owner,id,'Progress room fixture','A local test request',5,'test','running',now,now,lease))
    db.commit()
    events=[{'seq':i+1,'at':now,'code':'working','category':'source','detail':f'Open source {i} '+'x'*700,'url':f'https://example.com/article?id={i}','state':'completed'} for i in range(400)]
    note={'seq':1,'at':now,'code':'working','category':'note','reported':True,'phase':'design','slide':2,'detail':'Use a clear comparison.','next':'Render page two.','reasoning':'PRIVATE-NOTE'}
    body={'updatedAt':now,'events':events,'notes':[note],'previews':[2],'previewVersions':{'2':'0123456789abcdef'}}
    assert len(json.dumps(body))>65536
    bad_lease=call(f'/api/worker/{ids[0]}?action=progress',body=body,lease='bad')
    assert bad_lease[0]==409,bad_lease
    assert call(f'/api/worker/{ids[0]}?action=progress',body=body,lease=lease)[0]==200
    assert call(f'/api/jobs/{ids[0]}/progress')[0]==401
    status,data=call(f'/api/jobs/{ids[0]}/progress',True)
    assert status==200 and data['title']=='Progress room fixture' and data['scope']=='user'
    assert len(data['progress']['events'])==400 and data['progress']['events'][399]['url'].endswith('id=399')
    assert data['progress']['notes'][0]['phase']=='design' and data['progress']['notes'][0]['slide']==2
    assert data['progress']['notes'][0]['next']=='Render page two.'
    assert 'PRIVATE-NOTE' not in json.dumps(data)
    assert data['progress']['previewVersions']['2']=='0123456789abcdef'
    if account.get('admin'):
        assert call(f'/api/admin/jobs/{ids[0]}',True)[1]['progress']['notes'][0]['detail']=='Use a clear comparison.'
    assert all(key not in data for key in ['lease','user_id','result_key','thread_id'])
    assert call(f'/api/jobs/{ids[1]}/progress',True)[0]==(200 if account.get('admin') else 404)
    status,page=call(f'/jobs/{ids[0]}',True)
    assert status==200 and b'Progress room fixture' in page,(status,'Missing authorized title')
    assert b'property="og:image"' not in page and b'name="twitter:image"' not in page
    status,page=call(f'/jobs/{ids[0]}')
    assert status==200 and b'Progress room fixture' not in page
    db.execute("UPDATE jobs SET status='complete' WHERE id=?",(ids[0],));db.commit()
    assert call(f'/api/worker/{ids[0]}?action=progress',body=body,lease=lease)[0]==409
    assert call(f'/api/jobs/{ids[0]}/progress',True)[1]['status']=='complete'
    print('PASS: 400 detailed events >64KB, source IDs, owner/admin isolation, authenticated page metadata, terminal state and lease checks')
finally:
    db.executemany('DELETE FROM jobs WHERE id=?',[(i,) for i in ids]);db.commit();db.close()
