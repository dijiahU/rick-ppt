import sys
from pathlib import Path
from lxml import etree
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'skills/pptx/scripts'))
from native_builds import set_builds
from review_packet import simple_appear_steps,state_previews

P='http://schemas.openxmlformats.org/presentationml/2006/main'
def slide():
    return etree.fromstring(f'<p:sld xmlns:p="{P}"><p:cSld><p:spTree><p:sp><p:nvSpPr><p:cNvPr id="2"/></p:nvSpPr></p:sp><p:sp><p:nvSpPr><p:cNvPr id="3"/></p:nvSpPr></p:sp></p:spTree></p:cSld></p:sld>')

def test_supported_builds_and_unsupported_effects_are_distinct():
    tree=slide();assert simple_appear_steps(tree)==[]
    set_builds(tree,[[2],[3]])
    assert simple_appear_steps(tree)==[['2'],['3']]
    tree.find('.//{'+P+'}cTn[@nodeType="clickEffect"]').set('presetID','10')
    assert simple_appear_steps(tree) is None

def test_text_range_reveal_is_not_reported_as_whole_shape_simulation():
    tree=slide();set_builds(tree,[[2]])
    etree.SubElement(tree.find('.//{'+P+'}spTgt'),'{'+P+'}txEl')
    assert simple_appear_steps(tree) is None

def test_relative_state_output_uses_absolute_render_inputs(tmp_path,monkeypatch):
    import native_canvas as canvas
    import review_packet
    from PIL import Image
    from pptx_core.package import unpack
    from pptx_core.relationships import slide_parts
    ws=unpack(Path(__file__).resolve().parents[2]/'skills/pptx/assets/blank.pptx',tmp_path/'workspaces')
    objs=[canvas.add_shape(ws.root,1,(x,1,1,1),geometry='ellipse',fill=None,stroke='202020',line_width=1,name='State') for x in (1,3)]
    canvas.reveal(ws.root,1,[[objs[0]],[objs[1]]])
    before=(ws.root/'ppt/slides/slide1.xml').read_bytes()
    def render(package,destination,expected_pages,slide=None):
        # Previously the relative destination propagated to pack/render and failed.
        assert Path(package).is_absolute() and Path(destination).is_absolute()
        assert Path(package).is_file()
        assert slide==1
        Path(destination).mkdir(parents=True)
        png=Path(destination)/'page.png';Image.new('RGB',(20,10),'white').save(png)
        return {'pages':[str(png)]}
    monkeypatch.setattr(review_packet,'render_package',render);monkeypatch.chdir(tmp_path)
    Path('relative-states').mkdir()
    report=state_previews(ws.root,slide_parts(ws.root),Path('relative-states'))
    assert len(report['frames'])==2
    assert all((tmp_path/'relative-states'/f['file']).exists() for f in report['frames'])
    assert (ws.root/'ppt/slides/slide1.xml').read_bytes()==before


def test_one_animated_page_in_a_deck_exports_only_its_original_page(ws,tmp_path,monkeypatch):
    import native_canvas as canvas
    import review_packet
    from PIL import Image
    from pptx_core.relationships import slide_parts
    parts=slide_parts(ws.root)
    objects=[canvas.add_shape(ws.root,3,(x,1,1,1),geometry='ellipse',fill=None,stroke='202020',line_width=1,name='State') for x in (1,3)]
    canvas.reveal(ws.root,3,[[objects[0]],[objects[1]]])
    before={part:(ws.root/part).read_bytes() for part in parts};calls=[]
    def render(package,destination,expected_pages,slide=None):
        import zipfile
        with zipfile.ZipFile(package) as archive:
            assert all(part in archive.namelist() for part in parts)
        assert slide==3 and expected_pages==3
        calls.append(slide);Path(destination).mkdir()
        image=Path(destination)/'slide-3.png';Image.new('RGB',(20,10),'green').save(image)
        return {'pages':[str(image)]}
    monkeypatch.setattr(review_packet,'render_package',render)
    destination=tmp_path/'states';destination.mkdir()
    report=state_previews(ws.root,parts,destination)
    assert calls==[3,3]
    assert [(f['page'],f['after_clicks']) for f in report['frames']]==[(3,0),(3,1)]
    assert all((destination/f['file']).exists() for f in report['frames'])
    assert {part:(ws.root/part).read_bytes() for part in parts}==before


def test_several_animated_pages_keep_one_conversion_for_each_state_slot(ws,tmp_path,monkeypatch):
    import native_canvas as canvas
    import review_packet
    from PIL import Image
    from pptx_core.relationships import slide_parts
    parts=slide_parts(ws.root)
    for page in (1,3):
        objects=[canvas.add_shape(ws.root,page,(x,1,1,1),geometry='ellipse',fill=None,stroke='202020',line_width=1,name='State') for x in (1,3)]
        canvas.reveal(ws.root,page,[[objects[0]],[objects[1]]])
    calls=[]
    def render(package,destination,expected_pages,slide=None):
        assert slide is None and expected_pages==3
        calls.append(slide);Path(destination).mkdir();images=[]
        for page in (1,2,3):
            image=Path(destination)/f'slide-{page}.png';Image.new('RGB',(20,10),(page,0,0)).save(image);images.append(str(image))
        return {'pages':images}
    monkeypatch.setattr(review_packet,'render_package',render)
    destination=tmp_path/'states';destination.mkdir()
    report=state_previews(ws.root,parts,destination)
    assert calls==[None,None] and len(report['frames'])==4
    for frame in report['frames']:
        with Image.open(destination/frame['file']) as image:assert image.getpixel((0,0))==(frame['page'],0,0)
