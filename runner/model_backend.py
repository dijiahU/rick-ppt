"""Host-owned model selection. Provider keys never enter model tool environments."""
from pathlib import Path
from urllib.parse import urlsplit
import hashlib,json,os,stat

KEY_ENV='PPTX_MODEL_API_KEY'
DEFAULT_TASK_MODEL='gpt-6.2-sol'
DEFAULT_TASK_REASONING_EFFORT='xhigh'

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

SERVICE_TIERS=('auto','default','fast','priority')
TASK_SERVICE_TIERS=('fast',)
# Only providers known to accept an OpenAI service_tier receive the task's Fast
# choice when their profile does not set one. Others ignore it (recorded).
FAST_TIER_HOSTS=('api.openai.com',)

def task_service_tier(state_root,task_id,existing,requested=None):
    """Pin the website's per-task speed choice at first admission.

    Like default-model.json, the receipt is written only for a new admission;
    resume/repair rounds reuse it. Tasks without a receipt (all historical and
    every non-Fast task) keep the worker-level behavior unchanged."""
    if requested is not None and requested not in TASK_SERVICE_TIERS:raise ValueError('Invalid task service_tier')
    folder=Path(state_root)/task_id;path=folder/'service-tier.json'
    if path.exists():
        tier=json.loads(path.read_text()).get('service_tier')
        if tier not in TASK_SERVICE_TIERS:raise ValueError('Invalid pinned task service_tier')
        return tier
    if existing or requested is None:return None
    folder.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as out:json.dump({'service_tier':requested},out)
    return requested

def service_tier_for(cfg,*,task_only=False):
    """Task choice first, then the worker-level default_service_tier."""
    cfg=cfg or {}
    tier=cfg.get('_task_service_tier')
    if tier is not None:
        if tier not in SERVICE_TIERS:raise ValueError('Invalid task service_tier')
        return tier
    if task_only:return None
    tier=cfg.get('default_service_tier')
    if tier is not None and tier not in SERVICE_TIERS:raise ValueError('Invalid default_service_tier')
    return tier

def apply_service_tier(config,cfg,*,task_only=False):
    """Speed tier for Codex sessions on the operator's Codex account (e.g. "fast").
    Fast mode trades higher credit use for lower latency; unset keeps Codex's own.
    task_only=True applies only a per-task choice, for helpers that never used the
    worker-level default (so a task without the choice is unchanged)."""
    tier=service_tier_for(cfg,task_only=task_only)
    if tier is None:return config
    config['service_tier']=tier
    config.setdefault('features',{})['fast_mode']=tier in ('fast','priority')
    return config

def profile_with_task_tier(profile,tier):
    """API profile route: an explicit profile service_tier wins; otherwise apply
    the task choice only where the provider supports it. Never fails the task.
    Returns (profile, note) where note records the decision or is None."""
    if profile is None or tier is None:return profile,None
    if profile.get('service_tier') is not None:
        return profile,{'requested':tier,'applied':profile['service_tier'],'reason':'profile_service_tier'}
    if urlsplit(profile['base_url']).hostname not in FAST_TIER_HOSTS:
        return profile,{'requested':tier,'applied':None,'reason':'provider_unsupported'}
    return {**profile,'service_tier':tier},{'requested':tier,'applied':tier,'reason':'task_choice'}

def load_profile(path):
    path=Path(path).resolve(strict=True);info=path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size>65536:raise ValueError('Invalid model profile file')
    data=json.loads(path.read_text())
    allowed={'model','base_url','api_key','api_key_env','wire_api','web_search','image_generation','reasoning_effort','auxiliary_tools','service_tier','responses_transport'}
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
    if data.get('service_tier') is not None and data['service_tier'] not in SERVICE_TIERS:raise ValueError('Invalid service_tier')
    if data.get('responses_transport','buffered') not in ('buffered','streaming'):raise ValueError('Invalid responses_transport')
    return {**data,'model':model.strip(),'base_url':url.rstrip('/'),'api_key':key,'wire_api':data.get('wire_api','responses')}

def public_identity(profile):
    if profile is None:return {'backend':'codex-default'}
    identity={'backend':profile.get('wire_api','responses'),'model':profile['model'],'base_url':profile['base_url'],
      'web_search':profile.get('web_search','disabled'),'image_generation':profile.get('image_generation',False),
      'reasoning_effort':profile.get('reasoning_effort')}
    if profile.get('auxiliary_tools','disabled')!='disabled':identity['auxiliary_tools']=profile['auxiliary_tools']
    if profile.get('service_tier') is not None:identity['service_tier']=profile['service_tier']
    if 'responses_transport' in profile:identity['responses_transport']=profile['responses_transport']
    if profile.get('customer_funded'):identity.update(customer_funded=True,store=False)
    return identity

def retained_tools(profile):return bool(profile and profile.get('auxiliary_tools')=='existing_backend')

def available_backends(cfg):
    """Advertise actual host routes; a configured API never replaces Codex."""
    return ['api','codex'] if cfg.get('_model_profile') else ['codex']


def profile_for_task(state_root,task_id,profile,existing,*,execution_backend=None):
    if execution_backend not in (None,'api','codex'):raise ValueError('Invalid task execution_backend')
    selection=Path(state_root)/task_id/'execution-choice.json'
    if selection.exists():
        pinned=json.loads(selection.read_text())['execution_backend']
        if execution_backend is not None and execution_backend!=pinned:
            raise ValueError('An existing task cannot change execution backend')
        execution_backend=pinned
    path=Path(state_root)/task_id/'model-backend.json'
    # Historical/default-provider admissions keep their original provider on resume.
    # A backend receipt may already exist before journal initialization succeeded.
    if not path.exists():
        if existing:
            if execution_backend=='api':raise ValueError('An existing default task cannot switch to API')
            return None
        if execution_backend=='codex':return None
        if execution_backend=='api' and profile is None:raise ValueError('API backend is not configured; no fallback was performed')
        return profile
    if json.loads(path.read_text()).get('backend')=='codex-default':
        if execution_backend=='api':raise ValueError('This task is pinned to local Codex')
        return None
    if execution_backend=='codex':raise ValueError('This task is pinned to API')
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

def bind_task(state_root,task_id,profile,existing,*,execution_backend=None):
    # Host-only directory, outside the model workspace and checkpoint blobs.
    identity=public_identity(profile);folder=Path(state_root)/task_id;folder.mkdir(parents=True,exist_ok=True)
    path=folder/'model-backend.json'
    if execution_backend not in (None,'api','codex'):raise ValueError('Invalid task execution_backend')
    if execution_backend=='api' and profile is None:raise ValueError('API task requires an API profile')
    if execution_backend=='codex' and profile is not None:raise ValueError('Local Codex task cannot use an API profile')
    choice=folder/'execution-choice.json'
    if choice.exists():
        pinned=json.loads(choice.read_text())['execution_backend']
        if execution_backend is not None and pinned!=execution_backend:raise ValueError('Task execution choice is immutable')
        if (pinned=='api')!=(profile is not None):raise ValueError('Model provider differs from pinned execution choice')
    if path.exists():
        if json.loads(path.read_text())!=identity:raise ValueError('Task belongs to another model/API. Use a new task for comparison, or restore its original model profile to resume.')
    else:
        if existing and profile is not None:raise ValueError('An existing default-model task cannot silently resume under another API. Create a new comparison task.')
        body=(json.dumps(identity,sort_keys=True)+'\n').encode()
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as out:out.write(body)
    if execution_backend is not None and not choice.exists():
        fd=os.open(choice,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as out:json.dump({'execution_backend':execution_backend},out)
