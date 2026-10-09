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
    def render(package,destination,expected_pages):
        # Previously the relative destination propagated to pack/render and failed.
        assert Path(package).is_absolute() and Path(destination).is_absolute()
        assert Path(package).is_file()
        Path(destination).mkdir(parents=True)
        png=Path(destination)/'page.png';Image.new('RGB',(20,10),'white').save(png)
        return {'pages':[str(png)]}
    monkeypatch.setattr(review_packet,'render_package',render);monkeypatch.chdir(tmp_path)
    Path('relative-states').mkdir()
    report=state_previews(ws.root,slide_parts(ws.root),Path('relative-states'))
    assert len(report['frames'])==2
    assert all((tmp_path/'relative-states'/f['file']).exists() for f in report['frames'])
    assert (ws.root/'ppt/slides/slide1.xml').read_bytes()==before
