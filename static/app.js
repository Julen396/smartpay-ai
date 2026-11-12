'use strict';
const $ = (id) => document.getElementById(id);
const state = { sessionId: null, recommendations: [], config: null, selected: null };
function setStatus(text) { $('global-status').textContent = text || ''; }
function euro(amount) { return new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR' }).format(amount); }
function setStep(number) { for (let n=1; n<=4; n++) { $(`step${n}`).className = `step ${n===number ? 'current' : (n<number ? 'done' : '')}`; } }
async function postJson(path, payload) {
  const r = await fetch(path, { method: 'POST', headers: {'Content-Type':'application/json'}, body:JSON.stringify(payload) });
  let content;
  try { content = await r.json(); } catch { throw Error(`Error HTTP ${r.status}`); }
  if (!r.ok) throw Error(content.detail || `Error HTTP ${r.status}`);
  return content;
}
function renderProduct(p) {
  const card = document.createElement('article'); card.className = 'product';
  const art = document.createElement('img'); art.className = 'product-image'; art.src = p.image; art.alt = `Illustration of ${p.name} (fictional demo product)`; card.append(art);
  const cat = document.createElement('div'); cat.className = 'product-category'; cat.textContent = p.category; card.append(cat);
  const title = document.createElement('h3'); title.textContent = p.name; card.append(title);
  const desc = document.createElement('p'); desc.className = 'product-description'; desc.textContent = p.description; card.append(desc);
  const price = document.createElement('div'); price.className = 'product-price'; price.textContent = euro(p.price); card.append(price);
  const meta = document.createElement('div'); meta.className = 'product-meta';
  meta.textContent = `${p.risk.label} · ${p.match_score.toFixed(1)} ranking points`; card.append(meta);
  const button = document.createElement('button'); button.textContent = 'Choose this product →';
  button.addEventListener('click', () => chooseProduct(p, button)); card.append(button);
  return card;
}
async function analyze(event) {
  event.preventDefault(); setStatus(''); $('checkout').hidden = true; $('approval-info').hidden = true;
  $('results-section').hidden = true; $('product-list').replaceChildren();
  $('analyze').disabled = true; $('analyze').innerHTML = 'Analyzing your request…';
  try {
    const query = $('query').value.trim();
    const data = await postJson('/api/recommend', {query, max_price:Number($('max-price').value), monthly_available:Number($('available').value)});
    state.sessionId = data.session_id; state.recommendations = data.recommendations; state.selected = null;
    $('reasoning').textContent = data.explanation;
    $('ai-mode').textContent = data.ai_mode.includes('llm+') ? '✦ LLM + ML enabled' : '✦ Local ML';
    for (const p of data.recommendations) $('product-list').append(renderProduct(p));
    if (!data.recommendations.length) {
      const empty = document.createElement('p'); empty.textContent = 'No relevant matches within your limits. Try a supported product or adjust your budget.'; $('product-list').append(empty);
    }
    $('results-section').hidden = false; setStep(2);
    $('results-section').scrollIntoView({behavior:'smooth',block:'start'});
  } catch(err) { setStatus(err.message); }
  finally { $('analyze').disabled = false; $('analyze').innerHTML = '✧ &nbsp; Analyze my request <span>→</span>'; }
}
async function loadPayPal(clientId) {
  if (window.paypal) return;
  const script = document.createElement('script');
  script.src = `https://www.paypal.com/sdk/js?client-id=${encodeURIComponent(clientId)}&currency=EUR&intent=capture&components=buttons`;
  await new Promise((resolve,reject)=>{ script.onload=resolve; script.onerror=()=>reject(new Error('No se ha podido cargar el SDK de PayPal.')); document.head.append(script); });
  if (!window.paypal) throw Error('PayPal SDK no disponible.');
}
async function chooseProduct(product, clickedButton) {
  setStatus(''); clickedButton.disabled = true;
  try {
    const result = await postJson('/api/select',{session_id:state.sessionId, sku:product.sku, confirmed:true});
    state.selected = result.product; setStep(3);
    document.querySelectorAll('.product button').forEach((b) => { b.disabled = true; });
    $('approval-info').hidden = false;
    $('approval-info').textContent = `✓ You selected ${product.name} for ${euro(product.price)}. This is only approval to prepare checkout; PayPal will ask you to authorize the sandbox transaction.`;
    $('checkout').hidden = false;
    $('checkout-summary').textContent = `${product.name} · ${euro(product.price)} · EUR · Sandbox funds only`;
    $('paypal-button-container').replaceChildren(); $('checkout-status').textContent = '';
    if (!state.config || !state.config.paypal_ready) {
      $('checkout-status').textContent = 'PayPal Sandbox is not configured yet. Add PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET to .env, restart the server, then analyze again.';
      return;
    }
    await loadPayPal(state.config.paypal_client_id);
    setStep(4);
    await window.paypal.Buttons({
      style: { layout:'vertical', color:'gold', shape:'rect', label:'paypal' },
      createOrder: async () => { const o = await postJson('/api/paypal/orders', {session_id:state.sessionId}); return o.id; },
      onApprove: async (details) => {
        try {
          const response = await postJson(`/api/paypal/orders/${encodeURIComponent(details.orderID)}/capture`, {session_id:state.sessionId});
          $('checkout-status').textContent = response.status === 'COMPLETED' ? `✓ Sandbox payment completed! Order: ${response.id}` : `PayPal status: ${response.status}`;
        } catch(err) { $('checkout-status').textContent = err.message; }
      },
      onCancel: () => { $('checkout-status').textContent = 'Payment cancelled; no funds were captured.'; },
      onError: (err) => { $('checkout-status').textContent = 'PayPal Checkout error: ' + (err?.message || 'See browser console'); },
    }).render('#paypal-button-container');
  } catch(err) { clickedButton.disabled = false; setStatus(err.message); }
}
window.addEventListener('DOMContentLoaded', async () => {
  $('search-form').addEventListener('submit', analyze);
  document.querySelectorAll('[data-query]').forEach(btn => btn.addEventListener('click', ()=>{$('query').value = btn.dataset.query; $('query').focus();}));
  try { const r=await fetch('/api/config'); state.config=await r.json(); }
  catch { setStatus('No se ha podido consultar la configuración del servidor.'); }
});
