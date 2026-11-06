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

def test_literal_scripts_are_localized_clues_not_code_rewrites():
    root=module.ET.fromstring(f'''<p:sld xmlns:p="{module.P}" xmlns:a="{module.A}">
      <p:sp><p:nvSpPr><p:cNvPr id="19" name="decision equation"/></p:nvSpPr>
      <p:txBody><a:p><a:r><a:t>p_</a:t></a:r><a:r><a:t>R = x^2</a:t></a:r></a:p>
      <a:p><a:r><a:t>password_empty create_public_link api_key</a:t></a:r></a:p>
      </p:txBody></p:sp></p:sld>''')
    before=module.ET.tostring(root);result=module.inspect_slide(root)
    assert len(result['warnings'])==1
    warning=result['warnings'][0]
    assert warning['tokens']==['p_R','x^2'] and warning['object_id']=='19'
    assert warning['object_name']=='decision equation'
    assert 'literal code' in warning['interpretation']
    assert module.ET.tostring(root)==before

def test_real_baseline_and_office_math_are_preserved():
    root=module.ET.fromstring(f'''<p:sld xmlns:p="{module.P}" xmlns:a="{module.A}" xmlns:m="{module.M}">
      <a:p><a:r><a:t>p</a:t></a:r><a:r><a:rPr baseline="-25000"/><a:t>R</a:t></a:r></a:p>
      <m:oMath><m:sSub><m:e><m:r><m:t>q</m:t></m:r></m:e><m:sub><m:r><m:t>E</m:t></m:r></m:sub></m:sSub></m:oMath>
      </p:sld>''')
    result=module.inspect_slide(root)
    assert result['explicitBaselineRunCount']==1 and result['nativeOfficeMathCount']==1
    assert result['warnings']==[]  # No warning still does not certify the equation.

def test_reject_dtd(tmp_path):
    path=tmp_path/'bad.pptx'
    with zipfile.ZipFile(path,'w') as z:z.writestr('ppt/_rels/presentation.xml.rels','<!DOCTYPE a><a/>')
    with pytest.raises(ValueError,match='DTD'):module.inspect(path)
