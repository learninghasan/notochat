export function appOrigin(value){
 const u=new URL(value);
 if(u.username||u.password||u.search||u.hash||u.pathname!=='/'||!(u.protocol==='https:'||(u.protocol==='http:'&&u.hostname==='localhost')))throw Error('Enter the HTTPS app origin, such as https://your-app.vercel.app');
 return u.origin;
}
export function permittedRequest(path,method='GET',body){
 if(method==='GET'&&['/api/auth/organization/get-active-member','/api/conversations'].includes(path))return true;
 if(method==='POST'&&/^\/api\/conversations\/[1-9]\d*\/assistant$/.test(path)&&body&&['summary','draft','question'].includes(body.action)&&typeof body.question==='string'&&body.question.length<=4000&&Object.keys(body).every(k=>['action','question'].includes(k)))return true;
 return false;
}
