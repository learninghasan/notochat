export function orderItems(form,catalog){
 const ids=form.getAll('cart_product'),quantities=form.getAll('cart_quantity');
 if(!ids.length||ids.length>10||ids.length!==quantities.length)throw Error('Choose between 1 and 10 product lines');
 const merged=new Map();
 ids.forEach((raw,index)=>{
  const id=Number(raw),quantity=Number(quantities[index]);
  if(!Number.isSafeInteger(id)||id<1||!Number.isSafeInteger(quantity)||quantity<1||quantity>1000)throw Error('Each product needs a whole quantity between 1 and 1000');
  merged.set(id,(merged.get(id)||0)+quantity);
 });
 return [...merged].map(([product_id,quantity])=>{
  const product=catalog.find(p=>p.id===product_id);
  if(!product)throw Error('A selected product no longer exists. Refresh the catalog.');
  if(quantity>1000||quantity>product.stock)throw Error('Not enough stock: '+product.name);
  return {product_id,quantity,expected_unit_price:product.price};
 });
}
