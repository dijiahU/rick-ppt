"""Host-only per-task customer credentials. No key is persisted in task state."""
import json
import os
from pathlib import Path

CATALOG = {
    'openai': ('https://api.openai.com/v1', 'responses', ('gpt-6-astra','gpt-6.1-sol','gpt-6-luna')),
    'deepseek': ('https://api.deepseek.com', 'responses', ('deepseek-flash',)),
    'siliconflow': ('https://api.siliconflow.cn/v1', 'chat_completions', (
        'deepseek-ai/DeepSeek-V4.1-Flash','zai-org/GLM-5.3-Flash',
        'Pro/moonshotai/Kimi-K2.6','Qwen/Qwen3.6-35B-A3B')),
}

def customer_profile(state_root,task,send):
    """Called before workspace creation, model calls, or recovery replay."""
    path=Path(state_root)/task['id']/'customer-account.json'
    marker=task.get('funding_mode')
    if marker is None and not path.exists():return None
    if marker!='user_api' or task.get('execution_backend')!='api':
        raise ValueError('Customer-funded task cannot change funding route')
    result=send(f'/api/worker/{task["id"]}/model-profile',lease=task['lease'])
    binding=result.get('funding');key=result.get('apiKey')
    if (not isinstance(binding,dict) or set(binding)!={'version','credentialId','provider','model'}
            or binding['version']!=1 or binding['provider'] not in CATALOG
            or not isinstance(binding['credentialId'],str) or not binding['credentialId']
            or not isinstance(key,str) or not 12<=len(key)<=1024 or any(ord(c)<33 or ord(c)>126 for c in key)):
        raise ValueError('Customer credential is unavailable; no fallback was performed')
    origin,wire,models=CATALOG[binding['provider']]
    if binding['model'] not in models:raise ValueError('Customer model is not approved')
    if path.exists():
        if json.loads(path.read_text())!=binding:raise ValueError('Customer task identity changed')
    else:
        path.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as stream:json.dump(binding,stream,sort_keys=True)
    return {'base_url':origin,'wire_api':wire,'api_key':key,'model':binding['model'],
            'reasoning_effort':'high','responses_transport':'streaming',
            'web_search':'disabled','image_generation':False,'auxiliary_tools':'disabled',
            'customer_funded':True,'store':False}
