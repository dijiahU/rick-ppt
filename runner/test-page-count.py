import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from outline import validate_outline, MAX_SLIDES, MAX_OUTLINE_BYTES, page_version
from progress import Reporter


class PageCountTests(unittest.TestCase):
    def test_30_page_outline_matches_resolved_total(self):
        value={'title':'历史课程','purpose':'理解事件的背景和影响','slides':[
            {'id':f's{i}','title':f'主题 {i}','summary':'事件、原因与具体例子'} for i in range(1,31)]}
        self.assertEqual(len(validate_outline(value,30)['slides']),30)
        with self.assertRaises(ValueError):validate_outline(value,15)
        with self.assertRaises(ValueError):validate_outline({**value,'slides':value['slides']*4})

    def test_outline_cli_and_thirtieth_preview_reach_reporter(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in ('public-progress.py','outline.py'):
                shutil.copyfile(Path(__file__).parent/name,root/name)
            value={'title':'历史课程','purpose':'理解事件的背景和影响','slides':[
                {'id':f's{i}','title':f'主题 {i}','summary':'事件、原因与具体例子'} for i in range(1,31)]}
            (root/'outline.json').write_text(json.dumps(value))
            (root/'request.json').write_text(json.dumps({'pages':30}))
            output=subprocess.check_output([sys.executable,str(root/'public-progress.py'),'outline'],text=True)
            self.assertEqual(json.loads(output)['pages'],30)
            subprocess.run([sys.executable,str(root/'public-progress.py'),'note','--phase','building','--slide','30','--summary','最后一页的总结'],check=True,capture_output=True)
            calls=[];r=Reporter({}, {'id':'test','lease':'test','pages':30},root,lambda *args:calls.append(args),explicit_previews=True)
            r.poll_public_journal();self.assertEqual(len(r.outline['slides']),30)
            self.assertEqual(r.notes[-1]['slide'],30)
            png=b'\x89PNG\r\n\x1a\n'+b'\x00\x00\x00\rIHDR'+(100).to_bytes(4,'big')+(50).to_bytes(4,'big')
            image=root/'slide.png';image.write_bytes(png)
            with (root/'public-progress.jsonl').open('a') as stream:
                for i in range(1,31):
                    stream.write(json.dumps({'kind':'preview','slide':i,'contentVersion':page_version(r.outline,i),'render':{'ok':True,'renderer':'LibreOffice','pages':[str(image)]}})+'\n')
            r.poll_public_journal();r.flush(force=True)
            self.assertEqual(len([c for c in calls if 'action=preview' in c[1]]),30)
            self.assertEqual(json.loads(calls[-1][2])['previews'],list(range(1,31)))

    def test_long_multibyte_outline_fits_transport(self):
        value={'title':'课程','purpose':'完整讲解','slides':[
            {'id':f's{i}','title':'主题','summary':'知识'*1200} for i in range(1,MAX_SLIDES+1)]}
        outline=validate_outline(value,MAX_SLIDES)
        self.assertLess(len(json.dumps({'kind':'outline','outline':outline}).encode()),MAX_OUTLINE_BYTES)


if __name__=='__main__':unittest.main()
