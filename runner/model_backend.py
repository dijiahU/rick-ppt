"""Host-owned model selection. Provider keys never enter model tool environments."""
from pathlib import Path
from urllib.parse import urlsplit
import hashlib,json,os,stat

KEY_ENV='PPTX_MODEL_API_KEY'
DEFAULT_TASK_MODEL='gpt-6.1-sol'
DEFAULT_TASK_REASONING_EFFORT='high'

def task_default_model(state_root,task_id,existing,configured=DEFAULT_TASK_MODEL,reasoning_effort=DEFAULT_TASK_REASONING_EFFORT):
    """Pin new default-provider tasks without changing legacy or external jobs."""
    folder=Path(state_root)/task_id;folder.mkdir(parents=True,exist_ok=True)
    path=folder/'default-model.json'
    if path.exists():return json.loads(path.read_text())['model']
    if existing:return None
    if not isinstance(configured,str) or not configured.strip():raise ValueError('Default task model is required')
    if reasoning_effort not in ('low','medium','high','xhigh','max','ultra'):raise ValueError('Invalid default task reasoning effort')
    model=configured.strip()
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as out:json.dump({'model':model,'reasoning_effort':reasoning_effort},out)
    return model

def task_default_reasoning_effort(state_root,task_id):
    """Old model-only receipts retain their original implicit effort."""
    path=Path(state_root)/task_id/'default-model.json'
    return json.loads(path.read_text()).get('reasoning_effort') if path.exists() else None

def load_profile(path):
    path=Path(path).resolve(strict=True);info=path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size>65536:raise ValueError('Invalid model profile file')
    data=json.loads(path.read_text())
    allowed={'model','base_url','api_key','api_key_env','wire_api','web_search','image_generation','reasoning_effort','auxiliary_tools','service_tier'}
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
    if data.get('auxiliary_tools','disabled') not in ('disabled','existing_backend'):raise ValueError('Invalid auxiliary tool route')
    effort=data.get('reasoning_effort')
    if effort is not None and effort not in ('minimal','low','medium','high','xhigh'):raise ValueError('Invalid reasoning_effort')
    if data.get('service_tier') is not None and data['service_tier'] not in ('auto','default','fast','priority'):raise ValueError('Invalid service_tier')
    return {**data,'model':model.strip(),'base_url':url.rstrip('/'),'api_key':key,'wire_api':data.get('wire_api','responses')}

def public_identity(profile):
    if profile is None:return {'backend':'codex-default'}
    identity={'backend':profile.get('wire_api','responses'),'model':profile['model'],'base_url':profile['base_url'],
      'web_search':profile.get('web_search','disabled'),'image_generation':profile.get('image_generation',False),
      'reasoning_effort':profile.get('reasoning_effort')}
    if profile.get('auxiliary_tools','disabled')!='disabled':identity['auxiliary_tools']=profile['auxiliary_tools']
    if profile.get('service_tier') is not None:identity['service_tier']=profile['service_tier']
    return identity

def retained_tools(profile):return bool(profile and profile.get('auxiliary_tools')=='existing_backend')

def profile_for_task(state_root,task_id,profile,existing):
    path=Path(state_root)/task_id/'model-backend.json'
    # Historical/default-provider admissions keep their original provider on resume.
    # A backend receipt may already exist before journal initialization succeeded.
    if not path.exists():return None if existing else profile
    if json.loads(path.read_text()).get('backend')=='codex-default':return None
    if json.loads(path.read_text())!=public_identity(profile):
        raise ValueError('Restore the original external API profile to resume this task')
    return profile

def overrides(profile):
    if profile is None:return {}
    config={'model':profile['model'],'model_provider':'pptx_external',
      'model_providers':{'pptx_external':{'name':'PPTX external API','base_url':profile['base_url'],'wire_api':'responses','env_key':KEY_ENV,'requires_openai_auth':False}},
      'web_search':profile.get('web_search','disabled'),'features.image_generation':profile.get('image_generation',False),
      'model_supports_reasoning_summaries':False,'model_reasoning_summary':'none'}
    if profile.get('reasoning_effort'):config['model_reasoning_effort']=profile['reasoning_effort']
    if profile.get('service_tier') is not None:
        config['service_tier']=profile['service_tier']
        config['features.fast_mode']=profile['service_tier'] in ('fast','priority')
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
