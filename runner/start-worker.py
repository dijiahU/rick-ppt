"""Start the configured bridge independently of the current terminal/session.

No login service, credentials, queue mutation or automatic rerun is added. The
worker's existing singleton lock remains authoritative. Output stays host-local.
"""
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import time
import signal

ROOT=Path(__file__).resolve().parent
WORKER=ROOT.parent/'.work/interactive-runtime-20260920/repo/runner'
if not (WORKER/'runner.py').is_file():WORKER=ROOT

with (WORKER/'launch.lock').open('a+') as guard:
    fcntl.flock(guard,fcntl.LOCK_EX)
    with (WORKER/'worker.lock').open('a+') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            if sys.argv[1:]!=['--reload']:
                print('Worker already running; no second process started.')
                sys.exit(0)
            lock.seek(0);pid=int(lock.read().strip())
            command=subprocess.check_output(['ps','-p',str(pid),'-o','command='],text=True)
            if str(WORKER/'runner.py') not in command:
                raise SystemExit('Lock owner could not be verified; no signal sent.')
            os.kill(pid,signal.SIGTERM)  # Drain; never kill active jobs forcibly.
            for _ in range(50):
                try:
                    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    break
                except BlockingIOError:time.sleep(.1)
            else:
                raise SystemExit('Worker is draining active jobs; retry after it finishes. No duplicate started.')
        # Release before the child acquires the same authoritative lock. Other
        # starters use launch.lock; the worker itself rejects any duplicate.
        fcntl.flock(lock,fcntl.LOCK_UN)
    log=WORKER/'worker-output.log'
    fd=os.open(log,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
    try:
        child=subprocess.Popen([sys.executable,str(ROOT/'runner.py')],cwd=ROOT,
            stdin=subprocess.DEVNULL,stdout=fd,stderr=fd,start_new_session=True)
    finally:os.close(fd)
    for _ in range(30):
        if child.poll() is not None:
            raise SystemExit('Worker exited during startup; inspect the host-local worker-output.log.')
        try:
            if int((WORKER/'worker.lock').read_text().strip())==child.pid:
                print('Background worker started:',child.pid)
                break
        except (ValueError,OSError):pass
        time.sleep(.1)
    else:raise SystemExit('Worker startup not yet confirmed; inspect the host-local log before starting again.')
