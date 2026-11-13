"""Real boundary regression checks against synthetic canaries only."""
import subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runner'))
import runner
cfg=runner.settings();job=runner.prepare(cfg)
with tempfile.TemporaryDirectory(prefix='pptx-boundary-canary-') as private:
    outside=Path(private)/'canary.txt';outside.write_text('SYNTHETIC-CANARY')
    (job/'escape').symlink_to(outside)
    source=r'''
import os,socket,errno
from pathlib import Path
outside=Path(OUTSIDE)
assert os.getuid()!=0 and os.getresuid()==(os.getuid(),)*3
def denied(action):
    try:action()
    except PermissionError:return
    raise AssertionError('Boundary operation was unexpectedly allowed')
denied(lambda:outside.read_text())
denied(lambda:Path('escape').read_text())
denied(lambda:outside.write_text('changed'))
denied(lambda:os.chmod(outside,0o777))
denied(lambda:os.truncate(outside,0))
denied(lambda:os.setuid(0))
for family in (socket.AF_UNIX,socket.AF_INET,socket.AF_INET6):
    denied(lambda:socket.socket(family))
Path('allowed.txt').write_text('OK')
Path('allowed.txt').rename('renamed.txt')
assert Path('renamed.txt').read_text()=='OK'
import xml.etree.ElementTree as E
assert E.fromstring('<ok/>').tag=='ok'
print('PASS: uid drop, file/symlink confinement, host metadata protection, truncate denial, no privilege regain, all socket families denied, task write/rename and XML parsing')
'''.replace('OUTSIDE',repr(str(outside)))
    subprocess.run(runner.sandbox(cfg,job,[cfg['python'],'-c',source]),cwd=job,env=runner.environment(job),check=True)
    assert outside.read_text()=='SYNTHETIC-CANARY'
print('Sandbox boundary checks passed:',job)
