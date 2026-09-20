import importlib.util,tempfile,unittest,zipfile
from pathlib import Path
from lxml import etree as E
spec=importlib.util.spec_from_file_location('launch',Path(__file__).with_name('launch.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class LaunchTest(unittest.TestCase):
 def test_relinks_all_scenes_without_touching_content(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);source=root/'source.pptx';target=root/'session.pptx'
   with zipfile.ZipFile(source,'w') as z:
    z.writestr('ppt/slides/slide1.xml',b'preserved native content')
    for n in range(1,21):z.writestr(f'ppt/slides/_rels/slide{n}.xml.rels',f'<Relationships><Relationship Id="rIdLocalInteractive" Target="http://127.0.0.1:1/preview.html?deck=test&amp;scene=scene-{n}"/><Relationship Id="keep" Target="unchanged"/></Relationships>')
   original=source.read_bytes();self.assertEqual(m.materialize(source,target,'http://127.0.0.1:54321'),20)
   self.assertEqual(source.read_bytes(),original)
   with zipfile.ZipFile(target) as z:
    self.assertEqual(z.read('ppt/slides/slide1.xml'),b'preserved native content')
    for n in range(1,21):
     x=E.fromstring(z.read(f'ppt/slides/_rels/slide{n}.xml.rels'));self.assertEqual(x[0].get('Target'),f'http://127.0.0.1:54321/preview.html?deck=test&scene=scene-{n}');self.assertEqual(x[1].get('Target'),'unchanged')
   with self.assertRaises(FileExistsError):m.materialize(source,target,'http://127.0.0.1:54321')
   with self.assertRaises(ValueError):m.materialize(source,root/'bad.pptx','http://example.com:80')
if __name__=='__main__':unittest.main()
