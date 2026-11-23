// Optional per-task Fast choice: real form markup, real job/claim routes and an
// in-memory SQLite D1 stand-in. No website jobs, quota, worker or model calls.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {DatabaseSync} from 'node:sqlite';
import ts from 'typescript';
import * as React from 'react';
import * as jsx from 'react/jsx-runtime';
import {renderToStaticMarkup} from 'react-dom/server';
import * as limits from '../lib/slide-limits.mjs';

function loader(modules){
 return function load(path){const code=ts.transpileModule(readFileSync(new URL('../'+path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;const exports={};new Function('require','exports',code)(name=>{assert.ok(modules[name],name);return modules[name];},exports);return exports;};
}

// 1. Form: one unchecked toggle beside the existing options, in both modes and all five languages.
{
 let mode='create',locale='en',calls=0;
 const modules={react:{...React,useState(initial){calls++;return React.useState(calls===2?mode:initial);}},'react/jsx-runtime':jsx,'./slide-limits.mjs':limits,'@/lib/slide-limits.mjs':limits};
 const load=loader(modules);
 for(const name of ['i18n','quota-i18n','queue-i18n','upload-i18n','task-mode-i18n','task-mode','page-count-i18n','presentation-language','execution-backend','execution-backend-i18n','brief-fields']){modules['@/lib/'+name]=load('lib/'+name+'.ts');modules['./'+name]=modules['@/lib/'+name];}
 modules['./language']={useLanguage:()=>({locale,t:modules['@/lib/i18n'].messages[locale]})};
 modules['@/lib/upload-client']={uploadFiles:async()=>[]};
 modules['./attachment-previews']={default:()=>null};
 modules['./file-upload']={default:()=>null};
 modules['./model-accounts.css']={};
 modules['./model-accounts']=load('app/model-accounts.tsx');
 modules['./brief-fields']=load('app/brief-fields.tsx');
 const Form=load('app/brief-form.tsx').default;
 const words=modules['@/lib/execution-backend-i18n'].executionWords;
 const locales=Object.keys(modules['@/lib/i18n'].languages);
 assert.deepEqual(Object.keys(words).sort(),[...locales].sort());
 for(locale of locales){
  assert.ok(words[locale].fast&&words[locale].fastHelp,locale);
  for(mode of ['create','edit']){
   calls=0;const html=renderToStaticMarkup(React.createElement(Form));
   const toggle=html.match(/<input[^>]*id="fast-mode"[^>]*>/g);
   assert.equal(toggle?.length,1,locale+' '+mode);
   assert.ok(toggle[0].includes('type="checkbox"')&&toggle[0].includes('name="fast"')&&toggle[0].includes('value="true"'));
   assert.ok(!toggle[0].includes('checked'),'Fast is off by default');
   assert.ok(html.includes(words[locale].fast)&&html.includes(words[locale].fastHelp));
   // Placed after the presentation-language choice, before references.
   assert.ok(html.indexOf('id="ppt-language"')<html.indexOf('id="fast-mode"'));
  }
 }
 assert.equal(words['zh-CN'].fast,'Fast 模式：更快出结果，消耗更多额度');
 const source=readFileSync(new URL('../app/brief-form.tsx',import.meta.url),'utf8');
 assert.ok(source.includes("...(fast?{fast:true}:{})"),'only an explicit choice is sent; default requests are unchanged');
 console.log('PASS: unchecked Fast toggle in create and edit forms for all five languages, after the language option');
}

// 2. Routes: strict boolean admission, atomic option row, idempotency and worker claim.
{
 const db=new DatabaseSync(':memory:');
 db.exec(readFileSync(new URL('../drizzle/0000_absurd_mongoose.sql',import.meta.url),'utf8'));
 db.exec(readFileSync(new URL('../drizzle/0001_misty_tyger_tiger.sql',import.meta.url),'utf8'));
 let user='owner';
 const statement=(sql)=>{let args=[];const s={bind(...values){args=values;return s;},async first(){return db.prepare(sql).get(...args)??null;},async all(){return {results:db.prepare(sql).all(...args)};},async run(){return {meta:{changes:Number(db.prepare(sql).run(...args).changes)}};}};return s;};
 // D1 batches are transactional and return each statement's RETURNING rows.
 const binding={prepare:statement,async batch(items){db.exec('BEGIN');try{const out=[];for(const s of items)out.push(await s.all());db.exec('COMMIT');return out;}catch(error){db.exec('ROLLBACK');throw error;}}};
 const token='local-synthetic-worker-token-over-32-characters';
 const modules={'./slide-limits.mjs':limits,'@/lib/slide-limits.mjs':limits,'cloudflare:workers':{env:{DB:binding,WORKER_TOKEN:token,FILES:{async put(){},async delete(){},async head(){return null;}}}},'@/app/chatgpt-auth':{getChatGPTUser:async()=>user?{userId:user}:null},'@/lib/admin':{isAdmin:async()=>false}};
 const load=loader(modules);
 for(const name of ['execution-backend','worker-routing','server','model-providers','model-accounts','i18n','execution-backend-i18n','attachments','queries','task-mode','task-mode-i18n','page-count-i18n','upload-i18n','staged-uploads']){modules['@/lib/'+name]=load('lib/'+name+'.ts');modules['./'+name]=modules['@/lib/'+name];}
 const submit=load('app/api/jobs/route.ts').POST,claim=load('app/api/worker/route.ts').POST;
 const base='https://local.test';
 const fields=(extra={},key=crypto.randomUUID())=>({title:'LOCAL fast fixture',brief:'Explain this local-only test example.',pages:5,style:'test',language:'en',requestKey:key,...extra});
 const post=body=>submit(new Request(base+'/api/jobs',{method:'POST',headers:{Origin:base,'Content-Type':'application/json'},body:JSON.stringify(body)}));
 const count=()=>db.prepare('SELECT COUNT(*) n FROM jobs WHERE user_id=?').get(user).n;
 const tier=id=>db.prepare('SELECT service_tier FROM task_options WHERE job_id=?').get(id)?.service_tier??null;

 for(const value of ['true','yes',1,0,null,{},[]]){assert.equal((await post(fields({fast:value}))).status,400,JSON.stringify(value));}
 assert.equal(count(),0,'invalid Fast values consume no quota');

 const plain=await post(fields());assert.equal(plain.status,201);const plainId=(await plain.json()).id;
 const off=await post(fields({fast:false}));assert.equal(off.status,201);const offId=(await off.json()).id;
 assert.equal(tier(plainId),null);assert.equal(tier(offId),null);
 const fastKey=crypto.randomUUID();
 const fast=await post(fields({fast:true},fastKey));assert.equal(fast.status,201);const fastId=(await fast.json()).id;
 assert.equal(tier(fastId),'fast');
 // Retry of the same submission is idempotent; a changed choice cannot reuse it.
 assert.equal((await (await post(fields({fast:true},fastKey))).json()).id,fastId);
 assert.equal((await post(fields({},fastKey))).status,409);
 assert.equal(count(),3);

 // Legacy multipart form submissions accept only true/false strings.
 const multipart=value=>{const form=new FormData();for(const [k,v] of Object.entries(fields()))form.set(k,String(v));form.set('fast',value);return submit(new Request(base+'/api/jobs',{method:'POST',headers:{Origin:base},body:form}));};
 assert.equal((await multipart('on')).status,400);
 const formFast=await multipart('true');assert.equal(formFast.status,201);const formId=(await formFast.json()).id;assert.equal(tier(formId),'fast');

 // Worker claims receive service_tier only for Fast jobs, in FIFO order.
 db.prepare("UPDATE jobs SET execution_backend='codex'").run();
 const claimed=[];
 for(let i=0;i<4;i++){const response=await claim(new Request(base+'/api/worker',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({execution_backends:['codex'],funding_version:1})}));claimed.push((await response.json()).job);}
 assert.deepEqual(claimed.map(job=>job.id),[plainId,offId,fastId,formId]);
 assert.deepEqual(claimed.map(job=>job.service_tier),[undefined,undefined,'fast','fast']);
 assert.ok(!('service_tier' in claimed[0]),'default claims are unchanged');
 db.close();
 console.log('PASS: strict boolean admission without quota on errors, atomic task_options row, idempotent retries, multipart, worker claim carries service_tier only for Fast jobs');
}
