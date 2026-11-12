import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app import app
from ai_engine import rank_products, risk_assessment

client = TestClient(app)


def test_budget_constraints():
    results = rank_products('Auriculares bluetooth', 60, 45)
    assert results
    assert all(item['price'] <= 45 for item in results)
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
