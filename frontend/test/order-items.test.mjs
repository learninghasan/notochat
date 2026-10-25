import test from 'node:test';
import assert from 'node:assert/strict';
import {orderItems} from '../lib/order-items.mjs';
const catalog=[{id:1,name:'Shirt',price:100,stock:5},{id:2,name:'Scarf',price:50,stock:3}];
function form(lines){const f=new FormData();for(const [id,qty] of lines){f.append('cart_product',id);f.append('cart_quantity',qty)}return f;}
test('multi-product form keeps distinct quantities, merges duplicate products and binds quoted prices',()=>{
 assert.deepEqual(orderItems(form([[1,1],[2,3],[1,2]]),catalog),[{product_id:1,quantity:3,expected_unit_price:100},{product_id:2,quantity:3,expected_unit_price:50}]);
});
test('invalid multi-product quantities and stale catalog selections are rejected before sending',()=>{
 for(const lines of [[],[[1,1.5]],[[1,0]],[[1,3],[1,3]],[[2,4]],[[99,1]]])assert.throws(()=>orderItems(form(lines),catalog));
});
