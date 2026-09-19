"""Read-only/invalid submissions against the already exhausted local fixture account."""
import http.cookiejar
import json
import urllib.request
import urllib.error
import uuid
BASE='http://localhost:3000'
jar=http.cookiejar.CookieJar()
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(jar))
opener.open(BASE+'/signin-with-chatgpt?return_to=/api/account').read()
before=json.loads(opener.open(BASE+'/api/account').read())
assert before['remaining']==0,'This test requires the exhausted local fixture account; no submissions otherwise.'
assert all(j['title']=='本地额度测试' for j in before['jobs']),'Refuse non-fixture account'
assert all('language' in j for j in before['jobs'])
def submit(language,ui='en',signed=True):
    data={'title':'Local language test','brief':'This must not run as a real task.','pages':5,'style':'Designer choice','requestKey':str(uuid.uuid4()),'language':language}
    headers={'Content-Type':'application/json','Origin':BASE,'X-UI-Language':ui}
    request=urllib.request.Request(BASE+'/api/jobs',data=json.dumps(data).encode(),headers=headers)
    client=opener if signed else urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:r=client.open(request)
    except urllib.error.HTTPError as e:r=e
    return r.status,json.loads(r.read())
for code in ['en','fr','es','zh-CN','ja']:
    status,result=submit(code,code)
    assert status==429 and result['code']=='quota',(status,result)
for invalid in [None,'xx',1,[],{}]:
    status,result=submit(invalid,'fr')
    assert status==400 and result['code']=='invalid' and 'Envoi invalide' in result['error']
assert submit('fr','fr',False)[0]==401
after=json.loads(opener.open(BASE+'/api/account').read())
assert len(before['jobs'])==len(after['jobs']) and after['remaining']==0
print('PASS: five accepted language codes, localized API errors, invalid language rejection, authentication, private history language and zero new jobs')
