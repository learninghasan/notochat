'use client';
import {useState} from 'react';
export default function OrderLines({products}){
 const [lines,setLines]=useState([{key:0,id:products[0]?.id||'',quantity:1}]);
 function update(key,values){setLines(rows=>rows.map(r=>r.key===key?{...r,...values}:r))}
 const subtotal=lines.reduce((sum,line)=>sum+(products.find(p=>p.id===Number(line.id))?.price||0)*(Number(line.quantity)||0),0);
 return <fieldset><legend>Products in this order</legend>{lines.map((line,index)=><div className="formgrid" key={line.key}><label className="field"><span>Product {index+1}</span><select name="cart_product" required value={line.id} onChange={e=>update(line.key,{id:e.target.value})}>{products.map(p=><option key={p.id} value={p.id}>{p.name} · {p.size||''} · ৳{p.price} · {p.stock} in stock</option>)}</select></label><label className="field"><span>Quantity {index+1}</span><input name="cart_quantity" required type="number" min="1" max="1000" step="1" value={line.quantity} onChange={e=>update(line.key,{quantity:e.target.value})}/></label><button type="button" className="secondary" disabled={lines.length===1} onClick={()=>setLines(rows=>rows.filter(r=>r.key!==line.key))}>Remove product {index+1}</button></div>)}<button type="button" className="secondary" disabled={!products.length||lines.length>=10} onClick={()=>setLines(rows=>[...rows,{key:Math.max(...rows.map(r=>r.key))+1,id:products[0]?.id||'',quantity:1}])}>＋ Add product</button><p>Products subtotal: ৳{subtotal.toLocaleString()} · Delivery is added once below.</p></fieldset>;
}
