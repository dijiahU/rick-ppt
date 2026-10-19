#!/usr/bin/env python3
"""Request actual font files from the production host, without shell networking."""
import argparse
import json
import os
from pathlib import Path
import time
import uuid

p=argparse.ArgumentParser(description=__doc__);p.add_argument('font_id');p.add_argument('--text',default='');p.add_argument('--url');p.add_argument('--license-url');p.add_argument('--family');p.add_argument('--weight',type=int,default=400)
args=p.parse_args();root=Path(__file__).resolve().parent;queue=root/'font-requests';ident=uuid.uuid4().hex
data=json.dumps(vars(args),ensure_ascii=False).encode()
if len(data)>16000:raise SystemExit('Font request too large')
pending=queue/(ident+'.pending');pending.write_bytes(data);os.replace(pending,queue/(ident+'.request.json'))
deadline=time.monotonic()+180
while time.monotonic()<deadline:
    reply=queue/(ident+'.reply.json')
    if reply.is_file():
        result=json.loads(reply.read_text());print(json.dumps(result,ensure_ascii=False));raise SystemExit(0 if result.get('ok') else 1)
    time.sleep(.25)
raise SystemExit('Font import timed out; inspect the existing reply before retrying')
