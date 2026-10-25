import {POST as proxy} from '../../../[...path]/route';
import {metaCookie,validateMetaCallback} from '../../../../../lib/meta-oauth.mjs';
export const runtime='nodejs';
export async function GET(request){
 const url=new URL(request.url);
 const cookie=(request.headers.get('cookie')||'').split(';').map(x=>x.trim()).find(x=>x.startsWith(metaCookie+'='))?.slice(metaCookie.length+1);
 const bound=validateMetaCallback(url.searchParams.get('state'),cookie);
 const origin=process.env.BETTER_AUTH_URL?new URL(process.env.BETTER_AUTH_URL).origin:url.origin;
 let message='Meta connection failed. Return to Connections and try again.';
 if(bound&&url.searchParams.get('code')&&!url.searchParams.has('error')){
  const headers=new Headers({'Content-Type':'application/json',Origin:origin,Cookie:request.headers.get('cookie')||'','X-NotoChat-Expected-Organization':bound.organizationId});
  const result=await proxy(new Request(origin+'/api/oauth/meta/complete',{method:'POST',headers,body:JSON.stringify({state:bound.state,code:url.searchParams.get('code')})}),{params:Promise.resolve({path:['oauth','meta','complete']})});
  if(result.ok)message='Meta authorized. Open your business, go to Connections, and choose your page.';
 }
 // No code, state, provider errors or credentials appear in the returned page.
 return new Response(`<!doctype html><html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NotoChat · Meta connection</title><body><h1>NotoChat</h1><p>${message}</p><a href="/">Return to NotoChat</a></body></html>`,{headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'none'; base-uri 'none'; frame-ancestors 'none'",'Set-Cookie':`${metaCookie}=; HttpOnly; Secure; SameSite=Lax; Path=/api/oauth/meta/callback; Max-Age=0`}});
}
