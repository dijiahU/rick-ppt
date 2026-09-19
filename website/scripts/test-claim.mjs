import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {CLAIM_JOB} from '../lib/queries.ts';
test('atomic claim admits three, blocks fourth, refills FIFO and leases stay distinct',()=>{
 const db=new DatabaseSync(':memory:');
 try{
 db.exec('CREATE TABLE jobs(id TEXT,status TEXT,lease TEXT,updated_at INTEGER,created_at INTEGER,title TEXT,brief TEXT,pages INTEGER,style TEXT,language TEXT,attachments TEXT)');
 for(let i=0;i<5;i++)db.prepare("INSERT INTO jobs(id,status,created_at) VALUES (?,'queued',?)").run(String(i),i);
 const claim=()=>db.prepare(CLAIM_JOB).get(crypto.randomUUID(),Date.now());
 const rows=[claim(),claim(),claim()];assert.deepEqual(rows.map(x=>x.id),['0','1','2']);
 assert.equal(new Set(rows.map(x=>x.lease)).size,3);assert.equal(claim(),undefined);
 db.prepare("UPDATE jobs SET status='complete' WHERE id=? AND lease=?").run('0','wrong');
 assert.equal(claim(),undefined);
 db.prepare("UPDATE jobs SET status='complete' WHERE id=? AND lease=?").run('0',rows[0].lease);
 assert.equal(claim().id,'3');assert.equal(claim(),undefined);
 db.exec("UPDATE jobs SET status='failed' WHERE id='1'");assert.equal(claim().id,'4');
 }finally{db.close();}
});
