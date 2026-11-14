from pptx_core.renderer import font_environment,run
from pptx_core.common import PptxError
from unittest.mock import patch
from types import SimpleNamespace
import pytest

def test_font_configuration_is_scoped_and_preserves_host_override(tmp_path,monkeypatch):
    monkeypatch.delenv('FONTCONFIG_FILE',raising=False)
    with patch('pptx_core.renderer.sys.platform','darwin'),patch('pptx_core.renderer.Path.is_dir',return_value=True):
        env=font_environment(tmp_path,'/Applications/LibreOffice.app/Contents/MacOS/soffice')
        assert env['FONTCONFIG_FILE']==str(tmp_path/'fonts.conf')
        assert '<dir>/System/Library/Fonts</dir>' in (tmp_path/'fonts.conf').read_text()
        monkeypatch.setenv('FONTCONFIG_FILE','/host/fonts.conf')
        assert font_environment(tmp_path,'soffice')['FONTCONFIG_FILE']=='/host/fonts.conf'

def test_empty_render_failure_has_actionable_diagnostic():
    with patch('pptx_core.renderer.subprocess.run',return_value=SimpleNamespace(returncode=1,stderr='',stdout='')):
        with pytest.raises(PptxError,match='host sandbox access'):run(['soffice'],1)

def test_host_render_budget_covers_bridge_wait_without_changing_default(monkeypatch):
    monkeypatch.delenv('PPTX_RENDER_TIMEOUT_SECONDS',raising=False)
    with patch('pptx_core.renderer.subprocess.run',return_value=SimpleNamespace(returncode=0)) as execute:
        run(['soffice'],90)
        assert execute.call_args.kwargs['timeout']==90
        run(['soffice'],90,env={'PPTX_RENDER_TIMEOUT_SECONDS':'210'})
        assert execute.call_args.kwargs['timeout']==210

@pytest.mark.parametrize('value',['0','89','301','infinite'])
def test_invalid_host_render_budget_fails_before_start(value):
    with patch('pptx_core.renderer.subprocess.run') as execute:
        with pytest.raises(PptxError,match='render timeout'):
            run(['soffice'],90,env={'PPTX_RENDER_TIMEOUT_SECONDS':value})
        execute.assert_not_called()
