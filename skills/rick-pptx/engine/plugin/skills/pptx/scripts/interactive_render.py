"""Run scene testPlans in real Chromium and retain initial/intermediate/reset PNGs."""
from __future__ import annotations
import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from playwright.async_api import async_playwright
from pptx_core.common import PptxError,atomic_json,sha256
from pptx_core.interactive_server import start_server
from pptx_core.interactive_validate import read_json,safe_path,validate_spec,runtime_fingerprint


async def execute(page, action):
    kind=action['type'];target=action.get('target');locator=page.locator('[data-node-id='+json.dumps(target)+']') if target else None
    if kind=='click':await locator.click()
    elif kind=='hover':await locator.hover()
    elif kind in ('input','slider'):
        control=locator.locator('input,textarea').first
        if kind=='input':await control.fill(str(action['value']))
        else:
            await control.evaluate('(el,value)=>{const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set;setter.call(el,String(value));el.dispatchEvent(new Event("input",{bubbles:true}));el.dispatchEvent(new Event("change",{bubbles:true}));}',action['value'])
    elif kind=='select':await locator.locator('select').select_option(str(action['value']))
    elif kind=='toggle':await locator.locator('input').set_checked(bool(action['value']))
    elif kind in ('keyboard','key'):
        if locator:await locator.focus()
        await page.keyboard.press(action['key'])
    elif kind in ('drag','pan'):
        box=await locator.bounding_box()
        if not box:raise PptxError('Drag target has no bounds')
        x,y=box['x']+box['width']/2,box['y']+box['height']/2
        await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x+action.get('dx',0),y+action.get('dy',0),steps=10);await page.mouse.up()
    elif kind=='wheel':
        await locator.hover();await page.mouse.wheel(action.get('dx',0),action.get('dy',0))
    elif kind=='seekTimeline':await page.evaluate('a=>window.__interactive.seek(a.timeline,a.time)',action)
    elif kind=='dispatch':await page.evaluate('a=>window.__interactive.dispatch(a)',action['actions'])
    elif kind=='resize':await page.set_viewport_size({'width':action['width'],'height':action['height']})
    elif kind=='wait':await page.wait_for_timeout(min(5000,action.get('duration',100)))
    elif kind=='snapshot':await page.evaluate('window.__savedScene=window.__interactive.snapshot()')
    elif kind=='restore':await page.evaluate('window.__interactive.restore(window.__savedScene)')
    elif kind=='media':await page.evaluate('a=>window.__interactive.dispatch([{type:"media",target:a.target,method:a.method,value:a.value}])',action)
    else:raise PptxError(f'Unsupported test action: {kind}')
    await page.wait_for_timeout(30)


async def assertion(page,item):
    kind=item['type'];expected=item.get('equals',True)
    if kind=='state':value=await page.evaluate('p=>window.__interactive.runtime.store.get(p)',item['path'])
    elif kind=='dataCount':value=await page.evaluate('p=>window.__interactive.runtime.store.getData()[p].length',item['source'])
    elif kind=='timeline':value=await page.evaluate('a=>window.__interactive.runtime.timeline.states[a.timeline][a.property]',item)
    else:
        locator=page.locator('[data-node-id='+json.dumps(item['target'])+']')
        if kind=='visible':value=await locator.is_visible()
        elif kind=='text':value=await locator.text_content()
        elif kind=='attribute':value=await locator.get_attribute(item['name'])
        elif kind=='property':value=await locator.locator(item.get('selector','input')).evaluate('(el,name)=>el[name]',item['name'])
        else:raise PptxError(f'Unsupported test assertion: {kind}')
    if 'contains' in item:
        if item['contains'] not in value:raise PptxError(f'Assertion failed: {item}; got {value!r}')
    elif 'tolerance' in item:
        if abs(value-expected)>item['tolerance']:raise PptxError(f'Assertion failed: {item}; got {value!r}')
    elif value!=expected:raise PptxError(f'Assertion failed: {item}; got {value!r}')


async def render_scene_async(spec,output,deck_root=None,deck_id=None,runtime=None):
    spec=Path(spec).resolve();scene=validate_spec(spec,deck_root or spec.parent);output=Path(output);output.mkdir(parents=True,exist_ok=False)
    fingerprint=runtime_fingerprint(runtime)
    runner,origin=await start_server(deck_root or spec.parent,runtime)
    url=origin+'/preview.html?'+('deck='+deck_id+'&scene='+scene['id'] if deck_id else 'spec=source/'+spec.name)
    errors=[];captures=[];tests=[]
    try:
        async with async_playwright() as p:
            browser=await p.chromium.launch()
            page=await browser.new_page(viewport=scene['viewport'],reduced_motion='reduce')
            page.on('pageerror',lambda e:errors.append(str(e)))
            await page.goto(url,wait_until='networkidle')
            await page.wait_for_function('window.__interactive?.ready || window.__interactive?.error',timeout=30000)
            boot=await page.evaluate('({ready:window.__interactive.ready,error:window.__interactive.error})')
            if not boot.get('ready'):raise PptxError(str(boot))
            await page.locator('[data-ready=true]').wait_for();await page.screenshot(path=str(output/'initial.png'));captures.append('initial.png')
            for index,test in enumerate(scene.get('testPlan',[])):
                if test.get('reset'):await page.evaluate('window.__interactive.dispatch([{type:"reset"}])')
                for action in test['actions']:await execute(page,action)
                for item in test['assertions']:await assertion(page,item)
                if test.get('capture',True):
                    label=re.sub(r'[^A-Za-z0-9_-]+','-',test['name'])[:80] or 'test'
                    filename=f'{index+1:02d}-{label}.png';await page.screenshot(path=str(output/filename));captures.append(filename)
                tests.append({'name':test['name'],'ok':True,'assertions':len(test['assertions'])})
            await page.evaluate('window.__interactive.dispatch([{type:"reset"}])');await page.wait_for_timeout(50);await page.screenshot(path=str(output/'reset.png'));captures.append('reset.png')
            runtime_error=await page.evaluate('window.__interactive.runtime.error')
            if runtime_error:errors.append(runtime_error)
            await browser.close()
    except Exception as error:
        errors.append(str(error))
    finally:await runner.cleanup()
    if runtime_fingerprint(runtime)!=fingerprint:errors.append('Runtime build changed during scene tests; rerun against a stable build')
    report={'receiptVersion':1,'runtime':fingerprint,'captureHashes':{name:sha256(output/name) for name in captures},'ok':not errors,'specHash':sha256(spec),'sceneId':scene['id'],'testCount':len(tests),'tests':tests,'errors':errors,'captures':captures,'directory':str(output),'runtime_verified':not errors and bool(tests) and all(test['assertions']>0 for test in tests),'powerpoint_playback_verified':False,'verification':'Standalone Chromium runtime; not desktop PowerPoint playback.'}
    atomic_json(output/'report.json',report)
    if errors:raise PptxError('; '.join(errors))
    return report


def render_scene(spec,output,**kwargs):
    proxy=os.environ.get('PPTX_INTERACTIVE_PROXY')
    if proxy:
        command=[sys.executable,proxy,'--spec',str(spec),'--output',str(output)]
        for key in ('deck_root','deck_id'):
            if kwargs.get(key) is not None:command.extend(['--'+key.replace('_','-'),str(kwargs[key])])
        result=subprocess.run(command,capture_output=True,text=True,timeout=360)
        if result.returncode:raise PptxError('Host interactive rendering failed: '+result.stderr[-2000:])
        if len(result.stdout)>2*1024*1024:raise PptxError('Interactive render receipt exceeds its limit')
        try:report=json.loads(result.stdout)
        except (ValueError,TypeError) as error:raise PptxError('Invalid host render receipt') from error
        if not isinstance(report,dict) or not report.get('ok'):raise PptxError('Host scene tests failed')
        return report
    return asyncio.run(render_scene_async(spec,output,**kwargs))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('spec');p.add_argument('--out',required=True);a=p.parse_args();print(json.dumps(render_scene(a.spec,a.out),indent=2))
