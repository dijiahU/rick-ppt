"""Exercise real native object capabilities and provenance notes without a model."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from lxml import etree as E
from PIL import Image

PLUGIN=Path(__file__).resolve().parents[1]/'pptx-agent'
SCRIPTS=PLUGIN/'skills/pptx/scripts';sys.path.insert(0,str(SCRIPTS))
import native_canvas as canvas
import design_references as notes
import workflow_decisions as decisions
FONT=Path('/System/Library/Fonts/Supplemental/Arial.ttf')

class NativeCanvasTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.workspace=self.root/'workspace';self.workspace.mkdir()
        with zipfile.ZipFile(PLUGIN/'skills/pptx/assets/blank.pptx') as archive:archive.extractall(self.workspace)
        Image.new('RGB',(200,100),'blue').save(self.root/'image.png')

    def test_font_measurement_prevents_real_short_box_clipping(self):
        if not FONT.is_file():self.skipTest('Installed Arial font unavailable')
        before=(self.workspace/'ppt/slides/slide1.xml').read_bytes()
        with self.assertRaisesRegex(ValueError,'allocated height'):canvas.add_text(self.workspace,1,'Inspect what happened',FONT,18,'202020',x=1,y=1,width=3,max_height=.01)
        self.assertEqual((self.workspace/'ppt/slides/slide1.xml').read_bytes(),before)
        result=canvas.add_text(self.workspace,1,'A large title with clear hierarchy',FONT,36,'202020',x=1,y=1,width=4,max_height=3)
        self.assertGreater(len(result['lines']),1)
        slide=canvas.parse(self.workspace/'ppt/slides/slide1.xml')
        sp=next(s for s in slide.iter('{'+canvas.P+'}sp') if s.find('{'+canvas.P+'}nvSpPr/{'+canvas.P+'}cNvPr').get('id')==str(result['shape_id']))
        self.assertIsNotNone(sp.find('{'+canvas.P+'}spPr/{'+canvas.A+'}noFill'))
        self.assertTrue(all(r.get('sz')=='3600' for r in sp.iter('{'+canvas.A+'}rPr')))

    def test_latin_product_name_is_not_silently_split_or_shrunk(self):
        if not FONT.is_file():self.skipTest('Installed Arial font unavailable')
        with self.assertRaisesRegex(ValueError,'Unbreakable'):canvas.text_measure('LongUnbreakableProductName',FONT,28,.4)

    def test_image_crop_and_background_preserve_text_and_actual_bytes(self):
        before=canvas.parse(self.workspace/'ppt/slides/slide1.xml')
        before_text=[x.text for x in before.iter('{'+canvas.A+'}t')]
        result=canvas.add_image(self.workspace,1,self.root/'image.png',(0,0,4,4),fit='cover',layer='back',task_root=self.root)
        tree=canvas.parse(self.workspace/'ppt/slides/slide1.xml');shapes=tree.find('{'+canvas.P+'}cSld/{'+canvas.P+'}spTree')
        self.assertEqual(shapes[2].tag,'{'+canvas.P+'}pic')
        crop=shapes[2].find('{'+canvas.P+'}blipFill/{'+canvas.A+'}srcRect');self.assertEqual(crop.attrib,{'l':'25000','r':'25000'})
        self.assertEqual([x.text for x in tree.iter('{'+canvas.A+'}t')],before_text)
        self.assertEqual((self.workspace/result['media']).read_bytes(),(self.root/'image.png').read_bytes())

    def test_outside_images_and_private_office_relationships_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'task-scoped'):canvas.add_image(self.workspace,1,self.root/'image.png',(0,0,4,4),fit='contain',layer='front',task_root=self.workspace)
        p=self.workspace/'ppt/_rels/presentation.xml.rels';tree=canvas.parse(p)
        rel=next(r for r in tree.getroot() if r.get('Type','').endswith('/slide'));rel.set('Target','../../private.xml');canvas.write(p,tree)
        with self.assertRaisesRegex(ValueError,'escaped'):canvas.page(self.workspace,1)

    def test_native_bar_chart_and_passive_workbook_preserve_exact_data(self):
        result=canvas.add_bar_chart(self.workspace,1,['Structure','Services','Other'],[12,9,21],'CNY million',['A84D3D','A84D3D','71816B'],(1,2,9,4),font_family='Arial',font_size=18)
        chart=canvas.parse(self.workspace/result['chart']);ns={'c':canvas.C}
        self.assertEqual([float(x.text) for x in chart.findall('.//c:numCache/c:pt/c:v',ns)],[12,9,21])
        self.assertEqual(chart.find('.//c:valAx/c:scaling/c:min',ns).get('val'),'0')
        slide=canvas.parse(self.workspace/'ppt/slides/slide1.xml');self.assertEqual(len(slide.findall('.//{'+canvas.C+'}chart')),1)
        with zipfile.ZipFile(self.workspace/result['workbook']) as z:
            self.assertEqual(len([n for n in z.namelist() if n.endswith('.xml')]),3)
            self.assertIn(b'spreadsheetml.sheet.main+xml',z.read('[Content_Types].xml'))
            data=E.fromstring(z.read('xl/worksheets/sheet1.xml'));ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            self.assertEqual([float(v.text) for v in data.findall('.//s:v',ns)],[12,9,21])
            self.assertNotIn(b'<f>',z.read('xl/worksheets/sheet1.xml'))

    def test_nonfinite_negative_and_untyped_chart_values_rejected(self):
        for values in [[float('nan')],[float('inf')],[-1],['12'],[0]]:
            with self.subTest(values=values),self.assertRaises(ValueError):canvas.add_bar_chart(self.workspace,1,['A'],values,'count',['202020'],(1,1,3,3),font_family='Arial',font_size=18)

    def plan(self):
        entry={'id':'R1','kind':'artwork','title':'Fixture study','creator':'Fixture creator','source':'https://museum.example/study','inspection':'local_image','evidence':'image.png','observed':'One field and a clear focal contrast.','borrowed':'Scale contrast.','applications':[{'pages':['intro'],'action':'Make the headline dominant and retain open space.'}]}
        return {'version':3,'task':{'operation':'create','viewing':'self_reading','research':'supplied_only','references':'use_available','style':'editorial','palette':'semantic','typography':'installed_role_system'},'design_direction':'One deliberately typographic statement with open space.','references':[entry],'pages':[{'id':'intro','intent':'introduce','strategy':'read','form':'typography','support':[],'composition':'type_statement','behavior':'static','assets':[{'route':'none'}],'role':'Recognize the central question.','visual_action':'Headline dominates an open field.','reference_ids':['R1']}]}

    def pack(self):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as z:
            for f in self.workspace.rglob('*'):
                if f.is_file():z.write(f,f.relative_to(self.workspace).as_posix())
        return stream.getvalue()

    def test_artwork_record_written_once_and_verified_in_actual_pptx_notes(self):
        value=self.plan();outline={'slides':[{'id':'intro'}]}
        with self.assertRaisesRegex(ValueError,'Final slide notes'):decisions.validate_plan(value,outline,root=self.root,stage='authored',artifact=self.pack(),require_click_reveal=False)
        notes.apply(self.workspace,value,outline,root=self.root,language='zh-CN')
        first=self.pack();notes.apply(self.workspace,value,outline,root=self.root,language='zh-CN')
        evidence=decisions._page_evidence(self.pack())[0]['notes']
        self.assertEqual(evidence.count(notes.BEGIN),1);self.assertIn('设计参考',evidence);self.assertIn('汲取',evidence)
        decisions.validate_plan(value,outline,root=self.root,stage='authored',artifact=self.pack(),require_click_reveal=False)
        record=decisions.design_report(value,self.pack());self.assertEqual(record['references'][0]['creator'],'Fixture creator')

    def test_existing_notes_and_nonapplying_pages_are_preserved(self):
        value=self.plan();outline={'slides':[{'id':'intro'}]}
        notes.apply(self.workspace,value,outline,root=self.root)
        note=next((self.workspace/'ppt/notesSlides').glob('notesSlide*.xml'));tree=canvas.parse(note);body=tree.find('.//{'+canvas.P+'}txBody')
        p=E.SubElement(body,'{'+canvas.A+'}p');r=E.SubElement(p,'{'+canvas.A+'}r');E.SubElement(r,'{'+canvas.A+'}t').text='Existing important source explanation'
        canvas.write(note,tree);notes.apply(self.workspace,value,outline,root=self.root)
        self.assertIn('Existing important source explanation',decisions._page_evidence(self.pack())[0]['notes'])
        value['references']=[];value['pages'][0]['reference_ids']=[]
        notes.apply(self.workspace,value,outline,root=self.root)
        text=decisions._page_evidence(self.pack())[0]['notes'];self.assertNotIn(notes.BEGIN,text);self.assertIn('Existing important source explanation',text)
        before=note.read_bytes();notes.apply(self.workspace,value,outline,root=self.root);self.assertEqual(note.read_bytes(),before)

if __name__=='__main__':unittest.main()
