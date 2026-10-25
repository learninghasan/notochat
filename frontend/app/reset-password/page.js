'use client';
import {useState} from 'react';
import {authClient} from '../../lib/auth-client';
export default function ResetPassword(){
 const [message,setMessage]=useState(''),[busy,setBusy]=useState(false);
 return <main><section className="login"><h1>Reset your password</h1><form className="accountform" onSubmit={async e=>{e.preventDefault();setBusy(true);try{const password=new FormData(e.currentTarget).get('password');const token=new URLSearchParams(window.location.search).get('token');if(!token)throw Error('Reset token is missing');const r=await authClient.resetPassword({newPassword:password,token});if(r.error)throw Error(r.error.message);setMessage('Password reset. Return to NotoChat and sign in.')}catch(e){setMessage(e.message)}finally{setBusy(false)}}}><label>New password<input type="password" name="password" required minLength={12} maxLength={128} autoComplete="new-password"/></label><button disabled={busy}>Reset password</button></form><p role="status">{message}</p><a href="/">Return to NotoChat</a></section></main>
}
