"""Usage accounting tests use synthetic receipts, temporary storage and no API."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from usage_ledger import UsageLedger, normalize_usage, price_usage
from responses_proxy import ResponsesProxy
from chat_proxy import ChatProxy, UpstreamError
from durable import AppServer

PROFILE={'model':'test-model','base_url':'https://provider.invalid/v1','api_key':'fixture-private-key','wire_api':'responses'}
USAGE={'input_tokens':1000,'output_tokens':200,'input_tokens_details':{'cached_tokens':400,'cache_write_tokens':100},'output_tokens_details':{'reasoning_tokens':50}}
PRICES={'version':'test-v1','rates':[{'provider':'provider.invalid','model':'test-model','serviceTier':'default','inputUsdPerMillion':'2','cachedInputUsdPerMillion':'0.5','cacheWriteUsdPerMillion':'2.5','outputUsdPerMillion':'8'}]}

class UsageTests(unittest.TestCase):
    def test_cache_and_reasoning_are_subsets_not_added_twice(self):
        u=normalize_usage(USAGE)
        self.assertEqual(u['totalTokens'],1200)
        self.assertEqual(price_usage(u,'provider.invalid','test-model','default',PRICES)['costMicrousd'],3050)
        self.assertIsNone(price_usage(u,'relay.invalid','test-model','default',PRICES))
        self.assertIsNone(price_usage(u,'provider.invalid','test-model','priority',PRICES))
        self.assertIsNone(normalize_usage({}))
        self.assertIsNone(normalize_usage({'input_tokens':True,'output_tokens':1}))
        self.assertIsNone(normalize_usage({'input_tokens':1,'output_tokens':1,'input_tokens_details':{'cached_tokens':2}}))
        self.assertIsNone(normalize_usage({'input_tokens':-1,'output_tokens':1}))

    def test_chat_and_native_anthropic_usage(self):
        u=normalize_usage({'prompt_tokens':100,'completion_tokens':10,'prompt_tokens_details':{'cached_tokens':20}})
        self.assertEqual(u['totalTokens'],110)
        u=normalize_usage({'input_tokens':100,'output_tokens':10,'cache_read_input_tokens':30,'cache_creation_input_tokens':20})
        self.assertEqual((u['inputTokens'],u['totalTokens']),(150,160))

    def test_durable_replay_dedup_and_frozen_pricing(self):
        with tempfile.TemporaryDirectory() as folder:
            rates=Path(folder)/'prices.json';rates.write_text(json.dumps(PRICES))
            cfg={'state_directory':folder,'usage_pricing_file':str(rates)}
            task={'id':'fixture-job','lease':'private-lease'}
            def offline(*a):raise OSError('offline')
            ledger=UsageLedger(cfg,task,offline)
            sink=ledger.api_sink('author',PROFILE)
            call={'response_id':'resp_once','usage':USAGE,'response_model':'test-model','response_status':'incomplete'}
            sink(call);sink(call)
            self.assertEqual(len(ledger.records),1)
            row=next(iter(ledger.records.values()))
            self.assertEqual(row['costMicrousd'],3050)
            self.assertEqual(row['outcome'],'incomplete')
            sink({'cache_hit':True,'usage':USAGE})
            self.assertEqual(len(ledger.records),1)
            with patch('builtins.print'):ledger.close()
            saved=''.join(p.read_text() for p in (Path(folder)/'fixture-job/usage').glob('*.json'))
            self.assertNotIn(PROFILE['api_key'],saved);self.assertNotIn(task['lease'],saved)
            prices=copy.deepcopy(PRICES);prices['version']='test-v2';prices['rates'][0]['inputUsdPerMillion']='99';rates.write_text(json.dumps(prices))
            sent=[]
            def online(cfg,path,body,lease):sent.append(json.loads(body));return {'ok':True}
            restored=UsageLedger(cfg,{**task,'lease':'new-lease'},online)
            restored.api_sink('author',PROFILE)(call)
            restored.flush();restored.close()
            self.assertEqual(len(sent),1)
            self.assertEqual(sent[0]['records'][0]['costMicrousd'],3050)
            self.assertEqual(sent[0]['records'][0]['priceVersion'],'test-v1')

    def test_local_partial_and_terminal_usage_updates_one_turn(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger=UsageLedger({'state_directory':folder},{'id':'job','lease':'lease'},lambda *a:{'ok':True})
            sink=ledger.codex_sink('research','local-model')
            event={'thread_id':'thread','turn_id':'turn','usage':{'input_tokens':100,'cached_input_tokens':20,'output_tokens':10,'reasoning_output_tokens':2}}
            sink(event);sink(event)
            self.assertEqual(next(iter(ledger.records.values()))['version'],1)
            sink({**event,'status':'completed','usage':{**event['usage'],'output_tokens':20}})
            sink({**event,'usage':None})
            row=next(iter(ledger.records.values()))
            self.assertEqual(len(ledger.records),1);self.assertEqual(row['totalTokens'],120)
            self.assertEqual(row['outcome'],'completed');self.assertIsNone(row['costMicrousd'])
            self.assertEqual(row['costSource'],'not_api');ledger.close()

    def test_proxy_callbacks_include_failed_generations_without_prompt_or_key(self):
        seen=[];proxy=ResponsesProxy({**PROFILE,'responses_transport':'buffered'},on_usage=seen.append)
        reply={'id':'resp_failed','object':'response','model':'test-model','status':'incomplete','output':[],'usage':USAGE}
        upstream=SimpleNamespace(returncode=0,stdout=json.dumps(reply)+'\n200\nreq-test\n',stderr='')
        with patch.object(proxy,'_upstream',return_value=upstream):
            with self.assertRaises(UpstreamError):proxy.complete({'model':'test-model','input':'private prompt','stream':False})
        self.assertEqual(seen[0]['usage'],USAGE);self.assertEqual(seen[0]['response_id'],'resp_failed')
        self.assertNotIn('private prompt',json.dumps(seen));self.assertNotIn(PROFILE['api_key'],json.dumps(seen))
        chat=ChatProxy({**PROFILE,'wire_api':'chat_completions'},on_usage=seen.append)
        reply={'id':'chat_once','model':'test-model','choices':[{'message':{'content':'done'},'finish_reason':'stop'}],'usage':{'prompt_tokens':20,'completion_tokens':2}}
        with patch.object(chat,'_upstream',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(reply)+'\n200',stderr='')):
            chat.complete({'model':'test-model','input':'private chat prompt'})
        self.assertEqual(seen[-1]['usage'],reply['usage']);self.assertEqual(seen[-1]['response_id'],'chat_once')

    def test_app_server_partial_and_completion_receipts_reach_private_ledger(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger=UsageLedger({'state_directory':folder},{'id':'job','lease':'lease'},lambda *a:{'ok':True})
            server=AppServer(cwd=folder,config={},on_usage=ledger.codex_sink('research','local-model'))
            params={'threadId':'thread','turnId':'turn','tokenUsage':{'last':{'inputTokens':100,'cachedInputTokens':20,'outputTokens':10},'total':{'inputTokens':100,'cachedInputTokens':20,'outputTokens':10}}}
            server._notification('thread/tokenUsage/updated',params)
            server._notification('thread/tokenUsage/updated',params)
            self.assertEqual(next(iter(ledger.records.values()))['version'],1)
            server._notification('turn/completed',{'threadId':'thread','turn':{'id':'turn','status':'completed'}})
            row=next(iter(ledger.records.values()))
            self.assertEqual(row['outcome'],'completed');self.assertEqual(row['totalTokens'],110)
            ledger.close()

if __name__=='__main__':unittest.main()
