"""Read-only formula/font inventory; not a renderer or mathematical validator."""
import argparse
import json
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET

A='http://schemas.openxmlformats.org/drawingml/2006/main'
P='http://schemas.openxmlformats.org/presentationml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
M='http://schemas.openxmlformats.org/officeDocument/2006/math'
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
MATH=re.compile(r'[=∇∂∑∫√∞≤≥±×÷−α-ωΑ-Ω]|\\(?:frac|sqrt|sum|int|begin)\b')
# Short variable notation only: do not treat ordinary snake_case fields as math.
# Literal code can still contain x_i. These are inspection leads, never verdicts.
PLAIN_SCRIPT=re.compile(r'(?<![\w\\])[A-Za-zα-ωΑ-Ω](?:_[A-Za-z0-9]{1,3}|\^[+-]?\d{1,3})(?!\w)')

def inspect_slide(root):
    """Facts from actual slide XML, shared by CLI, page context and review packet."""
    if hasattr(root, 'getroot'):root=root.getroot()
    fonts=set();warnings=[];candidates=[]
    parents={child:parent for parent in root.iter() for child in parent}
    def location(paragraph,number):
        node=paragraph
        while node is not None:
            if node.tag in (f'{{{P}}}sp',f'{{{P}}}graphicFrame'):
                prop=node.find(f'.//{{{P}}}cNvPr')
                if prop is not None:
                    return {'object_id':prop.get('id'),'object_name':prop.get('name'),'paragraph':number}
            node=parents.get(node)
        return {'paragraph':number}
    for item in root.iter():
        if item.tag in [f'{{{A}}}latin',f'{{{A}}}ea',f'{{{A}}}sym',f'{{{A}}}cs'] and item.get('typeface'):
            fonts.add(item.get('typeface'))
        if item.tag==f'{{{W}}}rFonts':fonts.update(v for k,v in item.attrib.items() if k.split('}')[-1] in ['ascii','hAnsi','eastAsia','cs'])
    for number,paragraph in enumerate(root.findall(f'.//{{{A}}}p'),1):
        text=''.join(t.text or '' for t in paragraph.findall(f'.//{{{A}}}t'))
        tokens=[m.group() for m in PLAIN_SCRIPT.finditer(text)]
        if MATH.search(text) or tokens:candidates.append(text)
        where=location(paragraph,number)
        if '\ufffd' in text:warnings.append({'kind':'replacement-character','text':text,**where})
        if re.search(r'\\(?:frac|sqrt|sum|int|begin)\b',text):warnings.append({'kind':'possible-unrendered-latex','text':text,**where})
        if tokens:warnings.append({'kind':'possible-plain-math-script','text':text,'tokens':tokens,**where,
            'interpretation':'Literal underscore/caret notation. Check intended math versus literal code against the source and render; no automatic replacement or failure.'})
    math=root.findall(f'.//{{{M}}}oMath')
    for item in math:
        text=''.join(t.text or '' for t in item.findall(f'.//{{{M}}}t'))
        if '\ufffd' in text:warnings.append({'kind':'replacement-character-in-math','text':text})
    return {'declaredFonts':sorted(fonts),'nativeOfficeMathCount':len(math),
            'explicitBaselineRunCount':sum(x.get('baseline') not in (None,'0') for x in root.findall(f'.//{{{A}}}rPr')),
            'candidateText':candidates,'warnings':warnings,
            'interpretation':'Read-only encoding clues, not a mathematical, visual or font-coverage verdict. Literal code may intentionally use underscores. Inspect actual notation and rendered pixels even without warnings.'}

def inspect(path):
    with zipfile.ZipFile(path) as package:
        entries=package.infolist()
        if len(entries)>20000 or sum(x.file_size for x in entries)>512*1024*1024:
            raise ValueError('Package exceeds inspection limits')
        if len({x.filename for x in entries})!=len(entries):raise ValueError('Duplicate ZIP entries')
        def xml(part):
            if package.getinfo(part).file_size>4*1024*1024:raise ValueError('XML part too large')
            data=package.read(part)
            if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise ValueError('DTD/entities not accepted')
            return ET.fromstring(data)
        import posixpath
        rels={r.get('Id'):r for r in xml('ppt/_rels/presentation.xml.rels')}
        pages=[]
        for number,slide in enumerate(xml('ppt/presentation.xml').findall(f'.//{{{P}}}sldId'),1):
            rel=rels[slide.get(f'{{{R}}}id')]
            if rel.get('TargetMode')=='External':raise ValueError('External slide relationship')
            target=rel.get('Target','')
            part=posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join('ppt',target))
            if not part.startswith('ppt/slides/'):raise ValueError('Invalid slide relationship')
            pages.append({'slide':number,'part':part,**inspect_slide(xml(part))})
    return {'file':str(Path(path).resolve()),'readOnly':True,'limitations':['Candidate detection is incomplete; inspect all actual formulas.','Declared fonts omit inherited theme resolution and do not prove installed glyph coverage.','No render, arithmetic, semantics or playback verification.'],'slides':pages}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('pptx');args=parser.parse_args()
    try:print(json.dumps(inspect(args.pptx),ensure_ascii=False,indent=2))
    except (ValueError,KeyError,OSError,zipfile.BadZipFile,ET.ParseError) as error:parser.exit(1,str(error)+'\n')
