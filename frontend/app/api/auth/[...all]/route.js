import {revokeMemberDevices} from '../../../../lib/member-devices.mjs';
import {getAuth} from '../../../../lib/auth.mjs';
export const runtime='nodejs';
async function handle(request){
 try{const auth=await getAuth();
  if(request.method==='POST'&&new URL(request.url).pathname.endsWith('/organization/leave')){
   const origin=new URL(process.env.BETTER_AUTH_URL||request.url).origin;
   if(request.headers.get('origin')!==origin)return Response.json({error:'Same-origin request required'},{status:403});
   const body=await request.clone().json(),session=await auth.api.getSession({headers:request.headers});
   if(!session?.user)return Response.json({error:'Sign in required'},{status:401});
   const organization=await auth.api.getFullOrganization({headers:request.headers,query:{organizationId:body.organizationId}});
   const member=organization?.members?.find(m=>m.userId===session.user.id);
   if(!member)return Response.json({error:'Membership required'},{status:403});
   if(member.role==='owner'&&organization.members.filter(m=>m.role==='owner').length<=1)return Response.json({error:'Transfer ownership before leaving'},{status:409});
   await revokeMemberDevices({member,organization});
  }
  return await auth.handler(request)}catch{return Response.json({error:'Authentication is unavailable. Configure its database, secret, public URL and email delivery.'},{status:503})}
}
export const GET=handle;
export const POST=handle;
