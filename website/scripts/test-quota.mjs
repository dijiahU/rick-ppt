import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {INSERT_JOB} from '../lib/queries.ts';
import {adminAllowed} from '../lib/admin-policy.ts';
function fixture(){
 const db=new DatabaseSync(':memory:');
 db.exec(`CREATE TABLE jobs(id TEXT PRIMARY KEY,user_id TEXT,request_key TEXT,title TEXT,brief TEXT,pages INTEGER,style TEXT,language TEXT,attachments TEXT,status TEXT,created_at INTEGER,updated_at INTEGER,UNIQUE(user_id,request_key))`);
 let i=0;
 const insert=(user,admin=false,key=String(++i))=>db.prepare(INSERT_JOB).get(crypto.randomUUID(),user,key,'Test','Test brief',5,'','en','[]',1,1,admin?1:0,user);
 return {db,insert};
}
test('regular account is limited to exactly ten; duplicate is idempotent',()=>{
 const {db,insert}=fixture();try{for(let i=0;i<10;i++)assert.ok(insert('user',false,String(i)));
 assert.equal(insert('user'),undefined);assert.equal(insert('user',false,'0'),undefined);
 assert.equal(db.prepare('SELECT COUNT(*) AS n FROM jobs').get().n,10);}finally{db.close();}
});
test('trusted administrator can submit past ten, still cannot exceed queue capacity',()=>{
 const {db,insert}=fixture();try{
 const admin=adminAllowed({userId:'owner',email:'owner@example.test'},{ADMIN_USER_ID:'owner'});
 for(let i=0;i<100;i++)assert.ok(insert('owner',admin,String(i)));
 assert.equal(insert('owner',admin),undefined);
 db.exec("UPDATE jobs SET status='complete'");
 assert.ok(insert('owner',admin,'after-completion'));
 assert.equal(insert('owner',admin,'after-completion'),undefined);
 }finally{db.close();}
});
test('body hints cannot confer admin identity',()=>{
 assert.equal(adminAllowed({userId:'other',email:'other@example.test',admin:true,unlimited:true},{ADMIN_USER_ID:'owner'}),false);
});
