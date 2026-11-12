# SmartPay AI — Explainable Agentic Checkout

**Hackathon prototype: human-in-the-loop AI commerce + PayPal Sandbox.**

SmartPay AI turns a natural-language shopping request into an explainable, budget-aware recommendation. A user must explicitly select a product before the server creates a PayPal order. The purchase is completed only through the official PayPal Checkout approval flow.

> All catalogue products and prices are fictional. This is a local proof of concept, not a merchant website, investment product, fraud-detection service, or source of financial advice. **Only PayPal Sandbox is supported: no real money.**

## Features

- **ML recommendation engine:** character n-gram TF-IDF retrieval matches natural-language requests to a fictional catalogue, including Spanish/English terms.
- **Optional LLM reasoning:** an OpenAI-compatible API can explain the shortlisted options. The LLM has no authority to choose order amounts or execute payments. If no key is configured, deterministic ML-based explanations remain available.
- **Budget guardrails:** every offer is filtered server-side against both a purchase cap and the available monthly discretionary budget.
- **Human-in-the-loop:** explicit selection unlocks PayPal Checkout; the user separately approves the payment inside PayPal.
- **PayPal Orders v2:** OAuth token retrieval, server-side order creation, browser Checkout Buttons, server-side capture, verified session-order association.
- **Visible safety:** sandbox-only merchant flow, no browser-accessible PayPal client secret, no hard-coded LLM key, in-memory 30-minute sessions.

## Quick start (Python 3.10+)

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
# On Windows, use: copy .env.example .env
python -m uvicorn app:app --reload
```

Open **http://127.0.0.1:8000** in a browser. Search for, say, `Busco auriculares con cancelación de ruido para trabajar`, with a €100 purchase limit and €180 available. The recommendation works **without any API key**.

## Enable real PayPal *Sandbox* checkout

1. At [PayPal Developer Dashboard](https://developer.paypal.com/dashboard/applications/sandbox), create or open a **Sandbox REST application**.
2. Copy its **Sandbox Client ID** and **Sandbox Secret** into the local `.env` file, never into frontend JavaScript.
3. Restart `uvicorn`. Open the UI and select a recommended fictional product.
4. Click the PayPal Sandbox button and authenticate with a **Sandbox Personal (buyer) test account**, not a real consumer account.
5. Approve the fictitious transaction. The server captures the order through the PayPal Sandbox Orders v2 endpoint.
6. Verify the order in the PayPal developer sandbox dashboard or the UI confirmation.

The API base is hardcoded to `https://api-m.sandbox.paypal.com` to avoid accidentally submitting live payments. PayPal JS SDK renders the checkout button and requires a public Client ID. **Do not set real/live credentials in this prototype.**

## Optional LLM

Specify the following in `.env` to enable natural-language explanations:

```dotenv
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4.1-mini
```

For other OpenAI-compatible providers, set `OPENAI_BASE_URL` and a supported model. The application keeps the product shortlist and all numerical controls server-side. It never feeds your PayPal credentials to the LLM.

## Run tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

Tests check the recommender, unauthorised orders, server-side budget constraints and deliberate user selection. **Live Sandbox API connectivity must be tested manually with your own keys**; local tests do not prove PayPal checkout completion.

## API summary

| Endpoint | Purpose |
| --- | --- |
| `GET /api/config` | Public (non-secret) UI configuration |
| `POST /api/recommend` | Rank and explain products, create ephemeral recommendation session |
| `POST /api/select` | Record human confirmation of a recommended product |
| `POST /api/paypal/orders` | Create a PayPal Sandbox order at the server-authoritative price |
| `POST /api/paypal/orders/{order_id}/capture` | Capture only the PayPal order belonging to that session |

### Illustrative transaction sequence

```text
Customer request
  -> Local TF-IDF ML ranking -> hard budget constraints
  -> Optional language-model explanation
  -> Customer selects specific SKU
  -> Server creates PayPal Sandbox order (authoritative EUR amount)
  -> PayPal's hosted buyer approval
  -> Server captures & reports status
```

## Demo caveats

- This is a **prototype**, not production payment code: storage is process-local, sessions expire after 30 minutes, there is no login, and the catalogue contains no physical inventory. Run only as a local demo or in an isolated hackathon deployment.
- Public deployment requires authentication, persistent database transactions, rate limits, production-grade logging, anti-CSRF protection where relevant, webhooks/reconciliation, idempotency/concurrency testing, and audit controls.
- AI ranks the demo catalogue, **not live market prices**. Budget assessment is arithmetic, not a professional affordability or fraud-risk judgment.
- The optional LLM may be inaccurate; the product, price, and payment APIs are never controlled by it.

## Hackathon submission checklist

- [ ] Confirm acceptance of the [PayPal AI Hackathon rules](https://paypalaihackathon.devpost.com/rules).
- [ ] Run `pytest -q` and manually complete at least one PayPal **Sandbox** transaction.
- [ ] Publish to a public GitHub/GitLab/Bitbucket repository with this `LICENSE` visible.
- [ ] Add a README screenshot and perhaps host the demo (alternatively, this README provides run instructions).
- [ ] Record a **public YouTube video under 3 minutes** showing the app working.
- [ ] Submit URL, description, tools and video by **12 November 2026 at 21:00 CET (Madrid time)**.

## Official references

- Hackathon: https://paypalaihackathon.devpost.com/rules
- PayPal REST Orders API: https://developer.paypal.com/api/rest/integration/orders-api
- PayPal Checkout Quick Start: https://developer.paypal.com/checkout/integrate

## License

MIT, see `LICENSE`.
