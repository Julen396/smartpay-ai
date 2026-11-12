"""Hybrid AI recommender: local TF-IDF ranking and optional LLM explanation.

The LLM can explain the recommendation but never controls product price,
order creation, or whether a budget constraint can be bypassed.
"""
import os
import httpx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from catalog import CATALOG

DOCUMENTS = [f'{p["name"]} {p["category"]} {p["features"]}' for p in CATALOG]
VECTORIZER = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5), strip_accents='unicode')
MATRIX = VECTORIZER.fit_transform(DOCUMENTS)


def risk_assessment(price: float, monthly_available: float) -> dict:
    if price > monthly_available + 1e-7:
        return {"level": "blocked", "label": "Supera tu presupuesto disponible", "ratio": round(price / max(monthly_available, .01), 2)}
    ratio = price / max(monthly_available, .01)
    if ratio >= .70:
        return {"level": "high", "label": "Consumiría al menos el 70 % de tu presupuesto disponible", "ratio": round(ratio, 2)}
    if ratio >= .35:
        return {"level": "moderate", "label": "Compromiso moderado de presupuesto", "ratio": round(ratio, 2)}
    return {"level": "low", "label": "Dentro de los límites introducidos", "ratio": round(ratio, 2)}


def rank_products(query: str, max_price: float, monthly_available: float) -> list[dict]:
    similarities = cosine_similarity(VECTORIZER.transform([query]), MATRIX)[0]
    out = []
    for product, relevance in zip(CATALOG, similarities):
        if product['price'] > max_price or product['price'] > monthly_available:
            continue
        # Relevance dominates; affordable options receive a modest boost.
        affordability = 1 - product['price'] / max(max_price, .01)
        score = .84 * float(relevance) + .16 * affordability
        risk = risk_assessment(product['price'], monthly_available)
        out.append({**product, 'match_score': round(score * 100, 1), 'risk': risk})
    out.sort(key=lambda p: (-p['match_score'], p['price']))
    return out[:3]


def fallback_explanation(query: str, results: list[dict], max_price: float, monthly_available: float) -> str:
    if not results:
        return 'No encuentro productos del catálogo de ejemplo que respeten los dos límites. Prueba aumentando el presupuesto o cambiando la búsqueda.'
    best = results[0]
    base = f'Recomiendo {best["name"]}: es la opción mejor clasificada para «{query}» entre los productos que respetan los límites de {max_price:.2f} € por compra y {monthly_available:.2f} € disponibles.'
    return base + f' Costaría {best["price"]:.2f} € y consumiría el {best["risk"]["ratio"] * 100:.0f} % del disponible indicado. Confirma tú mismo antes de pagar; la puntuación es orientativa.'


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
                    {'role': 'system', 'content': 'You are SmartPay AI, a cautious shopping assistant. Answer in Spanish in 2-3 sentences. Only recommend items in the provided list. Never invent prices, inventory, guarantees or payment status. The user must approve payment. Never promise financial safety.'},
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
