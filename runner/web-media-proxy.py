#!/usr/bin/env python3
"""Task-side request client. Never downloads directly or changes permissions."""
import argparse
import json
import os
from pathlib import Path
import time
import uuid

p=argparse.ArgumentParser();p.add_argument('url');p.add_argument('--source-page',required=True);p.add_argument('--purpose',required=True);args=p.parse_args()
root=Path(__file__).resolve().parent;queue=root/'media-requests';ident=uuid.uuid4().hex
data=json.dumps(vars(args)).encode()
if len(data)>8192:raise SystemExit('Request too large')
pending=queue/(ident+'.pending');pending.write_bytes(data);os.replace(pending,queue/(ident+'.request.json'))
deadline=time.monotonic()+300
while time.monotonic()<deadline:
    reply=queue/(ident+'.reply.json')
    if reply.is_file():
        result=json.loads(reply.read_text());print(json.dumps(result,ensure_ascii=False));raise SystemExit(0 if result.get('ok') else 1)
    time.sleep(.25)
raise SystemExit('Media import timed out; check the reply before retrying')
