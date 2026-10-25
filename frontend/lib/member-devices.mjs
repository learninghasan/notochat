import {createHash} from 'node:crypto';
import {signedIdentity} from './identity.mjs';
export async function revokeMemberDevices({member,organization},restore=false){
 const backend=process.env.BACKEND_URL,secret=process.env.INTERNAL_API_SECRET;
 if(!backend||!secret)throw Error('Backend device cleanup must be configured before removing a member');
 const path=restore?'/push/restore-member':'/push/revoke-member',body=JSON.stringify({user_id:member.userId});
 const proof=signedIdentity({userId:'auth-membership-hook',organizationId:organization.id,role:'admin',serviceEvent:restore?'member-added':'member-removal'},'POST',path,createHash('sha256').update(body).digest('hex'),secret);
 const response=await fetch(backend.replace(/\/$/,'')+path,{method:'POST',headers:{'Content-Type':'application/json','X-NotoChat-Identity':proof.payload,'X-NotoChat-Signature':proof.signature},body,redirect:'error',signal:AbortSignal.timeout(15000)});
 if(!response.ok)throw Error('Device cleanup failed; membership removal was not completed. Retry when the backend is available.');
}
export async function quarantineOrganizationDevices({organization}){
 const backend=process.env.BACKEND_URL,secret=process.env.INTERNAL_API_SECRET;
 if(!backend||!secret)throw Error('Backend cleanup must be configured before removing a business');
 const path='/push/revoke-organization',body='{}';const proof=signedIdentity({userId:'auth-membership-hook',organizationId:organization.id,role:'admin',serviceEvent:'organization-removal'},'POST',path,createHash('sha256').update(body).digest('hex'),secret);
 const response=await fetch(backend.replace(/\/$/,'')+path,{method:'POST',headers:{'Content-Type':'application/json','X-NotoChat-Identity':proof.payload,'X-NotoChat-Signature':proof.signature},body,redirect:'error',signal:AbortSignal.timeout(15000)});
 if(!response.ok)throw Error('Workspace quarantine failed; business account removal was not completed.');
}
