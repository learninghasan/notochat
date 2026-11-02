export async function readApiResponse(response){
 let data;
 try{data=await response.json()}catch{
  const error=new Error('The business server is unavailable or still starting. Wait a moment and try Open workspace again.');
  error.retryable=response.status>=500||response.ok;throw error;
 }
 if(!response.ok){
  const error=new Error(response.status===401?'Workspace token was not accepted. Copy APP_TOKEN from the backend Environment settings.':typeof data.detail==='string'?data.detail:'Request failed. Please try again.');
  error.retryable=[502,503,504].includes(response.status);throw error;
 }
 return data;
}
