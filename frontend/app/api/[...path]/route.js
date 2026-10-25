import {createHash} from 'node:crypto';
import {getAuth} from '../../../lib/auth.mjs';
import {signedIdentity} from '../../../lib/identity.mjs';
export const runtime='nodejs';
export const dynamic='force-dynamic';
async function proxy(request,{params}){
 const backend=process.env.BACKEND_URL;
 if(!backend)return Response.json({detail:'Backend is not connected. Explore the browser demo, or configure BACKEND_URL.'},{status:503});
 const {path:parts}=await params;
 if(parts.some(p=>p==='.'||p==='..'||p.includes('/')||p.includes('\\')))return Response.json({detail:'Invalid API path'},{status:400});
 const path='/'+parts.map(encodeURIComponent).join('/');
 const headers={'Content-Type':request.headers.get('content-type')||'application/json'};
 const body=['GET','HEAD'].includes(request.method)?undefined:await request.arrayBuffer();
 if(body&&body.byteLength>12500000)return Response.json({detail:'Request too large'},{status:413});
 const authorization=request.headers.get('authorization')||'';
 // The legacy workspace stays explicitly separate from all account-backed business data.
 if(authorization.startsWith('Bearer ')&&authorization.slice(7).trim())headers.Authorization=authorization;
 else{
  if(!['GET','HEAD'].includes(request.method)){
   const expectedOrigin=process.env.BETTER_AUTH_URL?new URL(process.env.BETTER_AUTH_URL).origin:new URL(request.url).origin;
   if(request.headers.get('origin')!==expectedOrigin)return Response.json({detail:'Same-origin request required'},{status:403});
  }
  let auth;
  try{auth=await getAuth()}catch{return Response.json({detail:'Business login is not configured on this deployment'},{status:503})}
  const session=await auth.api.getSession({headers:request.headers});
  if(!session?.user)return Response.json({detail:'Sign in to your business account'},{status:401});
  if(!session.session.activeOrganizationId)return Response.json({detail:'Choose or create a business first'},{status:403});
  let member;
  try{member=await auth.api.getActiveMember({headers:request.headers})}catch{return Response.json({detail:'Active business membership is required'},{status:403})}
  if(member.userId!==session.user.id||member.organizationId!==session.session.activeOrganizationId)return Response.json({detail:'Business membership could not be verified'},{status:403});
  let proof;
  try{proof=signedIdentity({userId:session.user.id,organizationId:member.organizationId,role:member.role},request.method,path+new URL(request.url).search,createHash('sha256').update(body?Buffer.from(body):'').digest('hex'),process.env.INTERNAL_API_SECRET)}catch{return Response.json({detail:'Business API trust is not configured'},{status:503})}
  headers['X-NotoChat-Identity']=proof.payload;headers['X-NotoChat-Signature']=proof.signature;
 }
 try{
  const target=new URL(backend.replace(/\/$/,'')+path);target.search=new URL(request.url).search;
  const r=await fetch(target,{method:request.method,headers,body,redirect:'error',cache:'no-store',signal:AbortSignal.timeout(65000)});
  return new Response(r.body,{status:r.status,headers:{'Content-Type':r.headers.get('content-type')||'application/json','Cache-Control':'no-store'}});
 }catch{return Response.json({detail:'Backend unavailable. Check server status and BACKEND_URL.'},{status:502})}
}
export const GET=proxy;export const POST=proxy;export const PUT=proxy;export const PATCH=proxy;export const DELETE=proxy;
