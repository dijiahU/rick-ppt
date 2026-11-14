import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
import pytest
from pptx_core import renderer
from pptx_core.common import PptxError


def renderer_fixture(tmp_path,monkeypatch,*,pdf_pages=1,selected=True):
    source=tmp_path/'original.pptx';source.write_bytes(b'IMMUTABLE SOURCE FIXTURE')
    monkeypatch.setenv('PPTX_RENDER_PAGE_RANGE','1' if selected else '0')
    monkeypatch.setattr(renderer,'executables',lambda:('office','ppm'))
    monkeypatch.setattr(renderer.shutil,'which',lambda name:'pdfinfo' if name=='pdfinfo' else None)
    calls=[]
    def run(command,timeout,env=None):
        calls.append(command)
        if command[0]=='office':
            stage=Path(command[command.index('--outdir')+1])
            (stage/'original.pdf').write_bytes(b'%PDF-'+b'x'*120)
            (stage/'render-environment.json').write_text(json.dumps({'source_sha256':'SOURCE','stable_font':'VERIFIED'}))
            (stage/'render-timings.json').write_text(json.dumps({'office_process_seconds':.4}))
        elif command[0]=='pdfinfo':return SimpleNamespace(stdout=f'Pages: {pdf_pages}\n',returncode=0)
        else:
            first=int(command[command.index('-f')+1]) if '-f' in command else 1
            last=int(command[command.index('-l')+1]) if '-l' in command else pdf_pages
            for page in range(first,last+1):Image.new('RGB',(80,40),'#164b83').save(str(command[-1])+f'-{page}.png')
        return SimpleNamespace(stdout='',stderr='',returncode=0)
    monkeypatch.setattr(renderer,'run',run)
    return source,calls


def test_selected_page_exports_one_pdf_page_and_keeps_original_page_number(tmp_path,monkeypatch):
    source,calls=renderer_fixture(tmp_path,monkeypatch)
    result=renderer.render_package(source,tmp_path/'out',slide=13,expected_pages=15)
    options=json.loads(calls[0][calls[0].index('--convert-to')+1].split(':',2)[2])
    assert options['PageRange']['value']=='13'
    png=next(command for command in calls if command[0]=='ppm')
    assert png[png.index('-f')+1]=='1' and png[png.index('-l')+1]=='1'
    assert Path(result['pages'][0]).name=='slide-13.png'
    assert result['selected_page_export'] is True
    assert source.read_bytes()==b'IMMUTABLE SOURCE FIXTURE'
    assert result['environment']=={'source_sha256':'SOURCE','stable_font':'VERIFIED'}
    assert result['timings']['host']['office_process_seconds']==.4
    assert (Path(result['pdf']).parent/'render-timings.json').is_file()


def test_ignored_page_range_fails_before_returning_the_wrong_page(tmp_path,monkeypatch):
    source,calls=renderer_fixture(tmp_path,monkeypatch,pdf_pages=15)
    with pytest.raises(PptxError,match='exactly one PDF page'):
        renderer.render_package(source,tmp_path/'out',slide=13,expected_pages=15)
    assert not any(command[0]=='ppm' for command in calls)


def test_final_whole_deck_export_retains_all_pages(tmp_path,monkeypatch):
    source,calls=renderer_fixture(tmp_path,monkeypatch,pdf_pages=3)
    result=renderer.render_package(source,tmp_path/'out',expected_pages=3)
    options=json.loads(calls[0][calls[0].index('--convert-to')+1].split(':',2)[2])
    assert 'PageRange' not in options and len(result['pages'])==3
    assert result['selected_page_export'] is False


def test_legacy_renderer_keeps_original_page_extraction(tmp_path,monkeypatch):
    source,calls=renderer_fixture(tmp_path,monkeypatch,pdf_pages=15,selected=False)
    result=renderer.render_package(source,tmp_path/'out',slide=13,expected_pages=15)
    png=next(command for command in calls if command[0]=='ppm')
    assert png[png.index('-f')+1]=='13' and Path(result['pages'][0]).name=='slide-13.png'
    assert not any(command[0]=='pdfinfo' for command in calls)
