import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {getMigrations} from 'better-auth/db/migration';
import {makeAuth} from '../lib/auth.mjs';
import {signedIdentity} from '../lib/identity.mjs';
import {createHmac,createHash} from 'node:crypto';

async function setup(){
 const db=new DatabaseSync(':memory:');const mailbox=[];
 const auth=makeAuth({database:db,secret:'test-auth-secret-longer-than-thirty-two-characters',baseURL:'http://localhost:3000',sendMail:async m=>mailbox.push(m),requireVerification:false});
 await (await getMigrations(auth.options)).runMigrations();
 async function call(path,body,cookie='',method='POST'){
  const r=await auth.handler(new Request('http://localhost:3000/api/auth'+path,{method,headers:{'Content-Type':'application/json',Origin:'http://localhost:3000',...(cookie?{Cookie:cookie}:{})},...(body?{body:JSON.stringify(body)}:{})}));
  const json=await r.json();const cookies=r.headers.getSetCookie().map(s=>s.split(';')[0]).filter(Boolean).join('; ');
  return {status:r.status,data:json,cookie:cookies||cookie};
 }
 return {db,auth,mailbox,call};
}

test('real auth: signup, sign-in, business ownership, verified invitation and revocation',async()=>{
 const {db,call,mailbox}=await setup();
 const owner=await call('/sign-up/email',{name:'Owner',email:'owner@example.test',password:'owner-password-for-tests'});
 assert.equal(owner.status,200);assert.ok(owner.cookie);
 const org=await call('/organization/create',{name:'Example shop',slug:'example-shop'},owner.cookie);
 assert.equal(org.status,200,JSON.stringify(org.data));
 let ownerCookie=org.cookie;
 const member=await call('/organization/get-active-member',null,ownerCookie,'GET');assert.equal(member.data.role,'owner');
 const other=await call('/sign-up/email',{name:'Agent',email:'agent@example.test',password:'agent-password-for-tests'});assert.equal(other.status,200);
 const denied=await call('/organization/get-full-organization?organizationId='+org.data.id,null,other.cookie,'GET');assert.notEqual(denied.status,200);
 const invitation=await call('/organization/invite-member',{email:'agent@example.test',role:'member',organizationId:org.data.id},ownerCookie);
 assert.equal(invitation.status,200,JSON.stringify(invitation.data));assert.ok(mailbox.some(m=>m.to==='agent@example.test'));
 const unverified=await call('/organization/accept-invitation',{invitationId:invitation.data.id},other.cookie);assert.equal(unverified.status,403);
 db.prepare('UPDATE user SET emailVerified=1 WHERE id=?').run(other.data.user.id);
 const accepted=await call('/organization/accept-invitation',{invitationId:invitation.data.id},other.cookie);assert.equal(accepted.status,200,JSON.stringify(accepted.data));
 const selected=await call('/organization/set-active',{organizationId:org.data.id},accepted.cookie);
 assert.equal(selected.status,200);
 const active=await call('/organization/get-active-member',null,selected.cookie,'GET');assert.equal(active.data.role,'member');
 const forbidden=await call('/organization/invite-member',{email:'outsider@example.test',role:'admin',organizationId:org.data.id},selected.cookie);assert.equal(forbidden.status,403);
 const removed=await call('/organization/remove-member',{memberIdOrEmail:active.data.id,organizationId:org.data.id},ownerCookie);assert.equal(removed.status,200,JSON.stringify(removed.data));
 const revoked=await call('/organization/get-active-member',null,selected.cookie,'GET');assert.notEqual(revoked.status,200);
 const login=await call('/sign-in/email',{email:'owner@example.test',password:'owner-password-for-tests'});assert.equal(login.status,200);
 const logout=await call('/sign-out',{},login.cookie);assert.equal(logout.status,200);
 const session=await call('/get-session',null,login.cookie,'GET');assert.equal(session.data,null);
 db.close();
});

test('identity proofs bind exact method, path and body without exposing signing key',()=>{
 const secret='internal-signing-secret-at-least-thirty-two-characters';
 const bodyHash=createHash('sha256').update('{"name":"Product"}').digest('hex');
 const proof=signedIdentity({userId:'user_1',organizationId:'org_1',role:'owner'},'POST','/products',bodyHash,secret);
 assert.equal(proof.signature,createHmac('sha256',secret).update(proof.payload).digest('hex'));
 const decoded=JSON.parse(Buffer.from(proof.payload,'base64url'));
 assert.equal(decoded.organization_id,'org_1');assert.equal(decoded.method,'POST');assert.equal(decoded.body_sha256,bodyHash);assert.ok(decoded.nonce);assert.ok(!proof.payload.includes(secret));
 assert.throws(()=>signedIdentity({userId:'u',organizationId:'o',role:'owner'},'GET','/catalog',bodyHash,''),/at least/);
});
