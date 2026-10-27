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
            root=xml(part);fonts=set();warnings=[];candidates=[]
            for item in root.iter():
                if item.tag in [f'{{{A}}}latin',f'{{{A}}}ea',f'{{{A}}}sym',f'{{{A}}}cs'] and item.get('typeface'):
                    fonts.add(item.get('typeface'))
                if item.tag==f'{{{W}}}rFonts':fonts.update(v for k,v in item.attrib.items() if k.split('}')[-1] in ['ascii','hAnsi','eastAsia','cs'])
            for paragraph in root.findall(f'.//{{{A}}}p'):
                text=''.join(t.text or '' for t in paragraph.findall(f'.//{{{A}}}t'))
                if MATH.search(text):candidates.append(text)
                if '\ufffd' in text:warnings.append({'kind':'replacement-character','text':text})
                if re.search(r'\\(?:frac|sqrt|sum|int|begin)\b',text):warnings.append({'kind':'possible-unrendered-latex','text':text})
            math=root.findall(f'.//{{{M}}}oMath')
            for item in math:
                text=''.join(t.text or '' for t in item.findall(f'.//{{{M}}}t'))
                if '\ufffd' in text:warnings.append({'kind':'replacement-character-in-math','text':text})
            pages.append({'slide':number,'part':part,'declaredFonts':sorted(fonts),'nativeOfficeMathCount':len(math),'candidateText':candidates,'warnings':warnings})
    return {'file':str(Path(path).resolve()),'readOnly':True,'limitations':['Candidate detection is incomplete; inspect all actual formulas.','Declared fonts omit inherited theme resolution and do not prove installed glyph coverage.','No render, arithmetic, semantics or playback verification.'],'slides':pages}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('pptx');args=parser.parse_args()
    try:print(json.dumps(inspect(args.pptx),ensure_ascii=False,indent=2))
    except (ValueError,KeyError,OSError,zipfile.BadZipFile,ET.ParseError) as error:parser.exit(1,str(error)+'\n')
