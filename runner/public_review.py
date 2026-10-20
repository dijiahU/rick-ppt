"""A bounded public review receipt; full original reports remain in the archive."""
import json,re

def envelope(receipt,kind,report,revision):
    def text(value,limit):
        value=str(value)
        value=re.sub(r'(?:/Users/|/private/|/tmp/|[A-Z]:\\)[^\s\"\x27<>]*','[local file]',value)
        return value[:limit]
    findings=report['findings']
    public={'summary':text(report['summary'],2000),'pages_reviewed':list(report['pages_reviewed']),
            'findings':[{**{k:text(f[k],100 if k=='id' else 1200) for k in ('id','observation','impact','recommendation')},
                         'pages':list(f['pages']),'severity':f['severity']} for f in sorted(findings,key=lambda f:f['severity']!='required')],
            'limitations':[text(s,1200) for s in report['limitations'][:20]]}
    value={'schema':'rickppt-review/v1','kind':kind,'artifactSha256':receipt['artifact_sha256'],
           'revision':revision,'round':receipt['round'],'requiredCount':sum(f['severity']=='required' for f in findings),
           'suggestionCount':sum(f['severity']=='suggestion' for f in findings),'report':public,
           'truncated':any(any(len(str(f[k]))>(100 if k=='id' else 1200) for k in ('id','observation','impact','recommendation')) for f in findings) or public['limitations']!=report['limitations'] or public['summary']!=report['summary']}
    # AdminTrace's detail limit is 16000 UTF-16 units. Keep complete JSON below
    # that boundary, with counts retained if long reports need an excerpt.
    def size():return len(json.dumps(value,ensure_ascii=False).encode('utf-16-le'))//2
    while size()>15000 and public['findings']:
        public['findings'].pop();value['truncated']=True
    while size()>15000 and public['limitations']:
        public['limitations'].pop();value['truncated']=True
    return value

def publish(trace,receipt,revision):
    for kind,key in [('content-first','content_first_view'),('content-evidence','content'),('visual','visual')]:
        trace.emit('review','Validated review result',detail=envelope(receipt,kind,receipt[key],revision))
    trace.flush(force=True)
