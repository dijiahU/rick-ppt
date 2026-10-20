import sys
from pathlib import Path
import pytest
from lxml import etree
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'skills/pptx/scripts'))
from native_builds import set_builds,appear_steps
from pptx_core.common import NS
from xml.etree import ElementTree as StdET


def slide():
    return etree.fromstring(b'<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:sp><p:nvSpPr><p:cNvPr id="2"/></p:nvSpPr></p:sp><p:sp><p:nvSpPr><p:cNvPr id="3"/></p:nvSpPr></p:sp><p:pic><p:nvPicPr><p:cNvPr id="4"/></p:nvPicPr></p:pic></p:spTree></p:cSld><p:extLst/></p:sld>')


def test_build_groups_preserve_objects_and_order():
    tree=slide();objects=etree.tostring(tree.find('p:cSld',NS));timing=set_builds(tree,[[2,4],[3]])
    assert etree.tostring(tree.find('p:cSld',NS))==objects
    assert timing.xpath('.//p:spTgt/@spid',namespaces=NS)==['2','4','3']
    assert len(timing.xpath('.//p:cTn[@nodeType="clickEffect"]',namespaces=NS))==2
    ids=timing.xpath('.//p:cTn/@id',namespaces=NS);assert len(ids)==len(set(ids))
    assert tree[-1].tag.endswith('extLst')
    assert appear_steps(tree)==[['2','4'],['3']]
    effects=timing.xpath('.//p:cTn[@presetClass="entr"]',namespaces=NS)
    assert [e.get('nodeType') for e in effects]==['clickEffect','withEffect','clickEffect']
    assert all(len(e.xpath('.//p:spTgt',namespaces=NS))==1 for e in effects)
    before=etree.tostring(tree)
    with pytest.raises(ValueError):set_builds(tree,[[2]])
    assert etree.tostring(tree)==before


def test_legacy_multi_target_entrance_is_not_certified_as_a_click_state():
    tree=slide();set_builds(tree,[[2,4],[3]])
    rows=tree.findall('.//p:cTn[@presetClass="entr"]',NS)
    first=rows[0].find('p:childTnLst',NS)
    first.append(rows[1].find('p:childTnLst/p:set',NS))
    rows[1].getparent().getparent().remove(rows[1].getparent())
    # This is the old writer's structure: the first text hides but the second
    # text/image can remain visible at entry in a different viewer.
    assert appear_steps(tree) is None
    assert appear_steps(StdET.fromstring(etree.tostring(tree))) is None


def test_host_stdlib_and_author_lxml_read_identical_click_groups():
    tree=slide();set_builds(tree,[[2,4],[3]])
    expected=[['2','4'],['3']]
    assert appear_steps(tree)==expected
    assert appear_steps(StdET.fromstring(etree.tostring(tree)))==expected
    assert appear_steps(StdET.ElementTree(StdET.fromstring(etree.tostring(tree))))==expected


def test_stdlib_reader_rejects_group_and_child_targets():
    tree=slide();set_builds(tree,[[2,4],[3]])
    objects=tree.find('p:cSld/p:spTree',NS)
    parent=etree.SubElement(objects,'{'+NS['p']+'}grpSp')
    props=etree.SubElement(parent,'{'+NS['p']+'}nvGrpSpPr')
    etree.SubElement(props,'{'+NS['p']+'}cNvPr',id='5')
    parent.append(objects[0])
    tree.find('.//p:spTgt[@spid="3"]',NS).set('spid','5')
    assert appear_steps(tree) is None
    assert appear_steps(StdET.fromstring(etree.tostring(tree))) is None


@pytest.mark.parametrize('mutation',['automatic','delayed','after_previous','paragraph','missing_shape'])
def test_simulation_does_not_invent_click_order_for_unverified_timing(mutation):
    tree=slide();set_builds(tree,[[2,4],[3]])
    effect=tree.find('.//p:cTn[@presetClass="entr"]',NS)
    if mutation=='automatic':
        main=tree.find('.//p:cTn[@nodeType="mainSeq"]',NS)
        main.find('p:childTnLst/p:par/p:cTn/p:stCondLst/p:cond',NS).set('delay','0')
    elif mutation=='delayed':effect.find('p:stCondLst/p:cond',NS).set('delay','250')
    elif mutation=='after_previous':effect.set('nodeType','afterEffect')
    elif mutation=='paragraph':etree.SubElement(effect.find('.//p:spTgt',NS),'{'+NS['p']+'}txEl')
    else:effect.find('.//p:spTgt',NS).set('spid','999')
    assert appear_steps(tree) is None
    assert appear_steps(StdET.fromstring(etree.tostring(tree))) is None


@pytest.mark.parametrize('steps',[[[99]],[[2],[2]],[],[[]],[[True]]])
def test_invalid_targets_do_not_modify_slide(steps):
    tree=slide();before=etree.tostring(tree)
    with pytest.raises(ValueError):set_builds(tree,steps)
    assert etree.tostring(tree)==before
