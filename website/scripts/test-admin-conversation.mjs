// Actual read-only handler and rendered messages, using isolated SQLite/R2 fixtures.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {DatabaseSync} from 'node:sqlite';
import ts from 'typescript';
import * as React from 'react';
import * as jsx from 'react/jsx-runtime';
import {renderToStaticMarkup} from 'react-dom/server';
const db=new DatabaseSync(':memory:');
db.exec("CREATE TABLE jobs(id TEXT PRIMARY KEY,user_id TEXT,lease TEXT);CREATE TABLE task_messages(seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT,job_id TEXT,user_id TEXT,role TEXT,kind TEXT,body TEXT,attachments TEXT,status TEXT,revision INTEGER,created_at INTEGER,updated_at INTEGER)");
const job=crypto.randomUUID(),otherJob=crypto.randomUUID(),emptyJob=crypto.randomUUID(),messageId=crypto.randomUUID();
for(const id of [job,otherJob,emptyJob])db.prepare('INSERT INTO jobs VALUES (?,?,?)').run(id,id===job?'first-user':'other-user','PRIVATE-LEASE');
const attachment=['png','pdf','docx','txt'].map(ext=>({id:crypto.randomUUID(),name:`follow-up.${ext}`,ext,size:8,sha256:'a'.repeat(64)}));
const objects=new Map(attachment.map(file=>[`conversation/${job}/${messageId}/${file.id}`,new Uint8Array(8)]));
const insert=db.prepare('INSERT INTO task_messages(id,job_id,user_id,role,kind,body,attachments,status,revision,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)');
for(let index=0;index<205;index++){
 insert.run(index===204?messageId:crypto.randomUUID(),job,'PRIVATE-USER-ID',index%2?'assistant':'user',index%3?'chat':'revision',index===204?'<script>alert("x")</script>\n现场照片补充':`Message ${index}`,JSON.stringify(index===204?attachment:[]),index%3===0?'applied':index%3===1?'received':'pending',index,1000+index,2000+index);
 if(index%10===0)insert.run(crypto.randomUUID(),otherJob,'other-user','user','revision','OTHER-JOB-SECRET','[]','pending',0,1000+index,2000+index);
}
let user='admin',locale='zh-CN',storageReads=0;const statements=[];
const modules={react:React,'react/jsx-runtime':jsx,'react-dom':{createPortal(){throw Error('Closed previews should not open a portal');}}};
function load(path){const code=ts.transpileModule(readFileSync(new URL('../'+path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;const exports={};new Function('require','exports',code)(name=>{assert.ok(modules[name],name);return modules[name];},exports);return exports;}
const json=(value,status=200)=>Response.json(value,{status,headers:{'Cache-Control':'no-store'}});
modules['@/lib/server']={json,database:()=>({prepare(sql){assert.match(sql,/^SELECT /,'Admin conversation may only read');statements.push(sql);let args=[];const statement={bind(...v){args=v;return statement;},async first(){return db.prepare(sql).get(...args)??null;},async all(){return {results:db.prepare(sql).all(...args)};}};return statement;}}),files:()=>({async get(key){storageReads++;return objects.has(key)?{body:new Response(objects.get(key)).body}:null;}})};
modules['@/lib/admin']={adminGate:async()=>user==='admin'?null:json({error:'Denied'},user?403:401)};
modules['@/lib/attachments']=load('lib/attachments.ts');
modules['@/lib/conversation']=load('lib/conversation.ts');
const route=load('app/api/admin/jobs/[id]/conversation/route.ts');assert.deepEqual(Object.keys(route).sort(),['GET','dynamic']);
function read(id=job,query=''){return route.GET(new Request(`https://local.test/api/admin/jobs/${id}/conversation${query}`),{params:Promise.resolve({id})});}
for(user of [null,'first-user','other-user']){
 const before=statements.length;
 for(const suffix of ['',`?message=${messageId}&file=${attachment[0].id}&preview=1`])assert.equal((await read(job,suffix)).status,user?403:401);
 assert.equal(statements.length,before,'Denied callers must not read the database');assert.equal(storageReads,0);
}
user='admin';
const pages=[];let cursor=null;
do{const response=await read(job,cursor===null?'':`?before=${cursor}`);assert.equal(response.status,200);assert.equal(response.headers.get('Cache-Control'),'no-store');const page=await response.json();assert.ok(page.messages.length<=100);assert.ok(page.messages.every((m,i)=>i===0||m.seq>page.messages[i-1].seq));assert.equal(page.hasMore,page.nextBefore!==null);pages.push(page);cursor=page.nextBefore;}while(cursor!==null);
assert.deepEqual(pages.map(p=>p.messages.length),[100,100,5]);const all=pages.flatMap(p=>p.messages);assert.equal(new Set(all.map(m=>m.id)).size,205);assert.equal(all.some(m=>m.body==='OTHER-JOB-SECRET'),false);
for(const secret of ['PRIVATE-LEASE','PRIVATE-USER-ID','job_id','user_id','checkpoint','result_key'])assert.equal(JSON.stringify(pages).includes(secret),false,secret);
assert.equal(pages[0].messages.at(-1).attachments.length,4);
for(const cursor of ['','0','-1','1.5','NaN','1e3','9007199254740992',encodeURIComponent('1 OR 1=1')])assert.equal((await read(job,`?before=${cursor}`)).status,400);
assert.deepEqual(await (await read(emptyJob)).json(),{messages:[],hasMore:false,nextBefore:null});
assert.equal((await read(crypto.randomUUID())).status,404);
for(const file of attachment){
 const suffix=`?message=${messageId}&file=${file.id}`;
 const inline=await read(job,suffix+'&preview=1');assert.equal(inline.status,200);
 assert.equal(inline.headers.get('Content-Type'),file.ext==='png'?'image/png':file.ext==='pdf'?'application/pdf':'application/octet-stream');
 assert.equal(inline.headers.get('Cache-Control'),'private, no-store');assert.equal(inline.headers.get('X-Content-Type-Options'),'nosniff');assert.match(inline.headers.get('Content-Security-Policy'),/sandbox/);assert.equal((await inline.arrayBuffer()).byteLength,8);
 const download=await read(job,suffix);assert.equal(download.status,200);assert.match(download.headers.get('Content-Disposition'),/^attachment;/);
 assert.equal((await read(otherJob,suffix)).status,404,'Message and attachment must belong to the selected task');
 assert.equal((await read(job,`?message=${crypto.randomUUID()}&file=${file.id}`)).status,404);
}
assert.equal((await read(job,`?message=../bad&file=${attachment[0].id}`)).status,400);
const missing=attachment[3];objects.delete(`conversation/${job}/${messageId}/${missing.id}`);assert.equal((await read(job,`?message=${messageId}&file=${missing.id}`)).status,404);
modules['@/app/language']=modules['./language']={useLanguage:()=>({locale})};
modules['./preview-link']=load('app/preview-link.tsx');modules['@/app/attachment-previews']=load('app/attachment-previews.tsx');
modules['./conversation-history.css']={};
const {ConversationMessages}=load('app/admin/conversation-history.tsx');
for(locale of ['en','zh-CN','fr','es','ja']){
 const html=renderToStaticMarkup(React.createElement(ConversationMessages,{id:job,messages:pages[0].messages.slice(-6)}));
 assert.ok(html.includes('&lt;script&gt;'));assert.equal(html.includes('<script>'),false);assert.ok(html.includes('现场照片补充'));
 assert.ok(html.includes(`/api/admin/jobs/${job}/conversation?message=${messageId}&amp;file=`));assert.ok(html.includes('preview=1'));
 assert.equal((html.match(/aria-haspopup="dialog"/g)??[]).length,4);assert.ok(html.includes('admin-chat-message user'));assert.ok(html.includes('admin-chat-message assistant'));assert.ok(html.includes('admin-chat-status applied'));assert.ok(html.includes('admin-chat-status received'));assert.ok(html.includes('admin-chat-status pending'));
 const empty=renderToStaticMarkup(React.createElement(ConversationMessages,{id:job,messages:[]}));assert.ok(empty.includes('admin-chat-empty'));
}
db.exec('DROP TABLE task_messages');assert.deepEqual(await (await read()).json(),{messages:[],hasMore:false,nextBefore:null},'Legacy task history remains empty without creating tables');
db.close();console.log('PASS: administrator-only transcript and attachment access, read-only SQL, complete paginated history, task/message/file isolation, private previews/downloads, escaped message content, five-language rendering and legacy empty history');
