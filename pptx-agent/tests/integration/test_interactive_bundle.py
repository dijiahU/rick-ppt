"""Real Office-package/browser export and portable lifecycle acceptance tests."""
import asyncio
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
import pytest
from playwright.async_api import async_playwright
from pptx_core.common import PptxError,atomic_json,sha256
from pptx_core.interactive import attach,scene_render
from pptx_core.interactive_bundle import assemble_bundle
from pptx_core.interactive_validate import PLUGIN_ROOT,read_json,validate_interactive
from pptx_core.manifest import manifest,changed_paths
from pptx_core.package import Workspace,unpack,export
from pptx_core.validator import validate


def run_control(bundle,*args,check=True):
    result=subprocess.run([sys.executable,str(bundle/'scripts/bundle_control.py'),*args],capture_output=True,text=True,timeout=40,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    if check and result.returncode:raise AssertionError('Bundle controller failed: '+result.stderr[-1000:])
    return result


@pytest.fixture(scope='module')
def completed_bundle(tmp_path_factory):
    base=tmp_path_factory.mktemp('real-interactive-bundle');source=PLUGIN_ROOT/'skills/pptx/assets/blank.pptx';source_hash=sha256(source)
    ws=unpack(source,base/'authoring');protected_hash=sha256(ws.home/'original.pptx')
    scene=base/'scene.json'
    atomic_json(scene,{'schemaVersion':1,'id':'bundle-example','viewport':{'width':1000,'height':700},'theme':{'background':'#f8fafc','text':'#172033'},'initialState':{'count':0},'nodes':[{'id':'title','type':'Text','props':{'x':50,'y':70,'width':900,'height':60,'fontSize':38,'text':'Verified native + interactive bundle'}},{'id':'increment','type':'Button','props':{'x':50,'y':200,'width':200,'height':55,'text':'Increment'}},{'id':'count','type':'Text','props':{'x':300,'y':200,'width':350,'height':55},'bind':{'text':{'expr':'"Count: " + state.count'}}},{'id':'reset','type':'Button','props':{'x':50,'y':290,'width':200,'height':55,'text':'Reset'}}],'interactions':[{'target':'increment','event':'click','actions':[{'type':'increment','path':'count'}]},{'target':'reset','event':'click','actions':[{'type':'reset'}]}],'testPlan':[{'name':'increment-real-state','actions':[{'type':'click','target':'increment'}],'assertions':[{'type':'state','path':'count','equals':1},{'type':'text','target':'count','contains':'Count: 1'}],'capture':True},{'name':'reset-real-state','reset':False,'actions':[{'type':'click','target':'reset'}],'assertions':[{'type':'state','path':'count','equals':0}],'capture':True}]})
    attached=attach(ws,1,scene)
    assert attached['runtime_verified']
    assert validate(ws.root).ok and validate_interactive(ws.root,require_runtime=True)['ok']
    first=export(ws,base/'before-bundle.pptx')
    assert Path(ws.state['last_render']['pdf']).is_file()
    reopened=unpack(first,base/'reopened')
    assert validate(reopened.root).ok
    shutil.copytree(ws.home/'interactive',reopened.home/'interactive')
    assert not validate_interactive(reopened.root,require_runtime=True)['ok']  # Copied receipts still name the old render directory.
    scene_render(reopened,'bundle-example')
    assert validate_interactive(reopened.root,require_runtime=True)['ok']
    native_before=manifest(ws.root);sidecar_before=manifest(ws.home/'interactive/deck')
    result=assemble_bundle(ws,base/'review bundle v1',zip_output=True);bundle=Path(result['bundle'])
    assert not changed_paths(native_before,manifest(ws.root))
    assert not changed_paths(sidecar_before,manifest(ws.home/'interactive/deck'))
    assert sha256(source)==source_hash and sha256(ws.home/'original.pptx')==protected_hash
    atomic_json(base/'acceptance-evidence.json',{'bundle':str(bundle),'authoring':str(ws.home),'sourceHash':source_hash,'sourceUnchanged':True,'nativeUnchanged':True,'sidecarUnchanged':True,'firstExport':str(first),'reopened':str(reopened.home),'runtimeReport':read_json(ws.home/'interactive/tests/bundle-example.json'),'nativeRender':ws.state['last_render'],'bundleResult':result})
    return {'base':base,'ws':ws,'bundle':bundle,'result':result}


def test_real_native_interactive_bundle_clears_final_baselines_and_reopens(completed_bundle):
    data=completed_bundle;ws=Workspace(data['ws'].home);bundle=data['bundle']
    assert ws.state['latest_output']==str(bundle/'presentation.pptx') and Path(ws.state['latest_output']).is_file()
    assert ws.state['latest_bundle']==str(bundle)
    assert not ws.state['dirty'] and not ws.state['native_dirty'] and not ws.state['interactive_dirty']
    ws.refresh();assert not ws.state['dirty']
    result=json.loads(run_control(bundle,'verify').stdout);assert result['ok'] and result['files']>20
    assert result['pptxHash']==sha256(bundle/'presentation.pptx')
    with zipfile.ZipFile(data['result']['zip']) as archive:
        assert archive.testzip() is None
        assert data['bundle'].name+'/presentation.pptx' in archive.namelist()


def test_existing_destinations_and_zip_are_never_overwritten(completed_bundle):
    data=completed_bundle;before=manifest(data['bundle']);archive=Path(data['result']['zip']);archive_hash=sha256(archive)
    with pytest.raises(PptxError,match='already exists'):assemble_bundle(data['ws'],data['bundle'],True)
    assert not changed_paths(before,manifest(data['bundle'])) and sha256(archive)==archive_hash
    reserved=data['base']/'reserved.zip';reserved.write_bytes(b'keep existing zip')
    with pytest.raises(PptxError,match='ZIP destination'):assemble_bundle(data['ws'],data['base']/'reserved',True)
    assert reserved.read_bytes()==b'keep existing zip' and not (data['base']/'reserved').exists()


@pytest.mark.parametrize('relative',['presentation.pptx','deck/scenes/bundle-example.json','runtime/dist/preview.html'])
def test_corrupt_bundle_fails_before_server_start(completed_bundle,tmp_path,relative):
    copied=tmp_path/'corrupt bundle';shutil.copytree(completed_bundle['bundle'],copied);target=copied/relative
    with target.open('ab') as stream:stream.write(b'corrupted')
    result=run_control(copied,'verify',check=False)
    assert result.returncode!=0 and 'checksum mismatch' in result.stderr
    result=run_control(copied,'start','--http','--port','0',check=False)
    assert result.returncode!=0 and 'checksum mismatch' in result.stderr


def test_portable_start_stop_serves_preview_and_cannot_signal_unrelated_pid(completed_bundle):
    data=completed_bundle;bundle=data['bundle'];env={**os.environ,'PPTX_PYTHON':sys.executable,'PYTHONDONTWRITEBYTECODE':'1'}
    started=subprocess.run([str(bundle/'scripts/start.command'),'--http','--port','0'],capture_output=True,text=True,timeout=40,env=env)
    assert started.returncode==0,started.stderr
    status=json.loads(started.stdout);assert status['running'] and status['url'].startswith('http://127.0.0.1:')
    assert json.loads(run_control(bundle,'start','--http','--port','0').stdout)['pid']==status['pid']
    async def preview():
        async with async_playwright() as p:
            browser=await p.chromium.launch();page=await browser.new_page(viewport={'width':1200,'height':840})
            identity=read_json(bundle/'deck/bundle.json');url=status['url']+'/preview.html?deck='+identity['deckId']+'&scene=bundle-example'
            await page.goto(url);await page.wait_for_function('window.__interactive?.ready === true')
            await page.get_by_role('button',name='Increment',exact=True).click()
            assert await page.evaluate('window.__interactive.runtime.store.get("count")')==1
            await page.screenshot(path=str(data['base']/'served-bundle-after-click.png'))
            response=await page.request.get(status['url']+'/api/health');assert response.status==200
            response=await page.request.get(status['url']+'/source/.runtime/state.json');assert response.status==404
            await browser.close()
    other=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])
    try:
        asyncio.run(preview())
        spec=importlib.util.spec_from_file_location('portable_bundle_control',bundle/'scripts/bundle_control.py');control=importlib.util.module_from_spec(spec);spec.loader.exec_module(control)
        path=control.state_path();saved=json.loads(path.read_text());changed={**saved,'pid':other.pid};control.save(path,changed)
        result=run_control(bundle,'stop',check=False)
        assert result.returncode!=0 and 'identity mismatch' in result.stderr
        assert other.poll() is None
        control.save(path,saved)
        stopped=subprocess.run([str(bundle/'scripts/stop.command')],capture_output=True,text=True,timeout=30,env=env)
        assert stopped.returncode==0,stopped.stderr
        assert json.loads(stopped.stdout)['stopped']
        assert not json.loads(run_control(bundle,'status').stdout)['running']
        assert other.poll() is None
    finally:
        other.terminate();other.wait(timeout=10)
        run_control(bundle,'stop',check=False)


def test_relocation_requires_validated_host_path_rewrite(completed_bundle,tmp_path):
    ws=completed_bundle['ws'];moved=tmp_path/'restored workspace';shutil.copytree(ws.home,moved)
    with pytest.raises(PptxError,match='Invalid workspace state'):Workspace(moved)
    state=read_json(moved/'state.json');assert state['workspace']==str(ws.root)
    assert Path(state['latest_output']).is_absolute() and Path(state['source']).is_absolute()


def test_stop_finalizes_dirty_interactive_workspace_outside_its_home(completed_bundle,tmp_path):
    from pptx_core.hooks import stop
    source=PLUGIN_ROOT/'skills/pptx/assets/blank.pptx';before=sha256(source)
    ws=unpack(source,tmp_path/'authoring')
    attach(ws,1,completed_bundle['base']/'scene.json')
    assert ws.state['dirty']
    result=stop(ws,{'stop_hook_active':False})
    assert 'decision' not in result,result
    message=result['systemMessage']
    assert 'runtime_verified: true' in message and 'desktop_verified: false' in message
    reopened=Workspace(ws.home);bundle=Path(reopened.state['latest_bundle'])
    assert not bundle.is_relative_to(ws.home)
    assert Path(reopened.state['latest_output']).is_file()
    assert str(bundle/'presentation.pptx') in message
    assert json.loads(run_control(bundle,'verify').stdout)['ok']
    assert not reopened.state['dirty'] and sha256(source)==before


@pytest.mark.parametrize('damage',['runtime','capture-hash','assertions','capture-bytes','missing-capture'])
def test_local_receipt_rejects_stale_or_incomplete_evidence(completed_bundle,damage):
    ws=completed_bundle['ws'];path=ws.home/'interactive/tests/bundle-example.json'
    original=path.read_bytes();report=read_json(path)
    capture=Path(report['directory'])/'initial.png';before=capture.read_bytes()
    try:
        if damage=='runtime':report['runtime']['sha256']='0'*64
        elif damage=='capture-hash':report['captureHashes']['initial.png']='0'*64
        elif damage=='assertions':report['tests'][0]['assertions']=0
        elif damage=='capture-bytes':capture.write_bytes(b'changed image')
        elif damage=='missing-capture':report['directory']=str(ws.home/'interactive/renders/missing')
        atomic_json(path,report)
        assert not validate_interactive(ws.root,require_runtime=True)['ok']
    finally:
        path.write_bytes(original);capture.write_bytes(before)
    assert validate_interactive(ws.root,require_runtime=True)['ok']
