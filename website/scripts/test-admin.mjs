import test from 'node:test';
import assert from 'node:assert/strict';
import {adminAllowed} from '../lib/admin-policy.ts';
import {adminQuery} from '../lib/admin-query.ts';
const owner={userId:'owner-site-id',email:'owner@example.test'};
test('missing configuration and anonymous callers fail closed',()=>{
 assert.equal(adminAllowed(null,{ADMIN_EMAIL:owner.email}),false);
 assert.equal(adminAllowed(owner,{}),false);
 assert.equal(adminAllowed(owner,{ADMIN_EMAIL:' '}),false);
});
test('only exact configured trusted identity passes',()=>{
 assert.equal(adminAllowed(owner,{ADMIN_EMAIL:'OWNER@example.test'}),true);
 assert.equal(adminAllowed({...owner,email:'other@example.test'},{ADMIN_EMAIL:owner.email}),false);
 assert.equal(adminAllowed({...owner,email:'owner@example.test.attacker.invalid'},{ADMIN_EMAIL:owner.email}),false);
});
test('site-scoped ID pin overrides email without fallback',()=>{
 assert.equal(adminAllowed(owner,{ADMIN_USER_ID:owner.userId}),true);
 assert.equal(adminAllowed(owner,{ADMIN_USER_ID:'different',ADMIN_EMAIL:owner.email}),false);
});
test('pagination and enum input are bounded',()=>{
 for(const query of ['page=0','page=-1','page=1.1','page=9999999','status=cancelled','q='+ 'x'.repeat(201)])assert.throws(()=>adminQuery(new URL('http://localhost/?'+query)));
 const q=adminQuery(new URL('http://localhost/?page=2&status=running'));
 assert.equal(q.offset,25);assert.equal(q.limit,25);assert.deepEqual(q.args,['running']);
});
test('search is bound and SQL wildcard characters are literal',()=>{
 const q=adminQuery(new URL('http://localhost/?q='+encodeURIComponent("50%_\\' OR 1=1 --")));
 assert.equal(q.where.includes('1=1'),false);
 assert.equal(q.args[0],"50%_\\' OR 1=1 --");
});
