"""Real font files, glyph coverage, immutable recovery and broker boundaries."""
import io
import json
from pathlib import Path
import tempfile
import time
import sys
import unittest
import zipfile
from unittest.mock import patch
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
import font_assets as f
from font_broker import FontBroker

def font_bytes(family='Test Latin',chars='ABC123'):
    builder=FontBuilder(1000,isTTF=True);glyphs=['.notdef']+['g'+str(ord(c)) for c in chars]
    builder.setupGlyphOrder(glyphs);builder.setupCharacterMap({ord(c):'g'+str(ord(c)) for c in chars})
    pen=TTGlyphPen(None);pen.moveTo((50,0));pen.lineTo((450,0));pen.lineTo((450,700));pen.lineTo((50,700));pen.closePath();glyph=pen.glyph()
    builder.setupGlyf({x:glyph for x in glyphs});builder.setupHorizontalMetrics({x:(500,0) for x in glyphs});builder.setupHorizontalHeader(ascent=800,descent=-200)
    builder.setupNameTable(dict(familyName=family,styleName='Regular',uniqueFontIdentifier=family,fullName=family+' Regular',psName=family.replace(' ','')+'-Regular'))
    builder.setupOS2(sTypoAscender=800,sTypoDescender=-200,usWinAscent=800,usWinDescent=200,fsType=0);builder.setupPost();builder.setupMaxp();out=io.BytesIO();builder.save(out);return out.getvalue()

class FontsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.font=font_bytes();self.license=b'SIL OPEN FONT LICENSE Version 1.1 test fixture'
        self.spec={'url':'https://fonts.example/font.ttf','license_url':'https://fonts.example/OFL.txt','family':'Test Latin','weight':400}
    def tearDown(self):self.tmp.cleanup()
    def download(self,url):return (self.license if url.endswith('.txt') else self.font,url,'')
    def install(self,**kwargs):return f.install(self.root,'fixture',descriptor=self.spec,downloader=self.download,**kwargs)
    def test_real_font_metadata_hash_license_and_missing_characters(self):
        meta=self.install(text='AB中');self.assertEqual(meta['family'],'Test Latin');self.assertEqual(meta['missing_characters'],['中']);self.assertEqual(meta['weight'],400)
        self.assertEqual(f.verified_files(self.root)[meta['file']],self.font);self.assertTrue(meta['editable_embedding_allowed'])
    def test_reuse_does_not_download_and_modified_bytes_are_rejected(self):
        meta=self.install()
        def forbidden(url):raise AssertionError('Unnecessary network')
        self.assertTrue(f.install(self.root,'fixture',downloader=forbidden)['cache_hit'])
        (self.root/meta['file']).write_bytes(font_bytes('Changed'))
        with self.assertRaises(ValueError):f.install(self.root,'fixture',downloader=forbidden)
        with self.assertRaises(ValueError):f.verified_files(self.root)
    def test_cjk_and_latin_pair_coverage_is_actual_not_family_claim(self):
        self.install();self.font=font_bytes('Test Chinese','中文字');self.spec={**self.spec,'family':'Test Chinese'}
        f.install(self.root,'cjk',descriptor=self.spec,downloader=self.download)
        self.assertTrue(f.coverage(self.root,['fixture','cjk'],'中文 ABC 123')['ok'])
        self.assertEqual(f.coverage(self.root,['fixture','cjk'],'中文😀')['missing_characters'],['😀'])
    def test_html_and_missing_license_or_mismatched_family_are_rejected(self):
        self.font=b'<html>not a font</html>'
        with self.assertRaises(ValueError):self.install()
        self.font=font_bytes();self.license=b'No license'
        with self.assertRaises(ValueError):self.install()
        self.license=b'SIL OPEN FONT LICENSE';self.spec['family']='Pretend Font'
        with self.assertRaises(ValueError):self.install()
        self.assertFalse((self.root/'fonts/index.json').exists())
    def test_parent_escape_leaf_and_directory_symlinks_are_denied(self):
        private=self.root/'private';private.write_bytes(b'unchanged');(self.root/'alias').symlink_to(private)
        with self.assertRaises(ValueError):f.read(self.root,'alias')
        with self.assertRaises(ValueError):f.publish(self.root,'../escape',b'bad')
        (self.root/'fonts').symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError):self.install()
        self.assertEqual(private.read_bytes(),b'unchanged')
    def test_recovery_keeps_font_and_license_checksums(self):
        self.install();other=self.root/'recovered';other.mkdir();f.copy_fonts(self.root,other)
        self.assertEqual(f.verified_files(self.root),f.verified_files(other));self.assertIn(str(other/'fonts'),(other/'fonts.conf').read_text())
        (self.root/'fonts/fixture-OFL.txt').write_bytes(b'changed license')
        with self.assertRaises(ValueError):f.copy_fonts(self.root,other)
    def test_broker_queue_downloads_font_and_publishes_verified_reply(self):
        queue=self.root/'font-requests';queue.mkdir();ident='a'*32
        (queue/(ident+'.request.json')).write_text(json.dumps({'font_id':'fixture',**self.spec,'text':'ABC中'}))
        broker=FontBroker(self.root)
        try:
            with patch('font_broker.download',side_effect=self.download):
                until=time.monotonic()+3
                while time.monotonic()<until and not (queue/(ident+'.reply.json')).exists():broker.poll();time.sleep(.01)
            reply=json.loads((queue/(ident+'.reply.json')).read_text());self.assertTrue(reply['ok']);self.assertEqual(reply['font']['missing_characters'],['中'])
            self.assertEqual(f.verified_files(self.root)[reply['font']['file']],self.font)
        finally:broker.close()
    def test_mixed_native_text_uses_medium_and_semibold_legacy_names(self):
        from fontTools.ttLib import TTFont
        scripts=Path(__file__).parents[1]/'pptx-agent/skills/pptx/scripts';sys.path.insert(0,str(scripts));import native_canvas as canvas
        faces=[]
        for legacy,preferred,style,weight,chars in [('Test CJK Medium','Test CJK','Medium',500,'中文'),('Test Latin SemiBold','Test Latin','SemiBold',600,'English2026 ')]:
            face=TTFont(io.BytesIO(font_bytes(legacy,''.join(dict.fromkeys(chars)))))
            face['name'].setName(preferred,16,3,1,0x409);face['name'].setName(style,17,3,1,0x409);face['OS/2'].usWeightClass=weight
            path=self.root/(str(weight)+'.ttf');face.save(path);faces.append(path)
        workspace=self.root/'workspace';workspace.mkdir()
        with zipfile.ZipFile(scripts.parent/'assets/blank.pptx') as z:z.extractall(workspace)
        result=canvas.add_text(workspace,1,'中文 English 2026',faces[0],18,'202020',x=1,y=1,width=5,max_height=2,latin_font=faces[1])
        self.assertEqual(result['font_family'],'Test CJK Medium');self.assertEqual(result['latin_family'],'Test Latin SemiBold')
        tree=canvas.parse(workspace/'ppt/slides/slide1.xml');shape=next(x for x in tree.iter('{'+canvas.P+'}sp') if x.find('{'+canvas.P+'}nvSpPr/{'+canvas.P+'}cNvPr').get('id')==str(result['shape_id']))
        self.assertEqual(''.join(x.text for x in shape.iter('{'+canvas.A+'}t')),'中文 English 2026')
        self.assertGreater(len(list(shape.iter('{'+canvas.A+'}r'))),1)
        self.assertTrue(all(x.get('typeface')=='Test CJK Medium' for x in shape.iter('{'+canvas.A+'}ea')))
        self.assertTrue(all(x.get('typeface')=='Test Latin SemiBold' for x in shape.iter('{'+canvas.A+'}latin')))
        self.assertTrue(all(x.get('b')=='0' for x in shape.iter('{'+canvas.A+'}rPr')))
    def test_theme_change_keeps_native_slide_bytes_and_requires_available_faces(self):
        from lxml import etree as E
        self.install();workspace=self.root/'workspace';workspace.mkdir()
        with zipfile.ZipFile(Path(__file__).parents[1]/'pptx-agent/skills/pptx/assets/blank.pptx') as z:z.extractall(workspace)
        slide=(workspace/'ppt/slides/slide1.xml').read_bytes()
        with self.assertRaises(ValueError):f.set_theme(self.root,workspace,'Unavailable','Test Latin')
        f.set_theme(self.root,workspace,'Test Latin','Test Latin');self.assertEqual((workspace/'ppt/slides/slide1.xml').read_bytes(),slide)
        ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
        tree=E.parse(str(workspace/'ppt/theme/theme1.xml'))
        self.assertTrue(all(x.get('typeface')=='Test Latin' for x in tree.findall('.//a:fontScheme/*/a:latin',ns)))

if __name__=='__main__':unittest.main()
