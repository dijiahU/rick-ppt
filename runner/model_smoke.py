"""A real tool-use smoke for the selected API, without claiming queue jobs."""
import json,tempfile,time
from pathlib import Path
from durable import AppServer,task_configuration
from model_backend import KEY_ENV,overrides,public_identity

def smoke(cfg):
    profile=cfg.get('_model_profile')
    root=Path(tempfile.mkdtemp(prefix='pptx-model-smoke-')).resolve();(root/'tmp').mkdir()
    config=task_configuration(root,web_search='disabled');config.update(overrides(profile))
    config['web_search']='disabled';config['features.image_generation']=False
    try:
        with AppServer(cwd=root,config=config,provider_env={KEY_ENV:profile['api_key']} if profile else None) as server:
            thread=server.start_thread()['thread']['id']
            prompt='Use the shell tool to calculate 17 * 19 and write the answer as plain text to model-smoke.txt in the current directory. Also use the shell tool to check whether PPTX_MODEL_API_KEY exists in the tool environment, without printing its value, and write ONLY absent or present to key-visibility.txt. Do not read any other credentials. Then report completion.'
            turn=server.start_turn(thread,prompt)['id'];result=server.wait_turn(thread,turn,timeout=120)
            if result.get('status')!='completed':raise RuntimeError('Model smoke did not complete')
        if (root/'model-smoke.txt').read_text().strip()!='323':raise RuntimeError('Model tool-use file check failed')
        if (root/'key-visibility.txt').read_text().strip()!='absent':raise RuntimeError('Provider key was visible to the tool environment')
        proof={'ok':True,'model':public_identity(profile),'checks':['tool execution','actual file write','provider key absent from tools'],'workspace':str(root)}
        (root/'proof.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof))
    except Exception as error:
        print(json.dumps({'ok':False,'model':public_identity(profile),'error':type(error).__name__,'workspace':str(root)}))
        raise SystemExit(1)
