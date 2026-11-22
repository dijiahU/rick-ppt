"""Remove legacy design-reference blocks from existing slide notes."""
import argparse
import json
from pathlib import Path
from lxml import etree as E
import workflow_decisions as decisions
import speaker_notes
from pptx_core.relationships import relationships, slide_parts

A=speaker_notes.A
BEGIN='[PPTX-DESIGN-REFERENCES-BEGIN]'
END='[PPTX-DESIGN-REFERENCES-END]'


def write(path,tree):
    Path(path).write_bytes(E.tostring(tree,encoding='UTF-8',xml_declaration=True,standalone=True))


def parse(path):return E.parse(str(path),E.XMLParser(resolve_entities=False,no_network=True))


def remove_managed(body):
    paragraphs=body.findall('{'+A+'}p')
    first=None;removed=False
    for index,p in enumerate(paragraphs):
        text=''.join(t.text or '' for t in p.iter('{'+A+'}t')).strip()
        if text==BEGIN and first is None:first=index
        if text==END and first is not None:
            for old in paragraphs[first:index+1]:body.remove(old)
            first=None;removed=True
    if removed and body.find('{'+A+'}p') is None:E.SubElement(body,'{'+A+'}p')
    return removed


def scoped(workspace,relative):
    root=Path(workspace).resolve(strict=True)
    path=root/relative
    if not path.resolve().is_relative_to(root):raise ValueError('Office relationship escaped the workspace')
    current=root
    for part in Path(relative).parts:
        current=current/part
        if current.is_symlink():raise ValueError('Office symlinks are not allowed')
    return path


def apply(workspace,plan,outline,*,root,language='en',allow_legacy=False):
    decisions.validate_plan(plan,outline,root=root,mode=plan['task'].get('operation', {'scoped_edit':'edit','redesign':'edit'}.get(plan['task'].get('scope'),'create')),allow_legacy=allow_legacy,require_click_reveal=False)
    if plan['version'] not in (3,4):return {'pages_updated':[],'reason':'Historical provenance was not invented'}
    workspace=Path(workspace).resolve(strict=True)
    if not workspace.is_relative_to(Path(root).resolve()):raise ValueError('Notes workspace must remain inside the task')
    slides=slide_parts(workspace)
    if len(slides)!=len(plan['pages']):raise ValueError(f'Deck has {len(slides)} slides but decision-plan.json lists {len(plan["pages"])} pages')
    updated=[]
    for number,part in enumerate(slides,1):
        note_part=next((rel['resolved'] for rel in relationships(workspace,part)
                        if not rel['external'] and rel['type'].endswith('/notesSlide')),None)
        if note_part is None:continue
        note_path=scoped(workspace,note_part)
        notes=parse(note_path)
        body=speaker_notes.body_of(notes,create=False)
        if body is not None and remove_managed(body):write(note_path,notes);updated.append(number)
    return {'pages_updated':updated}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',required=True);p.add_argument('--plan',default='decision-plan.json');p.add_argument('--outline',default='outline.json');p.add_argument('--allow-legacy',action='store_true');args=p.parse_args()
    plan=json.loads(Path(args.plan).read_text());outline=json.loads(Path(args.outline).read_text())
    print(json.dumps(apply(args.workspace,plan,outline,root=Path.cwd(),allow_legacy=args.allow_legacy)))

if __name__=='__main__':main()
