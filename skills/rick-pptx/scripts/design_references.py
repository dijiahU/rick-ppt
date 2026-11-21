"""Write checked artistic provenance into affected native slide notes, not slide copy."""
import argparse
import json
from pathlib import Path
import posixpath
from lxml import etree as E
import workflow_decisions as decisions
import speaker_notes

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
    decisions.validate_plan(plan,outline,root=root,mode=plan['task'].get('operation', {'scoped_edit':'edit','redesign':'edit'}.get(plan['task'].get('scope'),'create')),allow_legacy=allow_legacy,require_click_reveal=False)
    if plan['version'] not in (3,4):return {'pages_updated':[],'reason':'Historical provenance was not invented'}
    workspace=Path(workspace).resolve(strict=True)
    if not workspace.is_relative_to(Path(root).resolve()):raise ValueError('Notes workspace must remain inside the task')
    pres=parse(scoped(workspace,'ppt/presentation.xml'))
    rels=parse(scoped(workspace,'ppt/_rels/presentation.xml.rels'))
    targets={r.get('Id'):r.get('Target') for r in rels.getroot() if r.get('TargetMode')!='External'}
    lookup={r['id']:r for r in plan['references']};updated=[]
    built=len(pres.findall('{'+P+'}sldIdLst/{'+P+'}sldId'))
    if built!=len(plan['pages']):raise ValueError(f'Deck has {built} slides but decision-plan.json lists {len(plan["pages"])} pages; run design_references.py once after the last page is built, just before candidate_save')
    for number,(slide,page) in enumerate(zip(pres.findall('{'+P+'}sldIdLst/{'+P+'}sldId'),plan['pages']),1):
        reference_ids = decisions.page_reference_ids(plan, page)
        target=targets[slide.get('{'+R+'}id')]
        part=posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join('ppt',target))
        note_part,notes=speaker_notes.notes_part(workspace,part,create=bool(reference_ids))
        if note_part is None:continue
        note_path=scoped(workspace,note_part)
        body=speaker_notes.body_of(notes,create=bool(reference_ids))
        if not reference_ids:
            if body is not None and remove_managed(body):write(note_path,notes);updated.append(number)
            continue
        remove_managed(body)
        lines=[BEGIN]
        for ident in reference_ids:lines+=paragraphs(lookup[ident],page['id'],language)
        lines.append(END)
        for line in lines:
            p=E.SubElement(body,'{'+A+'}p');r=E.SubElement(p,'{'+A+'}r');pr=E.SubElement(r,'{'+A+'}rPr',sz='1200');E.SubElement(pr,'{'+A+'}latin',typeface='Times New Roman');E.SubElement(pr,'{'+A+'}ea',typeface='SimSun');E.SubElement(r,'{'+A+'}t').text=line
        write(note_path,notes)
        updated.append(number)
    return {'pages_updated':updated,'references_recorded':sum(bool(r['applications']) for r in plan['references'])}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',required=True);p.add_argument('--plan',default='decision-plan.json');p.add_argument('--outline',default='outline.json');p.add_argument('--allow-legacy',action='store_true');args=p.parse_args()
    plan=json.loads(Path(args.plan).read_text());outline=json.loads(Path(args.outline).read_text())
    request=json.loads(Path('request.json').read_text()) if Path('request.json').is_file() else {}
    print(json.dumps(apply(args.workspace,plan,outline,root=Path.cwd(),language=request.get('language') or 'en',allow_legacy=args.allow_legacy)))

if __name__=='__main__':main()
