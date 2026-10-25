import {createHmac,randomUUID} from 'node:crypto';
export function signedIdentity({userId,organizationId,role,serviceEvent},method,path,bodyHash,secret){
 if(!secret||secret.length<32)throw Error('INTERNAL_API_SECRET must contain at least 32 characters');
 const payload=Buffer.from(JSON.stringify({user_id:userId,organization_id:organizationId,role,...(serviceEvent?{service_event:serviceEvent}:{}),method,path,body_sha256:bodyHash,timestamp:Math.floor(Date.now()/1000),nonce:randomUUID()})).toString('base64url');
 return {payload,signature:createHmac('sha256',secret).update(payload).digest('hex')};
}
