import test from 'node:test';
import assert from 'node:assert/strict';
import {appOrigin,permittedRequest} from '../../chrome-extension/contracts.mjs';
test('copilot accepts only explicit secure app origins',()=>{
 assert.equal(appOrigin('https://notochat.example/'),'https://notochat.example');
 assert.equal(appOrigin('http://localhost:3000'),'http://localhost:3000');
 for(const url of ['http://example.com','https://user:secret@example.com','https://example.com/api','https://example.com?token=x','javascript:alert(1)'])assert.throws(()=>appOrigin(url));
});
test('copilot denies tokens, sends, arbitrary fetches and tools',()=>{
 assert.equal(permittedRequest('/api/conversations'),true);
 assert.equal(permittedRequest('/api/auth/organization/get-active-member'),true);
 assert.equal(permittedRequest('/api/conversations/1/assistant','POST',{action:'draft',question:''}),true);
 for(const path of ['/api/auth/get-session','/api/connections/configuration','https://evil.example/','/api/orders','/api/conversations/1/deliver','/api/conversations/1/messages'])assert.equal(permittedRequest(path,'POST',{action:'draft',question:''}),false);
 assert.equal(permittedRequest('/api/conversations/1/assistant','POST',{action:'draft',question:'',tools:['send']}),false);
 assert.equal(permittedRequest('/api/conversations/1/assistant','POST',{action:'send',question:''}),false);
});
