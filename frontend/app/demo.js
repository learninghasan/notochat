const KEY='commerce-inbox-demo-v1';
const seed=()=>({conversations:[{id:1,customer:'রাফি আহমেদ',channel:'Messenger',mode:'ai'},{id:2,customer:'নুসরাত জাহান',channel:'Website',mode:'ai'},{id:3,customer:'সাদিয়া রহমান',channel:'Instagram',mode:'human'}],messages:{1:[{id:1,role:'customer',text:'পাঞ্জাবিটার দাম কত? ৪২ সাইজ আছে?'}],2:[{id:2,role:'customer',text:'ঢাকায় ডেলিভারি কত দিনে হবে?'}],3:[{id:3,role:'customer',text:'আমার অর্ডারটা এক্সচেঞ্জ করতে চাই।'}]},products:[{id:1,name:'Ivory Panjabi · 42',price:2450,stock:12},{id:2,name:'Navy Linen Shirt · L',price:1390,stock:8}]});
function read(){try{const raw=localStorage.getItem(KEY);if(raw){const s=JSON.parse(raw);if(Array.isArray(s.conversations)&&s.messages&&Array.isArray(s.products))return s;}}catch{}return seed();}
function save(state){try{localStorage.setItem(KEY,JSON.stringify(state));}catch{throw Error('Browser storage is unavailable or full. Allow local storage to save demo replies.');}}
export async function demoApi(path,options={}){
 const state=read();const method=options.method||'GET';
 if(path==='/conversations'&&method==='GET')return state.conversations;
 if(path==='/products'&&method==='GET')return state.products;
 const match=path.match(/^\/conversations\/(\d+)\/(messages|mode|draft)$/);
 if(!match)throw Error('Unknown demo action');
 const id=Number(match[1]),kind=match[2],c=state.conversations.find(c=>c.id===id);
 if(!c)throw Error('Conversation not found');
 if(kind==='messages'&&method==='GET')return state.messages[id]||[];
 const body=options.body?JSON.parse(options.body):{};
 if(kind==='mode'&&method==='PATCH'){
  if(!['ai','human'].includes(body.mode))throw Error('Invalid conversation mode');
  c.mode=body.mode;save(state);return {mode:c.mode};
 }
 if(kind==='messages'&&method==='POST'){
  if(c.mode!=='human')throw Error('Take over before replying');
  const text=typeof body.text==='string'?body.text.trim():'';
  if(!text||text.length>8000)throw Error('Reply must contain 1–8,000 characters');
  (state.messages[id]??=[]).push({id:Date.now(),role:'team',text});save(state);return {saved:true,delivery:'browser-only demo'};
 }
 if(kind==='draft')throw Error('AI is not connected in this demo. Configure your backend AI provider to enable drafts.');
 throw Error('Unsupported demo action');
}
