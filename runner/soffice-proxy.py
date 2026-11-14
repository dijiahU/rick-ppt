#!/usr/bin/env python3
"""Task-scoped file IPC; the host only accepts a fixed PPTX-to-PDF operation."""
import json
import os
from pathlib import Path
import sys
import time
import uuid

job=Path(__file__).resolve().parent
queue=job/'render-requests'
queue.mkdir(exist_ok=True)
identifier=uuid.uuid4().hex
request=queue/(identifier+'.request.json')
temporary=queue/(identifier+'.pending')
temporary.write_text(json.dumps({'args':sys.argv[1:]}))
os.replace(temporary,request)
reply=queue/(identifier+'.reply.json')
reply_timeout=180 if sys.platform=='linux' else 85
deadline=time.monotonic()+reply_timeout
while time.monotonic()<deadline:
    if reply.is_file():
        result=json.loads(reply.read_text())
        if result.get('environment') and '--outdir' in sys.argv:
            destination=Path(sys.argv[sys.argv.index('--outdir')+1])
            (destination/'render-environment.json').write_text(json.dumps(result['environment']))
        print(result.get('stdout',''),end='')
        print(result.get('stderr',''),end='',file=sys.stderr)
        raise SystemExit(result['returncode'])
    time.sleep(.2)
raise SystemExit(f'Isolated renderer did not respond within {reply_timeout} seconds')
