"""Real task-scoped DSH material sessions; never imports a Codex image cache."""
import hashlib,json,tempfile,time,uuid
from pathlib import Path


def install(runtime):
    import assets,auxiliary_tools,material_prefetch
    from dsh_adapter import DshServer
    from trajectory import record
    from progress import read_scoped
    original=assets.AssetImporter
    class LocalAssetImporter(original):
        def __init__(self,job,generated_root=None,trajectory=None):
            super().__init__(job,generated_root=generated_root or Path(job)/'assets/generated',trajectory=trajectory)
    runtime.workflow.AssetImporter=LocalAssetImporter
    material_prefetch.AssetImporter=LocalAssetImporter
    base=auxiliary_tools.AuxiliaryTools
    class DshMaterials(base):
        def execute(self,tool,request,references,files):
            started=time.monotonic();ident=uuid.uuid4().hex
            record(self.trajectory,'emit','auxiliary.request',{'id':ident,'tool':tool,'request':request,'harness':'dsh'})
            with tempfile.TemporaryDirectory(prefix='pptx-dsh-material-') as tmp:
                root=Path(tmp).resolve();(root/'tmp').mkdir();(root/'assets').mkdir()
                for name,body in files:(root/'assets'/name).write_bytes(body)
                prompt=('Perform only this bounded material request using actual configured DSH tools. '
                        'Do not author a PPT, read private files, install tools or fabricate evidence. '
                        'Return concise inspected findings with source URLs and limitations. ')
                if tool=='pptx_generate_image':
                    prompt+=('Use a registered image-generation tool. Save actual generated PNG output under assets/. '
                             'Do not substitute a Python/SVG drawing or copy a reference as newly generated. '
                             'If no image-generation provider is configured, explicitly report unavailable. '
                             'Input references: '+json.dumps([str(root/'assets'/name) for name,_ in files])+'. ')
                prompt+='Request:\n'+request
                events=[]
                def event(value):
                    events.append(value)
                    record(self.trajectory,'emit','auxiliary.event',{'request_id':ident,'event':value,'harness':'dsh'})
                meter=self.cfg.get('_usage_ledger')
                usage_options={'on_usage':meter.codex_sink(self.cfg.get('_usage_stage','auxiliary')+'.'+tool,DshServer.options['model'])} if meter else {}
                with DshServer(cwd=root,config={},tick=self.tick,on_event=event,**usage_options) as server:
                    thread=server.start_thread()['thread']['id'];turn=server.start_turn(thread,prompt)['id']
                    receipt=server.wait_turn(thread,turn,timeout=300 if tool=='pptx_generate_image' else 180)
                    if receipt['status']!='completed':return self.reply(False,'DSH material operation did not complete')
                    text=server.result_text(thread,turn);usage=server.usage.get((thread,turn))
                used={v['item'].get('tool','') for v in events if v.get('type')=='item.completed' and v.get('item')}
                self.calls.append({'tool':tool,'harness':'dsh','model':DshServer.options['model'],
                                   'seconds':time.monotonic()-started,'usage':usage,'actual_tools':sorted(used)})
                output={'tool':tool,'text':text[:32000],'model':DshServer.options['model'],'files':[]}
                if tool=='pptx_generate_image':
                    accepted=set(DshServer.options.get('generation_tool_names',('generate_image','image_generation','imagegen','image_generate')))
                    if not used&accepted:return self.reply(False,'No registered image-generation tool execution was observed; configure DSH generation_tool_names/provider')
                    before={hashlib.sha256(body).hexdigest() for _,body in files}
                    importer=self.importer or LocalAssetImporter(self.job)
                    for path in sorted((root/'assets').glob('*.png')):
                        if len(output['files'])>=12:break
                        data=read_scoped(root,path.relative_to(root),20*1024*1024)
                        digest=hashlib.sha256(data).hexdigest()
                        if digest in before or not original.valid_png(data):continue
                        key='exec-'+str(uuid.uuid4())+'.png';name='generated-'+key
                        descriptor={'file':name,'sha256':digest,'source':'configured DSH image generation'}
                        importer._publish(name,data,{**importer.imported,key:descriptor});importer.imported[key]=descriptor
                        output['files'].append(descriptor)
                    if not output['files']:return self.reply(False,'DSH returned no actual new task-local generated PNG')
                folder=self.job/'retained-tool-evidence';folder.mkdir(exist_ok=True)
                from portable_transport import _write
                _write(folder/(ident+'.json'),output)
                record(self.trajectory,'emit','auxiliary.result',{'request_id':ident,**output,'harness':'dsh'})
                return self.reply(True,json.dumps(output,ensure_ascii=False))
    auxiliary_tools.AuxiliaryTools=DshMaterials
    material_prefetch.AuxiliaryTools=DshMaterials
