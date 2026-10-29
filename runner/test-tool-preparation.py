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

    def test_advertised_geometry_choices_execute_and_unsupported_choice_preserves_parts(self):
        from lxml import etree
        ws=helper._module('pptx_core.package').unpack(PLUGIN/'skills/pptx/assets/blank.pptx',self.root/'projects')
        helper.prepare_tool_manifest(self.root,workspace=ws.root)
        manifest=self.read_manifest();canvas=helper._module('native_canvas')
        choices=manifest['native_canvas']['add_shape']['choices']['geometry']
        self.assertEqual(choices,manifest['native_batch']['operation_choices']['shape']['geometry'])
        for n,geometry in enumerate(choices):
            canvas.add_shape(ws.root,1,[1+n*1.5,2,1,1],geometry=geometry,fill='DDEEFF',stroke='223344',line_width=1,name=geometry)
        tree=etree.parse(str(ws.root/'ppt/slides/slide1.xml'))
        self.assertEqual(tree.xpath('//*[local-name()="prstGeom"]/@prst'),choices)
        before={p:p.read_bytes() for p in ws.root.rglob('*') if p.is_file()}
        with self.assertRaisesRegex(ValueError,'Unsupported explicit geometry'):
            canvas.add_shape(ws.root,1,[1,4,1,1],geometry='downArrow',fill='DDEEFF',stroke=None,line_width=1,name='unsupported')
        self.assertEqual(before,{p:p.read_bytes() for p in ws.root.rglob('*') if p.is_file()})

    def test_invalid_retained_plan_is_diagnosed_without_mutating_or_blocking_it(self):
        outline={'slides':[{'id':'actual','title':'Actual page','summary':'Keep actual evidence'}]}
        plan=helper._module('workflow_decisions').plan_template(outline)
        (self.root/'outline.json').write_text(json.dumps(outline))
        (self.root/'decision-plan.json').write_text(json.dumps(plan))
        original=(self.root/'decision-plan.json').read_bytes()
        helper.prepare_tool_manifest(self.root)
        self.assertEqual(self.read_manifest()['plan_check']['status'],'needs_repair')
        self.assertEqual((self.root/'decision-plan.json').read_bytes(),original)
        self.assertIn('check_glyphs',self.read_manifest()['native_canvas'])

    def test_reference_kind_error_is_reported_and_correct_existing_contract_is_accepted(self):
        from PIL import Image
        outline={'slides':[{'id':'actual','title':'Actual page','summary':'Keep actual evidence'}]}
        plan={'version':4,'task':{'operation':'create','viewing':'dual_use','research':'supplied_only'},
            'template_preservation':[],'design_direction':'Large editable mechanism with adjacent annotation.',
            'pages':[{'id':'actual','behavior':'click_reveal','assets':[{'route':'source_grounded_native'}]}],
            'references':[{'id':'r','kind':'design','title':'Actual work','creator':'Actual creator',
                'source':'https://example.org/work','inspection':'local_image','evidence':'reference.png',
                'observed':'Adjacent labels follow the mechanism.','borrowed':'Adjacent annotation.',
                'applications':[{'pages':['actual'],'action':'Place the label by its actual path.'}]}]}
        Image.new('RGB',(20,12),'green').save(self.root/'reference.png')
        (self.root/'outline.json').write_text(json.dumps(outline))
        (self.root/'decision-plan.json').write_text(json.dumps(plan))
        helper.prepare_tool_manifest(self.root)
        self.assertEqual(self.read_manifest()['plan_check']['status'],'needs_repair')
        self.assertIn('kind',self.read_manifest()['plan_check']['detail'])
        plan['references'][0]['kind']='design_work'
        (self.root/'decision-plan.json').write_text(json.dumps(plan))
        helper.prepare_tool_manifest(self.root)
        self.assertEqual(self.read_manifest()['plan_check']['status'],'valid')

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

    def test_page_handoff_is_discoverable_without_creating_a_required_page_form(self):
        original='Original evidence remains.\n\n```pptx-handoff\n'+json.dumps({
            'page_id':'mechanism','question':'How is information aggregated?',
            'preserve':['Illustrative values are not measurements'],
            'materials':[{'file':'pending.png','role':'Pending actual detail'}]})+'\n```\n'
        (self.root/'source-notes.md').write_text(original)
        helper.prepare_tool_manifest(self.root)
        value=self.read_manifest()['page_design']
        self.assertEqual(value['context_command'][0],sys.executable)
        self.assertFalse(value['handoff_index']['required'])
        self.assertEqual(value['handoff_index']['pages'][0]['page_id'],'mechanism')
        self.assertIn('preserve',value['handoff_index']['pages'][0]['fields'])
        self.assertEqual((self.root/'source-notes.md').read_text(),original)
        self.assertFalse((self.root/'outline.json').exists())

    def test_refresh_keeps_explicit_workspace_and_reads_updated_handoff(self):
        workspace=helper._module('pptx_core.package').unpack(
            PLUGIN/'skills/pptx/assets/blank.pptx',self.root/'projects')
        helper.prepare_tool_manifest(self.root,workspace=workspace.root)
        (self.root/'source-notes.md').write_text('```pptx-handoff\n'+json.dumps({
            'page_id':'later-page','uncertainties':['Actual material still pending']})+'\n```\n')
        value=helper.prepare_tool_manifest(self.root)
        self.assertEqual(value['parts_dir'],str(workspace.root))
        self.assertEqual(self.read_manifest()['page_design']['handoff_index']['pages'][0]['page_id'],'later-page')

    def test_batch_entry_uses_same_interpreter_and_no_design_defaults(self):
        helper.prepare_tool_manifest(self.root)
        value = self.read_manifest()
        command = value['commands']['native_page_batch']
        self.assertEqual(command[0], sys.executable)
        self.assertEqual(command[command.index('--workspace')+1], 'PARTS_DIR_FROM_UNPACK')
        self.assertEqual(value['native_batch']['operations']['connector'], 'add_connector')
        self.assertEqual(value['native_batch']['document_fields'], ['version', 'batch_id', 'operations'])
        self.assertIn('does not create decision-plan.json', value['command_outputs']['decision_scaffold'])

    def test_prepared_batch_contract_runs_without_reading_helper_sources(self):
        workspace=helper._module('pptx_core.package').unpack(
            PLUGIN/'skills/pptx/assets/blank.pptx',self.root/'projects')
        helper.prepare_tool_manifest(self.root,workspace=workspace.root)
        manifest=self.read_manifest()
        operations=[]
        for ident,box in [('left',[1,2,2,1]),('right',[4,2,2,1])]:
            operations.append({'op':'shape','id':ident,'slide':1,'box':box,
                               'geometry':'rect','fill':'DDEEFF','stroke':'223344','line_width':1,'name':ident})
        operations += [
            {'op':'group','id':'pair','slide':1,'members':['left','right'],'name':'Related modules'},
            {'op':'connector','id':'relation','slide':1,'start':'left','end':'right',
             'points':[3,2.5,4,2.5],'start_site':3,'end_site':1,'ink':'223344',
             'line_width':1,'arrow':'triangle','name':'Relationship'},
            {'op':'reveal','slide':1,'steps':[['pair','relation']]}]
        for operation in operations:
            params=manifest['native_batch']['operation_parameters'][operation['op']]
            required={p['name'] for p in params if p['required']}
            provided=set(operation)-{'op','id','slide'}
            self.assertTrue(required<=provided)
            self.assertTrue(provided<={p['name'] for p in params})
        document=self.root/'page.json'
        document.write_text(json.dumps({'version':1,'batch_id':'prepared-tools','operations':operations}))
        command=list(manifest['commands']['native_page_batch'])
        command[-1]=str(document)
        first=subprocess.run(command,cwd=self.root,check=True,capture_output=True,text=True)
        result=json.loads(first.stdout)
        second=subprocess.run(command,cwd=self.root,check=True,capture_output=True,text=True)
        self.assertEqual(result['handles'],json.loads(second.stdout)['handles'])
        from lxml import etree
        tree=etree.parse(str(workspace.root/'ppt/slides/slide1.xml'))
        ns={'p':'http://schemas.openxmlformats.org/presentationml/2006/main',
            'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
        self.assertEqual(len(tree.findall('.//p:grpSp',ns)),1)
        self.assertEqual(len(tree.findall('.//a:stCxn',ns)),1)
        self.assertEqual(len(tree.findall('.//a:endCxn',ns)),1)
        self.assertEqual(len(tree.findall('.//p:spTgt',ns)),2)

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
        self.assertEqual(set(scaffold['pages'][0]), {'id','behavior','assets'})
        self.assertIsNone(scaffold['pages'][0]['behavior'])
        self.assertEqual(value['decision_contract']['page_options'], {'behavior':['static','click_reveal','internal_navigation','embedded_playback']})
        self.assertEqual(value['decision_contract']['page_fields'], ['id','behavior','assets'])
        self.assertNotIn('eligible_forms', value['decision_contract'])

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
