import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from phase_context import MAX_DOCUMENT, prepared_phase_context
from workflow import _repair_candidate


class Tests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.job = self.root / 'job'
        self.job.mkdir()
        self.plugin = self.root / 'plugin'
        self.skill = self.plugin / 'skills/pptx'
        (self.skill / 'scripts').mkdir(parents=True)
        (self.skill / 'scripts/planning_commit.py').write_text('# Opt in')
        self.cfg = {'plugin': str(self.plugin)}
        self.request = {'title': 'A real brief', 'pages': 2, 'mode': 'create',
                        'attachments': [{'path': 'references/actual.md'}]}
        (self.job / 'request.json').write_text(json.dumps(self.request))
        (self.job / 'source-notes.md').write_text('RETAINED AUTHOR EVIDENCE')
        (self.job / 'outline.json').write_text('{"slides":[]}')
        (self.job / 'decision-plan.json').write_text('{"task":{"style":"expressive"}}')
        (self.skill / 'SKILL.md').write_text('CURRENT INSTALLED SKILL')

    def documents(self, text):
        start = text.index('{"stage"')
        return json.loads(text[start:])['documents']

    def test_planning_receives_current_contracts_without_reading_sources_or_author_rationale(self):
        (self.job / 'references').mkdir()
        (self.job / 'references/actual.md').write_text('UNINSPECTED ACTUAL SOURCE')
        text = prepared_phase_context(self.cfg, self.job, 'research')
        self.assertIn('CURRENT INSTALLED SKILL', text)
        self.assertIn('A real brief', text)
        self.assertNotIn('RETAINED AUTHOR EVIDENCE', text)
        self.assertNotIn('UNINSPECTED ACTUAL SOURCE', text)
        self.assertIn('read/inspect', text)
        request = next(d for d in self.documents(text) if d['path'].endswith('/request.json'))
        self.assertEqual(json.loads(request['content']), self.request)
        self.assertEqual(request['sha256'], hashlib.sha256((self.job/'request.json').read_bytes()).hexdigest())

    def test_author_gets_latest_state_and_only_needed_manifest_sections(self):
        (self.job/'tool-manifest.json').write_text(json.dumps({
            'python':'EXACT_VENV_INVOCATION', 'native_canvas':{'add_text':'ACTUAL SIGNATURE'},
            'not_needed_for_author':'UNNEEDED MANIFEST SECTION'}))
        text = prepared_phase_context(self.cfg,self.job,'author')
        self.assertIn('RETAINED AUTHOR EVIDENCE',text)
        self.assertIn('ACTUAL SIGNATURE',text)
        self.assertNotIn('UNNEEDED MANIFEST SECTION',text)
        (self.job/'source-notes.md').write_text('NEW RESOLVED EVIDENCE')
        text = prepared_phase_context(self.cfg,self.job,'repair')
        self.assertIn('NEW RESOLVED EVIDENCE',text)
        self.assertNotIn('RETAINED AUTHOR EVIDENCE',text)

    def test_continuity_keeps_callable_native_interfaces_for_author_and_repair(self):
        (self.skill/'references').mkdir()
        (self.skill/'references/execution-continuity.md').write_text('CONTINUITY')
        manifest={'native_canvas':{'add_connector':{'parameters':[{'name':'start_site','required':True}]}},
                  'native_pages':{'command':['exact-python','page-helper']},
                  'native_authoring':{'module_directory':'actual-installed-scripts'},
                  'native_batch':{'operations':{'connector':'add_connector'}},
                  'unrelated':'NOT FOR AUTHOR'}
        (self.job/'tool-manifest.json').write_text(json.dumps(manifest))
        for stage in ('author','repair'):
            doc=next(d for d in self.documents(prepared_phase_context(self.cfg,self.job,stage))
                     if d['path'].endswith('/tool-manifest.json'))
            value=json.loads(doc['content'])
            for name in ('native_canvas','native_pages','native_batch','native_authoring'):
                self.assertEqual(value[name],manifest[name])
            self.assertNotIn('unrelated',value)

    def test_callable_interfaces_survive_optional_guide_context_budget(self):
        (self.skill/'SKILL.md').write_text('GUIDE'*1000)
        (self.job/'tool-manifest.json').write_text(json.dumps({'native_canvas':{'add_shape':{'signature':'EXACT'}}}))
        with patch('phase_context.MAX_CONTEXT',512):
            text=prepared_phase_context(self.cfg,self.job,'author')
        documents=self.documents(text)
        self.assertTrue(any(d['path'].endswith('/tool-manifest.json') for d in documents))
        self.assertFalse(any(d['path'].endswith('/SKILL.md') for d in documents))

    def test_large_unneeded_manifest_sections_do_not_hide_compact_callable_subset(self):
        manifest={'native_canvas':{'add_shape':{'signature':'CURRENT'}},
                  'decision_scaffold':'unused '*MAX_DOCUMENT}
        (self.job/'tool-manifest.json').write_text(json.dumps(manifest))
        doc=next(d for d in self.documents(prepared_phase_context(self.cfg,self.job,'author'))
                 if d['path'].endswith('/tool-manifest.json'))
        self.assertEqual(json.loads(doc['content']),{'native_canvas':manifest['native_canvas']})

    def test_author_receives_material_status_without_source_result_payloads(self):
        (self.job/'material-prefetch').mkdir()
        index={'version':1,'requests':[{'id':'a'*32,'state':'running',
               'payload':{'kind':'search','page_ids':['later-page'],'purpose':'Actual image source'}}]}
        (self.job/'material-prefetch/index.json').write_text(json.dumps(index))
        (self.job/('material-prefetch/'+'a'*32+'.result.json')).write_text('LARGE CANDIDATE SOURCE BODY')
        text=prepared_phase_context(self.cfg,self.job,'author')
        doc=next(d for d in self.documents(text) if d['path'].endswith('/material-prefetch/index.json'))
        self.assertEqual(json.loads(doc['content']),index)
        self.assertNotIn('LARGE CANDIDATE SOURCE BODY',text)

    def test_oversize_document_is_deferred_whole_instead_of_silently_cut(self):
        (self.job/'source-notes.md').write_text('SOURCE'*MAX_DOCUMENT)
        text = prepared_phase_context(self.cfg,self.job,'author')
        data = json.loads(text[text.index('{"stage"'):])
        self.assertIn(str(self.job/'source-notes.md'),data['deferred'])
        self.assertFalse(any(d['path'].endswith('/source-notes.md') for d in data['documents']))

    def test_legacy_runtime_gets_no_new_documents(self):
        (self.skill/'scripts/planning_commit.py').unlink()
        self.assertEqual(prepared_phase_context(self.cfg,self.job,'research'),'')

    def test_task_cannot_substitute_host_progress_instructions(self):
        (self.job/'PROGRESS.md').write_text('TASK MUTATED PROGRESS')
        text = prepared_phase_context(self.cfg,self.job,'research')
        self.assertNotIn('TASK MUTATED PROGRESS',text)
        self.assertTrue(any(d['kind']=='host_instruction' for d in self.documents(text)))

    def test_symlink_input_is_not_inlined(self):
        (self.job/'request.json').unlink()
        (self.job/'request.json').symlink_to(self.skill/'SKILL.md')
        with self.assertRaises(ValueError):
            prepared_phase_context(self.cfg,self.job,'research')

    def test_partial_saved_plan_reaches_repair_context_without_discarding_it(self):
        partial='{"slides":[{"id":"retained-page",'
        (self.job/'outline.json').write_text(partial)
        text=prepared_phase_context(self.cfg,self.job,'repair')
        doc=next(d for d in self.documents(text) if d['path'].endswith('/outline.json'))
        self.assertEqual(doc['content'],partial)
        self.assertIn('Partial/invalid saved JSON',doc['format_error'])
        self.assertEqual((self.job/'outline.json').read_text(),partial)
        (self.job/'decision-plan.json').write_bytes(b'{"part":"\xe4\xb8')
        text=prepared_phase_context(self.cfg,self.job,'repair')
        self.assertIn('decision-plan.json',text)
        self.assertEqual((self.job/'decision-plan.json').read_bytes(),b'{"part":"\xe4\xb8')

    def test_planning_inlines_quickstart_instead_of_requiring_another_read(self):
        (self.job/'tool-quickstart.md').write_text('EXACT CURRENT QUICKSTART')
        self.assertIn('EXACT CURRENT QUICKSTART',prepared_phase_context(self.cfg,self.job,'research'))

    def repair(self, *, content_required=True, content_findings=True, failed=False):
        finding = {'severity':'required','route':'content_revision'}
        receipt = {'content':{'findings':[finding] if content_findings else []},
                   'visual':{'findings':[]}}
        path = self.job/'review-findings-1.json'
        path.write_text(json.dumps(receipt))
        (self.job/'candidate.pptx').write_bytes(b'UNTOUCHED FROZEN CANDIDATE')
        run = SimpleNamespace(cfg=self.cfg,job=self.job,author_thread='author-context',
                              recovery_plan={},seed_repair_workspace=Mock(),
                              phase=Mock(side_effect=RuntimeError('disconnect') if failed else None),
                              delivery=Mock(return_value={'path':'candidate.pptx'}),complete_phase=Mock())
        _repair_candidate(run,'Host scope','Native author instructions',path,1,content_required=content_required)
        return run

    def test_content_and_native_correction_share_one_context_and_archive_both(self):
        run = self.repair()
        run.seed_repair_workspace.assert_called_once()
        self.assertEqual([call.args[0] for call in run.phase.call_args_list],['repair-1'])
        self.assertIn('Then apply those resolved corrections',run.phase.call_args.args[1])
        self.assertEqual(run.phase.call_args.kwargs['thread'],'author-context')
        artifacts = run.complete_phase.call_args.args[1]
        self.assertIn('outline.json',artifacts)
        self.assertIn('source-notes.md',artifacts)

    def test_resume_of_combined_repair_retains_required_content_work(self):
        run = self.repair(content_required=False)
        self.assertIn('source/content corrections',run.phase.call_args.args[1])
        self.assertIn('Reuse completed verified content work',run.phase.call_args.args[1])
        self.assertIn('source-notes.md',run.complete_phase.call_args.args[1])

    def test_native_only_repair_does_not_request_source_research(self):
        run = self.repair(content_required=False,content_findings=False)
        self.assertNotIn('This revision includes source/content corrections',run.phase.call_args.args[1])

    def test_interruption_never_records_combined_repair_complete(self):
        with self.assertRaisesRegex(RuntimeError,'disconnect'):
            self.repair(failed=True)
        self.assertEqual((self.job/'candidate.pptx').read_bytes(),b'UNTOUCHED FROZEN CANDIDATE')


if __name__ == '__main__':
    unittest.main()
