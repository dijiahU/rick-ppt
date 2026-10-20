"""Exercise actual cross-viewer failure modes without claiming WPS playback."""
import hashlib
import json
from pathlib import Path
from unittest import mock

from lxml import etree
import pytest

import compatibility
import native_canvas as canvas
from native_structure import anchor, connection_point, group, shape
from pptx_core.common import NS, PptxError
from pptx_core.package import export, unpack

EMU=914400
FONT=next((p for p in (Path('/System/Library/Fonts/Supplemental/Arial.ttf'),
                      Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')) if p.is_file()),None)


@pytest.fixture
def ws(tmp_path):
    return unpack(Path(canvas.__file__).parent.parent/'assets/blank.pptx',tmp_path/'projects')


def obj(ws,x=1,geometry='rect',box=None):
    return canvas.add_shape(ws.root,1,box or (x,1,2,1),geometry=geometry,
                            fill=None,stroke='223344',line_width=1,name='Node')


def connect(ws,a,b,points=(3,1.5,4,1.5),sites=(3,1)):
    return canvas.add_connector(ws.root,1,a,b,points=points,start_site=sites[0],end_site=sites[1],
                                ink='223344',line_width=1,arrow='triangle',name='Relationship')


def test_ellipse_uses_eight_sites_and_rejects_rectangle_site_assumption_without_writes(ws):
    a,b=obj(ws,geometry='ellipse'),obj(ws,4,geometry='ellipse')
    path=ws.root/'ppt/slides/slide1.xml';before=path.read_bytes()
    with pytest.raises(PptxError,match='disagrees'):
        connect(ws,a,b)
    assert path.read_bytes()==before
    connect(ws,a,b,sites=(6,2))
    report=compatibility.inspect(ws.root)
    assert report['verified_binding_geometry_count']==1 and report['finding_count']==0


def test_invalid_geometry_site_does_not_change_either_binding(ws):
    a,b=obj(ws),obj(ws,4);link=connect(ws,a,b)
    tree=canvas.parse(ws.root/'ppt/slides/slide1.xml');before=etree.tostring(tree)
    with pytest.raises(PptxError,match='4 connection sites'):
        anchor(tree,link['shape_id'],a['shape_id'],b['shape_id'],3,4)
    assert etree.tostring(tree)==before


def test_group_scale_flip_and_rotation_are_applied_before_endpoint_comparison(ws):
    a=obj(ws);decoration=obj(ws,box=(1,1,.2,.2))
    g=canvas.semantic_group(ws.root,1,[a,decoration],name='Rotated process')
    path=ws.root/'ppt/slides/slide1.xml';tree=canvas.parse(path)
    xf=shape(tree,g['shape_id']).find('p:grpSpPr/a:xfrm',NS)
    xf.set('rot','5400000');xf.set('flipH','1')
    for tag,values in [('off',{'x':4*EMU,'y':3*EMU}),('ext',{'cx':4*EMU,'cy':2*EMU})]:
        for key,value in values.items():xf.find('a:'+tag,NS).set(key,str(value))
    canvas.write(path,tree)
    b=obj(ws,box=(10,1.5,2,1))
    connect(ws,a,b,points=(6,2,10,2))
    assert compatibility.inspect(ws.root)['verified_binding_geometry_count']==1


def test_connector_reverse_direction_uses_flips_and_preserves_arrow_end(ws):
    a,b=obj(ws,4),obj(ws)
    link=connect(ws,a,b,points=(4,1.5,3,1.5),sites=(1,3))
    node=shape(canvas.parse(ws.root/'ppt/slides/slide1.xml'),link['shape_id'])
    assert node.find('p:spPr/a:xfrm',NS).get('flipH')=='1'
    assert node.find('p:spPr/a:ln/a:tailEnd',NS).get('type')=='triangle'
    assert compatibility.inspect(ws.root)['finding_count']==0


def test_unknown_group_sites_are_not_silently_guessed(ws):
    a,b=obj(ws),obj(ws,4);g=canvas.semantic_group(ws.root,1,[a,b],name='Context')
    target=obj(ws,8)
    path=ws.root/'ppt/slides/slide1.xml';before=path.read_bytes()
    with pytest.raises(PptxError,match='anchor to the intended child'):
        connect(ws,g,target,points=(6,1.5,8,1.5))
    assert path.read_bytes()==before


def test_diagonal_ellipse_site_is_not_a_bounding_box_corner(ws):
    a=obj(ws,geometry='ellipse')
    node=shape(canvas.parse(ws.root/'ppt/slides/slide1.xml'),a['shape_id'])
    x,y=connection_point(node,1)
    assert x==pytest.approx(1.292893218*EMU,abs=1)
    assert y==pytest.approx(1.146446609*EMU,abs=1)


def test_triangle_uses_its_six_actual_sites_and_adjusted_vertex(ws):
    a=obj(ws,geometry='triangle')
    node=shape(canvas.parse(ws.root/'ppt/slides/slide1.xml'),a['shape_id'])
    assert connection_point(node,5)==(2.5*EMU,1.5*EMU)
    guides=node.find('p:spPr/a:prstGeom/a:avLst',NS)
    etree.SubElement(guides,'{'+NS['a']+'}gd',name='adj',fmla='val 20000')
    assert connection_point(node,0)==(1.4*EMU,1*EMU)
    with pytest.raises(PptxError,match='6 connection sites'):connection_point(node,6)


def test_legacy_multi_target_entrance_is_reported_with_exact_target_ids(ws):
    a,b=obj(ws),obj(ws,4)
    canvas.reveal(ws.root,1,[[a,b]])
    path=ws.root/'ppt/slides/slide1.xml';tree=canvas.parse(path)
    rows=tree.findall('.//p:cTn[@presetClass="entr"]',NS)
    rows[0].find('p:childTnLst',NS).append(rows[1].find('p:childTnLst/p:set',NS))
    rows[1].getparent().getparent().remove(rows[1].getparent())
    canvas.write(path,tree);before=path.read_bytes()
    report=compatibility.inspect(ws.root)
    finding=next(f for f in report['findings'] if f['code']=='multi_target_entrance')
    assert finding['target_ids']==[str(a['shape_id']),str(b['shape_id'])]
    assert path.read_bytes()==before


@pytest.mark.skipif(FONT is None,reason='Real font unavailable')
def test_missing_glyph_rejected_before_text_is_written(ws):
    path=ws.root/'ppt/slides/slide1.xml';before=path.read_bytes()
    with pytest.raises(ValueError,match='U\\+10FFFF'):
        canvas.add_text(ws.root,1,'Missing \U0010ffff',FONT,18,'223344',x=1,y=1,width=5,max_height=2)
    assert path.read_bytes()==before


@pytest.mark.skipif(FONT is None,reason='Real font unavailable')
def test_text_explicitly_disables_autofit_and_pins_paragraph_end_fonts(ws):
    h=canvas.add_text(ws.root,1,'First\nSecond',FONT,18,'223344',x=1,y=1,width=5,max_height=2)
    node=shape(canvas.parse(ws.root/'ppt/slides/slide1.xml'),h['shape_id'])
    assert node.find('p:txBody/a:bodyPr/a:noAutofit',NS) is not None
    for end in node.findall('p:txBody/a:p/a:endParaRPr',NS):
        assert end.find('a:latin',NS).get('typeface')==h['latin_family']
        assert end.find('a:ea',NS).get('typeface')==h['font_family']


def test_existing_mismatched_binding_is_reported_read_only_not_repaired_or_blocked(ws,tmp_path):
    a,b=obj(ws,geometry='ellipse'),obj(ws,4,geometry='ellipse');link=connect(ws,a,b,sites=(6,2))
    path=ws.root/'ppt/slides/slide1.xml';tree=canvas.parse(path)
    shape(tree,link['shape_id']).find('p:nvCxnSpPr/p:cNvCxnSpPr/a:stCxn',NS).set('idx','3')
    canvas.write(path,tree);before=path.read_bytes()
    report=compatibility.inspect(ws.root)
    assert report['findings'][0]['code']=='connector_binding'
    assert path.read_bytes()==before
    original=Path(ws.state['source']).read_bytes()
    with mock.patch('pptx_core.renderer.render_package',return_value={'pages':[]}):
        dest=export(ws,tmp_path/'result.pptx')
    assert path.read_bytes()==before and Path(ws.state['source']).read_bytes()==original
    receipt=json.loads(Path(ws.state['last_compatibility']['report']).read_text())
    assert receipt['artifact_sha256']==hashlib.sha256(dest.read_bytes()).hexdigest()
    assert receipt['finding_count']==1 and receipt['windows_wps_verified'] is False
    assert not receipt['declared_embedded_fonts']
