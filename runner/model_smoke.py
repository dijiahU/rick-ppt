"""A real tool-use smoke for the selected API, without claiming queue jobs."""
import json,tempfile,time
from pathlib import Path
from durable import AppServer,task_configuration
from model_backend import KEY_ENV,overrides,public_identity
from chat_proxy import provider_session
from contextlib import ExitStack

def smoke(cfg):
    profile=cfg.get('_model_profile')
    root=Path(tempfile.mkdtemp(prefix='pptx-model-smoke-')).resolve();(root/'tmp').mkdir()
    config=task_configuration(root,web_search='disabled')
    config['web_search']='disabled';config['features.image_generation']=False
    try:
        with ExitStack() as resources:
            selected,provider_env,api_calls=resources.enter_context(provider_session(profile))
            config.update(selected)
            server=resources.enter_context(AppServer(cwd=root,config=config,provider_env=provider_env))
            thread=server.start_thread()['thread']['id']
            prompt='Use the shell tool to calculate 17 * 19 and write ONLY the resulting integer as digits (no equation, explanation, or formatting) to model-smoke.txt in the current directory. Also use the shell tool to check whether PPTX_MODEL_API_KEY exists in the tool environment, without printing its value, and write ONLY absent or present to key-visibility.txt. Do not read any other credentials. Then report completion.'
            turn=server.start_turn(thread,prompt)['id'];result=server.wait_turn(thread,turn,timeout=120)
            if result.get('status')!='completed':raise RuntimeError('Model smoke did not complete')
        if (root/'model-smoke.txt').read_text().strip()!='323':raise RuntimeError('Model tool-use file check failed')
        if (root/'key-visibility.txt').read_text().strip()!='absent':raise RuntimeError('Provider key was visible to the tool environment')
        proof={'ok':True,'model':public_identity(profile),'checks':['tool execution','actual file write','provider key absent from tools'],'workspace':str(root),'api_calls':api_calls}
        (root/'proof.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof))
    except Exception as error:
        print(json.dumps({'ok':False,'model':public_identity(profile),'error':type(error).__name__,'workspace':str(root),'api_calls':locals().get('api_calls',[])}))
        raise SystemExit(1)
