"""Passive native chart attachments; no live task, model or user files."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import uuid
import zipfile

from attachments import receive,validate_content

REL='http://schemas.openxmlformats.org/package/2006/relationships'
OFFICE='http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def packed(parts):
    result=io.BytesIO()
    with zipfile.ZipFile(result,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in parts.items():z.writestr(name,data)
    return result.getvalue()


def workbook(extra=None):
    return packed({'[Content_Types].xml':'<Types/>',
                   'xl/workbook.xml':'<workbook/>',
                   'xl/worksheets/sheet1.xml':'<worksheet><sheetData/></worksheet>',
                   **(extra or {})})


def presentation(data=None,*,extra=None,linked=True,target='chart1.xlsx',kind='package'):
    parts={'[Content_Types].xml':'<Types/>','ppt/presentation.xml':'<presentation/>',
           'ppt/charts/chart1.xml':'<chartSpace/>',
           'ppt/embeddings/'+target:workbook() if data is None else data}
    if linked:
        parts['ppt/charts/_rels/chart1.xml.rels']=(
            f'<Relationships xmlns="{REL}"><Relationship Id="rIdWorkbook" '
            f'Type="{OFFICE}/{kind}" Target="../embeddings/{target}"/></Relationships>')
    parts.update(extra or {})
    return packed(parts)


class ChartAttachmentTests(unittest.TestCase):
    def test_passive_native_chart_data_is_accepted(self):
        validate_content(presentation(),'pptx')

    def test_receive_and_recovery_preserve_exact_pptx_and_embedded_data(self):
        data=presentation();ident=str(uuid.uuid4())
        item={'id':ident,'name':'chart-reference.pptx','ext':'pptx','size':len(data),
              'sha256':hashlib.sha256(data).hexdigest()}
        task={'id':str(uuid.uuid4()),'lease':'synthetic','attachments':[item]}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            result=receive({},task,root,lambda *a,**k:data)
            saved=root/result[0]['path']
            self.assertEqual(saved.read_bytes(),data)
            with zipfile.ZipFile(saved) as z,zipfile.ZipFile(io.BytesIO(data)) as original:
                self.assertEqual(z.read('ppt/embeddings/chart1.xlsx'),original.read('ppt/embeddings/chart1.xlsx'))
            result2=receive({},task,root,lambda *a,**k:self.fail('Already verified original'),recover=True)
            self.assertEqual(result2,result)
            self.assertEqual(json.loads((root/'references/index.json').read_text())[0]['sha256'],item['sha256'])

    def test_unreferenced_or_arbitrary_embedded_payloads_stay_rejected(self):
        cases=[presentation(linked=False),presentation(b'not an XLSX'),
               presentation(b'active object',target='oleObject1.bin',kind='oleObject')]
        for data in cases:
            with self.subTest(digest=hashlib.sha256(data).hexdigest()),self.assertRaises((ValueError,zipfile.BadZipFile)):
                validate_content(data,'pptx')

    def test_macro_and_activex_presentations_stay_rejected(self):
        for path in ['ppt/vbaProject.bin','ppt/activeX/activeX1.bin']:
            with self.subTest(path=path),self.assertRaises(ValueError):
                validate_content(presentation(extra={path:b'active'}),'pptx')

    def test_active_workbooks_stay_rejected(self):
        cases=[{'xl/vbaProject.bin':b'active'},
               {'xl/externalLinks/externalLink1.xml':'<externalLink/>'},
               {'xl/worksheets/sheet1.xml':'<worksheet><ddeLink/></worksheet>'},
               {'[Content_Types].xml':'<Types><Override ContentType="application/vnd.ms-excel.sheet.macroEnabled.main+xml"/></Types>'},
               {'xl/_rels/workbook.xml.rels':f'<Relationships xmlns="{REL}"><Relationship Id="rId1" Type="{OFFICE}/hyperlink" Target="https://example.test/" TargetMode="External"/></Relationships>'}]
        for extra in cases:
            with self.subTest(parts=list(extra)),self.assertRaises(ValueError):
                validate_content(presentation(workbook(extra)),'pptx')

    def test_unsafe_nested_archive_and_presentation_paths_stay_rejected(self):
        for data in [presentation(workbook({'../outside.xml':'<x/>'})),
                     presentation(extra={'../outside.xml':'<x/>'})]:
            with self.assertRaises(ValueError):validate_content(data,'pptx')

    def test_docx_embedding_policy_is_unchanged(self):
        data=packed({'[Content_Types].xml':'<Types/>','word/document.xml':'<document/>',
                     'word/embeddings/data.xlsx':workbook()})
        with self.assertRaises(ValueError):validate_content(data,'docx')


if __name__=='__main__':unittest.main()
