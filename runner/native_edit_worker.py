"""Small deterministic editor queue alongside the model queue; one render at a time."""
import hashlib,json,posixpath,sys,tempfile,threading,time,uuid
from pathlib import Path
from canvas_snapshot import native_pages
from native_editor import apply
from user_pages import graft,fingerprint

def execute_once(cfg,edit,send):
    base=f'/api/worker/native-edits?id={edit["id"]}'
    def api(action,body=b'{}',raw=False,query=''):return send(cfg,base+'&action='+action+query,body,edit['lease'],raw=raw)
    source=api('source',raw=True)
    if hashlib.sha256(source).hexdigest()!=edit['baseSha256']:raise ValueError('Direct edit source checksum differs')
    pictures={p['image']['id']:api('picture',raw=True,query='&picture='+p['image']['id']) for p in edit['patches'] if 'image' in p}
    result,affected=apply(source,edit['patches'],pictures)
    manifest=api('base-manifest')
    parent=manifest['snapshot']['sha256']
    if edit.get('progressive'):
        latest=api('rebase-source',raw=True,query='&parent='+parent)
        if hashlib.sha256(latest).hexdigest()!=parent:raise ValueError('Growing source checksum differs')
        result=graft(latest,[{'artifact':result,'pages':affected}])
    sha=hashlib.sha256(result).hexdigest()
    # The shared native renderer uses a dedicated LibreOffice profile per render.
    scripts=str(Path(cfg['plugin'])/'skills/pptx/scripts')
    if scripts not in sys.path:sys.path.append(scripts)
    from pptx_core.renderer import executables,font_environment,run
    with tempfile.TemporaryDirectory(prefix='rickppt-direct-save-') as t:
        root=Path(t);artifact=root/'edited.pptx';artifact.write_bytes(result);office,ppm=executables()
        run([office,f'-env:UserInstallation={(root/"profile").as_uri()}','--headless','--convert-to','pdf:impress_pdf_Export:{"ExportHiddenSlides":{"type":"boolean","value":"true"}}','--outdir',str(root),str(artifact)],90,env=font_environment(root,office))
        pdf=root/'edited.pdf'
        if not pdf.is_file() or pdf.stat().st_size<100:raise ValueError('Native editor produced no render')
        rendered={}
        for n in affected:
            run([ppm,'-png','-r','100','-f',str(n),'-l',str(n),str(pdf),str(root/'page')],45)
            paths=list(root.glob('page-*.png'))
            if len(paths)!=1:raise ValueError('Unexpected direct edit preview')
            data=paths[0].read_bytes();paths[0].unlink()
            if len(data)>2*1024*1024:raise ValueError('Direct edit preview exceeds limit')
            rendered[n]=api('page',data,query='&page='+str(n))['sha256']
        uploaded=api('artifact',result)
        if uploaded.get('sha256')!=sha:raise ValueError('Edited artifact upload differs')
        pages=native_pages(result)
        # The server copies untouched page PNGs from the frozen source snapshot.
        for page in pages:page['imageSha256']=rendered.get(page['number']) or manifest['snapshot']['pages'][page['number']-1]['imageSha256']
        if edit.get('progressive'):
            for page in pages:page['contentSha256']=fingerprint(result,page['number'])
        snapshot={'schema':'rickppt-canvas/v1','sha256':sha,'versionId':str(uuid.uuid5(uuid.NAMESPACE_URL,'rickppt-canvas:'+sha)),'createdAt':int(time.time()*1000),'pages':pages}
        if edit.get('progressive'):snapshot['readyPages']=sorted(set(manifest['snapshot'].get('readyPages',range(1,len(pages)+1)))|set(affected))
        return api('finish',json.dumps(snapshot,separators=(',',':'),ensure_ascii=False).encode(),query='&parent='+parent if edit.get('progressive') else '')

def execute(cfg,edit,send):
    from resilience import WorkerHTTPError
    for attempt in range(3):
        try:return execute_once(cfg,edit,send)
        except WorkerHTTPError as error:
            if not edit.get('progressive') or error.status!=409 or attempt==2:raise


def start(cfg,send,stop,log=print):
    def loop():
        unavailable=False
        while not stop.is_set():
            edit=None
            try:
                edit=send(cfg,'/api/worker/native-edits?action=claim').get('edit')
                if edit:
                    execute(cfg,edit,send);log('Native save complete:',edit['jobId'],edit['id'],flush=True)
                unavailable=False
            except Exception as error:
                if edit:
                    try:send(cfg,f'/api/worker/native-edits?id={edit["id"]}&action=fail',b'{}',edit['lease'])
                    except Exception:pass
                if not unavailable:log('Native editor queue:',type(error).__name__,flush=True)
                unavailable=True
            stop.wait(3 if not unavailable else 15)
    thread=threading.Thread(target=loop,name='pptx-native-editor',daemon=True);thread.start();return thread
