import {test} from 'node:test';
import assert from 'node:assert/strict';
import {connectWorkspace} from '../lib/workspace-connect.mjs';
test('connection survives a 35 second cold start and stops after success',async()=>{
 let time=0,calls=0;const notices=[];
 const result=await connectWorkspace(async()=>{calls++;if(time<35000)throw Object.assign(Error('starting'),{retryable:true});return []},{now:()=>time,wait:async ms=>{time+=ms},notice:n=>notices.push(n)});
 assert.deepEqual(result,[]);assert.equal(calls,8);assert.equal(time,35000);
});
test('invalid credentials are not retried and persistent outage is bounded',async()=>{
 let calls=0;
 await assert.rejects(()=>connectWorkspace(async()=>{calls++;throw Error('bad token')}));assert.equal(calls,1);
 let time=0;calls=0;
 await assert.rejects(()=>connectWorkspace(async()=>{calls++;throw Object.assign(Error('offline'),{retryable:true})},{now:()=>time,wait:async ms=>{time+=ms}}));
 assert.equal(calls,13);assert.equal(time,60000);
});
