import hashlib
import importlib.util
from pathlib import Path
import zipfile
import pytest

SCRIPT=Path(__file__).resolve().parents[2]/'skills/pptx/scripts/inspect_formulas.py'
spec=importlib.util.spec_from_file_location('formula_inventory',SCRIPT)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def fixture(path,text):
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('ppt/presentation.xml','<p:presentation xmlns:p="'+module.P+'" xmlns:r="'+module.R+'"><p:sldIdLst><p:sldId id="256" r:id="rId2"/></p:sldIdLst></p:presentation>')
        z.writestr('ppt/_rels/presentation.xml.rels','<Relationships><Relationship Id="rId2" Target="slides/slide7.xml"/></Relationships>')
        z.writestr('ppt/slides/slide7.xml','<p:sld xmlns:p="'+module.P+'" xmlns:a="'+module.A+'" xmlns:m="'+module.M+'"><a:p><a:r><a:rPr><a:latin typeface="Cambria Math"/></a:rPr><a:t>'+text+'</a:t></a:r></a:p><m:oMath><m:r><m:t>α</m:t></m:r></m:oMath></p:sld>')

def test_diagnostics_and_order_preserve_file(tmp_path):
    path=tmp_path/'equation.pptx';fixture(path,r'∇f(x)=\frac{1}{2}�')
    before=hashlib.sha256(path.read_bytes()).hexdigest();result=module.inspect(path)
    page=result['slides'][0]
    assert page['slide']==1 and page['part']=='ppt/slides/slide7.xml'
    assert page['nativeOfficeMathCount']==1 and page['declaredFonts']==['Cambria Math']
    assert {w['kind'] for w in page['warnings']}=={'replacement-character','possible-unrendered-latex'}
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before

def test_no_warning_not_proof_of_correctness(tmp_path):
    path=tmp_path/'equation.pptx';fixture(path,'x = 2')
    result=module.inspect(path)
    assert result['slides'][0]['warnings']==[] and result['limitations']

def test_reject_dtd(tmp_path):
    path=tmp_path/'bad.pptx'
    with zipfile.ZipFile(path,'w') as z:z.writestr('ppt/_rels/presentation.xml.rels','<!DOCTYPE a><a/>')
    with pytest.raises(ValueError,match='DTD'):module.inspect(path)
