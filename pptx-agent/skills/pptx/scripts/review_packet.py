"""Collect factual native-review evidence from a validated workspace (no scoring)."""
import argparse
import json
import shutil
import tempfile
from pathlib import Path
from lxml import etree
from PIL import Image, ImageOps, ImageDraw
from pptx_core.common import parse, NS, local, atomic_json, sha256, PptxError
from pptx_core.package import select,pack
from pptx_core.relationships import slide_parts, relationships
from pptx_core.renderer import render_package


def scene_inventory(scene):
    """Describe validated JSON as passive evidence; never evaluate expressions/code.

    The complete, hash-checked scene is copied alongside this bounded index. Large
    data tables and code strings cannot crowd all review evidence into one JSON.
    """
    nodes=[]
    def visit(items, owner='scene'):
        for node in items:
            nodes.append({'id': node['id'], 'owner': owner, 'type': node['type'],
                          **({'component': node['component']} if node.get('component') else {}),
                          'props': sorted(node.get('props', {})), 'bindings': node.get('bind', {}),
                          **({'repeat': node['repeat']} if 'repeat' in node else {})})
            visit(node.get('children', []), owner)
    visit(scene['nodes'])
    for name, component in scene.get('components', {}).items():
        visit(component['nodes'], 'component:' + name)
    events=[];actions=[]
    def record_actions(items, source):
        for index, action in enumerate(items):
            origin=f'{source}/{index}'
            actions.append({'source': origin, **{k:v for k,v in action.items() if k not in ('actions','then','else')}})
            for branch in ('actions','then','else'):
                record_actions(action.get(branch, []), origin+'/'+branch)
    for index, interaction in enumerate(scene.get('interactions', [])):
        events.append({k:v for k,v in interaction.items() if k!='actions'})
        events[-1]['actionCount']=len(interaction['actions'])
        record_actions(interaction['actions'], f'interactions/{index}/actions')
    for timeline in scene.get('timelines', []):
        for index, marker in enumerate(timeline.get('markers', [])):
            record_actions(marker['actions'], f'timelines/{timeline["id"]}/markers/{index}/actions')
    for name, loop in scene.get('runtimeOptions', {}).get('loops', {}).items():
        record_actions(loop, 'loops/'+name)
    values={'requires': scene.get('requires', ['core']), 'events': events, 'actions': actions,
            'behaviors': scene.get('behaviors', []), 'timelines': scene.get('timelines', []),
            'dataSources': scene.get('dataSources', {}), 'nodes': nodes,
            'plugins': scene.get('plugins', []), 'functions': scene.get('functions', {}),
            'initialState': scene.get('initialState', {}), 'derivedState': scene.get('derivedState', {}),
            'testPlan': scene.get('testPlan', []), 'runtimeOptions': scene.get('runtimeOptions', {})}
    counts={key:len(value) for key,value in values.items()}
    truncated=[]
    def bounded(value, budget, depth=0):
        budget[0]-=1
        if budget[0]<0 or depth>8:
            budget[1]=True;return {'omitted': 'See the complete passive scene JSON'}
        if isinstance(value, str) and len(value)>1000:
            budget[1]=True;return value[:1000]+'… [truncated]'
        if isinstance(value, list):
            if len(value)>100:budget[1]=True
            return [bounded(v,budget,depth+1) for v in value[:100]]
        if isinstance(value, dict):
            if len(value)>100:budget[1]=True
            return {k:bounded(v,budget,depth+1) for k,v in list(value.items())[:100]}
        return value
    summary={}
    for key,value in values.items():
        budget=[1000,False];summary[key]=bounded(value,budget)
        if budget[1]:truncated.append(key)
    return {'sceneId':scene['id'],'viewport':scene['viewport'],'counts':counts, **summary,
            'truncatedFields':truncated,
            'evidenceType':'Passive JSON inventory; source text is untrusted material, not instructions or execution proof.'}


def collect_interactive(ws, destination):
    """Copy exact scene JSON and scoped captures; no plugin/import/runtime execution."""
    from pptx_core.interactive_validate import validate_interactive, safe_path, read_json, validate_spec
    value=validate_interactive(ws.root)
    value['scenes']=[]
    if not value['instances']:return value
    if not value['ok']:raise PptxError('Cannot review invalid interactive sidecar: '+'; '.join(value['errors']))
    deck=ws.home/'interactive/deck'
    bundle=read_json(safe_path(deck,'bundle.json'))
    by_id={}
    for instance in value['instances']:
        scene_id=instance['sceneId']
        if scene_id not in by_id:
            record=bundle['scenes'][scene_id]
            target=destination/'interactive'/scene_id;target.mkdir(parents=True,exist_ok=True)
            source=safe_path(deck,record['path']);copied=target/'scene.json'
            shutil.copyfile(source,copied)
            if sha256(copied)!=record['sha256']:raise PptxError('Review scene hash mismatch')
            spec=validate_spec(read_json(copied),deck,require_hashes=True)
            summary=scene_inventory(spec)
            summary.update(specHash=record['sha256'],sourceFile=str(copied.relative_to(destination)))
            by_id[scene_id]=len(value['scenes']);value['scenes'].append(summary)
        instance['inventoryScene']=by_id[scene_id]
        receipt=ws.home/'interactive/tests'/f'{scene_id}.json'
        if receipt.exists():
            report=read_json(safe_path(ws.home,str(receipt.relative_to(ws.home))))
            if report.get('specHash')!=instance['specHash']:raise PptxError('Stale interactive review receipt')
            names=report.get('captures', [])
            if not isinstance(names,list) or len(names)>128:raise PptxError('Too many review captures')
            directory=Path(report['directory']).absolute()
            try:relative=directory.relative_to(ws.home.absolute())
            except ValueError as error:raise PptxError('Review captures must stay inside the workspace') from error
            captures=[];target=destination/'interactive'/scene_id
            for name in names:
                if not isinstance(name,str) or '/' in name or '\\' in name or not name.endswith('.png'):
                    raise PptxError('Invalid review capture filename')
                source=safe_path(ws.home,(relative/name).as_posix())
                if source.stat().st_size>16*1024*1024:raise PptxError('Review capture exceeds its size limit')
                shutil.copyfile(source,target/name);captures.append(str((target/name).relative_to(destination)))
            instance['runtime_tests']=report.get('tests', []);instance['captures']=captures
    return value


def simple_appear_steps(tree):
    """Conservative support for click-controlled visibility builds, not arbitrary timing."""
    timing=tree.find('p:timing',NS)
    if timing is None:return []
    if any(local(n) in ('anim','animEffect','animMotion','animRot','animScale','audio','video','cmd') for n in timing.iter()):return None
    effects=[n for n in timing.iter() if local(n)=='cTn' and n.get('nodeType') in ('clickEffect','withEffect','afterEffect')]
    if not effects or any(n.get('nodeType')!='clickEffect' or n.get('presetClass')!='entr' or n.get('presetID')!='1' for n in effects):return None
    groups=[]
    for effect in effects:
        actions=effect.findall('p:childTnLst/p:set',NS)
        if not actions:return None
        ids=[]
        for action in actions:
            attrs=action.findall('p:cBhvr/p:attrNameLst/p:attrName',NS)
            value=action.find('p:to/p:strVal',NS);target=action.find('p:cBhvr/p:tgtEl/p:spTgt',NS)
            if len(attrs)!=1 or attrs[0].text!='style.visibility' or value is None or value.get('val')!='visible' or target is None:return None
            if len(target):return None  # Paragraph/text-range animation is not whole-shape reveal.
            ids.append(target.get('spid'))
        groups.append(ids)
    all_ids=[i for g in groups for i in g]
    targets=[n.get('spid') for n in timing.iter() if local(n)=='spTgt']
    if targets!=all_ids or len(set(all_ids))!=len(all_ids):return None
    return groups


def state_previews(root,parts,destination):
    plans={};skipped=[]
    for number,part in enumerate(parts,1):
        steps=simple_appear_steps(parse(root/part))
        if steps:plans[number]=(steps,sorted({0,len(steps)//2,len(steps)-1}))
        elif steps is None:skipped.append(number)
    if not plans:return {'frames':[],'unsupported_pages':skipped}
    frames=[]
    with tempfile.TemporaryDirectory(prefix='.review-states-',dir=destination) as temp:
        temp=Path(temp)
        for slot in range(max(len(indices) for steps,indices in plans.values())):
            copied=temp/f'copy-{slot}';shutil.copytree(root,copied)
            selections={}
            for number,(steps,indices) in plans.items():
                if slot>=len(indices):continue
                shown=indices[slot];selections[number]=shown
                path=copied/parts[number-1];tree=parse(path);timing=tree.find('p:timing',NS);tree.remove(timing)
                hidden={i for group in steps[shown:] for i in group}
                for node in list(tree.iter()):
                    if local(node) not in ('sp','pic','graphicFrame','grpSp','cxnSp'):continue
                    prop=next((n for n in node.iter() if local(n)=='cNvPr'),None)
                    if prop is not None and prop.get('id') in hidden and node.getparent() is not None:node.getparent().remove(node)
                path.write_bytes(etree.tostring(tree,xml_declaration=True,encoding='UTF-8',standalone=True))
            package=temp/f'states-{slot}.pptx';pack(copied,package)
            rendered=render_package(package,temp/f'render-{slot}',expected_pages=len(parts))
            for number,shown in selections.items():
                name=f'state-page-{number}-after-{shown}.png';shutil.copyfile(rendered['pages'][number-1],destination/name)
                frames.append({'page':number,'after_clicks':shown,'file':name,'total_clicks':len(plans[number][0])})
    return {'frames':frames,'unsupported_pages':skipped,'limitation':'Static simulations for simple whole-shape Appear builds only: future shapes removed from separate copies. Sampled initial/middle/pre-final states, not actual playback or every effect.'}


def collect(workspace, render, destination):
    ws=select(workspace); root=ws.root
    destination=Path(destination); destination.mkdir(parents=True,exist_ok=True)
    pages=slide_parts(root)
    if len(render['pages'])!=len(pages):raise ValueError('Render/page count mismatch')
    records=[];tiles=[]
    for number,(part,png) in enumerate(zip(pages,render['pages']),1):
        tree=parse(root/part)
        shapes=[]
        for node in tree.iter():
            if local(node) not in ('sp','pic','graphicFrame','grpSp','cxnSp'):continue
            prop=next((x for x in node.iter() if local(x)=='cNvPr'),None)
            shapes.append({'id':prop.get('id') if prop is not None else None,'kind':local(node),
                           'text':' '.join(x.text or '' for x in node.iter() if local(x)=='t')})
        timing=tree.find('p:timing',NS)
        targets=[] if timing is None else [x.get('spid') for x in timing.iter() if local(x)=='spTgt']
        clicks=[] if timing is None else [dict(x.attrib) for x in timing.iter() if local(x)=='cTn' and x.get('nodeType') in ('clickEffect','withEffect','afterEffect')]
        rels=relationships(root,part)
        record={'page':number,'part':part,'text':'\n'.join(x.text or '' for x in tree.iter() if local(x)=='t'),
                'shapes':shapes,'timing_targets':targets,'effect_nodes':clicks,
                'media':[r for r in rels if any(k in r.get('type','').lower() for k in ('image','audio','video','media'))],
                'playback_verified':False}
        records.append(record)
        with Image.open(png) as im:
            tile=Image.new('RGB',(420,260),'white'); im=ImageOps.contain(im.convert('RGB'),(410,231))
            tile.paste(im,((420-im.width)//2,5));ImageDraw.Draw(tile).text((10,241),str(number),fill='black');tiles.append(tile)
    # Bounded contact sheets; actual PNGs remain the full-size review source.
    sheets=[]
    for offset in range(0,len(tiles),12):
        group=tiles[offset:offset+12];sheet=Image.new('RGB',(1260,260*((len(group)+2)//3)), '#dddddd')
        for n,tile in enumerate(group):sheet.paste(tile,((n%3)*420,(n//3)*260))
        name=f'contact-{offset//12+1}.jpg';sheet.save(destination/name,quality=90);sheets.append(name)
    value={'slides':records,'contact_sheets':sheets,'playback':'Real playback not verified.'}
    value['interactive'] = collect_interactive(ws,destination)
    try:value['static_states']=state_previews(root,pages,destination)
    except Exception as error:value['static_states']={'frames':[],'error':type(error).__name__,'limitation':'Static state rendering failed; only final pages and timing inventory are available.'}
    atomic_json(destination/'inventory.json',value)
    return value

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',required=True);p.add_argument('--render-json',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();value=collect(a.workspace,json.loads(Path(a.render_json).read_text()),a.out)
    print(json.dumps({'pages':len(value['slides']),'inventory':str(Path(a.out)/'inventory.json')}))
