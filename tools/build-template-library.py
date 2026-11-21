#!/usr/bin/env python3
"""Build a searchable library of editable PPTX templates (one collection, many templates).

SOURCE holds category folders of .pptx files (e.g. ~/Downloads/ppt模版/工作汇报/x.pptx).
Each template is copied into the library, rendered once, and every visible slide becomes a
1280-px JPEG with tone/colours plus a structural summary (pictures, text boxes, charts, tables).
Content tags (page_type, layout, description ...) are merged later with tools/tag-reference-library.py.
The library lives outside the repository (template licences belong to their authors).

  FONTCONFIG_FILE=... python tools/build-template-library.py ~/Downloads/ppt模版 \
      --target ~/.rick-ppt/reference-library/templates --source-label "WPS 稻壳会员模板"
"""
import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.util import Emu

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('build_reference_library', HERE / 'build-reference-library.py')
_brl = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_brl)
describe, WIDTH = _brl.describe, _brl.WIDTH
SOFFICE = '/Applications/LibreOffice.app/Contents/MacOS/soffice'


def structure(slide):
    counts = {'pictures': 0, 'text_boxes': 0, 'charts': 0, 'tables': 0, 'groups': 0}
    words = []

    def walk(shapes):
        for sh in shapes:
            kind = sh.shape_type
            if sh.shape_type == 6:  # group
                counts['groups'] += 1; walk(sh.shapes); continue
            if kind == 13 or (kind == 14 and hasattr(sh, 'image')):
                counts['pictures'] += 1
            if getattr(sh, 'has_chart', False) and sh.has_chart:
                counts['charts'] += 1
            if getattr(sh, 'has_table', False) and sh.has_table:
                counts['tables'] += 1
            if getattr(sh, 'has_text_frame', False) and sh.has_text_frame and sh.text_frame.text.strip():
                counts['text_boxes'] += 1; words.append(sh.text_frame.text.strip().replace('\n', ' ')[:40])
    try:
        walk(slide.shapes)
    except AttributeError:
        # python-pptx cannot wrap some vendor elements (e.g. mc:AlternateContent in the
        # shape tree); count from the XML instead of failing the whole template.
        ns = '{http://schemas.openxmlformats.org/presentationml/2006/main}'
        tree = slide._element
        counts['pictures'] = len(tree.findall(f'.//{ns}pic'))
        counts['groups'] = len(tree.findall(f'.//{ns}grpSp'))
        counts['tables'] = len(tree.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/main}tbl'))
        counts['charts'] = len(tree.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/chart}chart'))
        texts = [''.join(t.itertext()).strip() for t in tree.findall(f'.//{ns}txBody')]
        texts = [x for x in texts if x]
        counts['text_boxes'] = len(texts); words = [x.replace('\n', ' ')[:40] for x in texts]
    return counts, ' / '.join(words)[:240]


def render(pptx, temp):
    subprocess.run([SOFFICE, '--headless', '--convert-to', 'pdf', '--outdir', temp, str(pptx)],
                   check=True, capture_output=True, timeout=600)
    pdf = Path(temp) / (pptx.stem + '.pdf')
    if not pdf.is_file():
        raise OSError('render failed')
    subprocess.run(['pdftoppm', '-scale-to-x', str(WIDTH), '-scale-to-y', '-1', '-jpeg', '-jpegopt', 'quality=85',
                    str(pdf), str(Path(temp) / 'p')], check=True, capture_output=True, timeout=600)
    return sorted(Path(temp).glob('p-*.jpg'), key=lambda p: int(p.stem.split('-')[1]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('source', type=Path)
    ap.add_argument('--target', type=Path, required=True)
    ap.add_argument('--name', default='templates')
    ap.add_argument('--source-label', default='')
    ap.add_argument('--license', default='Licensed templates for the owner\'s own presentations; do not redistribute the files.')
    args = ap.parse_args()
    target = args.target
    (target / 'pages').mkdir(parents=True, exist_ok=True); (target / 'files').mkdir(exist_ok=True)
    pages, templates = [], []
    for path in sorted(args.source.rglob('*.pptx')):
        if path.name.startswith(('.', '~$')):
            continue
        category = path.parent.name if path.parent != args.source else '未分类'
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        tid = 't' + digest[:8]
        shutil.copy2(path, target / 'files' / f'{tid}.pptx')
        prs = Presentation(str(path))
        slides = list(prs.slides)
        visible = [i for i, s in enumerate(slides, 1) if s._element.get('show') != '0']
        try:
            with tempfile.TemporaryDirectory() as temp:
                images = render(target / 'files' / f'{tid}.pptx', temp)
                if len(images) != len(visible):
                    print('page count mismatch', path.name, len(images), len(visible))
                for n, (img, slide_no) in enumerate(zip(images, visible), 1):
                    ident = f'{tid}-{slide_no:02d}'
                    out = target / 'pages' / f'{ident}.jpg'
                    shutil.copyfile(img, out)
                    with Image.open(out) as im:
                        info = {'size': list(im.size), **describe(im.convert('RGB'))}
                    counts, text = structure(slides[slide_no - 1])
                    pages.append({'id': ident, 'file': f'pages/{ident}.jpg', 'deck': path.stem, 'template': tid,
                                  'category': category, 'slide': slide_no, 'structure': counts, 'sample_text': text, **info})
        except (OSError, subprocess.SubprocessError) as error:
            print('skip', path.name, error)
            (target / 'files' / f'{tid}.pptx').unlink(missing_ok=True)
            continue
        templates.append({'id': tid, 'name': path.stem, 'category': category, 'file': f'files/{tid}.pptx',
                          'sha256': digest, 'slides': len(slides), 'visible_slides': len(visible),
                          'size': [Emu(prs.slide_width).inches, Emu(prs.slide_height).inches]})
        print(f'{tid} {category}/{path.stem}: {len(visible)} slides', flush=True)
    index = {'name': args.name, 'kind': 'templates', 'source': args.source_label, 'license': args.license,
             'count': len(pages), 'templates': templates, 'pages': pages}
    (target / 'index.json').write_text(json.dumps(index, ensure_ascii=False, indent=1))
    print(f'{len(templates)} templates, {len(pages)} slides -> {target}')


if __name__ == '__main__':
    main()
