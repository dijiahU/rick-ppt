import json
from pathlib import Path
from unittest.mock import patch

import pytest

from pptx_core.common import PptxError, atomic_json, sha256
from pptx_core.interactive import attach
from review_packet import collect_interactive, scene_inventory


def example(code='print(2 + 2)'):
    return {'schemaVersion':1,'id':'review-example','viewport':{'width':800,'height':450},
            'requires':['core','code'],'initialState':{'x':0,'line':1},
            'nodes':[{'id':'box','type':'Rect','props':{'width':40,'height':40},'bind':{'x':{'expr':'state.x'}}},
                     {'id':'editor','type':'component','component':'CodeEditor','props':{'code':code,'language':'python'}}],
            'interactions':[{'target':'box','event':'click','actions':[
                {'type':'sequence','actions':[{'type':'increment','path':'x'},
                    {'type':'condition','condition':{'expr':'state.x > 0'},
                     'then':[{'type':'plugin','name':'code.run','target':'editor'}],
                     'else':[{'type':'set','path':'x','value':0}]}]}]}],
            'behaviors':[{'type':'drag','target':'box','xPath':'x','axis':'x','bounds':{'minX':0,'maxX':100}}],
            'timelines':[{'id':'scan','duration':1000,'tracks':[{'path':'x','keyframes':[{'time':0,'value':0},{'time':1000,'value':100}]}],
                          'markers':[{'time':500,'actions':[{'type':'emit','event':'middle'}]}]}],
            'dataSources':{'rows':{'type':'inline','value':[{'value':4}]}},
            'runtimeOptions':{'loops':{'again':[{'type':'refreshData','dataSource':'rows'}]}},
            'testPlan':[{'name':'changed','actions':[{'type':'click','target':'box'}],
                         'assertions':[{'type':'state','path':'x','equals':1}]}]}


def attach_example(ws, tmp_path, code='print(2 + 2)'):
    source=tmp_path/'review.scene.json';atomic_json(source,example(code))
    return attach(ws,1,source,fallback=tmp_path/'picture.png')


def test_inventory_describes_event_action_tree_behaviors_time_data_and_packs():
    inventory=scene_inventory(example())
    assert inventory['requires']==['core','code']
    assert inventory['events']==[{'target':'box','event':'click','actionCount':1}]
    assert {item['type'] for item in inventory['actions']}=={'sequence','increment','condition','plugin','set','emit','refreshData'}
    plugin=next(item for item in inventory['actions'] if item['type']=='plugin')
    assert plugin['source'].endswith('/then/0') and plugin['name']=='code.run'
    assert inventory['behaviors'][0]['xPath']=='x'
    assert inventory['timelines'][0]['tracks'][0]['keyframes'][1]['value']==100
    assert inventory['dataSources']['rows']['value']==[{'value':4}]
    assert inventory['nodes'][1]['component']=='CodeEditor'
    assert inventory['counts']['actions']==7
    assert inventory['truncatedFields']==[]


def test_large_inventory_is_explicitly_sampled():
    scene=example();scene['dataSources']['rows']['value']=[{'long':'x'*5000} for _ in range(200)]
    scene['initialState']['nested']={'one':{'two':{'three':{'four':{'five':{'six':{'seven':{'eight':'end'}}}}}}}}
    value=scene_inventory(scene)
    assert 'dataSources' in value['truncatedFields']
    assert len(value['dataSources']['rows']['value'])==100
    assert len(json.dumps(value))<130_000


def test_passive_source_copy_is_exact_and_never_runs_author_code(ws,tmp_path):
    marker=tmp_path/'must-not-exist'
    code=f"__import__('pathlib').Path({str(marker)!r}).write_text('executed')"
    instance=attach_example(ws,tmp_path,code)
    destination=tmp_path/'packet'
    with patch('subprocess.run',side_effect=AssertionError('No scene execution in review collection')):
        inventory=collect_interactive(ws,destination)
    assert not marker.exists()
    assert len(inventory['scenes'])==1 and inventory['instances'][0]['inventoryScene']==0
    record=inventory['scenes'][0];copied=destination/record['sourceFile']
    assert sha256(copied)==instance['specHash']==record['specHash']
    assert json.loads(copied.read_text())['nodes'][1]['props']['code']==code
    assert 'untrusted' in record['evidenceType']


def test_copy_scoped_capture_and_reject_escape_and_stale_receipt(ws,tmp_path):
    instance=attach_example(ws,tmp_path)
    renders=ws.home/'interactive/renders/example';renders.mkdir(parents=True)
    (renders/'initial.png').write_bytes((tmp_path/'picture.png').read_bytes())
    receipt=ws.home/'interactive/tests/review-example.json'
    report={'specHash':instance['specHash'],'directory':str(renders),
            'captures':['initial.png'],'tests':[{'name':'changed','ok':True}]}
    atomic_json(receipt,report)
    destination=tmp_path/'packet'
    inventory=collect_interactive(ws,destination)
    assert (destination/inventory['instances'][0]['captures'][0]).read_bytes()==(renders/'initial.png').read_bytes()
    atomic_json(receipt,{**report,'directory':str(tmp_path)})
    with pytest.raises(PptxError,match='inside the workspace'):collect_interactive(ws,tmp_path/'escape')
    atomic_json(receipt,{**report,'specHash':'f'*64})
    with pytest.raises(PptxError,match='Stale'):collect_interactive(ws,tmp_path/'stale')


def test_scene_tamper_does_not_reach_a_review_packet(ws,tmp_path):
    attach_example(ws,tmp_path)
    source=ws.home/'interactive/deck/scenes/review-example.json'
    source.write_text(source.read_text().replace('print(2 + 2)','print(3 + 3)'))
    with pytest.raises(PptxError,match='invalid interactive'):collect_interactive(ws,tmp_path/'packet')


def test_native_only_packet_keeps_legacy_behavior(ws,tmp_path):
    inventory=collect_interactive(ws,tmp_path/'packet')
    assert inventory['instances']==[] and inventory['scenes']==[] and inventory['ok']
