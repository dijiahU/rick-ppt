import json,unittest
from public_review import envelope,publish
class PublicReviewTests(unittest.TestCase):
 def report(self):return {'summary':'Clear', 'pages_reviewed':[1,2], 'findings':[{'id':'S1','pages':[2],'severity':'suggestion','observation':'Small note','impact':'Harder to read','recommendation':'Enlarge it','route':'retain_suggestion'}], 'limitations':['No Windows playback verification.']}
 def receipt(self):return {'artifact_sha256':'a'*64,'round':2,'content_first_view':self.report(),'content':self.report(),'visual':self.report()}
 def trace(self):
  class Trace:
   def __init__(self):self.events=[];self.flushed=False
   def emit(self,*args,**kwargs):self.events.append((args,kwargs))
   def flush(self,**kwargs):self.flushed=True
  return Trace()
 def test_versioned_public_fields_and_no_author_metadata(self):
  report=self.report();report['reasoning']='PRIVATE';report['thread_id']='PRIVATE';report['findings'][0]['local_file']='/Users/private/input'
  result=envelope(self.receipt(),'visual',report,7)
  self.assertEqual(result['artifactSha256'],'a'*64);self.assertEqual(result['revision'],7);self.assertEqual(result['suggestionCount'],1);self.assertNotIn('PRIVATE',json.dumps(result));self.assertNotIn('route',result['report']['findings'][0]);self.assertFalse(result['truncated'])
 def test_large_reports_keep_counts_and_valid_json_under_trace_limit(self):
  report=self.report();report['findings']=[{**report['findings'][0],'id':str(i),'severity':'required' if i%2 else 'suggestion','observation':'测'*2000,'impact':'测'*2000,'recommendation':'测'*2000} for i in range(60)]
  value=envelope(self.receipt(),'content-evidence',report,1)
  self.assertLessEqual(len(json.dumps(value,ensure_ascii=False).encode('utf-16-le'))//2,15000);self.assertTrue(value['truncated']);self.assertEqual(value['requiredCount'],30);self.assertEqual(value['suggestionCount'],30);self.assertTrue(all(f['severity']=='required' for f in value['report']['findings']))
 def test_actual_reports_are_published_without_new_model_or_review_pass(self):
  trace=self.trace();publish(trace,self.receipt(),3)
  self.assertEqual([e[1]['detail']['kind'] for e in trace.events],['content-first','content-evidence','visual']);self.assertTrue(trace.flushed)
  self.assertEqual([e[1]['detail']['suggestionCount'] for e in trace.events],[1,1,1])
 def test_faithful_source_publishes_both_real_reports_and_all_required_findings(self):
  receipt=self.receipt();receipt['content_first_view']=None
  for key,count in [('content',3),('visual',5)]:
   receipt[key]['summary']='Actual '+key+' review'
   receipt[key]['findings']=[{**receipt[key]['findings'][0],'id':key+'-'+str(i),'severity':'required'} for i in range(count)]
  trace=self.trace();publish(trace,receipt,7)
  reports=[e[1]['detail'] for e in trace.events]
  self.assertEqual([r['kind'] for r in reports],['content-evidence','visual']);self.assertTrue(trace.flushed)
  self.assertEqual([r['report']['summary'] for r in reports],['Actual content review','Actual visual review'])
  self.assertEqual([r['requiredCount'] for r in reports],[3,5])
  self.assertEqual([f['id'] for r in reports for f in r['report']['findings']],[f['id'] for key in ('content','visual') for f in receipt[key]['findings']])
  self.assertTrue(all(r['artifactSha256']=='a'*64 and r['revision']==7 and r['round']==2 and not r['truncated'] for r in reports))
 def test_required_report_missing_or_none_is_not_silently_skipped(self):
  for key in ('content','visual'):
   for absent in (False,True):
    with self.subTest(key=key,absent=absent):
     receipt=self.receipt();receipt['content_first_view']=None
     if absent:del receipt[key]
     else:receipt[key]=None
     trace=self.trace()
     with self.assertRaises(KeyError if absent else TypeError):publish(trace,receipt,3)
     self.assertFalse(trace.flushed)
 def test_design_status_is_visible_without_changing_public_schema(self):
  from design_completion import CONTRACT
  receipt=self.receipt();receipt.update(design_completion=dict(CONTRACT),output_language='zh-CN')
  receipt['visual']['design_assessment']={'readiness':'needs_revision','primary_findings':['S1']}
  value=envelope(receipt,'visual',receipt['visual'],3)
  self.assertEqual(value['schema'],'rickppt-review/v1');self.assertFalse(value['truncated'])
  self.assertTrue(value['report']['summary'].startswith('设计判断：仍需实质设计修改'))
  self.assertEqual(envelope(receipt,'content-evidence',receipt['content'],3)['report']['summary'],'Clear')
 def test_local_paths_are_not_published(self):
  report=self.report();report['limitations']=['Inspect /Users/rick/private/report.json and /private/tmp/secret.txt']
  self.assertNotIn('/Users',json.dumps(envelope(self.receipt(),'visual',report,0)))
if __name__=='__main__':unittest.main()
