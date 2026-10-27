"""Read-only simple Appear timing shared by host and native tools.

No authoring/package imports: the host may have other plugin versions installed.
Works with both stdlib ElementTree and lxml element objects.
"""
NS={'p':'http://schemas.openxmlformats.org/presentationml/2006/main',
    'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}

def local(node):
    return node.tag.rsplit('}',1)[-1] if isinstance(node.tag,str) else ''

def _ancestors(node,parents):
    while node in parents:
        node=parents[node]
        yield node


def appear_steps(tree):
    """Read supported executable click groups, not just XML traversal order.

    Reject legacy multi-target preset effects: treating their action list as
    synchronized entrances produced optimistic simulations unlike actual viewers.
    Unknown/delayed/triggered/paragraph timing stays unsupported, never a pass.
    """
    # Both stdlib ElementTree (decision checks) and lxml (native authoring)
    # are supported; do not assume lxml-only parent/QName APIs.
    if hasattr(tree, 'getroot'):tree=tree.getroot()
    parents={child:parent for parent in tree.iter() for child in parent}
    timing=tree.find('p:timing',NS)
    if timing is None:return []
    if any(local(n) in ('anim','animEffect','animMotion','animRot','animScale','audio','video','cmd') for n in timing.iter()):return None
    mains=timing.findall('p:tnLst/p:par/p:cTn/p:childTnLst/p:seq/p:cTn',NS)
    if len(mains)!=1 or mains[0].get('nodeType')!='mainSeq':return None
    seq=parents[mains[0]]
    for tag,event in (('prevCondLst','onPrev'),('nextCondLst','onNext')):
        cond=seq.find('p:'+tag+'/p:cond',NS)
        if cond is None or cond.get('evt')!=event or cond.get('delay')!='0':return None
    def starts(node,delay):
        items=node.findall('p:stCondLst/p:cond',NS)
        return len(items)==1 and dict(items[0].attrib)=={'delay':delay} and len(items[0])==0
    groups=[];seen_effects=[]
    clicks=mains[0].find('p:childTnLst',NS)
    if clicks is None or not len(clicks):return None
    for wrapper in clicks:
        if local(wrapper)!='par':return None
        click=wrapper.find('p:cTn',NS)
        if click is None or not starts(click,'indefinite'):return None
        offsets=click.findall('p:childTnLst/p:par/p:cTn',NS)
        if len(offsets)!=1 or not starts(offsets[0],'0'):return None
        rows=offsets[0].find('p:childTnLst',NS)
        if rows is None or not len(rows):return None
        targets=[]
        for index,row in enumerate(rows):
            effect=row.find('p:cTn',NS)
            if local(row)!='par' or effect is None:return None
            if effect.get('nodeType')!=('clickEffect' if index==0 else 'withEffect') or effect.get('presetClass')!='entr' or effect.get('presetID')!='1' or not starts(effect,'0'):return None
            seen_effects.append(effect)
            actions=effect.findall('p:childTnLst/p:set',NS)
            if len(actions)!=1:return None
            action=actions[0];attrs=action.findall('p:cBhvr/p:attrNameLst/p:attrName',NS)
            value=action.find('p:to/p:strVal',NS);target=action.find('p:cBhvr/p:tgtEl/p:spTgt',NS)
            behavior=action.find('p:cBhvr/p:cTn',NS)
            if len(attrs)!=1 or attrs[0].text!='style.visibility' or value is None or value.get('val')!='visible' or target is None or len(target):return None
            if behavior is None or behavior.get('dur')!='1':return None
            targets.append(target.get('spid'))
        groups.append(targets)
    all_effects=[n for n in timing.iter() if local(n)=='cTn' and n.get('nodeType') in ('clickEffect','withEffect','afterEffect')]
    if all_effects!=seen_effects:return None
    ids=[i for g in groups for i in g]
    if [n.get('spid') for n in timing.iter() if local(n)=='spTgt']!=ids or len(ids)!=len(set(ids)):return None
    shapes={}
    for node in tree.iter():
        if local(node) in ('sp','pic','graphicFrame','grpSp','cxnSp'):
            nv=next((p for p in node if local(p).startswith('nv')),None)
            prop=nv.find('p:cNvPr',NS) if nv is not None else None
            if prop is not None:shapes[prop.get('id')]=node
    if not set(ids)<=set(shapes):return None
    selected={shapes[i] for i in ids}
    if any(any(parent in selected for parent in _ancestors(node,parents)) for node in selected):return None
    return groups
