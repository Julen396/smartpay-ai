"""Hybrid AI recommender: local TF-IDF ranking and optional LLM explanation.

The LLM can explain the recommendation but never controls product price,
order creation, or whether a budget constraint can be bypassed.
"""
import os
import re
import unicodedata
import httpx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from catalog import CATALOG

DOCUMENTS = [f'{p["name"]} {p["category"]} {p["features"]}' for p in CATALOG]
VECTORIZER = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5), strip_accents='unicode')
MATRIX = VECTORIZER.fit_transform(DOCUMENTS)


def risk_assessment(price: float, monthly_available: float) -> dict:
    if price > monthly_available + 1e-7:
        return {"level": "blocked", "label": "Exceeds available funds", "ratio": round(price / max(monthly_available, .01), 2)}
    ratio = price / max(monthly_available, .01)
    if ratio >= .70:
        return {"level": "high", "label": "Uses at least 70% of available funds", "ratio": round(ratio, 2)}
    if ratio >= .35:
        return {"level": "moderate", "label": "Moderate budget commitment", "ratio": round(ratio, 2)}
    return {"level": "low", "label": "Within your stated limits", "ratio": round(ratio, 2)}


# Type and feature gates precede ranking: never fill a shortlist with unrelated bargains.
TYPE_TERMS = {
    'headphones': r'headphones?|earbuds?|headsets?|auriculares?|cascos?',
    'storage': r'ssd|storage|discos?|almacenamiento|hard drives?',
    'keyboard': r'keyboards?|teclados?',
    'mouse': r'mouse|mice|raton|ratones',
    'speaker': r'speakers?|altavoces?|altavoz',
    'lamp': r'lamps?|lamparas?',
    'backpack': r'backpacks?|mochilas?',
    'webcam': r'webcams?|cameras?|camaras?',
    'microphone': r'microphones?|microfonos?|mics?',
}


def normalize(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))


def rank_products(query: str, max_price: float, monthly_available: float) -> list[dict]:
    text = normalize(query)
    types = {kind for kind, pattern in TYPE_TERMS.items() if re.search(r'\b(?:' + pattern + r')\b', text)}
    # This small demo only supports its listed product types. Ask for a clearer request otherwise.
    if not types:
        return []
    wants_anc = bool(re.search(r'\banc\b|noise[ -]cancel|cancelacion (?:activa )?de ruido|cancelar (?:el )?ruido', text))
    wants_mechanical = bool(re.search(r'\b(?:mechanical|mecanico|mecanica|gaming)\b', text))
    capacity = re.search(r'\b(500\s*gb|[12]\s*tb)\b', text)
    similarities = cosine_similarity(VECTORIZER.transform([query]), MATRIX)[0]
    out = []
    for product, relevance in zip(CATALOG, similarities):
        if product['product_type'] not in types:
            continue
        if wants_anc and product['product_type'] == 'headphones' and not product['anc']:
            continue
        if wants_mechanical and product['product_type'] == 'keyboard' and product['sku'] != 'TECH-004':
            continue
        if capacity and product['product_type'] == 'storage' and re.sub(r'\s+', '', capacity.group(1)) not in re.sub(r'\s+', '', product['name'].lower()):
            continue
        if product['price'] > max_price or product['price'] > monthly_available:
            continue
        affordability = 1 - product['price'] / max(max_price, .01)
        score = .90 * float(relevance) + .10 * affordability
        risk = risk_assessment(product['price'], monthly_available)
        out.append({**product, 'match_score': round(score * 100, 1), 'risk': risk})
    out.sort(key=lambda p: (-p['match_score'], p['price']))
    return out[:3]


def fallback_explanation(query: str, results: list[dict], max_price: float, monthly_available: float) -> str:
    if not results:
        return 'No relevant products in this demo catalogue meet your request and both spending limits. Try a supported product type or adjust your budget.'
    best = results[0]
    return (f'{best["name"]} is the highest-ranked match for your request: {best["description"]}. '
            f'It costs €{best["price"]:.2f}, within your €{max_price:.2f} purchase limit and €{monthly_available:.2f} available funds. '
            f'It uses {best["risk"]["ratio"] * 100:.0f}% of the available amount. Review and approve before paying.')


async def explain_with_llm(query: str, results: list[dict], max_price: float, monthly_available: float) -> tuple[str, str]:
    """OpenAI-compatible API, opt-in; output is only explanatory text."""
    key = os.getenv('OPENAI_API_KEY', '').strip()
    if not key or not results:
        return fallback_explanation(query, results, max_price, monthly_available), 'local-tfidf'
    endpoint = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1').rstrip('/') + '/chat/completions'
    products = '\n'.join(f'- {p["name"]}: {p["price"]:.2f} EUR, risk={p["risk"]["level"]}' for p in results)
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post(endpoint, headers={'Authorization': f'Bearer {key}'}, json={
                'model': os.getenv('OPENAI_MODEL', 'gpt-4.1-mini'),
                'temperature': .2,
                'max_tokens': 180,
                'messages': [
                    {'role': 'system', 'content': 'You are SmartPay AI, a cautious shopping assistant. Answer in English in 2-3 sentences. Only recommend items in the provided list. Never invent prices, inventory, guarantees or payment status. The user must approve payment. Never promise financial safety.'},
                    {'role': 'user', 'content': f'Necesidad: {query}\nLímite por compra: {max_price:.2f} EUR\nDisponible: {monthly_available:.2f} EUR\nOpciones autorizadas:\n{products}\nExplica la mejor y una precaución presupuestaria.'},
                ],
            })
            response.raise_for_status()
            content = response.json()['choices'][0]['message']['content']
            if not isinstance(content, str) or not content.strip():
                raise ValueError('Empty model response')
            return content.strip()[:1200], 'llm+local-tfidf'
    except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError):
        return fallback_explanation(query, results, max_price, monthly_available), 'local-tfidf-fallback'
