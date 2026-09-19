import asyncio
import json
import zipfile
from pathlib import Path
import pytest
from aiohttp import ClientSession
from lxml import etree
from pptx_core.common import PptxError, atomic_json, parse, sha256
from pptx_core.interactive import attach, import_scene
from pptx_core.interactive_ooxml import (WE, MC, WEBCT, WEBREL, attach_content_addin,
    discover_content_addins, clone_content_addin, resize_content_addin, remove_content_addin,
    update_content_addin, validate_ooxml)
from pptx_core.interactive_validate import validate_spec, validate_interactive, safe_path, read_json
from pptx_core.interactive_server import start_server
from pptx_core.manifest import manifest, changed_paths
from pptx_core.package import Workspace, unpack, pack
from pptx_core.relationships import relationships
from pptx_core.snapshots import snapshot, rollback
from pptx_core.validator import validate


def scene(tmp_path):
    path=tmp_path/'scene.json'
    atomic_json(path,{'schemaVersion':1,'id':'example','viewport':{'width':800,'height':450},
        'initialState':{'count':0},'nodes':[{'id':'title','type':'Text','props':{'text':'Hello'}}],
        'testPlan':[{'name':'initial','actions':[], 'assertions':[{'type':'state','path':'count','equals':0}]}]})
    return path


def region(ws,tmp_path):
    return attach(ws,1,scene(tmp_path),fallback=tmp_path/'picture.png')


def test_managed_graph_and_unrelated_bytes(ws,tmp_path):
    before=manifest(ws.root);i=region(ws,tmp_path)
    assert validate(ws.root).ok
    assert validate_interactive(ws.root)['ok']
    assert not validate_interactive(ws.root,require_runtime=True)['ok']
    assert i['nativeFallback'] and i['managed']
    changed=changed_paths(before,manifest(ws.root))
    assert set(changed) & before.keys() == {'ppt/slides/slide1.xml','ppt/slides/_rels/slide1.xml.rels','[Content_Types].xml'}
    assert next(r for r in relationships(ws.root,i['part']) if r['id']==i['relationship'])['type']==WEBREL
    golden=Path(__file__).parents[1]/'fixtures/office/PowerPointPresentationWithContent.pptx'
    with zipfile.ZipFile(golden) as z:
        web=etree.fromstring(z.read('ppt/slides/udata/data.xml'))
        ours=parse(ws.root/i['webextension'])
        assert web.tag==ours.tag
        assert [n.tag for n in web]==[n.tag for n in ours]
        assert web.find(f'{{{WE}}}reference').get('storeType')==ours.find(f'{{{WE}}}reference').get('storeType')
        slide=etree.fromstring(z.read('ppt/slides/slide.xml'))
        assert slide.find(f'.//{{{MC}}}Choice').get('Requires')==parse(ws.root/i['part']).find(f'.//{{{MC}}}Choice').get('Requires')


def test_clone_resize_detach_and_update_own_parts(ws,tmp_path):
    i=region(ws,tmp_path);cloned=clone_content_addin(ws.root,i['instanceId'],2)
    assert i['instanceId']!=cloned['instanceId'] and i['webextension']!=cloned['webextension']
    bounds={'x':100,'y':100,'width':1000000,'height':1000000}
    assert resize_content_addin(ws.root,cloned['instanceId'],bounds)['bounds']==bounds
    update_content_addin(ws.root,cloned['instanceId'],{'specHash':'a'*64})
    assert discover_content_addins(ws.root)[0]['specHash']==i['specHash']
    assert not validate_interactive(ws.root)['ok']
    remove_content_addin(ws.root,cloned['instanceId'])
    assert len(discover_content_addins(ws.root))==1
    assert (ws.root/cloned['snapshot']).exists()
    assert validate(ws.root).ok


@pytest.mark.parametrize('damage',['app','snapshot','fallback','hash','identity','type'])
def test_graph_corruption_rejected(ws,tmp_path,damage):
    i=region(ws,tmp_path);path=ws.root/i['webextension'];web=parse(path)
    if damage=='app':web.find(f'{{{WE}}}reference').set('id','wrong')
    if damage=='snapshot':web.find(f'{{{WE}}}snapshot').set('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed','absent')
    if damage=='hash':web.find(f'{{{WE}}}properties/{{{WE}}}property[@name="specHash"]').set('value','"bad"')
    if damage=='identity':web.set('id','{00000000-0000-0000-0000-000000000000}')
    path.write_bytes(etree.tostring(web))
    if damage=='fallback':
        path=ws.root/i['part'];tree=parse(path);node=tree.find(f'.//{{{MC}}}Fallback');node.getparent().remove(node);path.write_bytes(etree.tostring(tree))
    if damage=='type':
        path=ws.root/'[Content_Types].xml';path.write_text(path.read_text().replace(WEBCT,'wrong/type'))
    assert not validate(ws.root).ok


def test_sidecar_snapshot_migration_and_stale_receipt(ws,tmp_path):
    ws.state['version']=1;ws.save();ws=Workspace(ws.home);assert ws.state['version']==2
    i=region(ws,tmp_path);ident=snapshot(ws)
    spec=ws.home/'interactive/deck/scenes/example.json';spec.write_text(spec.read_text().replace('Hello','Changed'))
    ws.refresh();assert ws.state['native_dirty'] and ws.state['interactive_dirty']
    assert not validate_interactive(ws.root)['ok']
    result=rollback(ws,ident);assert validate_interactive(ws.root)['ok']
    assert 'Changed' in (ws.home/'snapshots'/result['recovery_snapshot']/'interactive/deck/scenes/example.json').read_text()
    assert list(ws.home.glob('.replaced-interactive-*'))
    atomic_json(ws.home/'interactive/tests/example.json',{'ok':True,'testCount':1,'specHash':i['specHash']})
    assert validate_interactive(ws.root,require_runtime=True)['ok']
    spec.write_text(spec.read_text().replace('Hello','Changed'))
    assert not validate_interactive(ws.root,require_runtime=True)['ok']


def test_hooks_detect_scene_only_writes_and_bound_stop_retries(ws,tmp_path):
    from pptx_core.hooks import pre,post,stop
    region(ws,tmp_path)
    ws.state.update(baseline=manifest(ws.root),interactive_baseline=ws.sidecar_manifest());ws.save();ws.refresh()
    assert not ws.state['dirty']
    path=ws.home/'interactive/deck/scenes/example.json'
    event={'cwd':str(ws.home),'tool_name':'apply_patch','tool_input':{'path':str(path)},'tool_use_id':'scene-test'}
    before=len(list((ws.home/'snapshots').iterdir()))
    assert pre(ws,event) is None
    assert len(list((ws.home/'snapshots').iterdir()))==before+1
    path.write_text(path.read_text().replace('Hello','Changed'))
    assert post(ws,event)['decision']=='block'
    assert ws.state['interactive_dirty'] and not ws.state['native_dirty']
    for index in range(3):
        result=stop(ws,{'stop_hook_active':index>0})
        assert ('systemMessage' in result) if index==2 else result['decision']=='block'
    assert ws.state['latest_output'] is None and ws.state['stop_failures']==3


def test_snapshot_corruption_never_replaces_workspace(ws):
    ident=snapshot(ws);(ws.home/'snapshots'/ident/'workspace/bad').write_text('corruption')
    before=manifest(ws.root)
    with pytest.raises(PptxError,match='hashes'):rollback(ws,ident)
    assert not changed_paths(before,manifest(ws.root))


@pytest.mark.parametrize('name',['../secret','/etc/passwd','a%2fb','a\\b','a/./b','a//b'])
def test_sidecar_traversal(tmp_path,name):
    with pytest.raises(PptxError):safe_path(tmp_path,name,False)


def test_sidecar_duplicate_keys_symlinks_and_bad_network(tmp_path):
    p=tmp_path/'dup.json';p.write_text('{"a":1,"a":2}')
    with pytest.raises(PptxError):read_json(p)
    p=scene(tmp_path);value=read_json(p);value['assets']={'remote':{'path':'https://evil.test/image.png'}}
    with pytest.raises(PptxError,match='network'):validate_spec(value,tmp_path)
    (tmp_path/'link').symlink_to(p)
    with pytest.raises(PptxError):safe_path(tmp_path,'link')


def test_runtime_server_origin_path_csp_and_websocket(tmp_path):
    async def run():
        root=tmp_path/'root';root.mkdir();runtime=tmp_path/'dist';runtime.mkdir()
        (runtime/'preview.html').write_text('<p>safe</p>');(runtime/'link').symlink_to('/etc/passwd')
        atomic_json(root/'bundle.json',{'deckId':'deck-test','scenes':{}})
        runner,origin=await start_server(root,runtime)
        try:
            async with ClientSession() as client:
                async with client.get(origin+'/preview.html') as response:
                    assert response.status==200
                    assert "'unsafe-eval'" not in response.headers['Content-Security-Policy']
                for path in ['/link','/source/../outside','/%2e%2e/etc/passwd']:
                    async with client.get(origin+path) as response:assert response.status==404
                async with client.get(origin+'/api/health',headers={'Host':'evil.test'}) as response:assert response.status==403
                async with client.get(origin+'/api/session/deck-test',headers={'Origin':'https://evil.test'}) as response:assert response.status==403
                async with client.get(origin+'/api/session/deck-test') as response:nonce=(await response.json())['nonce']
                async with client.ws_connect(origin+'/api/ws/deck-test?nonce='+nonce) as socket:
                    await socket.send_json({'type':'ping'});assert (await socket.receive_json())['type']=='pong'
        finally:await runner.cleanup()
    asyncio.run(run())
