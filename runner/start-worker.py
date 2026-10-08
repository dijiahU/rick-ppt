"""Start/reload the configured worker, draining active jobs before handoff."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent
WORKER=ROOT.parent/'.work/interactive-runtime-20260920/repo/runner'
if not (WORKER/'runner.py').is_file():WORKER=ROOT
sys.path.insert(0,str(WORKER))
from production_bridge import launch_environment,launch_interpreter


def verified_process(pid):
    command=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True)
    return command.returncode==0 and str(WORKER/'runner.py') in command.stdout


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--reload',action='store_true');args=parser.parse_args()
    env=launch_environment(WORKER,ROOT/'settings.local.json')
    python=launch_interpreter(WORKER)
    with (WORKER/'launch.lock').open('a+') as guard:
        fcntl.flock(guard,fcntl.LOCK_EX)
        old_pid=None
        with (WORKER/'worker.lock').open('a+') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                lock.seek(0);old_pid=int(lock.read().strip())
                if not verified_process(old_pid):raise SystemExit('Lock owner could not be verified; no signal sent.')
                if not args.reload:
                    print('Worker already running:',old_pid);return
                handoff=WORKER/'handoff.local.json'
                if handoff.is_file():
                    prior=json.loads(handoff.read_text())
                    if prior['pid']!=old_pid and verified_process(prior['pid']):
                        if prior['plugin']!=env['PPTX_RUNNER_PLUGIN']:
                            raise SystemExit('A handoff to another runtime is already pending; no duplicate started.')
                        print('Configured successor is already waiting:',prior['pid']);return
                os.kill(old_pid,signal.SIGTERM)  # Stop new claims; finish active jobs.
            else:fcntl.flock(lock,fcntl.LOCK_UN)
        fd=os.open(WORKER/'worker-output.log',os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
        command=[python,str(WORKER/'runner.py')]
        if old_pid:command.append('--wait-for-worker')
        try:child=subprocess.Popen(command,cwd=WORKER,env=env,stdin=subprocess.DEVNULL,stdout=fd,stderr=fd,start_new_session=True)
        finally:os.close(fd)
        handoff=WORKER/'handoff.local.json'
        with os.fdopen(os.open(handoff,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600),'w') as stream:
            json.dump({'pid':child.pid,'previous_pid':old_pid,'plugin':env['PPTX_RUNNER_PLUGIN']},stream)
        for _ in range(50):
            if child.poll() is not None:raise SystemExit('Successor exited during startup; inspect the private worker log.')
            receipt=WORKER/('runtime-'+str(child.pid)+'.local.json')
            if receipt.is_file():
                active=json.loads(receipt.read_text())
                if active['pid']!=child.pid or active['plugin']!=env['PPTX_RUNNER_PLUGIN']:
                    raise SystemExit('Loaded runtime differs from selected settings; inspect the private receipt.')
                if active['status']=='ready':
                    print('Background worker ready:',child.pid,'runtime:',active['version']);return
                if active['status']=='waiting':
                    print('Successor configured:',child.pid,'runtime:',active['version'],'waiting for active jobs in',old_pid);return
            time.sleep(.1)
        raise SystemExit('Startup is not yet confirmed; inspect the private worker log before retrying.')

if __name__=='__main__':main()
