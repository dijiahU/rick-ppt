"""Real French deck from a Chinese topic, no production request or quota."""
import io
import uuid
import zipfile
import xml.etree.ElementTree as ET
import runner

cfg=runner.settings()
# Use the updated workflow in an isolated safe runtime selected by caller.
import sys
if len(sys.argv)>1:cfg['plugin']=sys.argv[1]
completed=[]
def receipt(cfg,path,body=b'{}',lease=None):
    if 'action=complete' in path:
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            text=[]
            for name in archive.namelist():
                if name.startswith('ppt/slides/slide') and name.endswith('.xml'):
                    root=ET.fromstring(archive.read(name))
                    text.extend(e.text or '' for e in root.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t'))
            joined='\n'.join(text)
            assert not any('\u4e00'<=c<='\u9fff' for c in joined),'Chinese leaked into selected French output'
            assert any(c in joined for c in 'éèàç'),'Expected native French accents'
        target=runner.ROOT/'language-fr-result.pptx'
        with target.open('xb') as out:out.write(body)
        completed.append(str(target))
        print('Slide text:',joined,flush=True)
    return {'ok':True}
runner.request=receipt
task={'id':str(uuid.uuid4()),'lease':'local-language-test','title':'团队协作：从想法到行动','brief':'制作两页简短介绍。第一页介绍团队协作的意义，第二页展示明确目标、分工、复盘三个步骤。不需要实时数据，不搜索，不生成图片。只使用原生可编辑文字与简单图形。按照已选输出语言翻译主题与内容。','pages':2,'style':'Restrained editorial','language':'fr'}
print(runner.run_job(cfg,task),flush=True)
assert completed
print('PASS: Chinese input → French editable PPTX → independent render/export',completed[0])
