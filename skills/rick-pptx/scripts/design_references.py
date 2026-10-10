"""Write checked artistic provenance into affected native slide notes, not slide copy."""
import argparse
import json
from pathlib import Path
import posixpath
from lxml import etree as E
import workflow_decisions as decisions

P='http://schemas.openxmlformats.org/presentationml/2006/main'
A='http://schemas.openxmlformats.org/drawingml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG='http://schemas.openxmlformats.org/package/2006/relationships'
CT='http://schemas.openxmlformats.org/package/2006/content-types'
LABELS={
 'en':('Design reference','Observed','Borrowed','Applied','Source'),
 'zh-CN':('设计参考','观察','汲取','应用','来源'),
 'fr':('Référence de conception','Observation','Principe retenu','Application','Source'),
 'es':('Referencia de diseño','Observación','Principio adoptado','Aplicación','Fuente'),
 'ja':('デザイン参考','観察','取り入れた原理','適用','出典')}
BEGIN='[PPTX-DESIGN-REFERENCES-BEGIN]'
END='[PPTX-DESIGN-REFERENCES-END]'


def write(path,tree):
    Path(path).write_bytes(E.tostring(tree,encoding='UTF-8',xml_declaration=True,standalone=True))


def parse(path):return E.parse(str(path),E.XMLParser(resolve_entities=False,no_network=True))


def remove_managed(body):
    old=list(body.findall('{'+A+'}p'));texts=[''.join(p.itertext()) for p in old]
    if BEGIN not in texts or END not in texts:return False
    first=texts.index(BEGIN)
    try:last=texts.index(END,first)
    except ValueError:return False
    for p in old[first:last+1]:body.remove(p)
    return True


def scoped(workspace,relative):
    root=Path(workspace).resolve(strict=True)
    path=root/relative
    if not path.resolve().is_relative_to(root):raise ValueError('Office relationship escaped the workspace')
    current=root
    for part in Path(relative).parts:
        current=current/part
        if current.is_symlink():raise ValueError('Office symlinks are not allowed')
    return path


def paragraphs(entry,page_id,language='en'):
    labels=LABELS.get(language,LABELS['en'])
    return [f'{labels[0]} [{entry["id"]}] {entry["title"]} — {entry["creator"]}',
            f'{labels[1]}: {entry["observed"]}',f'{labels[2]}: {entry["borrowed"]}',
            f'{labels[3]}: {decisions.reference_application(entry,page_id)}',
            f'{labels[4]}: {entry["source"]}']


def apply(workspace,plan,outline,*,root,language='en',allow_legacy=False):
    decisions.validate_plan(plan,outline,root=root,mode=plan['task']['operation'],allow_legacy=allow_legacy,require_click_reveal=False)
    if plan['version']!=3:return {'pages_updated':[],'reason':'Historical provenance was not invented'}
    workspace=Path(workspace).resolve(strict=True)
    if not workspace.is_relative_to(Path(root).resolve()):raise ValueError('Notes workspace must remain inside the task')
    pres=parse(scoped(workspace,'ppt/presentation.xml'))
    rels=parse(scoped(workspace,'ppt/_rels/presentation.xml.rels'))
    targets={r.get('Id'):r.get('Target') for r in rels.getroot() if r.get('TargetMode')!='External'}
    lookup={r['id']:r for r in plan['references']};updated=[]
    types=parse(scoped(workspace,'[Content_Types].xml'))
    if len(pres.findall('{'+P+'}sldIdLst/{'+P+'}sldId'))!=len(plan['pages']):raise ValueError('Write final reference notes after all planned pages exist')
    for number,(slide,page) in enumerate(zip(pres.findall('{'+P+'}sldIdLst/{'+P+'}sldId'),plan['pages']),1):
        target=targets[slide.get('{'+R+'}id')]
        part=posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join('ppt',target))
        relpart=posixpath.join(posixpath.dirname(part),'_rels',posixpath.basename(part)+'.rels')
        relpath=scoped(workspace,relpart)
        sr=parse(relpath) if relpath.is_file() else E.ElementTree(E.Element('{'+PKG+'}Relationships',nsmap={None:PKG}))
        note_rel=next((r for r in sr.getroot() if r.get('Type','').endswith('/notesSlide') and r.get('TargetMode')!='External'),None)
        if note_rel is not None:
            note_target=note_rel.get('Target');note_part=posixpath.normpath(note_target.lstrip('/') if note_target.startswith('/') else posixpath.join(posixpath.dirname(part),note_target))
        else:
            if not page['reference_ids']:continue
            folder=scoped(workspace,'ppt/notesSlides');folder.mkdir(exist_ok=True)
            ident=number
            while (folder/f'notesSlide{ident}.xml').exists():ident+=1
            note_part=f'ppt/notesSlides/notesSlide{ident}.xml'
            used={r.get('Id') for r in sr.getroot()};rid='rIdDesignNotes';suffix=1
            while rid in used:rid='rIdDesignNotes'+str(suffix);suffix+=1
            E.SubElement(sr.getroot(),'{'+PKG+'}Relationship',Id=rid,Type=R+'/notesSlide',Target='../notesSlides/'+Path(note_part).name)
            relpath.parent.mkdir(parents=True,exist_ok=True);write(relpath,sr)
        note_path=scoped(workspace,note_part)
        if note_path.exists():notes=parse(note_path)
        else:
            notes=E.ElementTree(E.Element('{'+P+'}notes',nsmap={'p':P,'a':A,'r':R}))
            tree=E.SubElement(E.SubElement(notes.getroot(),'{'+P+'}cSld'),'{'+P+'}spTree')
            nv=E.SubElement(tree,'{'+P+'}nvGrpSpPr');E.SubElement(nv,'{'+P+'}cNvPr',id='1',name='');E.SubElement(nv,'{'+P+'}cNvGrpSpPr');E.SubElement(nv,'{'+P+'}nvPr');E.SubElement(tree,'{'+P+'}grpSpPr')
            E.SubElement(E.SubElement(notes.getroot(),'{'+P+'}clrMapOvr'),'{'+A+'}masterClrMapping')
            nr=E.Element('{'+PKG+'}Relationships',nsmap={None:PKG})
            E.SubElement(nr,'{'+PKG+'}Relationship',Id='rId1',Type=R+'/slide',Target='../slides/'+Path(part).name)
            rp=scoped(workspace,posixpath.join(posixpath.dirname(note_part),'_rels',Path(note_part).name+'.rels'));rp.parent.mkdir(exist_ok=True);write(rp,nr)
        body=next((sp.find('{'+P+'}txBody') for sp in notes.findall('.//{'+P+'}sp') if sp.find('.//{'+P+'}ph[@type="body"]') is not None),None)
        if not page['reference_ids']:
            if body is not None and remove_managed(body):write(note_path,notes);updated.append(number)
            continue
        if body is None:
            tree=notes.find('{'+P+'}cSld/{'+P+'}spTree')
            ids=[int(n.get('id')) for n in tree.iter('{'+P+'}cNvPr')]
            sp=E.SubElement(tree,'{'+P+'}sp');nv=E.SubElement(sp,'{'+P+'}nvSpPr');E.SubElement(nv,'{'+P+'}cNvPr',id=str(max(ids,default=1)+1),name='Design source notes');E.SubElement(nv,'{'+P+'}cNvSpPr');E.SubElement(E.SubElement(nv,'{'+P+'}nvPr'),'{'+P+'}ph',type='body',idx='1');E.SubElement(sp,'{'+P+'}spPr')
            body=E.SubElement(sp,'{'+P+'}txBody');E.SubElement(body,'{'+A+'}bodyPr');E.SubElement(body,'{'+A+'}lstStyle')
        remove_managed(body)
        lines=[BEGIN]
        for ident in page['reference_ids']:lines+=paragraphs(lookup[ident],page['id'],language)
        lines.append(END)
        for line in lines:
            p=E.SubElement(body,'{'+A+'}p');r=E.SubElement(p,'{'+A+'}r');pr=E.SubElement(r,'{'+A+'}rPr',sz='1200');E.SubElement(pr,'{'+A+'}latin',typeface='Arial');E.SubElement(r,'{'+A+'}t').text=line
        write(note_path,notes)
        override='/'+note_part
        if not any(x.get('PartName')==override for x in types.getroot()):E.SubElement(types.getroot(),'{'+CT+'}Override',PartName=override,ContentType='application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml')
        updated.append(number)
    if updated:write(scoped(workspace,'[Content_Types].xml'),types)
    return {'pages_updated':updated,'references_recorded':sum(bool(r['applications']) for r in plan['references'])}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',required=True);p.add_argument('--plan',default='decision-plan.json');p.add_argument('--outline',default='outline.json');p.add_argument('--allow-legacy',action='store_true');args=p.parse_args()
    plan=json.loads(Path(args.plan).read_text());outline=json.loads(Path(args.outline).read_text())
    request=json.loads(Path('request.json').read_text()) if Path('request.json').is_file() else {}
    print(json.dumps(apply(args.workspace,plan,outline,root=Path.cwd(),language=request.get('language') or 'en',allow_legacy=args.allow_legacy)))

if __name__=='__main__':main()
