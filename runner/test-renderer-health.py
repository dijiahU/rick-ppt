"""Synthetic startup/dependency failures; no production queue calls or model usage."""
import subprocess,unittest,threading,json
from types import SimpleNamespace
from renderer_health import RendererReadiness,DOCKER,QUALIFIED_IMAGE,start_heartbeat

class ReadinessTests(unittest.TestCase):
 def make(self,engine=False,image=True):
  self.now=100.;self.engine=engine;self.image=image;self.calls=[];self.states=[]
  def run(args,**kwargs):
   self.calls.append((args,kwargs))
   if args[0]!=DOCKER:return SimpleNamespace(returncode=0,stdout='')
   if args[1]=='info':return SimpleNamespace(returncode=0 if self.engine else 1,stdout='29.2.1' if self.engine else '')
   return SimpleNamespace(returncode=0 if self.image else 1,stdout='sha256:fixture' if self.image else '')
  return RendererReadiness(run=run,clock=lambda:self.now,on_state=lambda *args:self.states.append(args),log=lambda *a,**k:None)
 def test_docker_down_never_claims_or_spends_a_model_turn(self):
  health=self.make();claims=[]
  self.assertIsNone(health.claim(lambda:claims.append(1)));self.assertEqual(claims,[])
  self.assertEqual(self.states,[(False,'docker_not_ready')]);self.assertEqual(self.calls[-1][0],['/usr/bin/open','-g','-a','/Applications/Docker.app'])
  health.claim(lambda:claims.append(1));self.assertEqual(len(self.calls),2)
 def test_engine_recovery_resumes_admission_and_notifies_once(self):
  health=self.make();health.ready();self.engine=True;self.now+=6
  self.assertEqual(health.claim(lambda:{'id':'synthetic'}),{'id':'synthetic'})
  self.assertEqual(self.states[-1],(True,'renderer_ready'));self.assertTrue(health.ready());self.assertEqual(len(self.states),2)
 def test_missing_image_never_downloads_or_claims(self):
  health=self.make(engine=True,image=False);claimed=[];health.claim(lambda:claimed.append(1))
  self.assertFalse(claimed);self.assertEqual(self.states,[(False,'renderer_image_missing')]);self.assertEqual([x[0][1] for x in self.calls],['info','image','image'])
 def test_short_name_false_negative_rechecks_equivalent_local_reference(self):
  def run(args,**kwargs):
   if args[1]=='info':return SimpleNamespace(returncode=0,stdout='29.2.1')
   return SimpleNamespace(returncode=0 if QUALIFIED_IMAGE in args else 1,stdout='sha256:local' if QUALIFIED_IMAGE in args else '')
  health=RendererReadiness(run=run,log=lambda *a,**k:None)
  self.assertEqual(health.claim(lambda:'allowed'),'allowed');self.assertEqual(health.reason,'renderer_ready')
 def test_waiting_heartbeat_never_calls_claim_and_advertises_no_ready_backend(self):
  stop=threading.Event();calls=[]
  def send(path,body):
   calls.append((path,json.loads(body)));stop.set();return {'ok':True}
  thread=start_heartbeat(self.make(),send,['codex','api'],stop,interval=.01);thread.join(1)
  self.assertFalse(thread.is_alive());self.assertEqual(calls,[('/api/worker?action=heartbeat',{'execution_backends':[]})])
 def test_heartbeat_failure_does_not_kill_supervisor_or_drop_the_next_pulse(self):
  stop=threading.Event();calls=[]
  def send(path,body):
   calls.append(path)
   if len(calls)==1:raise OSError('synthetic failure')
   stop.set();return {'ok':True}
  thread=start_heartbeat(self.make(engine=True),send,['codex'],stop,interval=.01,log=lambda *a,**k:None);thread.join(2)
  self.assertFalse(thread.is_alive());self.assertEqual(len(calls),2)
 def test_later_engine_failure_blocks_new_admission(self):
  health=self.make(engine=True);self.assertTrue(health.ready());self.engine=False;self.now+=16
  self.assertIsNone(health.claim(lambda:self.fail('must not claim')));self.assertEqual(self.states[-1],(False,'docker_not_ready'))
 def test_startup_is_throttled_and_probes_are_bounded(self):
  health=self.make()
  for _ in range(8):health.ready();self.now+=6
  self.assertEqual(sum(args[0]=='/usr/bin/open' for args,_ in self.calls),1)
  self.assertTrue(all(options['timeout']<=6 for _,options in self.calls))
 def test_timeout_stays_queued(self):
  states=[]
  def run(args,**kwargs):
   if args[0]==DOCKER:raise subprocess.TimeoutExpired(args,6)
   return SimpleNamespace(returncode=0,stdout='')
  health=RendererReadiness(run=run,on_state=lambda *a:states.append(a),log=lambda *a,**k:None)
  self.assertIsNone(health.claim(lambda:self.fail('must not claim')));self.assertEqual(states,[(False,'docker_not_ready')])

if __name__=='__main__':unittest.main()
