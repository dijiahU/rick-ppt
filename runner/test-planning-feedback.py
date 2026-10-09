import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from workflow import validated_planning

class Tests(unittest.TestCase):
    def run_case(self,profile,failures):
        run=SimpleNamespace(threads=[{'stage':'research','thread':'existing-research-thread'}],phase=Mock())
        cfg={'_model_profile':profile} if profile else {}
        with patch('workflow.read_json',return_value={}),patch('workflow.validate_outline',return_value={'slides':[{'id':'a'}]}),patch('workflow.check_decisions',side_effect=failures) as check:
            result=validated_planning(run,cfg,Path('/synthetic/job'),{'pages':1},{'mode':'create'},'Original scope.',required=True,require_variation=True)
        return run,check,result
    def test_external_plan_error_is_repaired_in_existing_research_context(self):
        run,check,result=self.run_case({'model':'external'},[ValueError('Missing exact fields'),{'ok':True}])
        self.assertEqual(check.call_count,2);run.phase.assert_called_once()
        self.assertEqual(run.phase.call_args.kwargs['thread'],'existing-research-thread')
        self.assertEqual(run.phase.call_args.args[0],'research')
        self.assertIn('--template',run.phase.call_args.args[1]);self.assertIn('do not repeat research',run.phase.call_args.args[1])
    def test_default_provider_retains_existing_hard_gate(self):
        with self.assertRaisesRegex(ValueError,'Invalid choices'):self.run_case(None,[ValueError('Invalid choices')])
    def test_external_feedback_is_bounded_and_does_not_accept_an_invalid_plan(self):
        run=SimpleNamespace(threads=[],phase=Mock())
        with patch('workflow.read_json',return_value={}),patch('workflow.validate_outline',return_value={'slides':[]}),patch('workflow.check_decisions',side_effect=ValueError('Still invalid')) as check:
            with self.assertRaisesRegex(ValueError,'Still invalid'):validated_planning(run,{'_model_profile':{'model':'external'}},Path('/synthetic/job'),{'pages':1},{},'Scope',required=True,require_variation=True)
        self.assertEqual(check.call_count,3);self.assertEqual(run.phase.call_count,2)

if __name__=='__main__':unittest.main()
