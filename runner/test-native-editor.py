"""Deterministic native edits on genuine PPTX packages; no production calls."""
import copy,hashlib,io,json,os,sys,tempfile,unittest,zipfile,uuid
from pathlib import Path
from PIL import Image
from lxml import etree as E
from native_editor import apply,xml,NS,content
from canvas_snapshot import native_pages

ROOT=Path(__file__).resolve().parents[1];BLANK=ROOT/'pptx-agent/skills/pptx/assets/blank.pptx'
P=NS['p'];A=NS['a'];R=NS['r'];CT='http://schemas.openxmlformats.org/package/2006/content-types';REL='http://schemas.openxmlformats.org/package/2006/relationships'
def picture(color):
    out=io.BytesIO();Image.new('RGB',(120,80),color).save(out,format='PNG');return out.getvalue()
def shape(i,text,x,y,w=4000000,h=700000):return f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="Object {i}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="F2F5EC"/></a:solidFill><a:ln><a:noFill/></a:ln></p:spPr><p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:pPr/><a:r><a:rPr sz="2800"><a:solidFill><a:srgbClr val="263C34"/></a:solidFill><a:latin typeface="Times New Roman"/><a:ea typeface="SimSun"/></a:rPr><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp>'
def fixture():
    source=zipfile.ZipFile(BLANK);parts={n:source.read(n) for n in source.namelist()}
    objects=shape(2,'Original title',700000,500000)+shape(3,'Native click target',700000,1500000)+shape(11,'Movable text',6500000,500000,4000000)
    for i,x in [(4,700000),(8,3200000)]:objects+=f'<p:pic><p:nvPicPr><p:cNvPr id="{i}" name="Shared picture {i}"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr><p:blipFill><a:blip r:embed="rIdTestPic"/><a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr><a:xfrm><a:off x="{x}" y="2800000"/><a:ext cx="2200000" cy="1400000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'
    rows=''.join('<a:tr h="500000">'+''.join(f'<a:tc><a:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr sz="2000"/><a:t>Cell {r}:{c}</a:t></a:r></a:p></a:txBody><a:tcPr/></a:tc>' for c in range(2))+'</a:tr>' for r in range(2))
    objects+=f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="5" name="Native table"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr><p:xfrm><a:off x="6500000" y="2800000"/><a:ext cx="4000000" cy="1000000"/></p:xfrm><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table"><a:tbl><a:tblPr firstRow="1"/><a:tblGrid><a:gridCol w="2000000"/><a:gridCol w="2000000"/></a:tblGrid>{rows}</a:tbl></a:graphicData></a:graphic></p:graphicFrame>'
    objects+='<p:grpSp><p:nvGrpSpPr><p:cNvPr id="6" name="Scaled group"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="700000" y="4900000"/><a:ext cx="6000000" cy="1000000"/><a:chOff x="0" y="0"/><a:chExt cx="3000000" cy="500000"/></a:xfrm></p:grpSpPr>'+shape(7,'Grouped text',0,0,2000000,400000)+'</p:grpSp>'
    parts['ppt/slides/slide1.xml']=(f'<p:sld xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}"><p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="FAFBF7"/></a:solidFill><a:effectLst/></p:bgPr></p:bg><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>{objects}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr><p:timing><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst><p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst><p:par><p:cTn id="3" fill="hold"><p:stCondLst><p:cond delay="indefinite"/></p:stCondLst><p:childTnLst><p:par><p:cTn id="4" presetID="1" presetClass="entr" presetSubtype="0" fill="hold" nodeType="clickEffect"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst><p:animEffect transition="in" filter="fade"><p:cBhvr><p:cTn id="5" dur="300"/><p:tgtEl><p:spTgt spid="3"/></p:tgtEl></p:cBhvr></p:animEffect></p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:seq></p:childTnLst></p:cTn></p:par></p:tnLst><p:bldLst><p:bldP spid="3" grpId="0"/></p:bldLst></p:timing></p:sld>').encode()
    rels=xml(parts['ppt/slides/_rels/slide1.xml.rels']);E.SubElement(rels,'{'+REL+'}Relationship',Id='rIdTestPic',Type=R+'/image',Target='../media/shared.png');parts['ppt/slides/_rels/slide1.xml.rels']=E.tostring(rels);parts['ppt/media/shared.png']=picture('#99bbaa')
    types=xml(parts['[Content_Types].xml'])
    if not any(n.get('Extension')=='png' for n in types):E.SubElement(types,'{'+CT+'}Default',Extension='png',ContentType='image/png')
    parts['[Content_Types].xml']=E.tostring(types)
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in parts.items():z.writestr(n,b)
    return out.getvalue()
PATCHES=[{'page':1,'objectId':'2','text':'Edited native title','fontSize':30,'bold':True,'fontColor':'215743','fontFace':'Times New Roman','align':'ctr','fill':'E1ECD8'}, {'page':1,'objectId':'11','box':{'x':.52,'y':.15,'width':.36,'height':.13},'rotation':3,'layer':'front'}, {'page':1,'objectId':'4','crop':{'l':.05,'r':.1,'t':.05,'b':.05},'image':{'id':'testpic'}},{'page':1,'objectId':'5','cells':[{'row':1,'column':1,'text':'Edited cell'}]},{'page':1,'objectId':'page','background':'F8F4E9'}]
class EditorTests(unittest.TestCase):
    def test_native_parts_scope_and_animation(self):
        before=fixture();after,affected=apply(before,PATCHES,{'testpic':picture('#ca815e')});self.assertEqual(affected,[1]);self.assertEqual(after,apply(before,PATCHES,{'testpic':picture('#ca815e')})[0])
        with zipfile.ZipFile(io.BytesIO(before)) as a,zipfile.ZipFile(io.BytesIO(after)) as b:
            for name in a.namelist():
                if name not in ('ppt/slides/slide1.xml','ppt/slides/_rels/slide1.xml.rels','[Content_Types].xml'):self.assertEqual(a.read(name),b.read(name),name)
            original=xml(a.read('ppt/slides/slide1.xml'));tree=xml(b.read('ppt/slides/slide1.xml'));self.assertEqual(E.tostring(original.find('p:timing',NS)),E.tostring(tree.find('p:timing',NS)))
            pics=tree.findall('.//p:pic',NS);self.assertNotEqual(pics[0].find('p:blipFill/a:blip',NS).get('{'+R+'}embed'),pics[1].find('p:blipFill/a:blip',NS).get('{'+R+'}embed'))
            self.assertEqual(content(tree.find('.//a:tbl/a:tr[2]/a:tc[2]/a:txBody',NS)),'Edited cell')
        objects=native_pages(after)[0]['objects'];self.assertEqual(next(o for o in objects if o['id']=='2')['text'],'Edited native title')
    def test_preserves_mixed_run_styles(self):
        tx=xml(f'<p:txBody xmlns:p="{P}" xmlns:a="{A}"><a:bodyPr/><a:p><a:r><a:rPr b="1"/><a:t>Bold</a:t></a:r><a:r><a:rPr i="1"/><a:t> plain</a:t></a:r></a:p></p:txBody>'.encode())
        from native_editor import replace_text
        replace_text(tx,'Bold new plain');self.assertEqual(content(tx),'Bold new plain');runs=tx.findall('a:p/a:r',NS);self.assertEqual(runs[0].find('a:rPr',NS).get('b'),'1');self.assertEqual(runs[-1].find('a:rPr',NS).get('i'),'1')
    def test_group_coordinates(self):
        source=fixture();original=next(o for o in native_pages(source)[0]['objects'] if o['id']=='7');box={**original['bounds'],'x':.2};out,_=apply(source,[{'page':1,'objectId':'7','box':box}]);new=next(o for o in native_pages(out)[0]['objects'] if o['id']=='7');self.assertAlmostEqual(new['bounds']['x'],.2,places=6)
    def test_animated_delete_rejected_and_plain_delete_safe(self):
        source=fixture()
        with self.assertRaisesRegex(ValueError,'Animated'):apply(source,[{'page':1,'objectId':'3','delete':True}])
        out,_=apply(source,[{'page':1,'objectId':'11','delete':True}]);self.assertFalse(any(o['id']=='11' for o in native_pages(out)[0]['objects']))
    def test_text_empty_is_still_editable(self):
        out,_=apply(fixture(),[{'page':1,'objectId':'2','text':''}]);obj=next(o for o in native_pages(out)[0]['objects'] if o['id']=='2');self.assertTrue(obj['textEditable']);self.assertEqual(obj['text'],'')
    def test_bad_picture_leaves_source_untouched(self):
        with self.assertRaises(Exception):apply(fixture(),[PATCHES[2]],{'testpic':b'not an image'})
if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--fixtures':
        root=Path(sys.argv[2]);root.mkdir(parents=True,exist_ok=True);before=fixture();after,_=apply(before,PATCHES,{'testpic':picture('#ca815e')});(root/'baseline.pptx').write_bytes(before);(root/'edited.pptx').write_bytes(after);(root/'patches.json').write_text(json.dumps(PATCHES))
        for name,data,at in [('baseline',before,100),('edited',after,200)]:
            pages=native_pages(data)
            for page in pages:page['imageSha256']='0'*64
            sha=hashlib.sha256(data).hexdigest()
            snapshot={'schema':'rickppt-canvas/v1','sha256':sha,'versionId':str(uuid.uuid5(uuid.NAMESPACE_URL,'rickppt-test:'+sha)),'createdAt':at,'pages':pages}
            (root/(name+'-snapshot.json')).write_text(json.dumps(snapshot))
        print('Native editor fixtures and structural snapshots written; no renderer or model used')
    else:unittest.main()
