import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readApiResponse} from '../lib/api-response.mjs';
test('HTML outages produce a retryable safe error without exposing server output',async()=>{
 await assert.rejects(()=>readApiResponse(new Response('<html>secret diagnostic</html>',{status:503})),e=>e.retryable&&!e.message.includes('secret diagnostic'));
});
test('bad tokens are not retried and successful JSON is preserved',async()=>{
 await assert.rejects(()=>readApiResponse(Response.json({detail:'Invalid access token'},{status:401})),e=>!e.retryable&&e.message.includes('APP_TOKEN'));
 assert.deepEqual(await readApiResponse(Response.json([{id:1}])),[{id:1}]);
});
test('mutating business validation failures are never marked retryable',async()=>{
 await assert.rejects(()=>readApiResponse(Response.json({detail:'Stock changed'},{status:409})),e=>!e.retryable&&e.message==='Stock changed');
});
