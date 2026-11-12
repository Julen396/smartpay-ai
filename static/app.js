'use strict';
const $ = id => document.getElementById(id);
const state = {sessionId:null, recommendations:[], config:null, selected:null, budget:null, busy:false, checkoutOpen:false, paymentComplete:false, paymentUncertain:false, orderAttempted:false, buttons:null, request:null};
function setStatus(text) { $('global-status').textContent = text || ''; }
function euro(n) { return new Intl.NumberFormat('en-IE',{style:'currency',currency:'EUR'}).format(n); }
function setStep(n) { for(let i=1;i<=4;i++) $('step'+i).className=`step ${i===n?'current':i<n?'done':''}`; }
function navigate(id) {
  const target=$(id);
  if(target.hidden || (id!=='shopping' && $('results-section').hidden)) {
    setStatus(id==='checkout'?'Choose a recommended product first.':'Analyze a request to see budget insights.');
    $('shopping').scrollIntoView({behavior:'smooth'}); return;
  }
  document.querySelectorAll('[data-nav]').forEach(a=>{a.classList.toggle('selected',a.dataset.nav===id); if(a.dataset.nav===id)a.setAttribute('aria-current','location');else a.removeAttribute('aria-current');});
  target.scrollIntoView({behavior:'smooth',block:'start'});
}
async function postJson(path,payload) {
  const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  let data; try{data=await r.json();}catch{throw Error(`HTTP ${r.status}`);}
  if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:`HTTP ${r.status}`); return data;
}
function moneyLeft(available,price){return (Math.round(available*100)-Math.round(price*100))/100;}
function pct(price,available){return available?Math.round(price/available*100):0;}
function renderProduct(p) {
  const card=document.createElement('article');card.className='product';
  const art=document.createElement('img');art.className='product-image';art.src=p.image;art.alt=`Illustration of ${p.name} (fictional demo product)`;card.append(art);
  for(const [tag,cls,text] of [['div','product-category',p.category],['h3','',p.name],['p','product-description',p.description],['div','product-price',euro(p.price)],['div','product-meta',`${p.risk.label} · ${p.match_score.toFixed(1)} ranking points`]]){const e=document.createElement(tag);e.className=cls;e.textContent=text;card.append(e);}
  if(p===state.recommendations[0]){const label=document.createElement('span');label.className='best-match';label.textContent='Top ranked match';card.prepend(label);}
  const b=document.createElement('button');b.dataset.sku=p.sku;b.textContent='Choose this product →';b.addEventListener('click',()=>chooseProduct(p,b));card.append(b);return card;
}
function syncControls(){
  const locked=state.busy||state.checkoutOpen||state.paymentComplete||state.paymentUncertain;
  document.querySelectorAll('.product button').forEach(b=>{
    const selected=b.dataset.sku===state.selected?.sku;
    b.disabled=locked;
    b.textContent=selected?'✓ Selected — choose again':'Choose this product →';
    b.setAttribute('aria-pressed',String(selected));
    b.closest('.product').classList.toggle('is-selected',selected);
  });
  $('change-product').disabled=locked;
  $('change-product').hidden=state.paymentComplete||state.paymentUncertain;
  $('analyze').disabled=state.busy||state.checkoutOpen||state.paymentUncertain;
}
async function clearPayPal(){
  const previous=state.buttons;state.buttons=null;
  if(previous?.close)await previous.close();
  $('paypal-button-container').replaceChildren();
}
function renderComparison(){
  const items=state.recommendations;const table=$('comparison-table');table.replaceChildren();$('comparison').hidden=items.length<2;if(items.length<2)return;
  const head=table.createTHead().insertRow();
  for(const name of ['Criteria',...items.map(p=>p.name)]){const th=document.createElement('th');th.scope='col';th.textContent=name;head.append(th);}
  const body=table.createTBody();
  const rows=[['Price',p=>euro(p.price)],['Features',p=>p.description],['Ranking points',p=>p.match_score.toFixed(1)],['Funds used',p=>pct(p.price,state.budget.available)+'%'],['Funds remaining',p=>euro(moneyLeft(state.budget.available,p.price))]];
  for(const [label,get] of rows){const tr=body.insertRow();const th=document.createElement('th');th.scope='row';th.textContent=label;tr.append(th);for(const p of items){tr.insertCell().textContent=get(p);}}
  const cheapest=items.reduce((a,b)=>a.price<=b.price?a:b), expensive=items.reduce((a,b)=>a.price>=b.price?a:b);
  $('comparison-note').textContent=`${items[0].name} is the top-ranked match. ${cheapest.name} is the lowest-priced option${expensive.price>cheapest.price?`, saving ${euro(moneyLeft(expensive.price,cheapest.price))} compared with ${expensive.name}`:''}. Ranking reflects catalogue relevance and affordability, not measured product quality.`;
}
function renderInsights(product,budget,selected=false){
  $('insights').hidden=false;const percent=pct(budget.price,budget.available);
  $('insight-title').textContent=selected?'Your selected purchase':'Budget impact of the top match';
  $('insight-badge').textContent=product.risk?.label || 'Within stated limits';
  $('insight-available').textContent=euro(budget.available);$('insight-price').textContent=euro(budget.price);$('insight-remaining').textContent=euro(budget.remaining);
  $('insight-percent').textContent=percent+'%';$('impact-fill').style.width=Math.min(100,percent)+'%';$('impact-track').setAttribute('aria-valuenow',String(Math.min(100,percent)));
  const alternatives=state.recommendations.filter(p=>p.sku!==product.sku && p.price>product.price).sort((a,b)=>a.price-b.price);
  const comparison=alternatives.length?` Compared with ${alternatives[0].name}, this option costs ${euro(moneyLeft(alternatives[0].price,product.price))} less.`:'';
  $('insight-note').textContent=`${product.name} costs ${euro(budget.price)}, stays within your ${euro(budget.max_price)} purchase limit and leaves ${euro(budget.remaining)} of your stated available funds.${comparison}`;
}
function renderReceipt(receipt){
  $('receipt-product').textContent=receipt.product_name;
  $('receipt-paid').textContent=euro(receipt.budget.price);$('receipt-remaining').textContent=euro(receipt.budget.remaining);
  $('receipt-order').textContent=receipt.order_id;$('receipt-capture').textContent=receipt.capture_id;
  state.paymentComplete=true;$('receipt').hidden=false;$('paypal-button-container').hidden=true;$('checkout-status').textContent='✓ Sandbox payment completed!';
  $('step4').className='step done';$('receipt').scrollIntoView({behavior:'smooth',block:'start'});
}
async function analyze(event){
  event.preventDefault();if(state.busy||state.checkoutOpen||state.paymentUncertain)return;state.busy=true;setStatus('');
  for(const id of ['checkout','approval-info','results-section','comparison','insights','receipt'])$(id).hidden=true;
  $('paypal-button-container').hidden=false;$('product-list').replaceChildren();$('analyze').disabled=true;$('analyze').textContent='Analyzing your request…';
  try{
    await clearPayPal();
    const request={query:$('query').value.trim(),max_price:Number($('max-price').value),monthly_available:Number($('available').value)};
    const data=await postJson('/api/recommend',request);
    state.request=request;state.orderAttempted=false;state.paymentComplete=false;state.paymentUncertain=false;
    state.sessionId=data.session_id;state.recommendations=data.recommendations;state.selected=null;state.budget=data.budget;
    $('reasoning').textContent=data.explanation;$('ai-mode').textContent=data.ai_mode.includes('llm+')?'✦ LLM + ML enabled':'✦ Local ML';
    for(const p of data.recommendations)$('product-list').append(renderProduct(p));
    if(!data.recommendations.length){const empty=document.createElement('p');empty.textContent='No relevant matches within your limits. Try a supported product or adjust your budget.';$('product-list').append(empty);}
    else{renderComparison();const p=data.recommendations[0];renderInsights(p,{...state.budget,price:p.price,remaining:moneyLeft(state.budget.available,p.price)});}
    $('results-section').hidden=false;setStep(2);$('results-section').scrollIntoView({behavior:'smooth',block:'start'});
  }catch(err){setStatus(err.message);}finally{state.busy=false;syncControls();$('analyze').innerHTML='✧ &nbsp; Analyze my request <span>→</span>';}
}
let sdkPromise;
async function loadPayPal(clientId){
  if(window.paypal)return;
  if(!sdkPromise){sdkPromise=new Promise((resolve,reject)=>{const script=document.createElement('script');script.src=`https://www.paypal.com/sdk/js?client-id=${encodeURIComponent(clientId)}&currency=EUR&intent=capture&components=buttons`;script.onload=resolve;script.onerror=()=>{script.remove();reject(Error('Could not load PayPal SDK.'));};document.head.append(script);}).catch(err=>{sdkPromise=null;throw err;});}
  await sdkPromise;if(!window.paypal)throw Error('PayPal SDK unavailable.');
}
async function chooseProduct(product){
  if(state.busy||state.checkoutOpen||state.paymentComplete||state.paymentUncertain)return;
  state.busy=true;syncControls();setStatus('');
  try{
    // If an order was attempted (e.g. cancelled), create a new analysis session.
    // Never attach a different SKU to an existing PayPal order.
    await clearPayPal();
    if(state.orderAttempted){
      const fresh=await postJson('/api/recommend',state.request);
      state.sessionId=fresh.session_id;state.orderAttempted=false;
    }
    const sessionId=state.sessionId;
    const result=await postJson('/api/select',{session_id:sessionId,sku:product.sku,confirmed:true});
    state.selected=result.product;setStep(3);syncControls();
    $('approval-info').hidden=false;$('approval-info').textContent=`✓ You selected ${product.name} for ${euro(product.price)}. You can change your selection before paying. PayPal will ask for final approval.`;
    renderInsights(product,result.budget,true);$('checkout').hidden=false;$('checkout-summary').textContent=`${product.name} · ${euro(product.price)} · EUR · Sandbox funds only`;
    $('paypal-button-container').hidden=false;$('checkout-status').textContent='';
    if(!state.config||!state.config.paypal_ready){$('checkout-status').textContent='PayPal Sandbox is not configured. Add credentials to .env and restart the server.';navigate('checkout');return;}
    await loadPayPal(state.config.paypal_client_id);setStep(4);
    const buttons=window.paypal.Buttons({
      style:{layout:'vertical',color:'gold',shape:'rect',label:'paypal'},
      onClick:(_data,actions)=>{
        if(state.busy||state.checkoutOpen||state.paymentComplete||state.paymentUncertain||state.buttons!==buttons)return actions.reject();
        state.checkoutOpen=true;syncControls();$('checkout-status').textContent='Waiting for your approval in PayPal…';return actions.resolve();
      },
      createOrder:async()=>{state.orderAttempted=true;const o=await postJson('/api/paypal/orders',{session_id:sessionId});return o.id;},
      onApprove:async details=>{
        try{
          const response=await postJson(`/api/paypal/orders/${encodeURIComponent(details.orderID)}/capture`,{session_id:sessionId});
          if(response.status==='COMPLETED'&&response.receipt){renderReceipt(response.receipt);}
          else{state.paymentUncertain=true;$('checkout-status').textContent=`PayPal status: ${response.status}. Verify the payment in PayPal Sandbox before starting another purchase.`;}
        }catch(err){state.paymentUncertain=true;$('checkout-status').textContent=err.message+' Verify the payment in PayPal Sandbox before starting another purchase.';}
        finally{state.checkoutOpen=false;syncControls();}
      },
      onCancel:()=>{if(state.buttons!==buttons)return;state.checkoutOpen=false;syncControls();$('checkout-status').textContent='Payment cancelled. Choose another product or select this one again to prepare a new order.';},
      onError:err=>{if(state.buttons!==buttons)return;state.checkoutOpen=false;syncControls();$('checkout-status').textContent='PayPal Checkout error: '+(err?.message||'See browser console');}
    });state.buttons=buttons;await buttons.render('#paypal-button-container');navigate('checkout');
  }catch(err){setStatus(err.message);$('checkout-status').textContent=err.message;}
  finally{state.busy=false;syncControls();}
}
window.addEventListener('DOMContentLoaded',async()=>{
  $('search-form').addEventListener('submit',analyze);
  $('change-product').addEventListener('click',()=>{$('product-list').scrollIntoView({behavior:'smooth',block:'start'});document.querySelector('.product button:not(:disabled)')?.focus({preventScroll:true});});
  document.querySelectorAll('[data-query]').forEach(b=>b.addEventListener('click',()=>{$('query').value=b.dataset.query;$('query').focus();}));
  document.querySelectorAll('[data-nav]').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();navigate(a.dataset.nav);}));
  $('new-purchase').addEventListener('click',()=>{$('results-section').hidden=true;setStep(1);navigate('shopping');$('query').focus();});
  try{const r=await fetch('/api/config');state.config=await r.json();}catch{setStatus('Could not load server configuration.');}
});
