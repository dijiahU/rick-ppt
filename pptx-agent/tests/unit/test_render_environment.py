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
