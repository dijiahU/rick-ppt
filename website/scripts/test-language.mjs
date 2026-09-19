// Pure data/SQL tests: no production requests and no user quota consumed.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
import {DatabaseSync} from 'node:sqlite';
async function moduleFrom(path){const source=readFileSync(new URL(path,import.meta.url),'utf8');return import('data:text/javascript;base64,'+Buffer.from(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText).toString('base64'));}
const {languages,messages,en,isLocale}=await moduleFrom('../lib/i18n.ts');
function validate(actual,expected){assert.deepEqual(Object.keys(actual),Object.keys(expected));for(const key of Object.keys(expected)){if(typeof expected[key]==='string')assert.equal(typeof actual[key],'string');else if(Array.isArray(expected[key])){assert.equal(actual[key].length,expected[key].length);assert.ok(actual[key].every(x=>typeof x==='string'&&x.length));}else validate(actual[key],expected[key]);}}
for(const code of Object.keys(languages)){assert.ok(isLocale(code));validate(messages[code],en);}
for(const code of [null,'xx','EN','__proto__',{},1])assert.equal(isLocale(code),false);
const {INSERT_JOB,CLAIM_JOB}=await moduleFrom('../lib/queries.ts');
const db=new DatabaseSync(':memory:');
db.exec('CREATE TABLE jobs(id TEXT PRIMARY KEY,user_id TEXT,request_key TEXT,title TEXT,brief TEXT,pages INTEGER,style TEXT,status TEXT,created_at INTEGER,updated_at INTEGER,lease TEXT,UNIQUE(user_id,request_key));');
// New migration preserves existing legacy rows as NULL, not an invented language.
db.exec("INSERT INTO jobs VALUES('legacy','old','old','原主题','原内容',5,'test','complete',0,0,NULL)");
db.exec(readFileSync(new URL('../drizzle/0002_wakeful_lucky_pierre.sql',import.meta.url),'utf8'));
db.exec(readFileSync(new URL('../drizzle/0003_conscious_bug.sql',import.meta.url),'utf8'));
assert.equal(db.prepare("SELECT language FROM jobs WHERE id='legacy'").get().language,null);
let i=0;for(const language of Object.keys(languages)){
 const id=String(++i);const args=[id,'test',id,'中文主题','中文需求内容',5,'Designer choice',language,null,i,i,0,'test'];
 assert.equal(db.prepare(INSERT_JOB).get(...args).id,id);
 assert.equal(db.prepare(INSERT_JOB).get(...args),undefined);
 const task=db.prepare(CLAIM_JOB).get('lease',i);assert.equal(task.language,language);assert.equal(task.title,'中文主题');
 db.prepare("UPDATE jobs SET status='complete' WHERE id=?").run(id);
}
for(let n=6;n<=10;n++)assert.ok(db.prepare(INSERT_JOB).get(String(n),'test',String(n),'title','brief',5,'test','en',null,n,n,0,'test'));
assert.equal(db.prepare(INSERT_JOB).get('11','test','11','title','brief',5,'test','en',null,11,11,0,'test'),undefined);
console.log('PASS: five complete dictionaries, locale allowlist, lossless migration, immutable language through SQL queue, idempotency and 10-trial quota');
