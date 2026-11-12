"""SmartPay AI demo server — PayPal Sandbox only. Not production-ready."""
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from decimal import Decimal
import os
import secrets
import time

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ai_engine import explain_with_llm, rank_products
from catalog import BY_SKU

ROOT = Path(__file__).parent
load_dotenv(ROOT / '.env')
app = FastAPI(title='SmartPay AI', version='0.3.0')
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')
SESSIONS: dict[str, dict] = {}
LOCK = Lock()
TTL_SECONDS = 60 * 30
SANDBOX_API = 'https://api-m.sandbox.paypal.com'


class RecommendRequest(BaseModel):
    query: str = Field(min_length=3, max_length=300)
    max_price: float = Field(gt=0, le=10000)
    monthly_available: float = Field(ge=0, le=100000)


class SelectRequest(BaseModel):
    session_id: str
    sku: str
    confirmed: bool = False


class SessionRequest(BaseModel):
    session_id: str


def get_session(session_id: str) -> dict:
    with LOCK:
        record = SESSIONS.get(session_id)
        if not record:
            raise HTTPException(404, 'Session not found. Start a new analysis.')
        if time.time() - record['created'] > TTL_SECONDS:
            SESSIONS.pop(session_id, None)
            raise HTTPException(410, 'Session expired. Start a new analysis.')
        return record


def budget_insight(product: dict, session: dict) -> dict:
    price = Decimal(str(product['price'])).quantize(Decimal('0.01'))
    available = Decimal(str(session['monthly_available'])).quantize(Decimal('0.01'))
    return {
        'price': float(price), 'available': float(available),
        'remaining': float(available - price),
        'impact_percent': round(float(price / available * 100), 2) if available else 0,
        'max_price': session['max_price'], 'currency': 'EUR',
    }


def require_sandbox_credentials() -> tuple[str, str]:
    cid = os.getenv('PAYPAL_CLIENT_ID', '').strip()
    secret = os.getenv('PAYPAL_CLIENT_SECRET', '').strip()
    if not (cid and secret):
        raise HTTPException(503, 'Configure PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET in .env to enable PayPal Sandbox.')
    return cid, secret


async def paypal_token(client: httpx.AsyncClient) -> str:
    cid, secret = require_sandbox_credentials()
    response = await client.post(f'{SANDBOX_API}/v1/oauth2/token', auth=(cid, secret), data={'grant_type': 'client_credentials'})
    response.raise_for_status()
    return response.json()['access_token']


async def paypal_post(client: httpx.AsyncClient, endpoint: str, payload=None, request_id=None) -> dict:
    token = await paypal_token(client)
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json', 'Prefer': 'return=representation'}
    if request_id:
        headers['PayPal-Request-Id'] = request_id
    r = await client.post(f'{SANDBOX_API}{endpoint}', headers=headers, json=payload or {})
    r.raise_for_status()
    return r.json()


@app.get('/')
def homepage():
    return FileResponse(ROOT / 'static' / 'index.html')


@app.get('/api/config')
def config():
    return {
        'paypal_ready': bool(os.getenv('PAYPAL_CLIENT_ID') and os.getenv('PAYPAL_CLIENT_SECRET')),
        'paypal_client_id': os.getenv('PAYPAL_CLIENT_ID', ''),  # public SDK identifier; NEVER expose client secret
        'environment': 'sandbox',
        'llm_ready': bool(os.getenv('OPENAI_API_KEY')),
    }


@app.get('/api/health')
def health():
    return {'status': 'ok', 'payment_mode': 'sandbox', 'time_utc': datetime.now(timezone.utc).isoformat()}


@app.post('/api/recommend')
async def recommend(data: RecommendRequest):
    results = rank_products(data.query, data.max_price, data.monthly_available)
    reasoning, ai_mode = await explain_with_llm(data.query, results, data.max_price, data.monthly_available)
    session_id = secrets.token_urlsafe(24)
    with LOCK:
        SESSIONS[session_id] = {
            'created': time.time(), 'allowed_skus': {p['sku'] for p in results},
            'max_price': data.max_price, 'monthly_available': data.monthly_available,
            'selected_sku': None, 'approved': False, 'paypal_order_id': None,
            'paypal_request_id': secrets.token_hex(16), 'captured': False, 'receipt': None,
        }
    return {'session_id': session_id, 'recommendations': results, 'explanation': reasoning, 'ai_mode': ai_mode, 'budget': {'max_price': data.max_price, 'available': data.monthly_available}}


@app.post('/api/select')
def select_product(data: SelectRequest):
    session = get_session(data.session_id)
    if not data.confirmed:
        raise HTTPException(400, 'Explicit user confirmation is required.')
    product = BY_SKU.get(data.sku)
    if not product or data.sku not in session['allowed_skus']:
        raise HTTPException(400, 'Product not authorized by this recommendation.')
    if product['price'] > session['max_price'] or product['price'] > session['monthly_available']:
        raise HTTPException(400, 'The product exceeds your spending limits.')
    with LOCK:
        if session['paypal_order_id']:
            raise HTTPException(409, 'An order already exists. Start a new analysis to change it.')
        session['selected_sku'] = data.sku
        session['approved'] = True
    return {'approved': True, 'product': product, 'budget': budget_insight(product, session), 'note': 'You approved checkout preparation. PayPal will request final approval.'}


@app.post('/api/paypal/orders')
async def create_order(data: SessionRequest):
    session = get_session(data.session_id)
    if not session['approved'] or not session['selected_sku']:
        raise HTTPException(403, 'Select and confirm a product first.')
    if session['captured']:
        raise HTTPException(409, 'This purchase is already complete.')
    if session['paypal_order_id']:
        return {'id': session['paypal_order_id']}
    product = BY_SKU[session['selected_sku']]
    # Server-side price is authoritative; never accept amounts from the browser.
    total = str(Decimal(str(product['price'])).quantize(Decimal('0.01')))
    payload = {
        'intent': 'CAPTURE',
        'purchase_units': [{
            'reference_id': product['sku'],
            'description': product['name'],
            'amount': {'currency_code': 'EUR', 'value': total},
        }],
        'application_context': {'shipping_preference': 'NO_SHIPPING', 'user_action': 'PAY_NOW'},
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await paypal_post(client, '/v2/checkout/orders', payload, session['paypal_request_id'])
        order_id = response['id']
    except (httpx.HTTPError, KeyError, ValueError):
        raise HTTPException(502, 'PayPal Sandbox could not create the order. Check your credentials.')
    with LOCK:
        session['paypal_order_id'] = order_id
    return {'id': order_id}


@app.post('/api/paypal/orders/{order_id}/capture')
async def capture_order(order_id: str, data: SessionRequest):
    session = get_session(data.session_id)
    if not session['approved'] or order_id != session['paypal_order_id']:
        raise HTTPException(403, 'This order does not belong to an approved purchase in your session.')
    if session['captured']:
        return {'status': 'COMPLETED', 'id': order_id, 'receipt': session['receipt'], 'message': 'Order already completed.'}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await paypal_post(client, f'/v2/checkout/orders/{order_id}/capture', request_id=f'capture-{session["paypal_request_id"]}')
    except (httpx.HTTPError, KeyError, ValueError):
        raise HTTPException(502, 'Could not capture the Sandbox payment. Check its status in PayPal.')
    status = response.get('status', 'UNKNOWN')
    receipt = None
    if status == 'COMPLETED':
        product = BY_SKU[session['selected_sku']]
        # Require the actual capture, not just an approved order or a client assertion.
        captures = [c for u in response.get('purchase_units', [])
                    for c in u.get('payments', {}).get('captures', [])]
        expected = Decimal(str(product['price'])).quantize(Decimal('0.01'))
        try:
            capture = next(c for c in captures if c.get('status') == 'COMPLETED'
                           and c.get('amount', {}).get('currency_code') == 'EUR'
                           and Decimal(c['amount']['value']) == expected and c.get('id'))
            if response.get('id') != order_id:
                raise ValueError('Unexpected order ID')
        except (StopIteration, KeyError, ValueError, ArithmeticError):
            raise HTTPException(502, 'PayPal capture could not be verified. Check the Sandbox transaction before retrying.')
        receipt = {
            'order_id': order_id, 'capture_id': capture['id'], 'product_name': product['name'],
            'status': 'COMPLETED', 'environment': 'sandbox', 'budget': budget_insight(product, session),
            'completed_at': capture.get('create_time') or datetime.now(timezone.utc).isoformat(),
        }
        with LOCK:
            session['captured'] = True
            session['receipt'] = receipt
    return {'status': status, 'id': response.get('id', order_id), 'receipt': receipt,
            'message': 'Payment confirmed in PayPal Sandbox' if receipt else 'PayPal has not confirmed the payment yet'}
