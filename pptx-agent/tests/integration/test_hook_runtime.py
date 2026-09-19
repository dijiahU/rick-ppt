"""Exercise actual hook launchers through the symlink used by installed plugins."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('entry', ['pre_tool.py', 'post_tool.py', 'stop.py'])
@pytest.mark.parametrize('launcher', ['base', 'venv', 'alias'])
def test_installed_hook_with_symlinked_venv(tmp_path, entry, launcher):
    plugin = tmp_path / 'installed'
    shutil.copytree(ROOT / 'hooks', plugin / 'hooks', ignore=shutil.ignore_patterns('__pycache__'))
    (plugin / 'skills').symlink_to(ROOT / 'skills', target_is_directory=True)
    (plugin / '.venv').symlink_to(Path(sys.prefix), target_is_directory=True)
    alias = plugin / '.venv/bin/python'
    python = {'base': sys._base_executable, 'venv': sys.executable, 'alias': str(alias)}[launcher]
    env = os.environ.copy()
    for key in ('PPTX_AGENT_PYTHON', 'PPTX_AGENT_REEXEC_TARGET', 'PPTX_AGENT_WORKSPACE', 'PLUGIN_DATA'):
        env.pop(key, None)
    payload = {'cwd': str(tmp_path), 'tool_name': 'Bash', 'tool_input': {'command': 'pwd'}}
    proc = subprocess.run([python, str(plugin / 'hooks' / entry)], input=json.dumps(payload),
                          text=True, capture_output=True, env=env, cwd=tmp_path, timeout=5)
    assert proc.returncode == 0, proc.stderr
    assert not proc.stdout.strip(), proc.stdout


def runner_module():
    spec = importlib.util.spec_from_file_location('runtime_under_test', ROOT / 'hooks/runner.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_same_binary_different_venv_is_not_same_runtime(tmp_path, monkeypatch):
    runner = runner_module()
    target = tmp_path / 'another-venv/bin/python'
    target.parent.mkdir(parents=True)
    target.symlink_to(sys.executable)
    (target.parent.parent / 'pyvenv.cfg').write_text('include-system-site-packages = false\n')
    assert os.path.samefile(target, sys.executable)
    assert not runner.same_runtime(target)


def test_reexec_guard_fails_fast(monkeypatch):
    runner = runner_module()
    target = Path(sys.executable)
    monkeypatch.setattr(runner, 'same_runtime', lambda _: False)
    monkeypatch.setenv(runner.REEXEC_GUARD, str(target.parent.resolve() / target.name))
    monkeypatch.setattr(runner.os, 'execv', lambda *args: pytest.fail('repeated execv'))
    with pytest.raises(SystemExit, match='did not match after re-exec'):
        runner.ensure_runtime(target)
