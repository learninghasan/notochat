import {timingSafeEqual} from 'node:crypto';
export const metaCookie='notochat-meta-state';
export function validateMetaCallback(state,cookie){
 try{
  const value=JSON.parse(Buffer.from(cookie,'base64url').toString());
  if(typeof state!=='string'||typeof value.state!=='string'||typeof value.organizationId!=='string'||!value.organizationId||state.length>200||value.state.length>200)return null;
  const a=Buffer.from(state),b=Buffer.from(value.state);
  return a.length>=32&&a.length===b.length&&timingSafeEqual(a,b)?value:null;
 }catch{return null;}
}
