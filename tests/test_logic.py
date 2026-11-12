import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app import app
from ai_engine import rank_products, risk_assessment

client = TestClient(app)


def test_budget_constraints():
    results = rank_products('Auriculares bluetooth', 60, 55)
    assert results
    assert all(item['price'] <= 55 for item in results)
    assert rank_products('teclado', 5, 4) == []


def test_risk_classification():
    assert risk_assessment(60, 50)['level'] == 'blocked'
    assert risk_assessment(49, 50)['level'] == 'high'
    assert risk_assessment(15, 100)['level'] == 'low'


def test_recommend_select_and_no_payment_without_credentials(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    resp = client.post('/api/recommend', json={'query':'auriculares bluetooth para trabajar','max_price':100,'monthly_available':180})
    assert resp.status_code == 200
    data = resp.json()
    assert data['recommendations']
    session = data['session_id']
    sku = data['recommendations'][0]['sku']
    assert client.post('/api/paypal/orders',json={'session_id':session}).status_code == 403
    assert client.post('/api/select',json={'session_id':session,'sku':sku,'confirmed':False}).status_code == 400
    assert client.post('/api/select',json={'session_id':session,'sku':'FAKE-100','confirmed':True}).status_code == 400
    assert client.post('/api/select',json={'session_id':session,'sku':sku,'confirmed':True}).status_code == 200
    monkeypatch.delenv('PAYPAL_CLIENT_ID',raising=False)
    monkeypatch.delenv('PAYPAL_CLIENT_SECRET',raising=False)
    assert client.post('/api/paypal/orders',json={'session_id':session}).status_code == 503


def test_cannot_capture_foreign_order():
    data = client.post('/api/recommend', json={'query':'quiero SSD externo','max_price':100,'monthly_available':120}).json()
    r = client.post('/api/paypal/orders/NOT-MY-ORDER/capture', json={'session_id':data['session_id']})
    assert r.status_code == 403


def test_homepage_and_config_do_not_leak_secret(monkeypatch):
    monkeypatch.setenv('PAYPAL_CLIENT_SECRET','super-secret-should-not-appear')
    monkeypatch.setenv('PAYPAL_CLIENT_ID','public-test-id')
    assert client.get('/').status_code == 200
    text = client.get('/api/config').text
    assert 'public-test-id' in text
    assert 'super-secret-should-not-appear' not in text
    assert 'sandbox' in text


def test_relevance_and_anc():
    for query in ('I need an external SSD for backups', 'Quiero un SSD externo para copias de seguridad'):
        results = rank_products(query, 100, 180)
        assert len(results) == 2
        assert all(p['product_type'] == 'storage' for p in results)
    for query in ('I need noise-cancelling headphones for work', 'Busco auriculares con cancelación de ruido para trabajar'):
        results = rank_products(query, 100, 180)
        assert len(results) == 2
        assert all(p['product_type'] == 'headphones' and p['anc'] for p in results)
        affordable = rank_products(query, 60, 180)
        assert len(affordable) == 1 and affordable[0]['sku'] == 'AUDIO-011'
    assert rank_products('headphones', 40, 180) == []
    assert rank_products('a refrigerator', 1000, 180) == []
    assert [p['sku'] for p in rank_products('gaming keyboard', 100, 180)] == ['TECH-004']
    assert [p['sku'] for p in rank_products('external SSD 1 TB', 100, 180)] == ['TECH-006']

def test_product_artwork():
    from catalog import CATALOG
    for product in CATALOG:
        response = client.get(product['image'])
        assert response.status_code == 200
    assert client.get('/static/favicon.svg').status_code == 200


def _selected_session():
    data = client.post('/api/recommend', json={'query':'noise-cancelling headphones','max_price':60,'monthly_available':180}).json()
    assert data['budget'] == {'max_price':60, 'available':180}
    session = data['session_id']
    chosen = client.post('/api/select', json={'session_id':session,'sku':'AUDIO-011','confirmed':True}).json()
    assert chosen['budget']['remaining'] == 120.10
    assert chosen['budget']['price'] == 59.90
    return session


def test_verified_receipt_and_repeat_capture(monkeypatch):
    import app as module
    calls=[]
    async def mock_post(client, endpoint, payload=None, request_id=None):
        calls.append(endpoint)
        if endpoint == '/v2/checkout/orders':
            assert payload['purchase_units'][0]['amount'] == {'currency_code':'EUR','value':'59.90'}
            return {'id':'ORDER-TEST'}
        return {'id':'ORDER-TEST','status':'COMPLETED','purchase_units':[{'payments':{'captures':[{'id':'CAPTURE-TEST','status':'COMPLETED','amount':{'currency_code':'EUR','value':'59.90'}}]}}]}
    monkeypatch.setattr(module,'paypal_post',mock_post)
    session=_selected_session()
    assert client.post('/api/paypal/orders',json={'session_id':session}).json()['id']=='ORDER-TEST'
    url='/api/paypal/orders/ORDER-TEST/capture'
    result=client.post(url,json={'session_id':session}).json()
    assert result['status']=='COMPLETED'
    assert result['receipt']['capture_id']=='CAPTURE-TEST'
    assert result['receipt']['budget']['remaining']==120.10
    assert client.post(url,json={'session_id':session}).json()['receipt']==result['receipt']
    assert len(calls)==2


def test_pending_and_mismatched_capture_no_receipt(monkeypatch):
    import app as module
    reply={'id':'ORDER-TEST','status':'PENDING'}
    async def mock_post(client, endpoint, payload=None, request_id=None):
        return {'id':'ORDER-TEST'} if endpoint=='/v2/checkout/orders' else reply
    monkeypatch.setattr(module,'paypal_post',mock_post)
    session=_selected_session()
    client.post('/api/paypal/orders',json={'session_id':session})
    url='/api/paypal/orders/ORDER-TEST/capture'
    assert client.post(url,json={'session_id':session}).json()['receipt'] is None
    reply.update(status='COMPLETED',purchase_units=[{'payments':{'captures':[{'id':'CAPTURE-TEST','status':'COMPLETED','amount':{'currency_code':'EUR','value':'1.00'}}]}}])
    assert client.post(url,json={'session_id':session}).status_code==502
