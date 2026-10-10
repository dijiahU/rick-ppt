"""Explicit native groups and connector endpoints; preserves existing shape IDs."""
import argparse
import json
import os
from pathlib import Path
from lxml import etree
from pptx_core.common import NS, parse, local, PptxError
from pptx_core.package import select
from pptx_core.relationships import slide_parts


def prop(node):
    return next((child for child in node if local(child).startswith('nv')),None)


def identity(node):
    nv=prop(node)
    return nv.find('p:cNvPr',NS) if nv is not None else None


def shape(tree,identifier):
    matches=[n for n in tree.iter() if local(n) in ('sp','pic','graphicFrame','grpSp','cxnSp')
             and identity(n) is not None and identity(n).get('id')==str(identifier)]
    if len(matches)!=1:raise PptxError('Shape ID must identify exactly one native object')
    return matches[0]


def bounds(node):
    xf=node.find('p:grpSpPr/a:xfrm',NS) if local(node)=='grpSp' else node.find('p:spPr/a:xfrm',NS)
    if xf is None:xf=node.find('p:xfrm',NS)
    if xf is None:raise PptxError('Object has no explicit transform; supply geometry first')
    off=xf.find('a:off',NS);ext=xf.find('a:ext',NS)
    if off is None or ext is None:raise PptxError('Object transform lacks bounds')
    return tuple(int(off.get(k)) for k in ('x','y'))+tuple(int(ext.get(k)) for k in ('cx','cy'))


def group(tree,ids,name):
    if len(ids)<2 or len(set(ids))!=len(ids) or not name.strip():raise PptxError('A named group needs distinct member IDs')
    members=[shape(tree,identifier) for identifier in ids];parent=members[0].getparent()
    if local(parent) not in ('spTree','grpSp') or any(n.getparent() is not parent for n in members):
        raise PptxError('Members must share a native shape-tree parent')
    positions=sorted(parent.index(n) for n in members)
    if positions!=list(range(positions[0],positions[-1]+1)):
        raise PptxError('Members must be adjacent in drawing order; grouping would reorder other objects')
    geometries=[bounds(n) for n in members]
    x=min(b[0] for b in geometries);y=min(b[1] for b in geometries)
    width=max(b[0]+b[2] for b in geometries)-x;height=max(b[1]+b[3] for b in geometries)-y
    if width<=0 or height<=0:raise PptxError('Group extent must be positive')
    ident=str(max(int(n.get('id')) for n in tree.iter() if local(n)=='cNvPr')+1)
    result=etree.Element('{'+NS['p']+'}grpSp')
    nv=etree.SubElement(result,'{'+NS['p']+'}nvGrpSpPr')
    etree.SubElement(nv,'{'+NS['p']+'}cNvPr',id=ident,name=name)
    etree.SubElement(nv,'{'+NS['p']+'}cNvGrpSpPr');etree.SubElement(nv,'{'+NS['p']+'}nvPr')
    gp=etree.SubElement(result,'{'+NS['p']+'}grpSpPr');xf=etree.SubElement(gp,'{'+NS['a']+'}xfrm')
    for tag,attrs in [('off',{'x':x,'y':y}),('ext',{'cx':width,'cy':height}),('chOff',{'x':x,'y':y}),('chExt',{'cx':width,'cy':height})]:
        etree.SubElement(xf,'{'+NS['a']+'}'+tag,**{k:str(v) for k,v in attrs.items()})
    ordered=[parent[i] for i in positions]
    parent.insert(positions[0],result)
    for node in ordered:result.append(node)
    return ident


def anchor(tree,connector,start,end,start_site,end_site):
    node=shape(tree,connector)
    if local(node)!='cxnSp':raise PptxError('Use a native p:cxnSp connector, not a line-shaped p:sp')
    if len({str(connector),str(start),str(end)})!=3:raise PptxError('Connector endpoints must be distinct objects')
    for identifier in (start,end):
        if local(shape(tree,identifier)) not in ('sp','pic','grpSp'):raise PptxError('Endpoint object has no native connection sites')
    if any(type(i) is not int or not 0<=i<=31 for i in (start_site,end_site)):raise PptxError('Invalid connection-site index')
    nv=node.find('p:nvCxnSpPr/p:cNvCxnSpPr',NS)
    if nv is None:raise PptxError('Missing native connector properties')
    for tag,identifier,index in [('stCxn',start,start_site),('endCxn',end,end_site)]:
        old=nv.find('a:'+tag,NS)
        if old is not None:nv.remove(old)
        endpoint=etree.Element('{'+NS['a']+'}'+tag,id=str(identifier),idx=str(index))
        extension=nv.find('a:extLst',NS)
        nv.insert(nv.index(extension),endpoint) if extension is not None else nv.append(endpoint)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',required=True);parser.add_argument('--slide',type=int,required=True)
    actions=parser.add_subparsers(dest='action',required=True)
    gp=actions.add_parser('group');gp.add_argument('--ids',type=int,nargs='+',required=True);gp.add_argument('--name',required=True)
    cp=actions.add_parser('anchor');cp.add_argument('--connector',type=int,required=True);cp.add_argument('--start',type=int,required=True);cp.add_argument('--end',type=int,required=True);cp.add_argument('--start-site',type=int,required=True);cp.add_argument('--end-site',type=int,required=True)
    args=parser.parse_args();ws=select(args.workspace)
    with ws.lock():
        parts=slide_parts(ws.root)
        if not 1<=args.slide<=len(parts):raise PptxError('Slide out of range')
        path=ws.root/parts[args.slide-1];tree=parse(path)
        identifier=group(tree,args.ids,args.name) if args.action=='group' else anchor(tree,args.connector,args.start,args.end,args.start_site,args.end_site)
        temporary=path.with_name(path.name+'.structure-pending')
        with temporary.open('xb') as stream:stream.write(etree.tostring(tree,xml_declaration=True,encoding='UTF-8',standalone=True));stream.flush();os.fsync(stream.fileno())
        temporary.replace(path);ws.refresh()
        print(json.dumps({'slide':args.slide,'action':args.action,'group_id':identifier,'render_required':True}))

if __name__=='__main__':main()
