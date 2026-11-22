"""Write speaker notes into an unpacked native workspace.

Creates a valid notes master (with its own theme copy) when the deck has none, then
creates or updates each slide's notes page. Text outside the design-reference block
written by design_references.py is replaced; that managed block is kept.

  speaker_notes.py --workspace PARTS_DIR --slide 3 --text "讲解要点……"
  speaker_notes.py --workspace PARTS_DIR --file notes.json   # {"1": "...", "3": "..."}
"""
import argparse
import json
import posixpath
from pathlib import Path

from lxml import etree as E

P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
BEGIN, END = '[Design sources]', '[/Design sources]'
NOTES_CT = 'application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml'
MASTER_CT = 'application/vnd.openxmlformats-officedocument.presentationml.notesMaster+xml'
THEME_CT = 'application/vnd.openxmlformats-officedocument.theme+xml'

MASTER = f'''<p:notesMaster xmlns:a="{A}" xmlns:r="{R}" xmlns:p="{P}"><p:cSld><p:bg><p:bgRef idx="1001"><a:schemeClr val="bg1"/></p:bgRef></p:bg><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr><p:sp><p:nvSpPr><p:cNvPr id="2" name="Slide Image Placeholder 1"/><p:cNvSpPr><a:spLocks noGrp="1" noRot="1" noChangeAspect="1"/></p:cNvSpPr><p:nvPr><p:ph type="sldImg" idx="2"/></p:nvPr></p:nvSpPr><p:spPr><a:xfrm><a:off x="381000" y="685800"/><a:ext cx="6096000" cy="3429000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln w="12700"><a:solidFill><a:prstClr val="black"/></a:solidFill></a:ln></p:spPr></p:sp><p:sp><p:nvSpPr><p:cNvPr id="3" name="Notes Placeholder 2"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph type="body" sz="quarter" idx="3"/></p:nvPr></p:nvSpPr><p:spPr><a:xfrm><a:off x="685800" y="4343400"/><a:ext cx="5486400" cy="4114800"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr><p:txBody><a:bodyPr vert="horz" lIns="91440" tIns="45720" rIns="91440" bIns="45720" rtlCol="0"/><a:lstStyle/><a:p><a:endParaRPr lang="zh-CN"/></a:p></p:txBody></p:sp></p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/><p:notesStyle><a:lvl1pPr marL="0" algn="l" defTabSz="914400" rtl="0" eaLnBrk="1" latinLnBrk="0" hangingPunct="1"><a:defRPr sz="1200" kern="1200"><a:solidFill><a:schemeClr val="tx1"/></a:solidFill><a:latin typeface="+mn-lt"/><a:ea typeface="+mn-ea"/><a:cs typeface="+mn-cs"/></a:defRPr></a:lvl1pPr></p:notesStyle></p:notesMaster>'''


def _parse(path):
    return E.parse(str(path), E.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=False))


def _write(path, tree):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tree.write(str(path), xml_declaration=True, encoding='UTF-8', standalone=True)


def _inside(workspace, relative):
    path = (workspace / relative).resolve()
    if not path.is_relative_to(workspace):
        raise ValueError('Notes path escapes the workspace')
    return path


def _rels(path):
    return _parse(path) if path.is_file() else E.ElementTree(E.Element('{%s}Relationships' % PKG, nsmap={None: PKG}))


def _add_rel(tree, rtype, target, prefix='rIdNotes'):
    used = {r.get('Id') for r in tree.getroot()}
    rid, n = prefix, 1
    while rid in used:
        rid, n = f'{prefix}{n}', n + 1
    E.SubElement(tree.getroot(), '{%s}Relationship' % PKG, Id=rid, Type=R + '/' + rtype, Target=target)
    return rid


def _override(types, part, ctype):
    name = '/' + part
    if not any(x.get('PartName') == name for x in types.getroot()):
        E.SubElement(types.getroot(), '{%s}Override' % CT, PartName=name, ContentType=ctype)


def ensure_notes_master(workspace):
    """Return the notes master part name, creating one (plus theme copy) if absent."""
    workspace = Path(workspace).resolve(strict=True)
    pres_path = _inside(workspace, 'ppt/presentation.xml')
    pres_rels_path = _inside(workspace, 'ppt/_rels/presentation.xml.rels')
    pres, rels = _parse(pres_path), _rels(pres_rels_path)
    for rel in rels.getroot():
        if rel.get('Type', '').endswith('/notesMaster'):
            return posixpath.normpath(posixpath.join('ppt', rel.get('Target')))
    types = _parse(_inside(workspace, '[Content_Types].xml'))
    folder = _inside(workspace, 'ppt/notesMasters'); folder.mkdir(exist_ok=True)
    master_part = 'ppt/notesMasters/notesMaster1.xml'
    _write(_inside(workspace, master_part), E.ElementTree(E.fromstring(MASTER)))
    themes = sorted(_inside(workspace, 'ppt/theme').glob('theme*.xml'))
    source = themes[0] if themes else None
    n = len(themes) + 1
    while _inside(workspace, f'ppt/theme/theme{n}.xml').exists():
        n += 1
    theme_part = f'ppt/theme/theme{n}.xml'
    if source is None:
        raise ValueError('Deck has no theme part to base the notes master on')
    _inside(workspace, theme_part).write_bytes(source.read_bytes())
    master_rels = _rels(Path('/nonexistent'))
    _add_rel(master_rels, 'theme', '../theme/' + Path(theme_part).name, 'rId1')
    _write(_inside(workspace, 'ppt/notesMasters/_rels/notesMaster1.xml.rels'), master_rels)
    rid = _add_rel(rels, 'notesMaster', 'notesMasters/notesMaster1.xml')
    _write(pres_rels_path, rels)
    root = pres.getroot()
    lst = root.find('{%s}notesMasterIdLst' % P)
    if lst is None:
        lst = E.Element('{%s}notesMasterIdLst' % P)
        anchor = root.find('{%s}sldMasterIdLst' % P)
        anchor.addnext(lst)
    E.SubElement(lst, '{%s}notesMasterId' % P).set('{%s}id' % R, rid)
    _write(pres_path, pres)
    _override(types, master_part, MASTER_CT)
    _override(types, theme_part, THEME_CT)
    _write(_inside(workspace, '[Content_Types].xml'), types)
    return master_part


def slide_part(workspace, number):
    pres = _parse(_inside(workspace, 'ppt/presentation.xml'))
    rels = _parse(_inside(workspace, 'ppt/_rels/presentation.xml.rels'))
    targets = {r.get('Id'): r.get('Target') for r in rels.getroot()}
    ids = pres.findall('{%s}sldIdLst/{%s}sldId' % (P, P))
    if not 1 <= number <= len(ids):
        raise ValueError(f'Slide {number} does not exist (deck has {len(ids)} slides)')
    target = targets[ids[number - 1].get('{%s}id' % R)]
    return posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join('ppt', target))


def notes_part(workspace, part, *, create=True):
    """Return (notes part, notes tree) for a slide part, creating a linked notes page."""
    workspace = Path(workspace).resolve(strict=True)
    master = ensure_notes_master(workspace)
    rel_path = _inside(workspace, posixpath.join(posixpath.dirname(part), '_rels', posixpath.basename(part) + '.rels'))
    slide_rels = _rels(rel_path)
    rel = next((r for r in slide_rels.getroot() if r.get('Type', '').endswith('/notesSlide')
                and r.get('TargetMode') != 'External'), None)
    if rel is not None:
        target = rel.get('Target')
        note = posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join(posixpath.dirname(part), target))
        tree = _parse(_inside(workspace, note))
        note_rels_path = _inside(workspace, posixpath.join(posixpath.dirname(note), '_rels', posixpath.basename(note) + '.rels'))
        note_rels = _rels(note_rels_path)
        if not any(r.get('Type', '').endswith('/notesMaster') for r in note_rels.getroot()):
            _add_rel(note_rels, 'notesMaster', '../notesMasters/' + Path(master).name, 'rIdMaster')
            _write(note_rels_path, note_rels)
        return note, tree
    if not create:
        return None, None
    folder = _inside(workspace, 'ppt/notesSlides'); folder.mkdir(exist_ok=True)
    n = 1
    while (folder / f'notesSlide{n}.xml').exists():
        n += 1
    note = f'ppt/notesSlides/notesSlide{n}.xml'
    _add_rel(slide_rels, 'notesSlide', '../notesSlides/' + Path(note).name)
    _write(rel_path, slide_rels)
    root = E.Element('{%s}notes' % P, nsmap={'a': A, 'r': R, 'p': P})
    tree_el = E.SubElement(E.SubElement(root, '{%s}cSld' % P), '{%s}spTree' % P)
    nv = E.SubElement(tree_el, '{%s}nvGrpSpPr' % P)
    E.SubElement(nv, '{%s}cNvPr' % P, id='1', name=''); E.SubElement(nv, '{%s}cNvGrpSpPr' % P); E.SubElement(nv, '{%s}nvPr' % P)
    E.SubElement(tree_el, '{%s}grpSpPr' % P)
    image = E.SubElement(tree_el, '{%s}sp' % P); inv = E.SubElement(image, '{%s}nvSpPr' % P)
    E.SubElement(inv, '{%s}cNvPr' % P, id='2', name='Slide Image Placeholder 1')
    E.SubElement(E.SubElement(inv, '{%s}cNvSpPr' % P), '{%s}spLocks' % A, noGrp='1', noRot='1', noChangeAspect='1')
    E.SubElement(E.SubElement(inv, '{%s}nvPr' % P), '{%s}ph' % P, type='sldImg')
    E.SubElement(image, '{%s}spPr' % P)
    E.SubElement(E.SubElement(root, '{%s}clrMapOvr' % P), '{%s}masterClrMapping' % A)
    note_rels = _rels(Path('/nonexistent'))
    _add_rel(note_rels, 'notesMaster', '../notesMasters/' + Path(master).name, 'rId1')
    _add_rel(note_rels, 'slide', '../slides/' + posixpath.basename(part), 'rId2')
    _write(_inside(workspace, posixpath.join('ppt/notesSlides/_rels', Path(note).name + '.rels')), note_rels)
    types = _parse(_inside(workspace, '[Content_Types].xml'))
    _override(types, note, NOTES_CT)
    _write(_inside(workspace, '[Content_Types].xml'), types)
    tree = E.ElementTree(root)
    _write(_inside(workspace, note), tree)
    return note, tree


def body_of(tree, *, create=True):
    for sp in tree.findall('.//{%s}sp' % P):
        if sp.find('.//{%s}ph[@type="body"]' % P) is not None:
            body = sp.find('{%s}txBody' % P)
            if body is None and create:
                body = E.SubElement(sp, '{%s}txBody' % P)
                E.SubElement(body, '{%s}bodyPr' % A); E.SubElement(body, '{%s}lstStyle' % A)
            return body
    if not create:
        return None
    spTree = tree.find('{%s}cSld/{%s}spTree' % (P, P))
    ids = [int(n.get('id')) for n in spTree.iter('{%s}cNvPr' % P) if (n.get('id') or '').isdigit()]
    sp = E.SubElement(spTree, '{%s}sp' % P); nv = E.SubElement(sp, '{%s}nvSpPr' % P)
    E.SubElement(nv, '{%s}cNvPr' % P, id=str(max(ids, default=1) + 1), name='Notes Placeholder')
    E.SubElement(E.SubElement(nv, '{%s}cNvSpPr' % P), '{%s}spLocks' % A, noGrp='1')
    E.SubElement(E.SubElement(nv, '{%s}nvPr' % P), '{%s}ph' % P, type='body', idx='1')
    E.SubElement(sp, '{%s}spPr' % P)
    body = E.SubElement(sp, '{%s}txBody' % P)
    E.SubElement(body, '{%s}bodyPr' % A); E.SubElement(body, '{%s}lstStyle' % A)
    return body


def paragraph(body, line):
    p = E.SubElement(body, '{%s}p' % A); r = E.SubElement(p, '{%s}r' % A)
    pr = E.SubElement(r, '{%s}rPr' % A, lang='zh-CN', sz='1200')
    E.SubElement(pr, '{%s}latin' % A, typeface='Times New Roman'); E.SubElement(pr, '{%s}ea' % A, typeface='SimSun')
    E.SubElement(r, '{%s}t' % A).text = line


def set_notes(workspace, number, text):
    """Replace the speaker text of one slide, keeping any managed design-reference block."""
    workspace = Path(workspace).resolve(strict=True)
    note, tree = notes_part(workspace, slide_part(workspace, number))
    body = body_of(tree)
    paragraphs = body.findall('{%s}p' % A)
    managed, inside = [], False
    for p in paragraphs:
        content = ''.join(t.text or '' for t in p.iter('{%s}t' % A))
        if content.strip() == BEGIN:
            inside = True
        if inside:
            managed.append(p)
        if content.strip() == END:
            inside = False
        body.remove(p)
    for line in (text or '').split('\n'):
        paragraph(body, line)
    for p in managed:
        body.append(p)
    _write(_inside(workspace, note), tree)
    return {'slide': number, 'notes_part': note, 'lines': len((text or '').split('\n')), 'kept_reference_block': bool(managed)}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--slide', type=int)
    parser.add_argument('--text')
    parser.add_argument('--file', help='JSON object mapping slide numbers to notes text')
    args = parser.parse_args()
    if args.file:
        items = {int(k): v for k, v in json.loads(Path(args.file).read_text()).items()}
    elif args.slide and args.text is not None:
        items = {args.slide: args.text}
    else:
        parser.error('Give --slide and --text, or --file')
    print(json.dumps([set_notes(args.workspace, n, t) for n, t in sorted(items.items())], ensure_ascii=False))


if __name__ == '__main__':
    main()
