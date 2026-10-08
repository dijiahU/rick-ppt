import json,sys,tempfile,unittest
from pathlib import Path
from lxml import etree
from PIL import Image

SCRIPTS=Path(__file__).resolve().parents[1]/'pptx-agent/skills/pptx/scripts'
sys.path.insert(0,str(SCRIPTS))
from native_structure import group,anchor,shape,bounds,identity
from pptx_core.common import NS,PptxError
from pptx_core.package import unpack,pack
from pptx_core.validator import validate
from review_packet import collect


def rectangle(identifier,x,text):
    node=etree.Element('{'+NS['p']+'}sp')
    nv=etree.SubElement(node,'{'+NS['p']+'}nvSpPr')
    etree.SubElement(nv,'{'+NS['p']+'}cNvPr',id=str(identifier),name=text)
    etree.SubElement(nv,'{'+NS['p']+'}cNvSpPr');etree.SubElement(nv,'{'+NS['p']+'}nvPr')
    sp=etree.SubElement(node,'{'+NS['p']+'}spPr');xf=etree.SubElement(sp,'{'+NS['a']+'}xfrm')
    etree.SubElement(xf,'{'+NS['a']+'}off',x=str(x),y='1000000');etree.SubElement(xf,'{'+NS['a']+'}ext',cx='2000000',cy='1000000')
    geo=etree.SubElement(sp,'{'+NS['a']+'}prstGeom',prst='rect');etree.SubElement(geo,'{'+NS['a']+'}avLst')
    fill=etree.SubElement(sp,'{'+NS['a']+'}solidFill');etree.SubElement(fill,'{'+NS['a']+'}srgbClr',val='B8D8F0')
    tx=etree.SubElement(node,'{'+NS['p']+'}txBody');etree.SubElement(tx,'{'+NS['a']+'}bodyPr');etree.SubElement(tx,'{'+NS['a']+'}lstStyle')
    p=etree.SubElement(tx,'{'+NS['a']+'}p');r=etree.SubElement(p,'{'+NS['a']+'}r');etree.SubElement(r,'{'+NS['a']+'}rPr',sz='2400')
    etree.SubElement(r,'{'+NS['a']+'}t').text=text
    return node


def connector(identifier=5):
    node=etree.Element('{'+NS['p']+'}cxnSp');nv=etree.SubElement(node,'{'+NS['p']+'}nvCxnSpPr')
    etree.SubElement(nv,'{'+NS['p']+'}cNvPr',id=str(identifier),name='Input to output')
    etree.SubElement(nv,'{'+NS['p']+'}cNvCxnSpPr');etree.SubElement(nv,'{'+NS['p']+'}nvPr')
    sp=etree.SubElement(node,'{'+NS['p']+'}spPr');xf=etree.SubElement(sp,'{'+NS['a']+'}xfrm')
    etree.SubElement(xf,'{'+NS['a']+'}off',x='3000000',y='1500000');etree.SubElement(xf,'{'+NS['a']+'}ext',cx='1000000',cy='0')
    geo=etree.SubElement(sp,'{'+NS['a']+'}prstGeom',prst='line');etree.SubElement(geo,'{'+NS['a']+'}avLst')
    line=etree.SubElement(sp,'{'+NS['a']+'}ln',w='25400')
    fill=etree.SubElement(line,'{'+NS['a']+'}solidFill');etree.SubElement(fill,'{'+NS['a']+'}srgbClr',val='202020')
    etree.SubElement(line,'{'+NS['a']+'}tailEnd',type='triangle')
    return node


def fixture(root):
    ws=unpack(SCRIPTS.parent/'assets/blank.pptx',root/'workspaces')
    path=ws.root/'ppt/slides/slide1.xml';tree=etree.parse(str(path));st=tree.find('p:cSld/p:spTree',NS)
    for node in [rectangle(2,1000000,'Input'),rectangle(3,4000000,'Output'),connector()]:st.append(node)
    return ws,path,tree


class NativeTests(unittest.TestCase):
    def test_group_preserves_child_coordinates_ids_and_z_order(self):
        with tempfile.TemporaryDirectory() as temp:
            ws,path,tree=fixture(Path(temp));before={i:etree.tostring(shape(tree,i)) for i in (2,3)}
            ident=group(tree,[3,2],'Process nodes');grp=shape(tree,ident)
            self.assertEqual([identity(n).get('id') for n in list(grp)[2:]],['2','3'])
            for i in (2,3):self.assertEqual(etree.tostring(shape(tree,i)),before[i])
            self.assertEqual(bounds(grp),(1000000,1000000,5000000,1000000))
            path.write_bytes(etree.tostring(tree,xml_declaration=True,encoding='UTF-8',standalone=True));validate(ws.root).require()

    def test_nonadjacent_or_cross_group_members_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            ws,path,tree=fixture(Path(temp));before=etree.tostring(tree)
            with self.assertRaises(PptxError):group(tree,[2,5],'Would reorder output')
            self.assertEqual(etree.tostring(tree),before)
            ident=group(tree,[2,3],'Nodes')
            with self.assertRaises(PptxError):group(tree,[2,5],'Mixed parents')

    def test_native_connector_anchors_keep_geometry_and_endpoint_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            ws,path,tree=fixture(Path(temp));geometry=bounds(shape(tree,5))
            anchor(tree,5,2,3,3,1)
            self.assertEqual(bounds(shape(tree,5)),geometry)
            self.assertEqual(shape(tree,5).find('p:nvCxnSpPr/p:cNvCxnSpPr/a:stCxn',NS).get('id'),'2')
            path.write_bytes(etree.tostring(tree,xml_declaration=True,encoding='UTF-8',standalone=True));validate(ws.root).require()
            with self.assertRaises(PptxError):anchor(tree,2,3,5,0,0)

    def test_reading_packet_records_semantic_structure_and_scaled_view(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);ws,path,tree=fixture(root)
            group(tree,[2,3],'Process nodes');anchor(tree,5,2,3,3,1)
            path.write_bytes(etree.tostring(tree,xml_declaration=True,encoding='UTF-8',standalone=True))
            image=root/'page.png';Image.new('RGB',(1920,1080),'white').save(image)
            packet=collect(ws.home,{'pages':[str(image)]},root/'packet');slide=packet['slides'][0]
            self.assertEqual(slide['editability'],{'groups':1,'connectors':1,'unanchored_connector_ids':[]})
            self.assertEqual(slide['reading_preview']['width'],900)
            text=next(s for s in slide['shapes'] if s['id']=='2')
            self.assertIsNotNone(text['group_id']);self.assertEqual(text['explicit_font_points'],[24.0])
            with Image.open(root/'packet/reading-page-1.png') as reading:self.assertEqual(reading.size,(900,506))

if __name__=='__main__':unittest.main()
