import {getAuth} from '../../../../lib/auth.mjs';
export const runtime='nodejs';
async function handle(request){
 try{return await (await getAuth()).handler(request)}catch{return Response.json({error:'Authentication is unavailable. Configure its database, secret, public URL and email delivery.'},{status:503})}
}
export const GET=handle;
export const POST=handle;
