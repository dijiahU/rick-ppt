import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {DatabaseSync} from 'node:sqlite';
import ts from 'typescript';
async function load(path){const source=readFileSync(new URL('../'+path,import.meta.url),'utf8');return import('data:text/javascript;base64,'+Buffer.from(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText).toString('base64'));}
const {publicJobStatus}=await load('lib/job-status.ts');
const {adminQuery}=await load('lib/admin-query.ts');
const {messages,en,displaySummary}=await load('lib/i18n.ts');
for(const locale of Object.values(messages)){
 assert.deepEqual(Object.keys(locale.statuses),Object.keys(en.statuses));
 assert.ok(locale.statuses.delivery_pending.length);
 assert.equal(displaySummary('delivery_pending',locale),locale.statuses.delivery_pending);
}
assert.equal(publicJobStatus('failed','delivery_pending'),'delivery_pending');
assert.equal(publicJobStatus('running','delivery_pending'),'running');
assert.equal(publicJobStatus('complete','complete'),'complete');
assert.equal(publicJobStatus('paused','pause_requested'),'paused');
const db=new DatabaseSync(':memory:');
db.exec("CREATE TABLE jobs(id TEXT,title TEXT,brief TEXT,user_id TEXT,status TEXT,summary TEXT);INSERT INTO jobs VALUES('delivery','title','brief','owner','failed','delivery_pending'),('failure','title','brief','owner','failed','failed'),('upload','title','brief','owner','running','delivery_pending');");
for(const [status,expected] of [['delivery_pending',['delivery']],['failed',['failure']],['running',['upload']]]){
 const query=adminQuery(new URL('https://local.test/?status='+status));
 assert.deepEqual(db.prepare('SELECT id FROM jobs '+query.where).all(...query.args).map(r=>r.id),expected);
}
console.log('PASS: localized delivery status, preserved lifecycle, exact administrator filters and no schema migration');
