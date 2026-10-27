"""Read-only portability diagnostics, never target-viewer certification or repair."""
import argparse
import json
from pathlib import Path

from native_structure import check_connection, identity
from pptx_core.common import NS, PptxError, atomic_json, local, parse
from pptx_core.relationships import relationships, slide_parts


def inspect(root):
    root=Path(root)
    findings=[];families=set();connectors=0;checked=0
    def finding(part,node,code,message):
        prop=identity(node)
        findings.append({'part':part,'object_id':prop.get('id') if prop is not None else None,
                         'code':code,'message':message})
    for part in slide_parts(root):
        tree=parse(root/part)
        for effect in tree.findall('.//p:cTn[@presetClass="entr"]',NS):
            targets=list(dict.fromkeys(n.get('spid') for n in effect.findall('.//p:spTgt',NS)))
            if len(targets)>1:
                findings.append({'part':part,'object_id':None,'time_node_id':effect.get('id'),
                    'target_ids':targets,'code':'multi_target_entrance',
                    'message':'One preset entrance targets multiple objects. Some viewers may initialize only its first target as hidden. Use one entrance row per object with explicit clickEffect/withEffect start modes; do not certify visibility from a synthetic hidden-target list.'})
        for node in tree.iter():
            if local(node)=='cxnSp':
                connectors+=1
                links=node.find('p:nvCxnSpPr/p:cNvCxnSpPr',NS)
                start=links.find('a:stCxn',NS) if links is not None else None
                end=links.find('a:endCxn',NS) if links is not None else None
                if start is None and end is None:continue  # Deliberately fixed native geometry is valid.
                if start is None or end is None:
                    finding(part,node,'partial_binding','Only one endpoint is bound; inspect the intended fixed/free end in the target viewer.')
                    continue
                try:
                    check_connection(tree,identity(node).get('id'),start.get('id'),end.get('id'),
                                     int(start.get('idx')),int(end.get('idx')))
                    checked+=1
                except (PptxError,ValueError,TypeError,AttributeError) as error:
                    finding(part,node,'connector_binding',str(error))
            if local(node) in ('sp','pic','grpSp','cxnSp','graphicFrame'):
                for ext in node.findall('p:spPr/a:xfrm/a:ext',NS)+node.findall('p:grpSpPr/a:xfrm/a:ext',NS)+node.findall('p:xfrm/a:ext',NS):
                    try:
                        if min(int(ext.get('cx')),int(ext.get('cy')))<0:
                            finding(part,node,'negative_extent','Negative extent; use nonnegative bounds with explicit flips.')
                    except (ValueError,TypeError):
                        finding(part,node,'invalid_extent','Native extent is not an integer.')
            if local(node)=='sp':
                for run in node.findall('.//a:rPr',NS):
                    names=[f.get('typeface','') for f in run if local(f) in ('latin','ea','cs')]
                    if any(n.casefold() in ('wingdings','wingdings 2','wingdings 3','webdings') for n in names):
                        finding(part,node,'symbol_font','Symbol-font text depends on recipient fonts; use editable geometry for graphical arrows/icons.')
                        break
    # Include themes, table/chart defaults and inherited source fonts in inventory.
    for folder in ('slides','slideMasters','slideLayouts','theme','charts'):
        for path in sorted((root/'ppt'/folder).glob('*.xml')):
            for node in parse(path).iter():
                if local(node) in ('latin','ea','cs'):
                    name=node.get('typeface','')
                    if name and not name.startswith('+'):families.add(name)
    presentation=parse(root/'ppt/presentation.xml')
    rels={r['id']:r for r in relationships(root,'ppt/presentation.xml')}
    embedded=[]
    for item in presentation.findall('p:embeddedFontLst/p:embeddedFont',NS):
        face=item.find('p:font',NS);styles={}
        for node in item:
            if local(node) not in ('regular','bold','italic','boldItalic'):continue
            rel=rels.get(node.get('{'+NS['r']+'}id'))
            styles[local(node)]=bool(rel and not rel['external'] and rel['type'].endswith('/font')
                                     and (root/rel['resolved']).is_file())
        embedded.append({'family':face.get('typeface') if face is not None else None,
                         'style_resources_present':styles})
    return {'target':'Windows WPS','windows_wps_verified':False,
            'scope':'Static OOXML diagnostics only; no repair, target font availability or playback certification.',
            'connector_count':connectors,'verified_binding_geometry_count':checked,
            'font_families':sorted(families),'declared_embedded_fonts':embedded,
            'font_embedding_note':'Resource presence does not verify embedding permissions, complete glyph coverage or target-viewer use.',
            'finding_count':len(findings),'findings':findings}


def main():
    from pptx_core.package import select
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();report=inspect(select(args.workspace).root)
    if args.output:atomic_json(args.output,report)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
