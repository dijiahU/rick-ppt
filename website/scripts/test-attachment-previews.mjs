// Actual attachment routes + rendered gallery; isolated fixtures only.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {DatabaseSync} from 'node:sqlite';
import ts from 'typescript';
import * as React from 'react';
import * as jsx from 'react/jsx-runtime';
import {renderToStaticMarkup} from 'react-dom/server';

let user='owner';
const db=new DatabaseSync(':memory:');db.exec('CREATE TABLE jobs(id TEXT PRIMARY KEY,user_id TEXT,attachments TEXT)');
const id=crypto.randomUUID(),objects=new Map();
const metadata=['png','jpg','txt','docx','pdf'].map(ext=>({id:crypto.randomUUID(),name:`reference.${ext}`,ext,size:8,sha256:'a'.repeat(64)}));
db.prepare('INSERT INTO jobs VALUES (?,?,?)').run(id,'owner',JSON.stringify(metadata));
for(const file of metadata)objects.set(`attachments/${id}/${file.id}`,new Uint8Array(8));
const modules={react:React,'react/jsx-runtime':jsx,'react-dom':{createPortal(){throw Error('Closed previews must not render a portal');}}};
function load(path){const code=ts.transpileModule(readFileSync(new URL('../'+path,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;const exports={};new Function('require','exports',code)(name=>{assert.ok(modules[name],name);return modules[name];},exports);return exports;}
modules['@/lib/server']={json:(value,status=200)=>Response.json(value,{status}),userId:async()=>user,database:()=>({prepare(sql){let args=[];const statement={bind(...values){args=values;return statement;},async first(){return db.prepare(sql).get(...args)??null;}};return statement;}}),files:()=>({async get(key){return objects.has(key)?{body:new Response(objects.get(key)).body}:null;}})};
modules['@/lib/admin']={adminGate:async()=>user==='admin'?null:Response.json({error:'Denied'},{status:user?403:401})};
modules['@/lib/attachments']=load('lib/attachments.ts');
const own=load('app/api/jobs/[id]/attachments/[file]/route.ts').GET,admin=load('app/api/admin/jobs/[id]/attachments/[file]/route.ts').GET;
const request=(file,preview=true)=>new Request(`https://local.test/api/jobs/${id}/attachments/${file.id}${preview?'?preview=1':''}`);
const params=file=>({params:Promise.resolve({id,file:file.id})});
for(const file of metadata){
 const inline=await own(request(file),params(file));assert.equal(inline.status,200);
 assert.equal(inline.headers.get('Content-Type'),file.ext==='png'?'image/png':file.ext==='jpg'?'image/jpeg':file.ext==='pdf'?'application/pdf':'application/octet-stream');
 assert.ok(inline.headers.get('Content-Disposition').startsWith(['png','jpg','pdf'].includes(file.ext)?'inline;':'attachment;'));
 assert.equal(inline.headers.get('Cache-Control'),'private, no-store');assert.equal(inline.headers.get('X-Content-Type-Options'),'nosniff');
 assert.ok(inline.headers.get('Content-Security-Policy').includes('sandbox'));assert.equal((await inline.arrayBuffer()).byteLength,file.size);
 const download=await own(request(file,false),params(file));assert.equal(download.headers.get('Content-Type'),'application/octet-stream');assert.ok(download.headers.get('Content-Disposition').startsWith('attachment;'));
}
user='stranger';assert.equal((await own(request(metadata[0]),params(metadata[0]))).status,404);assert.equal((await admin(request(metadata[0]),params(metadata[0]))).status,403);
user=null;assert.equal((await own(request(metadata[0]),params(metadata[0]))).status,401);assert.equal((await admin(request(metadata[0]),params(metadata[0]))).status,401);
user='admin';const preview=await admin(request(metadata[0]),params(metadata[0]));assert.equal(preview.status,200);assert.equal(preview.headers.get('Content-Type'),'image/png');
assert.equal((await admin(request(metadata[0]),params({...metadata[0],id:crypto.randomUUID()}))).status,404);
assert.equal((await own(request(metadata[0]),params(metadata[0]))).status,404,'Admin previews use the admin route, not widened owner access');
let locale='zh-CN';modules['./language']={useLanguage:()=>({locale})};
modules['./preview-link']=load('app/preview-link.tsx');
const Gallery=load('app/attachment-previews.tsx').default;
for(locale of ['en','zh-CN','fr','es','ja']){
 const html=renderToStaticMarkup(React.createElement(Gallery,{files:metadata,hrefFor:file=>`/api/jobs/${id}/attachments/${file.id}`}));
 assert.equal((html.match(/<img /g)??[]).length,2);assert.equal((html.match(/aria-haspopup="dialog"/g)??[]).length,5);
 assert.ok(html.includes('loading="lazy"'));assert.ok(html.includes('preview=1'));assert.ok(html.includes('reference.txt'));
 assert.equal((html.match(/class="attachment-meta"/g)??[]).length,5);
}
const conversation=renderToStaticMarkup(React.createElement(Gallery,{files:[metadata[0]],hrefFor:file=>`/api/jobs/${id}/conversation?message=test&file=${file.id}`}));assert.ok(conversation.includes('&amp;preview=1'));
db.close();console.log('PASS: PNG/JPEG inline previews, document/download preservation, owner/admin isolation, missing-file handling, private headers and five-language clickable image galleries');
