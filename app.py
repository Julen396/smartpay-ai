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
app = FastAPI(title='SmartPay AI', version='0.1.0')
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
            raise HTTPException(404, 'Sesión no encontrada: solicita una nueva recomendación.')
        if time.time() - record['created'] > TTL_SECONDS:
            SESSIONS.pop(session_id, None)
            raise HTTPException(410, 'Sesión caducada: vuelve a analizar la compra.')
        return record


def require_sandbox_credentials() -> tuple[str, str]:
    cid = os.getenv('PAYPAL_CLIENT_ID', '').strip()
    secret = os.getenv('PAYPAL_CLIENT_SECRET', '').strip()
    if not (cid and secret):
        raise HTTPException(503, 'Configura PAYPAL_CLIENT_ID y PAYPAL_CLIENT_SECRET en .env para activar PayPal Sandbox.')
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
            'paypal_request_id': secrets.token_hex(16), 'captured': False,
        }
    return {'session_id': session_id, 'recommendations': results, 'explanation': reasoning, 'ai_mode': ai_mode}


@app.post('/api/select')
def select_product(data: SelectRequest):
    session = get_session(data.session_id)
    if not data.confirmed:
        raise HTTPException(400, 'Necesitamos confirmación explícita del usuario.')
    product = BY_SKU.get(data.sku)
    if not product or data.sku not in session['allowed_skus']:
        raise HTTPException(400, 'Producto no autorizado por esta recomendación.')
    if product['price'] > session['max_price'] or product['price'] > session['monthly_available']:
        raise HTTPException(400, 'El producto supera uno de tus límites.')
    with LOCK:
        if session['paypal_order_id']:
            raise HTTPException(409, 'Ya existe una orden. Inicia una recomendación nueva para cambiarla.')
        session['selected_sku'] = data.sku
        session['approved'] = True
    return {'approved': True, 'product': product, 'note': 'Autorizaste preparar el pago. PayPal solicitará tu aprobación final.'}


@app.post('/api/paypal/orders')
async def create_order(data: SessionRequest):
    session = get_session(data.session_id)
    if not session['approved'] or not session['selected_sku']:
        raise HTTPException(403, 'Primero confirma un producto de forma explícita.')
    if session['captured']:
        raise HTTPException(409, 'La compra ya se completó.')
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
        raise HTTPException(502, 'PayPal Sandbox no ha podido crear la orden. Comprueba tus credenciales.')
    with LOCK:
        session['paypal_order_id'] = order_id
    return {'id': order_id}


@app.post('/api/paypal/orders/{order_id}/capture')
async def capture_order(order_id: str, data: SessionRequest):
    session = get_session(data.session_id)
    if not session['approved'] or order_id != session['paypal_order_id']:
        raise HTTPException(403, 'Esta orden no pertenece a una compra aprobada en tu sesión.')
    if session['captured']:
        return {'status': 'COMPLETED', 'id': order_id, 'message': 'Orden completada previamente.'}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await paypal_post(client, f'/v2/checkout/orders/{order_id}/capture', request_id=f'capture-{session["paypal_request_id"]}')
    except (httpx.HTTPError, KeyError, ValueError):
        raise HTTPException(502, 'No se ha podido capturar el pago en Sandbox; verifica el estado en PayPal.')
    status = response.get('status', 'UNKNOWN')
    if status == 'COMPLETED':
        with LOCK:
            session['captured'] = True
    return {'status': status, 'id': response.get('id', order_id), 'message': 'Pago confirmado en PayPal Sandbox' if status == 'COMPLETED' else 'PayPal aún no confirma el pago'}
