import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
function load(path,modules){const code=ts.transpileModule(readFileSync(new URL('../'+path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;const exports={};new Function('require','exports',code)(name=>modules[name],exports);return exports;}
const backend=load('lib/execution-backend.ts',{});
const {deferToLocal,combinedWorkerStatus,workerRow,WORKER_ONLINE_MS}=load('lib/worker-routing.ts',{'./execution-backend':backend});
test('server defers new work only while the local worker is online',()=>{
  const now=1_000_000;
  assert.equal(deferToLocal('server',now-1000,now),true);
  assert.equal(deferToLocal('server',now-WORKER_ONLINE_MS-1,now),false);
  assert.equal(deferToLocal('server',null,now),false);
  assert.equal(deferToLocal('server',undefined,now),false);
  assert.equal(deferToLocal('local',now-1000,now),false);
});
test('each worker reports into its own row; server keeps the historical row',()=>{
  assert.equal(workerRow('server'),'primary');
  assert.equal(workerRow('local'),'local');
});
test('site status combines live workers only',()=>{
  const now=1_000_000, stale=now-WORKER_ONLINE_MS-1;
  assert.deepEqual(combinedWorkerStatus([],now),{online:false,executionAvailability:{api:false,codex:false}});
  assert.deepEqual(combinedWorkerStatus([{heartbeat:stale,execution_backends:'["codex"]'}],now),
    {online:false,executionAvailability:{api:false,codex:false}});
  assert.deepEqual(combinedWorkerStatus([{heartbeat:stale,execution_backends:'["api"]'},{heartbeat:now,execution_backends:'["codex"]'}],now),
    {online:true,executionAvailability:{api:false,codex:true}});
  assert.deepEqual(combinedWorkerStatus([{heartbeat:now,execution_backends:'["api"]'},{heartbeat:now,execution_backends:'["codex"]'}],now),
    {online:true,executionAvailability:{api:true,codex:true}});
  assert.deepEqual(combinedWorkerStatus([{heartbeat:now,execution_backends:null}],now),
    {online:true,executionAvailability:{api:false,codex:false}});
});
