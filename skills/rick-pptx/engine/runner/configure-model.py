"""Interactive local profile creation; never accept a key on the command line."""
import argparse,getpass,json,os
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--base-url',required=True);p.add_argument('--model',required=True);p.add_argument('--protocol',choices=['responses','chat_completions'],default='responses');p.add_argument('--out',type=Path,default=Path(__file__).with_name('model-profile.local.json'));a=p.parse_args()
key=getpass.getpass('API Key (hidden; saved locally with mode 0600): ')
if not key or any(c in key for c in '\r\n'):raise SystemExit('API key must be nonempty and one line')
data={'model':a.model,'base_url':a.base_url,'wire_api':a.protocol,'api_key':key,'web_search':'disabled','image_generation':False}
# Validate with an exclusive private temporary file before publishing the profile.
import tempfile
from model_backend import load_profile
with tempfile.NamedTemporaryFile(mode='w',dir=a.out.parent,prefix='.model-profile-',suffix='.local.json') as f:
 json.dump(data,f);f.flush();load_profile(f.name)
fd=os.open(a.out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:json.dump(data,f,indent=2)
print('Profile created. Run runner.py --model-profile '+str(a.out.resolve())+' --model-smoke before starting jobs.')
