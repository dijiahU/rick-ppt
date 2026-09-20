"""Exercise local Sites UI and real routes. Only newly created test data is mutated.

Requires Python Playwright, a running local dev server and its local .env worker
token. Credentials remain in this host process and are never written to artifacts.
"""
import argparse
import asyncio
import json
import sqlite3
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from playwright.async_api import async_playwright, expect


async def run(base, site, output):
    assert urlsplit(base).hostname in ('localhost','127.0.0.1'), 'Local test only'
    output.mkdir(parents=True,exist_ok=True)
    token=None
    for line in (site/'.env').read_text().splitlines():
        if '=' in line and line.split('=',1)[0].strip()=='WORKER_TOKEN':token=line.split('=',1)[1].strip().strip('"\'')
    assert token, 'Local worker test credential missing'
    async with async_playwright() as p:
        browser=await p.chromium.launch()
        context=await browser.new_context(viewport={'width':1440,'height':1050})
        page=await context.new_page();errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        await page.goto(base+'/signin-with-chatgpt?return_to=/',wait_until='networkidle')
        result=await context.request.post(base+'/api/jobs',headers={'Origin':base},data={'requestKey':str(uuid.uuid4()),'title':'LOCAL TEST · Interactive CNN conversation','brief':'A local browser acceptance test, never sent to the production queue. Explain convolution interactively.','mode':'create','pages':5,'style':'Designer choice','language':'en'})
        if result.status==429:
            # Prior local suites may have exhausted the synthetic account's quota.
            # Seed a new local fixture under that known account; never alter old jobs.
            account=await (await context.request.get(base+'/api/account')).json()
            assert account.get('signedIn') and account.get('jobs'),'No local fixture identity'
            ident=str(uuid.uuid4());seeded=False
            for path in (site/'.wrangler/state/v3/d1').rglob('*.sqlite'):
                if path.name=='metadata.sqlite':continue
                with sqlite3.connect(path) as connection:
                    try:owner=connection.execute('SELECT user_id FROM jobs WHERE id=?',(account['jobs'][0]['id'],)).fetchone()
                    except sqlite3.OperationalError:continue
                    if owner:
                        now=int(time.time()*1000)
                        connection.execute("INSERT INTO jobs(id,user_id,request_key,title,brief,pages,style,language,attachments,status,created_at,updated_at) VALUES (?,?,?,'LOCAL TEST · Interactive CNN conversation','Local browser conversation fixture',5,'Designer choice','en','[]','queued',?,?)",(ident,owner[0],str(uuid.uuid4()),now,now));seeded=True;break
            assert seeded,'Could not seed local fixture'
        else:
            assert result.status in (200,201), f'Local job creation failed: {result.status}'
            ident=(await result.json())['id']
        lease=str(uuid.uuid4());database=None
        for path in (site/'.wrangler/state/v3/d1').rglob('*.sqlite'):
            if path.name=='metadata.sqlite':continue
            connection=sqlite3.connect(path)
            try:
                if connection.execute('SELECT id FROM jobs WHERE id=?',(ident,)).fetchone():database=path;break
            except sqlite3.OperationalError:pass
            finally:connection.close()
        assert database,'New local test job database not found'
        def update(sql,args=()):
            with sqlite3.connect(database) as connection:connection.execute(sql,(*args,ident))
        update("UPDATE jobs SET status='running',lease=?,updated_at=? WHERE id=?",(lease,int(time.time()*1000)))
        import atexit
        def finish_fixture():
            update("UPDATE jobs SET status='failed',summary='local-ui-test-finished',updated_at=? WHERE id=?",(int(time.time()*1000),))
        atexit.register(finish_fixture)
        async def worker(action,body):
            response=await context.request.post(base+f'/api/worker/{ident}/conversation?action={action}',headers={'Authorization':'Bearer '+token,'X-Job-Lease':lease},data=body)
            assert response.status==200,f'Worker {action} failed with status {response.status}'
            return await response.json()
        await page.goto(base+'/jobs/'+ident,wait_until='networkidle')
        panel=page.locator('.conversation');await expect(panel).to_be_visible()
        await panel.locator('textarea').fill('Please animate a 2 × 2 convolution window and show each multiply-add.')
        await panel.locator('input[type=file]').set_input_files({'name':'kernel.txt','mimeType':'text/plain','buffer':b'kernel = [[1,0],[0,-1]]'})
        await panel.locator('button[type=submit]').click()
        await expect(panel.locator('.conversation-message.user')).to_have_count(1)
        saved=(await worker('poll',{}))['messages'][0]
        assert saved['attachments'][0]['name']=='kernel.txt'
        await worker('ack',{'ids':[saved['id']]})
        await worker('assistant',{'id':str(uuid.uuid4()),'body':'I have your kernel. I will show the four products, then their sum, as the window moves.'})
        await expect(panel.locator('.message-status')).to_contain_text('Received by Codex',timeout=12000)
        await expect(panel.locator('.conversation-message.assistant')).to_have_count(1,timeout=12000)
        await worker('applied',{'ids':[saved['id']],'revision':saved['seq']})
        await expect(panel.locator('.message-status')).to_contain_text('Applied',timeout=12000)
        # Persisted after reload; normal chat uses a distinct intent.
        await page.reload(wait_until='networkidle');await expect(panel.locator('.conversation-message')).to_have_count(2)
        await panel.get_by_role('button',name='Chat',exact=True).click();await panel.locator('textarea').fill('Why does sharing a kernel reduce parameters?')
        await panel.locator('button[type=submit]').click();await expect(panel.locator('.conversation-message.user')).to_have_count(2)
        assert (await worker('poll',{}))['messages'][0]['kind']=='chat'
        await page.screenshot(path=str(output/'conversation-desktop.png'),full_page=True)
        # A temporary transport failure reconnects without duplicating messages.
        await page.route('**/api/jobs/*/conversation',lambda route:route.abort())
        await expect(panel.get_by_role('status')).to_be_visible(timeout=12000)
        await page.unroute('**/api/jobs/*/conversation')
        await expect(panel.get_by_role('status')).to_have_count(0,timeout=12000)
        await expect(panel.locator('.conversation-message.user')).to_have_count(2)
        # Real transcript overflow: reload follows the latest message, incoming
        # long replies stay visible at the end, and reading history is respected.
        for index in range(2):
            await worker('assistant',{'id':str(uuid.uuid4()),'body':f'Scroll fixture {index}\n'+('A complete explanation with several readable lines.\n'*45)+f'End of explanation {index}.'})
        await expect(panel.locator('.conversation-message.assistant')).to_have_count(3,timeout=12000)
        await page.reload(wait_until='networkidle')
        await expect(panel.locator('.conversation-message.assistant')).to_have_count(3,timeout=12000)
        transcript=panel.locator('.conversation-transcript')
        at_end="() => {const n=document.querySelector('.conversation-transcript');return n&&n.scrollHeight>n.clientHeight+200&&n.scrollHeight-n.scrollTop-n.clientHeight<5;}"
        await page.screenshot(path=str(output/'conversation-long-reload.png'),full_page=True)
        await page.wait_for_function(at_end,timeout=5000)
        await transcript.hover();await page.mouse.wheel(0,-20000)
        await page.wait_for_function("() => document.querySelector('.conversation-transcript').scrollTop<5")
        await worker('assistant',{'id':str(uuid.uuid4()),'body':'New information arrives while the reader is viewing earlier messages.'})
        await expect(panel.locator('.conversation-message.assistant')).to_have_count(4,timeout=12000)
        assert await transcript.evaluate('(n)=>n.scrollTop<5'),'Incoming message interrupted reading history'
        await transcript.hover();await page.mouse.wheel(0,20000)
        await page.wait_for_function(at_end)
        await worker('assistant',{'id':str(uuid.uuid4()),'body':('A long live reply must keep its current ending visible.\n'*45)+'Latest live ending.'})
        await expect(panel.locator('.conversation-message.assistant')).to_have_count(5,timeout=12000)
        await page.wait_for_function(at_end,timeout=5000)
        await transcript.hover();await page.mouse.wheel(0,-20000)
        await page.wait_for_function("() => document.querySelector('.conversation-transcript').scrollTop<5")
        await panel.locator('textarea').fill('LOCAL UI CHECK: return to my newly sent chat message.')
        await panel.locator('button[type=submit]').click()
        await expect(panel.locator('.conversation-message.user')).to_have_count(3)
        await page.wait_for_function(at_end,timeout=5000)
        await worker('checkpoint',{'checkpointId':str(uuid.uuid4()),'runId':str(uuid.uuid4()),'phase':'author','pluginVersion':'0.2.0','resumable':True,'revision':saved['seq'],'lastMessageSeq':saved['seq']})
        update("UPDATE jobs SET status='failed',updated_at=? WHERE id=?",(int(time.time()*1000),))
        await page.reload(wait_until='networkidle')
        await panel.get_by_role('button',name='Resume from checkpoint').click()
        await expect(page.locator('.room-status .status')).to_contain_text('queue',ignore_case=True,timeout=12000)
        await page.set_viewport_size({'width':390,'height':844})
        await page.wait_for_function(at_end,timeout=5000)
        await panel.scroll_into_view_if_needed();await page.screenshot(path=str(output/'conversation-mobile.png'),full_page=True)
        assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),'Horizontal overflow'
        assert not errors,errors
        # Mark only this local synthetic job terminal; leave its messages/files for review.
        update("UPDATE jobs SET status='failed',summary='local-ui-test-complete',updated_at=? WHERE id=?",(int(time.time()*1000),))
        await browser.close()
        (output/'report.json').write_text(json.dumps({'ok':True,'jobId':ident,'checks':['real message/attachment persistence','worker acknowledgement and assistant reply','applied status','reload','normal chat','reconnect deduplication','long transcript reload at latest message','preserve reading history during new messages','follow long replies at transcript end','sending returns to latest message','resume same job','mobile overflow','no browser errors']},indent=2))
        print('PASS: local browser conversation, uploads, status, reload, reconnect, resume and mobile layout')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--base',default='http://localhost:41975');parser.add_argument('--out',required=True);args=parser.parse_args()
    asyncio.run(run(args.base,Path(__file__).resolve().parents[1],Path(args.out)))
