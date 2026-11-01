"""Synthetic service failures, never terminates real apps or modifies real power settings."""
import importlib.util,unittest,subprocess,tempfile,plistlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('watch',Path(__file__).with_name('service-watchdog.py'));watch=importlib.util.module_from_spec(spec);spec.loader.exec_module(watch)
class WatchTests(unittest.TestCase):
 def test_battery_releases_sleep_and_stops_only_verified_worker_without_startup(self):
  import json,os
  calls=[]
  def run(args,timeout=6):
   calls.append(args)
   text='SleepDisabled 1' if args[0]=='/usr/bin/pmset' else '567' if args[0]=='/usr/bin/pgrep' else str(watch.WORKER/'runner.py') if args[0]=='/bin/ps' else ''
   return SimpleNamespace(returncode=0,stdout=text)
  with tempfile.TemporaryDirectory() as t,patch.object(watch,'WORKER',Path(t)),patch.object(watch,'command',side_effect=run),patch.object(watch,'power_source',return_value='battery'),patch.dict(os.environ,{'PPTX_WORKER_AC_ONLY':'1'}):
   (Path(t)/'worker.lock').write_text('123')
   (Path(t)/'runtime-123.local.json').write_text(json.dumps({'pid':123,'power_interrupt_supported':True}))
   report=watch.check(now=1000)
  self.assertFalse(report['status']['sleep_protected']);self.assertFalse(report['status']['services_allowed'])
  self.assertIn(['/usr/bin/sudo','-n','/usr/bin/pmset','-a','disablesleep','0'],calls)
  self.assertIn(['/bin/kill','-TERM','567'],calls);self.assertIn(['/bin/kill','-USR1','123'],calls)
  self.assertFalse(any(a[0] in ('/usr/bin/open','/usr/local/bin/docker','/usr/bin/curl') for a in calls))
  self.assertFalse(any(str(watch.ROOT/'start-worker.py') in a for a in calls))
 def test_unknown_supply_does_not_restart_and_wrong_pid_is_never_signalled(self):
  import os
  calls=[]
  def run(args,timeout=6):
   calls.append(args);return SimpleNamespace(returncode=0 if args[0]=='/bin/ps' else 1,stdout='/unrelated/runner.py')
  with tempfile.TemporaryDirectory() as t,patch.object(watch,'WORKER',Path(t)),patch.object(watch,'command',side_effect=run),patch.object(watch,'power_source',return_value='unknown'),patch.dict(os.environ,{'PPTX_WORKER_AC_ONLY':'1'}):
   (Path(t)/'worker.lock').write_text('123');report=watch.check(now=1000)
  self.assertFalse(report['status']['services_allowed']);self.assertFalse(report['status']['worker_running'])
  self.assertFalse(any(a[0] in ('/bin/kill','/usr/bin/open') for a in calls))
 def test_replug_restores_existing_services(self):
  import os
  with tempfile.TemporaryDirectory() as t,patch.object(watch,'WORKER',Path(t)),patch.object(watch,'command',side_effect=self.fixture()),patch.object(watch,'power_source',return_value='ac'),patch.object(watch,'local_proxy_ready',return_value=True),patch.dict(os.environ,{'PPTX_WORKER_AC_ONLY':'1'}):
   report=watch.check(now=1000)
  self.assertTrue(report['status']['services_allowed']);self.assertTrue(report['status']['sleep_protected'])
  self.assertTrue(any(str(watch.ROOT/'start-worker.py') in a for a in self.calls))
 def fixture(self):
  self.calls=[]
  def run(args,timeout=6):
   self.calls.append(args)
   if args[0]=='/usr/bin/pmset':return SimpleNamespace(returncode=0,stdout='SleepDisabled 0')
   if args[0]=='/usr/bin/pgrep':return SimpleNamespace(returncode=1,stdout='')
   if args[0]=='/usr/local/bin/docker':return SimpleNamespace(returncode=1,stdout='')
   return SimpleNamespace(returncode=0,stdout='')
  return run
 def test_awake_does_not_depend_on_worker_or_amp_being_alive(self):
  with tempfile.TemporaryDirectory() as t,patch.object(watch,'WORKER',Path(t)),patch.object(watch,'command',side_effect=self.fixture()),patch.object(watch,'local_proxy_ready',return_value=True):
   report=watch.check(now=1000)
  self.assertTrue(report['status']['sleep_protected']);self.assertFalse(report['status']['worker_running'])
  self.assertIn(['/usr/bin/sudo','-n','/usr/bin/pmset','-a','disablesleep','1'],self.calls)
  self.assertTrue(any('/Applications/Amphetamine.app' in a for a in self.calls));self.assertTrue(any('/Applications/Docker.app' in a for a in self.calls))
  self.assertTrue(any(str(watch.ROOT/'start-worker.py') in a for a in self.calls));self.assertFalse(any(a[-1]=='0' and 'disablesleep' in a for a in self.calls))
 def test_repeat_failure_throttles_launches_and_only_reopens_existing_proxy_app(self):
  with tempfile.TemporaryDirectory() as t,patch.object(watch,'WORKER',Path(t)),patch.object(watch,'command',side_effect=self.fixture()),patch.object(watch,'local_proxy_ready',return_value=False):
   first=watch.check(now=1000);self.calls.clear();watch.check(first,now=1010)
   self.assertFalse(any(a[0]=='/usr/bin/open' for a in self.calls));self.assertFalse(any(str(watch.ROOT/'start-worker.py') in a for a in self.calls))
 def test_unused_all_proxy_does_not_report_https_transport_down(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'login.plist';p.write_bytes(plistlib.dumps({'EnvironmentVariables':{'HTTPS_PROXY':'http://127.0.0.1:7890','HTTP_PROXY':'http://127.0.0.1:7890','ALL_PROXY':'socks5://127.0.0.1:7891'}}))
   with patch.object(watch,'LOGIN',p),patch.object(watch.socket,'create_connection') as connect:
    self.assertTrue(watch.local_proxy_ready());self.assertEqual(connect.call_count,1);self.assertEqual(connect.call_args.args[0],('127.0.0.1',7890))
 def test_short_image_lookup_failure_is_rechecked_without_pull(self):
  calls=[]
  def run(args,timeout=6):
   calls.append(args)
   if args[0]=='/usr/local/bin/docker':
    if args[1]=='info':return SimpleNamespace(returncode=0,stdout='29.2.1')
    ok='docker.io/library/pptx-lab-renderer:1' in args
    return SimpleNamespace(returncode=0 if ok else 1,stdout='sha256:local' if ok else '')
   return SimpleNamespace(returncode=0,stdout='SleepDisabled 1' if args[0]=='/usr/bin/pmset' else '')
  with tempfile.TemporaryDirectory() as t,patch.object(watch,'WORKER',Path(t)),patch.object(watch,'command',side_effect=run),patch.object(watch,'local_proxy_ready',return_value=True):
   report=watch.check(now=1000)
  self.assertTrue(report['status']['renderer_ready']);self.assertFalse(any('pull' in a or 'build' in a for a in calls))
if __name__=='__main__':unittest.main()
