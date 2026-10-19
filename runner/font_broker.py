"""Task-scoped font download broker shared by API and local Codex authors."""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from font_assets import install,publish,manifest,copy_fonts
from progress import read_scoped
from web_media import download
from trajectory import record

class FontBroker:
    def __init__(self,job,trajectory=None):
        self.job=Path(job);self.trajectory=trajectory;self.pool=ThreadPoolExecutor(max_workers=1)
        self.pending={};self.processed=set()

    def fetch(self,data):
        try:
            descriptor=None
            cache=Path(__file__).parent/'font-cache.local'
            if not data.get('url') and (cache/'fonts/index.json').is_file():
                found=next((x for x in manifest(cache)['fonts'] if x['id']==data.get('font_id')),None)
                if found:copy_fonts(cache,self.job,[found['id']])
            if data.get('url'):
                if not all(isinstance(data.get(x),str) and data[x] for x in ('url','license_url','family')):raise ValueError('Custom fonts need a direct font URL, real OFL license URL and family')
                descriptor={x:data[x] for x in ('url','license_url','family')}
                weight=data.get('weight',400)
                if type(weight) is not int or not 100<=weight<=900:raise ValueError('Invalid font weight')
                descriptor['weight']=weight
            font=install(self.job,data['font_id'],downloader=download,descriptor=descriptor,text=data.get('text',''))
            return {'ok':True,'font':font,'path':str(self.job/font['file'])}
        except Exception as error:return {'ok':False,'error':str(error)[:300]}

    def poll(self):
        queue=self.job/'font-requests'
        if queue.is_symlink():raise ValueError('Font request queue symlink forbidden')
        if not queue.exists():return
        for ident,future in list(self.pending.items()):
            if not future.done():continue
            result=future.result();del self.pending[ident]
            publish(self.job,'font-requests/'+ident+'.reply.json',json.dumps(result,ensure_ascii=False).encode())
            record(self.trajectory,'emit','font.result',{'request_id':ident,**result})
        if self.pending:return
        for path in sorted(queue.iterdir())[:1000]:
            if not re.fullmatch('[0-9a-f]{32}\\.request\\.json',path.name):continue
            ident=path.name.split('.')[0]
            if ident in self.processed or path.with_name(ident+'.reply.json').exists():continue
            if len(self.processed)>=32:return
            self.processed.add(ident)
            try:
                data=json.loads(read_scoped(self.job,'font-requests/'+path.name,16000))
                if not isinstance(data,dict) or not isinstance(data.get('text',''),str):raise ValueError('Invalid font request')
            except (ValueError,OSError):
                publish(self.job,'font-requests/'+ident+'.reply.json',b'{"ok":false,"error":"Invalid font request"}');continue
            record(self.trajectory,'emit','font.request',{'request_id':ident,'font_id':data.get('font_id')})
            self.pending[ident]=self.pool.submit(self.fetch,data)
            return

    def close(self):
        self.pool.shutdown(wait=False,cancel_futures=True)
