"""Regression coverage for stale launch overrides and graceful runtime handoff."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import production_bridge as bridge


class ProductionBridge(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.worker=self.root/'worker';self.worker.mkdir()
        self.plugin=self.worker/'runtime/new/pptx-agent'
        for path in ('.codex-plugin','skills/pptx/assets','skills/pptx/references','skills/pptx/scripts'):(self.plugin/path).mkdir(parents=True)
        (self.plugin/'.codex-plugin/plugin.json').write_text('{"version":"new"}')
        for path in ('assets/workflow-choices.json','assets/blank.pptx','references/workflow-branches.md','scripts/workflow_decisions.py'):(self.plugin/'skills/pptx'/path).write_text('{}')
        self.cfg={'plugin':str(self.plugin),'blank':str(self.plugin/'skills/pptx/assets/blank.pptx'),'python':sys.executable,'token':'private-worker-credential'}
        (self.worker/'settings.local.json').write_text(json.dumps(self.cfg))
        self.credentials=self.root/'settings.local.json';self.credentials.write_text('{"token":"different-live-credential"}')

    def test_current_settings_replace_inherited_old_runtime(self):
        env=bridge.launch_environment(self.worker,self.credentials,{'PPTX_RUNNER_PLUGIN':'old-designfit','PPTX_RUNNER_SETTINGS':'old-private-settings','PPTX_RUNNER_BLANK':'old-blank','PATH':'keep'})
        self.assertEqual(env['PPTX_RUNNER_PLUGIN'],str(self.plugin))
        self.assertEqual(env['PPTX_RUNNER_SETTINGS'],str(self.credentials))
        self.assertEqual(env['PPTX_RUNNER_BLANK'],self.cfg['blank'])
        self.assertEqual(env['PATH'],'keep')
        self.assertNotIn('private-worker-credential',str(env));self.assertNotIn('different-live-credential',str(env))

    def test_launcher_uses_configured_venv_without_resolving_python_link(self):
        python=self.root/'venv/bin/python';python.parent.mkdir(parents=True);python.symlink_to(sys.executable)
        self.cfg['python']=str(python)
        (self.worker/'settings.local.json').write_text(json.dumps(self.cfg))
        self.assertEqual(bridge.launch_interpreter(self.worker),str(python))

    def test_incomplete_branch_runtime_cannot_launch(self):
        (self.plugin/'skills/pptx/scripts/workflow_decisions.py').unlink()
        with self.assertRaisesRegex(ValueError,'Incomplete staged workflow'):bridge.launch_environment(self.worker,self.credentials,{})

    def test_v3_launch_requires_canvas_and_reference_helpers(self):
        (self.plugin/'skills/pptx/assets/workflow-choices.json').write_text('{"version":3}')
        helpers=('references/native-canvas.md','scripts/native_canvas.py','scripts/design_references.py')
        for relative in helpers:(self.plugin/'skills/pptx'/relative).write_text('fixture')
        bridge.launch_environment(self.worker,self.credentials,{})
        for relative in helpers:
            target=self.plugin/'skills/pptx'/relative;target.unlink()
            with self.assertRaisesRegex(ValueError,'Incomplete staged workflow'):bridge.launch_environment(self.worker,self.credentials,{})
            target.write_text('fixture')

    def test_receipt_records_loaded_configuration_not_current_settings(self):
        (self.worker/'settings.local.json').write_text('{"plugin":"some-later-version"}')
        receipt=bridge.write_runtime_receipt(self.worker,self.cfg,'ready')
        proof=json.loads(receipt.read_text())
        self.assertEqual(proof['plugin'],str(self.plugin));self.assertEqual(proof['version'],'new')
        self.assertTrue(proof['workflow_choices']);self.assertEqual(proof['default_model'],'gpt-6.1-sol')
        self.assertEqual(proof['default_reasoning_effort'],'high');self.assertNotIn('token',proof)
        self.assertEqual(receipt.stat().st_mode&0o777,0o600)

    def launcher(self):
        spec=importlib.util.spec_from_file_location('start_worker_test',Path(__file__).with_name('start-worker.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.ROOT=self.root;module.WORKER=self.worker
        (self.worker/'worker.lock').write_text('6007')
        return module

    def test_reload_drains_old_worker_and_stages_verified_successor(self):
        module=self.launcher();calls=[]
        def popen(command,**kwargs):
            calls.append((command,kwargs))
            (self.worker/'runtime-8009.local.json').write_text(json.dumps({'pid':8009,'plugin':str(self.plugin),'version':'new','status':'waiting'}))
            return SimpleNamespace(pid=8009,poll=lambda:None)
        with patch.object(module.sys,'argv',['start-worker.py','--reload']),patch.object(module.fcntl,'flock',side_effect=[None,BlockingIOError()]),patch.object(module,'verified_process',return_value=True),patch.object(module.os,'kill') as kill,patch.object(module.subprocess,'Popen',side_effect=popen),contextlib.redirect_stdout(io.StringIO()) as output:
            module.main()
        kill.assert_called_once_with(6007,signal.SIGTERM)
        self.assertIn('--wait-for-worker',calls[0][0]);self.assertEqual(calls[0][1]['env']['PPTX_RUNNER_PLUGIN'],str(self.plugin))
        self.assertIn('waiting for active jobs',output.getvalue())

    def test_second_reload_does_not_spawn_duplicate_successor(self):
        module=self.launcher()
        (self.worker/'handoff.local.json').write_text(json.dumps({'pid':8009,'plugin':str(self.plugin)}))
        with patch.object(module.sys,'argv',['start-worker.py','--reload']),patch.object(module.fcntl,'flock',side_effect=[None,BlockingIOError()]),patch.object(module,'verified_process',return_value=True),patch.object(module.os,'kill') as kill,patch.object(module.subprocess,'Popen') as popen,contextlib.redirect_stdout(io.StringIO()):module.main()
        kill.assert_not_called();popen.assert_not_called()


if __name__=='__main__':unittest.main()
