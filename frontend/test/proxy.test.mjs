import test from 'node:test';
import assert from 'node:assert/strict';
import {getMigrations} from 'better-auth/db/migration';
import {getAuth} from '../lib/auth.mjs';
import {GET,POST} from '../app/api/[...path]/route.js';
test('API proxy rejects stale business context and signs the fresh account membership',async()=>{
 process.env.AUTH_SQLITE_PATH=':memory:';process.env.BETTER_AUTH_SECRET='proxy-test-secret-more-than-thirty-two-characters';process.env.BETTER_AUTH_URL='http://localhost:3000';process.env.BACKEND_URL='https://backend.example';process.env.INTERNAL_API_SECRET='internal-test-secret-more-than-thirty-two-characters';
 const original=globalThis.fetch;
 try{
 globalThis.fetch=async(url,options)=>{assert.equal(new URL(url).pathname,'/push/restore-member');const proof=JSON.parse(Buffer.from(options.headers['X-NotoChat-Identity'],'base64url'));assert.equal(proof.service_event,'member-added');return Response.json({restored:true})};
 const auth=await getAuth();await (await getMigrations(auth.options)).runMigrations();
 const signup=await auth.handler(new Request('http://localhost:3000/api/auth/sign-up/email',{method:'POST',headers:{Origin:'http://localhost:3000','Content-Type':'application/json'},body:JSON.stringify({name:'Proxy owner',email:'proxy@example.test',password:'long-test-password'})}));
 assert.equal(signup.status,200);let cookie=signup.headers.getSetCookie().map(v=>v.split(';')[0]).join('; ');
 const org=await auth.handler(new Request('http://localhost:3000/api/auth/organization/create',{method:'POST',headers:{Origin:'http://localhost:3000','Content-Type':'application/json',Cookie:cookie},body:JSON.stringify({name:'Proxy shop',slug:'proxy-shop'})}));
 assert.equal(org.status,200);const business=await org.json();cookie=org.headers.getSetCookie().map(v=>v.split(';')[0]).join('; ')||cookie;
 const ctx={params:Promise.resolve({path:['conversations']})};
 const stale=await GET(new Request('http://localhost:3000/api/conversations',{headers:{Cookie:cookie,'X-NotoChat-Expected-Organization':'another-business'}}),ctx);assert.equal(stale.status,409);
 const csrf=await POST(new Request('http://localhost:3000/api/conversations',{method:'POST',headers:{Cookie:cookie,Origin:'https://other.example'},body:'{}'}),ctx);assert.equal(csrf.status,403);
  globalThis.fetch=async(url,options)=>{assert.equal(new URL(url).origin,'https://backend.example');const identity=JSON.parse(Buffer.from(options.headers['X-NotoChat-Identity'],'base64url'));assert.equal(identity.organization_id,business.id);assert.equal(identity.role,'owner');return Response.json([]);};
  const valid=await GET(new Request('http://localhost:3000/api/conversations',{headers:{Cookie:cookie,'X-NotoChat-Expected-Organization':business.id}}),ctx);assert.equal(valid.status,200);
 }finally{globalThis.fetch=original;}
});
