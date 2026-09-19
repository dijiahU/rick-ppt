import sys
from pathlib import Path
import pytest
from lxml import etree
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'skills/pptx/scripts'))
from native_builds import set_builds
from pptx_core.common import NS


def slide():
    return etree.fromstring(b'<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:sp><p:nvSpPr><p:cNvPr id="2"/></p:nvSpPr></p:sp><p:sp><p:nvSpPr><p:cNvPr id="3"/></p:nvSpPr></p:sp><p:pic><p:nvPicPr><p:cNvPr id="4"/></p:nvPicPr></p:pic></p:spTree></p:cSld><p:extLst/></p:sld>')


def test_build_groups_preserve_objects_and_order():
    tree=slide();objects=etree.tostring(tree.find('p:cSld',NS));timing=set_builds(tree,[[2,4],[3]])
    assert etree.tostring(tree.find('p:cSld',NS))==objects
    assert timing.xpath('.//p:spTgt/@spid',namespaces=NS)==['2','4','3']
    assert len(timing.xpath('.//p:cTn[@nodeType="clickEffect"]',namespaces=NS))==2
    ids=timing.xpath('.//p:cTn/@id',namespaces=NS);assert len(ids)==len(set(ids))
    assert tree[-1].tag.endswith('extLst')
    before=etree.tostring(tree)
    with pytest.raises(ValueError):set_builds(tree,[[2]])
    assert etree.tostring(tree)==before


@pytest.mark.parametrize('steps',[[[99]],[[2],[2]],[],[[]],[[True]]])
def test_invalid_targets_do_not_modify_slide(steps):
    tree=slide();before=etree.tostring(tree)
    with pytest.raises(ValueError):set_builds(tree,steps)
    assert etree.tostring(tree)==before
