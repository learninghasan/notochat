import {betterAuth} from 'better-auth';
import {organization} from 'better-auth/plugins/organization';
import {nextCookies} from 'better-auth/next-js';
import pg from 'pg';
import nodemailer from 'nodemailer';
import {revokeMemberDevices,quarantineOrganizationDevices} from './member-devices.mjs';

export function makeAuth({database,secret,baseURL,sendMail,requireVerification=true,onMemberRemoval=async()=>{},onMemberAdded=async()=>{},onOrganizationRemoval=async()=>{}}){
 if(!secret||secret.length<32)throw Error('BETTER_AUTH_SECRET must contain at least 32 characters');
 return betterAuth({
  database,secret,baseURL,
  emailAndPassword:{enabled:true,minPasswordLength:12,maxPasswordLength:128,requireEmailVerification:requireVerification,sendResetPassword:async({user,url})=>sendMail({to:user.email,subject:'Reset your NotoChat password',text:`Reset your password: ${url}`})},
  emailVerification:{sendOnSignUp:requireVerification,sendVerificationEmail:async({user,url})=>sendMail({to:user.email,subject:'Verify your NotoChat email',text:`Verify your email: ${url}`})},
  session:{cookieCache:{enabled:false},expiresIn:60*60*24*7,updateAge:60*60*24},
  rateLimit:{enabled:true,storage:'database',window:60,max:60,customRules:{'/sign-in/email':{window:60,max:5},'/sign-up/email':{window:60,max:3}}},
  plugins:[organization({organizationHooks:{beforeRemoveMember:onMemberRemoval,afterAddMember:onMemberAdded,beforeDeleteOrganization:onOrganizationRemoval},membershipLimit:100,organizationLimit:10,requireEmailVerificationOnInvitation:true,sendInvitationEmail:async data=>sendMail({to:data.email,subject:`Join ${data.organization.name} on NotoChat`,text:`You were invited to ${data.organization.name}. Sign in using this email and accept invitation ${data.id} at ${baseURL}/?invitation=${encodeURIComponent(data.id)}`})}),nextCookies()],
 });
}
let instance;
export async function getAuth(){
 if(instance)return instance;
 const secret=process.env.BETTER_AUTH_SECRET,baseURL=process.env.BETTER_AUTH_URL;
 if(!secret||!baseURL)throw Error('Authentication is not configured: set BETTER_AUTH_SECRET and BETTER_AUTH_URL');
 let database;
 if(process.env.AUTH_DATABASE_URL){database=new pg.Pool({connectionString:process.env.AUTH_DATABASE_URL,max:5});}
 else if(process.env.AUTH_SQLITE_PATH&&process.env.NODE_ENV!=='production'){
  const sqliteModule='node:sqlite';const {DatabaseSync}=await import(/* webpackIgnore: true */ sqliteModule);database=new DatabaseSync(process.env.AUTH_SQLITE_PATH);
 }else throw Error('Configure a durable AUTH_DATABASE_URL for accounts');
 const mailConfigured=Boolean(process.env.SMTP_HOST&&process.env.SMTP_FROM);
 if(process.env.NODE_ENV==='production'&&!mailConfigured)throw Error('SMTP_HOST and SMTP_FROM are required for verified signup and invitations');
 const transporter=mailConfigured?nodemailer.createTransport({host:process.env.SMTP_HOST,port:Number(process.env.SMTP_PORT||587),secure:process.env.SMTP_SECURE==='1',auth:process.env.SMTP_USER?{user:process.env.SMTP_USER,pass:process.env.SMTP_PASSWORD}:undefined}):null;
 instance=makeAuth({database,secret,baseURL,onOrganizationRemoval:quarantineOrganizationDevices,onMemberRemoval:revokeMemberDevices,onMemberAdded:data=>revokeMemberDevices(data,true),requireVerification:mailConfigured||process.env.NODE_ENV==='production',sendMail:async data=>{if(!transporter)throw Error('Email delivery is not configured');await transporter.sendMail({...data,from:process.env.SMTP_FROM})}});
 return instance;
}
