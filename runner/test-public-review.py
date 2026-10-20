import json,unittest
from public_review import envelope,publish
class PublicReviewTests(unittest.TestCase):
 def report(self):return {'summary':'Clear', 'pages_reviewed':[1,2], 'findings':[{'id':'S1','pages':[2],'severity':'suggestion','observation':'Small note','impact':'Harder to read','recommendation':'Enlarge it','route':'retain_suggestion'}], 'limitations':['No Windows playback verification.']}
 def receipt(self):return {'artifact_sha256':'a'*64,'round':2,'content_first_view':self.report(),'content':self.report(),'visual':self.report()}
 def test_versioned_public_fields_and_no_author_metadata(self):
  report=self.report();report['reasoning']='PRIVATE';report['thread_id']='PRIVATE';report['findings'][0]['local_file']='/Users/private/input'
  result=envelope(self.receipt(),'visual',report,7)
  self.assertEqual(result['artifactSha256'],'a'*64);self.assertEqual(result['revision'],7);self.assertEqual(result['suggestionCount'],1);self.assertNotIn('PRIVATE',json.dumps(result));self.assertNotIn('route',result['report']['findings'][0]);self.assertFalse(result['truncated'])
 def test_large_reports_keep_counts_and_valid_json_under_trace_limit(self):
  report=self.report();report['findings']=[{**report['findings'][0],'id':str(i),'severity':'required' if i%2 else 'suggestion','observation':'测'*2000,'impact':'测'*2000,'recommendation':'测'*2000} for i in range(60)]
  value=envelope(self.receipt(),'content-evidence',report,1)
  self.assertLessEqual(len(json.dumps(value,ensure_ascii=False).encode('utf-16-le'))//2,15000);self.assertTrue(value['truncated']);self.assertEqual(value['requiredCount'],30);self.assertEqual(value['suggestionCount'],30);self.assertTrue(all(f['severity']=='required' for f in value['report']['findings']))
 def test_actual_reports_are_published_without_new_model_or_review_pass(self):
  class Trace:
   def __init__(self):self.events=[];self.flushed=False
   def emit(self,*args,**kwargs):self.events.append((args,kwargs))
   def flush(self,**kwargs):self.flushed=True
  trace=Trace();publish(trace,self.receipt(),3)
  self.assertEqual([e[1]['detail']['kind'] for e in trace.events],['content-first','content-evidence','visual']);self.assertTrue(trace.flushed)
 def test_local_paths_are_not_published(self):
  report=self.report();report['limitations']=['Inspect /Users/rick/private/report.json and /private/tmp/secret.txt']
  self.assertNotIn('/Users',json.dumps(envelope(self.receipt(),'visual',report,0)))
if __name__=='__main__':unittest.main()
