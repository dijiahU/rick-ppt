"""Add simple native click-controlled entrance groups to a selected slide.

Does not replace existing timing unless explicitly requested. Static validation is
not a PowerPoint playback certification.
"""
import argparse
import json
from lxml import etree
from pptx_core.common import P,NS,parse,local,atomic_json
from pptx_core.package import select
from pptx_core.relationships import slide_parts
from pptx_core.snapshots import snapshot
from pptx_core.validator import validate


def element(parent,name,**attrs):
    return etree.SubElement(parent,'{'+P+'}'+name,{k:str(v) for k,v in attrs.items()})


def set_builds(tree,steps,replace=False):
    if not isinstance(steps,list) or not steps or any(not isinstance(s,list) or not s for s in steps):raise ValueError('Use a nonempty list of nonempty shape-ID groups')
    ids=[]
    for step in steps:
        for ident in step:
            if isinstance(ident,bool) or not str(ident).isdigit() or int(ident)<=0:raise ValueError('Shape IDs must be positive integers')
            ids.append(str(ident))
    if len(ids)!=len(set(ids)):raise ValueError('A shape can enter only once')
    shapes={}
    for node in tree.iter():
        if local(node) in ('sp','pic','graphicFrame','grpSp','cxnSp'):
            props=next((p for p in node.iter() if local(p)=='cNvPr'),None)
            if props is not None:shapes[props.get('id')]=node
    if not set(ids)<=set(shapes):raise ValueError('Unknown animation target')
    selected={shapes[i] for i in ids}
    if any(any(parent in selected for parent in node.iterancestors()) for node in selected):raise ValueError('Animate a group or its child, not both')
    old=tree.find('p:timing',NS)
    if old is not None:
        if not replace:raise ValueError('Existing timing preserved; use --replace only within authorized scope')
        tree.remove(old)
    timing=etree.Element('{'+P+'}timing')
    ext=tree.find('p:extLst',NS)
    if ext is None:tree.append(timing)
    else:tree.insert(tree.index(ext),timing)
    counter=iter(range(1,100000))
    def ctn(parent,**attrs):return element(parent,'cTn',id=next(counter),**attrs)
    def condition(parent,delay):element(element(parent,'stCondLst'),'cond',delay=delay)
    root=ctn(element(element(timing,'tnLst'),'par'),dur='indefinite',restart='never',nodeType='tmRoot')
    seq=element(element(root,'childTnLst'),'seq',concurrent='1',nextAc='seek')
    main=ctn(seq,dur='indefinite',nodeType='mainSeq')
    children=element(main,'childTnLst')
    for step in steps:
        click=ctn(element(children,'par'),fill='hold');condition(click,'indefinite')
        offset=ctn(element(element(click,'childTnLst'),'par'),fill='hold');condition(offset,'0')
        effect=ctn(element(element(offset,'childTnLst'),'par'),presetID='1',presetClass='entr',presetSubtype='0',fill='hold',nodeType='clickEffect');condition(effect,'0')
        effects=element(effect,'childTnLst')
        for ident in step:
            action=element(effects,'set');behavior=element(action,'cBhvr');ctn(behavior,dur='1',fill='hold')
            element(element(behavior,'tgtEl'),'spTgt',spid=str(ident))
            element(element(behavior,'attrNameLst'),'attrName').text='style.visibility'
            element(element(action,'to'),'strVal',val='visible')
    for name,event in (('prevCondLst','onPrev'),('nextCondLst','onNext')):
        cond=element(element(seq,name),'cond',evt=event,delay='0');element(element(cond,'tgtEl'),'sldTgt')
    return timing


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',required=True);p.add_argument('--slide',type=int,required=True);p.add_argument('--steps',required=True,help='JSON array of shape-ID groups, e.g. [[4,5],[6,7]]');p.add_argument('--replace',action='store_true')
    a=p.parse_args();ws=select(a.workspace);parts=slide_parts(ws.root)
    if not 1<=a.slide<=len(parts):raise ValueError('Invalid slide number')
    with ws.lock():
        ws.refresh();path=ws.root/parts[a.slide-1];tree=parse(path)
        set_builds(tree,json.loads(a.steps),a.replace)
        checkpoint=snapshot(ws,'before-native-builds')
        path.write_bytes(etree.tostring(tree,xml_declaration=True,encoding='UTF-8',standalone=True))
        validate(ws.root).require();ws.refresh();ws.save()
    print(json.dumps({'slide':a.slide,'snapshot':checkpoint,'steps':json.loads(a.steps),'playback_verified':False}))
