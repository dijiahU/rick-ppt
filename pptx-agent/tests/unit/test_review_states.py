import sys
from pathlib import Path
from lxml import etree
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'skills/pptx/scripts'))
from native_builds import set_builds
from review_packet import simple_appear_steps

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
