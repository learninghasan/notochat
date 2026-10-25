import {POST as proxy} from '../../../[...path]/route';
import {metaCookie} from '../../../../../lib/meta-oauth.mjs';
export const runtime='nodejs';
export async function POST(request){
 const organizationId=request.headers.get('X-NotoChat-Expected-Organization');
 if(!organizationId)return Response.json({detail:'Open your business account first'},{status:403});
 const headers=new Headers(request.headers);headers.delete('authorization');
 const result=await proxy(new Request(request.url,{method:'POST',headers,body:'{}'}),{params:Promise.resolve({path:['oauth','meta','start']})});
 if(!result.ok)return result;
 const data=await result.json();const state=new URL(data.url).searchParams.get('state');
 const value=Buffer.from(JSON.stringify({state,organizationId})).toString('base64url');
 return Response.json(data,{headers:{'Cache-Control':'no-store','Set-Cookie':`${metaCookie}=${value}; HttpOnly; Secure; SameSite=Lax; Path=/api/oauth/meta/callback; Max-Age=600`}});
}
