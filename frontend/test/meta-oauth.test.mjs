import test from 'node:test';
import assert from 'node:assert/strict';
import {validateMetaCallback} from '../lib/meta-oauth.mjs';
test('Meta callback binds redirect to the browser state cookie and business',()=>{
 const state='a'.repeat(54),value={state,organizationId:'business_a'};
 const cookie=Buffer.from(JSON.stringify(value)).toString('base64url');
 assert.deepEqual(validateMetaCallback(state,cookie),value);
 for(const wrong of [null,'b'.repeat(54),state+'x','short'])assert.equal(validateMetaCallback(wrong,cookie),null);
 for(const wrong of [null,'broken',Buffer.from('{}').toString('base64url')])assert.equal(validateMetaCallback(state,wrong),null);
});
