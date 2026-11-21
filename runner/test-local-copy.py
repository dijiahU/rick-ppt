import json,tempfile,unittest
from pathlib import Path
from local_copy import copy,name_for

class LocalCopyTests(unittest.TestCase):
    def test_disabled_without_setting(self):
        self.assertIsNone(copy({},{'id':'abc'},b'x'))
    def test_copies_once_and_records_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            cfg={'local_output_dir':d};task={'id':'68af4adc-f628','title':'公司 介绍/v1'}
            target=copy(cfg,task,b'PPTX',now=0)
            self.assertTrue(target.name.endswith('_公司介绍v1_68af4adc.pptx'));self.assertEqual(target.read_bytes(),b'PPTX')
            self.assertIsNone(copy(cfg,task,b'PPTX',now=60))
            rows=json.loads((Path(d)/'manifest.json').read_text());self.assertEqual(len(rows),1)
            self.assertIsNotNone(copy(cfg,task,b'PPTX2',now=120))
            self.assertEqual(len(json.loads((Path(d)/'manifest.json').read_text())),2)

if __name__=='__main__':unittest.main()
