import {test} from 'node:test';
import assert from 'node:assert/strict';
import {revokeMemberDevices} from '../lib/member-devices.mjs';
test('member cleanup signs a server-only tenant-bound event and fails closed',async()=>{
 const old=global.fetch;const saved={BACKEND_URL:process.env.BACKEND_URL,INTERNAL_API_SECRET:process.env.INTERNAL_API_SECRET};process.env.BACKEND_URL='https://backend.example.test';process.env.INTERNAL_API_SECRET='synthetic-secret-over-thirty-two-characters';let seen;
 try{global.fetch=async(url,options)=>{seen={url,options};return {ok:true}};await revokeMemberDevices({member:{userId:'removed-user'},organization:{id:'org-a'}});const proof=JSON.parse(Buffer.from(seen.options.headers['X-NotoChat-Identity'],'base64url'));assert.equal(proof.organization_id,'org-a');assert.equal(proof.service_event,'member-removal');assert.equal(JSON.parse(seen.options.body).user_id,'removed-user');global.fetch=async()=>({ok:false});await assert.rejects(()=>revokeMemberDevices({member:{userId:'removed-user'},organization:{id:'org-a'}}),/not completed/)}finally{global.fetch=old;for(const [k,v] of Object.entries(saved))if(v===undefined)delete process.env[k];else process.env[k]=v}
});
