import io
from pathlib import Path
import tempfile
import unittest
import zipfile
from render_inputs import render_input,publish_pdf

class FrozenInputTests(unittest.TestCase):
    def test_input_bytes_survive_later_source_edit_and_preserve_font_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path=root/'candidate.pptx'
            with zipfile.ZipFile(path,'w') as z:z.writestr('ppt/slides/slide1.xml','<slide><font typeface="Arial"/><font typeface="+mn-lt"/></slide>')
            before=path.read_bytes();data,environment=render_input(root,path)
            path.write_bytes(b'later author edit')
            self.assertEqual(data,before);self.assertEqual(environment['requested_fonts'],['Arial'])
            self.assertFalse(environment['powerpoint_playback_verified'])

    def test_entities_and_oversized_xml_are_rejected(self):
        for xml in ('<!DOCTYPE x [<!ENTITY a "bad">]><x>&a;</x>',b' '* (8*1024*1024+1)):
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp);path=root/'candidate.pptx'
                with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('ppt/slides/slide1.xml',xml)
                with self.assertRaises(ValueError):render_input(root,path)

    def test_output_publication_replaces_leaf_symlink_without_following_it(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);out=root/'output';out.mkdir();private=root/'private';private.write_bytes(b'keep')
            (out/'candidate.pdf').symlink_to(private)
            publish_pdf(root,out,'candidate.pdf',b'%PDF-fixture')
            self.assertEqual(private.read_bytes(),b'keep');self.assertFalse((out/'candidate.pdf').is_symlink())
            alias=root/'alias';alias.symlink_to(out,target_is_directory=True)
            with self.assertRaises(OSError):publish_pdf(root,alias,'other.pdf',b'%PDF-fixture')

if __name__=='__main__':unittest.main()
