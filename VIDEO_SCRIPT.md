# 2 minute 40 second English demo script (after Sandbox is configured)

**Important:** This is a *script*, not a finished recording. Record your own functioning application. Only state "payment completed" if PayPal Sandbox actually confirms it.

**00:00–00:15 — Problem / hook**
> AI agents can help us shop, but they shouldn't spend our money without control. Meet SmartPay AI: an explainable purchasing copilot with a human-approved PayPal checkout.

**00:15–00:35 — Natural language request**
> I enter: "I want noise-cancelling headphones for working." My maximum price is 100 euros, and I have 180 euros left this month.

**00:35–01:15 — Real AI recommendation**
> A local machine-learning model matches my request against the demo catalogue, filters out options that violate my limits, and ranks the remaining products. The explanation is transparent, and an optional LLM makes it even more conversational. It cannot change any payment amount.

**01:15–01:40 — Guardrails**
> Every recommendation includes a spending-risk indicator. To demonstrate the guardrail, I'll lower my budget: options above it immediately disappear. The catalogue and prices are fictional; this is a proof of concept.

**01:40–02:20 — PayPal Sandbox integration**
> I select a recommended product. Nothing is charged yet. The server creates a PayPal order using its own verified product price. I then approve the transaction in PayPal's Sandbox checkout. [SHOW ACTUAL TEST BUYER LOGIN AND APPROVAL, HIDE ANY SENSITIVE DETAILS.] The server captures the order and displays PayPal's response.

**02:20–02:40 — Takeaway**
> The idea is simple: AI for discovery and reasoning, strict guardrails for spending, and PayPal for checkout. SmartPay AI shows how agentic commerce can preserve human control.

## Capture checklist

- Use only sandbox buyer/merchant accounts; keep secrets and email addresses out of frame.
- Show real UI interaction and the actual sandbox result. No static-only mockup.
- Ensure your recording is **strictly shorter than 03:00**.
- Upload as a **public YouTube video** (not Unlisted, to comply with the rules).
- Link your public repository and Devpost entry.
