import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / 'pptx-agent'
SCRIPT = PLUGIN / 'skills/pptx/scripts/tool_prepare.py'
spec = importlib.util.spec_from_file_location('tested_tool_prepare', SCRIPT)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
sys.path.insert(0, str(ROOT / 'runner'))
from tool_preparation import prepare_tool_manifest


class ToolPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def read_manifest(self):
        return json.loads((self.root / 'tool-manifest.json').read_text())

    def test_host_prepares_exact_interpreter_without_workspace_or_design(self):
        cfg = {'plugin': str(PLUGIN), 'python': sys.executable}
        result = prepare_tool_manifest(cfg, self.root)
        value = self.read_manifest()
        self.assertEqual(value['python'], sys.executable)
        self.assertEqual(result['parts_dir'], None)
        self.assertEqual(value['decision_scaffold'], None)
        self.assertFalse((self.root / 'decision-plan.json').exists())
        self.assertFalse((self.root / 'blank.pptx').exists())
        for argv in value['commands'].values():
            self.assertEqual(argv[0], sys.executable)

    def test_venv_invocation_symlink_not_resolved_to_system_binary(self):
        invocation = self.root / 'venv/bin/python'
        invocation.parent.mkdir(parents=True)
        invocation.symlink_to(sys.executable)
        helper.prepare_tool_manifest(self.root, python=invocation)
        self.assertEqual(self.read_manifest()['python'], str(invocation))

    def test_native_signatures_match_current_helpers(self):
        helper.prepare_tool_manifest(self.root)
        value = self.read_manifest()['native_canvas']
        text = {p['name']: p for p in value['add_text']['parameters']}
        self.assertNotIn('box', text)
        for name in ('x', 'y', 'width', 'max_height'):
            self.assertEqual(text[name]['kind'], 'KEYWORD_ONLY')
            self.assertTrue(text[name]['required'])
        self.assertEqual(value['add_text']['signature'], str(helper.inspect.signature(helper._module('native_canvas').add_text)))

    def test_batch_entry_uses_same_interpreter_and_no_design_defaults(self):
        helper.prepare_tool_manifest(self.root)
        value = self.read_manifest()
        command = value['commands']['native_page_batch']
        self.assertEqual(command[0], sys.executable)
        self.assertEqual(command[command.index('--workspace')+1], 'PARTS_DIR_FROM_UNPACK')
        self.assertEqual(value['native_batch']['operations']['connector'], 'add_connector')
        self.assertEqual(value['native_batch']['document_fields'], ['version', 'batch_id', 'operations'])
        self.assertIn('does not create decision-plan.json', value['command_outputs']['decision_scaffold'])

    def test_planning_and_sequential_page_tools_use_installed_interfaces(self):
        helper.prepare_tool_manifest(self.root)
        value = self.read_manifest()
        self.assertEqual(value['planning_commit']['command'],value['commands']['planning_commit'])
        self.assertEqual(value['planning_commit']['outputs'],['outline.json','decision-plan.json','source-notes.md'])
        for name in ('planning_commit','ensure_next_page'):
            self.assertEqual(value['commands'][name][0],sys.executable)
        self.assertEqual(value['native_pages']['mode'],'blank_from_layout')
        self.assertIn('CHOSEN_LAYOUT_SOURCE_PAGE',value['commands']['ensure_next_page'])
        self.assertFalse((self.root/'outline.json').exists())
        self.assertFalse((self.root/'decision-plan.json').exists())

    def test_generated_examples_follow_actual_cli_parser(self):
        helper.prepare_tool_manifest(self.root)
        value = self.read_manifest()
        parser = helper._module('pptx_core.cli').parser()
        for name in ('unpack_selected_source', 'list_slides', 'inspect_page', 'validate', 'render_page', 'export'):
            args = parser.parse_args(value['commands'][name][2:])
            self.assertIsNotNone(args.command)
        self.assertEqual(value['pptx_cli']['commands']['list']['arguments'][0]['choices'], ['slides', 'media', 'charts', 'masters'])

    def test_selected_session_and_parts_paths_are_equal_and_do_not_change_parts(self):
        source = self.root / 'source.pptx'
        shutil.copyfile(PLUGIN / 'skills/pptx/assets/blank.pptx', source)
        workspace = helper._module('pptx_core.package').unpack(source, self.root / 'projects')
        before = {str(p.relative_to(workspace.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in workspace.root.rglob('*') if p.is_file()}
        first = helper.prepare_tool_manifest(self.root, workspace=workspace.home)
        second = helper.prepare_tool_manifest(self.root, workspace=workspace.root)
        self.assertEqual(first['session_dir'], second['session_dir'])
        self.assertEqual(first['parts_dir'], second['parts_dir'])
        self.assertEqual(second['parts_dir'], str(workspace.root))
        after = {str(p.relative_to(workspace.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in workspace.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_scaffold_keeps_all_choices_unselected_and_outline_unchanged(self):
        data = json.dumps({'title': 'T', 'purpose': 'P', 'slides': [{'id': 'one', 'title': 'T', 'summary': 'S'}]})
        (self.root / 'outline.json').write_text(data)
        helper.prepare_tool_manifest(self.root)
        value = self.read_manifest()
        self.assertEqual((self.root / 'outline.json').read_text(), data)
        scaffold = value['decision_scaffold']
        self.assertTrue(all(v is None for v in scaffold['task'].values()))
        for field in ('intent', 'strategy', 'form', 'composition', 'behavior'):
            self.assertIsNone(scaffold['pages'][0][field])
        self.assertEqual(value['decision_contract']['eligible_forms'], helper._module('workflow_decisions').load_catalog()['eligible_forms'])

    def test_actual_reference_paths_and_local_progress_location(self):
        (self.root / 'references').mkdir()
        (self.root / 'references/file.md').write_text('facts')
        (self.root / 'references/index.json').write_text(json.dumps([{'name': 'Facts', 'path': 'references/file.md'}]))
        (self.root / 'public-progress.py').write_text('# task helper')
        helper.prepare_tool_manifest(self.root)
        value = self.read_manifest()
        self.assertEqual(value['attachments'][0]['path'], 'references/file.md')
        self.assertEqual(value['commands']['publish_outline'][1], str(self.root / 'public-progress.py'))

    def test_rejects_output_symlink_and_foreign_workspace(self):
        target = self.root / 'outside'
        target.write_text('original')
        (self.root / 'tool-manifest.json').symlink_to(target)
        with self.assertRaises(ValueError):
            helper.prepare_tool_manifest(self.root)
        self.assertEqual(target.read_text(), 'original')
        with self.assertRaises(ValueError):
            helper.prepare_tool_manifest(self.root, workspace=ROOT)

    def test_old_plugin_without_helper_preserves_legacy_behavior(self):
        self.assertIsNone(prepare_tool_manifest({'plugin': str(self.root), 'python': sys.executable}, self.root))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_host_cli_uses_current_plugin_and_does_not_forward_secrets(self):
        foreign = self.root / 'old-plugin'
        (foreign / 'pptx_core').mkdir(parents=True)
        (foreign / 'pptx_core/__init__.py').write_text('raise RuntimeError("wrong plugin")')
        run = subprocess.run
        with mock.patch.dict(os.environ, {'PYTHONPATH': str(foreign), 'API_KEY': 'test-secret'}):
            with mock.patch('tool_preparation.subprocess.run', wraps=run) as child:
                result = prepare_tool_manifest({'plugin': str(PLUGIN), 'python': sys.executable}, self.root)
        call = child.call_args
        self.assertEqual(call.kwargs['env']['PYTHONPATH'], str(SCRIPT.parent))
        self.assertNotIn('API_KEY', call.kwargs['env'])
        self.assertEqual(call.kwargs['timeout'], 30)
        self.assertEqual(call.kwargs['cwd'], self.root)
        self.assertTrue(call.kwargs['check'])
        self.assertEqual(result['manifest'], str(self.root / 'tool-manifest.json'))
        self.assertEqual(self.read_manifest()['python'], sys.executable)

    def test_host_does_not_hide_helper_failure(self):
        error = subprocess.CalledProcessError(1, ['helper'], stderr='bounded failure')
        with mock.patch('tool_preparation.subprocess.run', side_effect=error):
            with self.assertRaises(subprocess.CalledProcessError):
                prepare_tool_manifest({'plugin': str(PLUGIN), 'python': sys.executable}, self.root)

    def test_malformed_partial_outline_does_not_block_interface_preparation(self):
        for text in ('{broken', '{"pages": []}', '{"slides": [{"id":"a"}, {"id":"a"}]}'):
            (self.root / 'outline.json').write_text(text)
            helper.prepare_tool_manifest(self.root)
            self.assertIsNone(self.read_manifest()['decision_scaffold'])
            self.assertTrue(self.read_manifest()['scaffold_error'])
            self.assertEqual((self.root / 'outline.json').read_text(), text)

    def test_reference_index_cannot_read_through_parent_symlink(self):
        with tempfile.TemporaryDirectory() as foreign:
            external = Path(foreign)
            (external / 'index.json').write_text('[]')
            (self.root / 'references').symlink_to(external, target_is_directory=True)
            with self.assertRaises(ValueError):
                helper.prepare_tool_manifest(self.root)


if __name__ == '__main__':
    unittest.main()
