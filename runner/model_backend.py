"""Host-owned model selection. Provider keys never enter model tool environments."""
from pathlib import Path
from urllib.parse import urlsplit
import hashlib,json,os,stat

KEY_ENV='PPTX_MODEL_API_KEY'

def load_profile(path):
    path=Path(path).resolve(strict=True);info=path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size>65536:raise ValueError('Invalid model profile file')
    data=json.loads(path.read_text())
    allowed={'model','base_url','api_key','api_key_env','wire_api','web_search','image_generation','reasoning_effort'}
    if not isinstance(data,dict) or set(data)-allowed:raise ValueError('Unknown model profile fields')
    model=data.get('model');url=data.get('base_url')
    if not isinstance(model,str) or not model.strip() or len(model)>200 or any(ord(c)<32 for c in model):raise ValueError('A valid model ID is required')
    if not isinstance(url,str):raise ValueError('base_url is required')
    u=urlsplit(url)
    if not u.hostname or u.username or u.password or u.query or u.fragment:raise ValueError('base_url must not contain credentials, query or fragment')
    if u.scheme!='https' and not(u.scheme=='http' and u.hostname in ('localhost','127.0.0.1','::1')):raise ValueError('Use HTTPS, or HTTP for a local provider')
    if data.get('wire_api','responses') not in ('responses','chat_completions'):raise ValueError('wire_api must be responses or chat_completions')
    if url.rstrip('/').endswith(('/responses','/chat/completions')):raise ValueError('Use the API base URL, without /responses or /chat/completions')
    if data.get('api_key') and data.get('api_key_env'):raise ValueError('Choose api_key OR api_key_env')
    if data.get('api_key') and info.st_mode&0o077:raise ValueError('Profile containing a key must be private: chmod 600 PROFILE')
    envname=data.get('api_key_env',KEY_ENV)
    if not isinstance(envname,str) or not envname or not all(c.isupper() or c.isdigit() or c=='_' for c in envname):raise ValueError('Invalid API key environment variable name')
    key=data.get('api_key') or os.environ.get(envname)
    if not isinstance(key,str) or not key.strip() or any(c in key for c in '\r\n'):raise ValueError('API key is missing; configure it locally or in the named environment variable')
    if data.get('web_search','disabled') not in ('disabled','live','cached'):raise ValueError('Invalid web_search capability')
    if type(data.get('image_generation',False)) is not bool:raise ValueError('image_generation must be boolean')
    effort=data.get('reasoning_effort')
    if effort is not None and effort not in ('minimal','low','medium','high','xhigh'):raise ValueError('Invalid reasoning_effort')
    return {**data,'model':model.strip(),'base_url':url.rstrip('/'),'api_key':key,'wire_api':data.get('wire_api','responses')}

def public_identity(profile):
    if profile is None:return {'backend':'codex-default'}
    return {'backend':profile.get('wire_api','responses'),'model':profile['model'],'base_url':profile['base_url'],
      'web_search':profile.get('web_search','disabled'),'image_generation':profile.get('image_generation',False),
      'reasoning_effort':profile.get('reasoning_effort')}

def overrides(profile):
    if profile is None:return {}
    config={'model':profile['model'],'model_provider':'pptx_external',
      'model_providers':{'pptx_external':{'name':'PPTX external API','base_url':profile['base_url'],'wire_api':'responses','env_key':KEY_ENV,'requires_openai_auth':False}},
      'web_search':profile.get('web_search','disabled'),'features.image_generation':profile.get('image_generation',False),
      'model_supports_reasoning_summaries':False,'model_reasoning_summary':'none'}
    if profile.get('reasoning_effort'):config['model_reasoning_effort']=profile['reasoning_effort']
    return config

def bind_task(state_root,task_id,profile,existing):
    # Host-only directory, outside the model workspace and checkpoint blobs.
    identity=public_identity(profile);folder=Path(state_root)/task_id;folder.mkdir(parents=True,exist_ok=True)
    path=folder/'model-backend.json'
    if path.exists():
        if json.loads(path.read_text())!=identity:raise ValueError('Task belongs to another model/API. Use a new task for comparison, or restore its original model profile to resume.')
        return
    if existing and profile is not None:raise ValueError('An existing default-model task cannot silently resume under another API. Create a new comparison task.')
    body=(json.dumps(identity,sort_keys=True)+'\n').encode()
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as out:out.write(body)
