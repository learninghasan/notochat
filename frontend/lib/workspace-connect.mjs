// Only called by the explicit Open workspace action; never retries mutations.
export async function connectWorkspace(probe,{notice=()=>{},wait=ms=>new Promise(r=>setTimeout(r,ms)),now=()=>Date.now(),budget=90000}={}){
 const deadline=now()+budget;
 for(let attempt=0;attempt<13;attempt++){
  notice(attempt?'Waiting for the business server to start…':'Connecting to your workspace…');
  try{return await probe()}catch(error){
   if(!error.retryable||attempt===12||now()+5000>=deadline)throw error;
   await wait(5000);
  }
 }
}
