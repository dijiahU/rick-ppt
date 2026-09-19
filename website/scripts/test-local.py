"""Local-only API tests, using Sites' simulated login (never production)."""
import concurrent.futures
import http.cookiejar
import json
import urllib.request
import urllib.error
import uuid

BASE = 'http://localhost:3000'
cookies = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(cookies))
opener.open(BASE+'/signin-with-chatgpt?return_to=/api/account').read()
cookie = '; '.join(f'{c.name}={c.value}' for c in cookies)

def call(path, data=None, signed=True, origin=BASE):
    headers={'Content-Type':'application/json','Origin':origin}
    if signed: headers['Cookie']=cookie
    req=urllib.request.Request(BASE+path, data=None if data is None else json.dumps(data).encode(), headers=headers)
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req) as response:
            return response.status,json.loads(response.read())
    except urllib.error.HTTPError as error:
        raw=error.read().decode()
        try: body=json.loads(raw)
        except json.JSONDecodeError: body={'error':raw[:200]}
        return error.code,body

def brief(key=None):
    return {'title':'本地额度测试','brief':'这是本地测试，不应该在真实执行端制作。','pages':5,'style':'清晰学术报告','requestKey':key or str(uuid.uuid4())}

assert call('/api/jobs',brief(),signed=False)[0]==401
assert call('/api/jobs',brief(),origin='https://untrusted.example')[0]==403
assert call('/api/worker',{})[0]==401
assert call('/api/jobs',{'title':'invalid'})[0]==400
before=call('/api/account')[1]['remaining']
assert before==10, 'Use a fresh local DB for this test.'
key=str(uuid.uuid4())
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    results=list(pool.map(lambda _:call('/api/jobs',brief(key)),range(8)))
assert len({r[1]['id'] for r in results})==1, results
assert call('/api/account')[1]['remaining']==9
with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
    results=list(pool.map(lambda _:call('/api/jobs',brief()),range(16)))
assert sum(status==201 for status,_ in results)==9,results
assert sum(status==429 for status,_ in results)==7,results
account=call('/api/account')[1]
assert account['remaining']==0 and len(account['jobs'])==10
assert call('/api/jobs',brief())[0]==429
job_id=account['jobs'][0]['id']
assert call(f'/api/jobs/{job_id}/download',signed=False)[0]==401
assert call(f'/api/jobs/{job_id}/download')[0]==404
assert call('/api/account',signed=False)[1]=={'signedIn':False}
print('PASS: authentication, CSRF, validation, worker auth, concurrent idempotency, exact quota 10, download gates, anonymous privacy')
