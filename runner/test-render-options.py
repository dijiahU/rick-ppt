import json
import unittest
from render_options import pdf_filter,requested_page


def args(value):return ['--convert-to',value,'--outdir','/task/out','/task/input.pptx']


class PdfOptionsTests(unittest.TestCase):
    def test_full_and_single_page_options_roundtrip(self):
        self.assertIsNone(requested_page(args('pdf')))
        self.assertIsNone(requested_page(args(pdf_filter())))
        for page in (1,13,200):self.assertEqual(requested_page(args(pdf_filter(page))),page)

    def test_ranges_and_untrusted_filter_properties_are_rejected(self):
        for value in ('0','01','-1','201','1-15','1,2','x'):
            with self.subTest(value=value),self.assertRaises(ValueError):
                requested_page(args('pdf:impress_pdf_Export:'+json.dumps({'PageRange':{'type':'string','value':value}})))
        for value in ('pdf:writer_pdf_Export','pdf:impress_pdf_Export:[]',
                      'pdf:impress_pdf_Export:{"EncryptFile":true}',
                      'pdf:impress_pdf_Export:{"PageRange":null}',
                      'pdf:impress_pdf_Export:{"ExportHiddenSlides":null}',
                      'pdf:impress_pdf_Export:{"PageRange":{"type":"long","value":2}}'):
            with self.subTest(value=value),self.assertRaises(ValueError):requested_page(args(value))

    def test_caller_cannot_disable_hidden_slide_support(self):
        with self.assertRaises(ValueError):
            requested_page(args('pdf:impress_pdf_Export:{"ExportHiddenSlides":{"type":"boolean","value":"false"}}'))


if __name__=='__main__':unittest.main()
